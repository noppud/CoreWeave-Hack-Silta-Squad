"""Deterministic fixed-job setup; call prepare(app, payload) on Fusion's main thread."""

import hashlib
import math
from pathlib import Path


def fixed_parameters(inputs):
    """Use the pinned job's explicit settings, never infer a new manufacturing setup."""
    setup = inputs["setup"]
    stock = setup["stock"]
    dimensions = stock["dimensions_mm"]
    if len(dimensions) != 3 or any(not math.isfinite(x) or x <= 0 for x in dimensions):
        raise ValueError("Stock requires three positive finite dimensions")
    position = setup["machine_position"]
    translation = position["translation_mm"]
    if len(translation) != 3 or any(not math.isfinite(x) for x in translation):
        raise ValueError("Machine placement requires three finite offsets")
    wcs = setup["work_coordinate_system"]
    if wcs["name"] != "G54" or wcs.get("work_offset") != 1:
        raise ValueError("This setup helper requires the fixed G54 job")
    parameters = {}
    for source, prefix in (
        (stock["api_parameters"], "job_stock"),
        (setup["work_coordinate_system"]["api_parameters"], "wcs_"),
        (position["reference_parameters"], "job_positionReference_"),
    ):
        for name, expression in source.items():
            allowed = name.startswith(prefix) or (prefix == "wcs_" and name == "job_workOffset")
            if not allowed or not isinstance(expression, str):
                raise ValueError("Unexpected fixed setup parameter")
            parameters[name] = expression
    for axis, value in zip("XYZ", translation, strict=True):
        parameters[f"job_position{axis}Offset"] = f"{value} mm"
    # Installed job_workOffset help delegates mapping to the post; our pinned
    # Haas post uses offset 1 for G54 (useZeroOffset is false).
    if parameters.get("job_workOffset") != "1":
        raise ValueError("G54 requires explicit job_workOffset expression 1")
    return parameters


def _verified_path(artifact):
    path = Path(artifact["path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
        raise ValueError(f"Pinned setup artifact changed: {path.name}")
    return path


def prepare(app, payload):
    import adsk.cam
    import adsk.core
    import adsk.fusion

    inputs = payload["inputs"]
    parameters = fixed_parameters(inputs)
    fixture = inputs["setup"]["fixture"]["artifact"]
    fixture_path = _verified_path(fixture)
    machine_path = _verified_path(inputs["machine"]["definition"])
    document = app.activeDocument
    if document is None:
        raise RuntimeError("No active target document")

    def activate_cam():
        if app.activeDocument != document:
            raise RuntimeError("Active document changed during setup preparation")
        workspace = app.userInterface.workspaces.itemById("CAMEnvironment")
        if workspace is None or (not workspace.isActive and not workspace.activate()):
            raise RuntimeError("Could not activate Manufacture workspace")
        design = adsk.fusion.Design.cast(document.products.itemByProductType("DesignProductType"))
        cam = adsk.cam.CAM.cast(document.products.itemByProductType("CAMProductType"))
        if design is None or cam is None:
            raise RuntimeError("Missing Design or CAM product")
        return design, cam

    design, cam = activate_cam()
    root = design.rootComponent

    def tag(entity, name):
        attribute = entity.attributes.itemByName("silta", name)
        return attribute.value if attribute else None

    def bodies():
        if root.meshBodies.count or any(o.component.meshBodies.count for o in root.allOccurrences):
            raise RuntimeError("Unsupported mesh geometry in the fixed CAM setup")
        result = list(root.bRepBodies)
        for occurrence in root.allOccurrences:
            result.extend(occurrence.bRepBodies)
        return result

    def target_id(body):
        return tag(body.nativeObject or body, "accepted_target_body")

    def fixture_owner(body):
        occurrence = body.assemblyContext
        while occurrence is not None:
            value = tag(occurrence.nativeObject or occurrence, "controller_fixture")
            if value:
                if value != fixture["sha256"]:
                    raise RuntimeError("Existing fixture belongs to different fixed inputs")
                return True
            occurrence = occurrence.assemblyContext
        return False

    def inventory():
        targets, others = [], []
        for body in bodies():
            if target_id(body):
                if fixture_owner(body):
                    raise RuntimeError("Accepted target appears inside a fixture")
                targets.append(body)
            elif fixture_owner(body):
                others.append(body)
            else:
                raise RuntimeError("Unowned non-target geometry in CAM document")
        ids = [target_id(body) for body in targets]
        if not targets or len(ids) != len(set(ids)):
            raise RuntimeError("Accepted target body IDs are missing or duplicated")
        return targets, others

    targets, _ = inventory()
    target_state = [
        (target_id(b), b.volume, b.boundingBox.minPoint.asArray(), b.boundingBox.maxPoint.asArray())
        for b in targets
    ]
    fixtures = [o for o in root.occurrences if tag(o, "controller_fixture")]
    if len(fixtures) > 1:
        raise RuntimeError("Multiple controller fixture imports")
    if cam.setups.count > 1 or (
        cam.setups.count == 1 and tag(cam.setups.item(0), "controller_setup") != "v1"
    ):
        raise RuntimeError("Unexpected setup; refusing to adopt or remove it")

    if not fixtures:
        before = list(root.occurrences)
        before_root_bodies = list(root.bRepBodies)
        options = app.importManager.createFusionArchiveImportOptions(str(fixture_path))
        imported = app.importManager.importToTarget2(options, root)
        # Import can switch back to Design; re-enter Manufacture before creating a setup.
        design, cam = activate_cam()
        if imported is None:
            raise RuntimeError("Fixture archive import failed")
        fixtures = [o for o in root.occurrences if not any(o == old for old in before)]
        if len(fixtures) != 1 or any(
            not any(body == old for old in before_root_bodies) for body in root.bRepBodies
        ):
            raise RuntimeError("Fixture import did not produce one isolated root occurrence")
        if not fixtures[0].attributes.add("silta", "controller_fixture", fixture["sha256"]):
            raise RuntimeError("Could not record controller fixture ownership")

    identity = adsk.core.Matrix3D.create().asArray()
    if any(
        abs(a - b) > 1e-8 for a, b in zip(fixtures[0].transform2.asArray(), identity, strict=True)
    ):
        raise RuntimeError("Prepared fixture occurrence must remain at identity")
    targets, fixture_bodies = inventory()
    if not fixture_bodies:
        raise RuntimeError("Prepared fixture contains no bodies")
    after = [
        (target_id(b), b.volume, b.boundingBox.minPoint.asArray(), b.boundingBox.maxPoint.asArray())
        for b in targets
    ]
    if after != target_state:
        raise RuntimeError("Target geometry changed during fixture import")

    library = adsk.cam.CAMManager.get().libraryManager.machineLibrary
    machine = library.machineAtURL(adsk.core.URL.create(inputs["machine"]["library_url"]))
    if machine is None or not machine.hasSimulationModel:
        raise RuntimeError("Configured library machine with simulation model unavailable")
    machine_input = adsk.cam.MachineFromFileInput.create(str(machine_path))
    machine_input.ignoreSimulationModel = False
    pinned_machine = adsk.cam.Machine.create(machine_input)
    if pinned_machine is None or not machine.equivalentTo(pinned_machine):
        raise RuntimeError("Library machine differs from pinned machine definition")

    if cam.setups.count:
        setup = cam.setups.item(0)
        if not setup.machine.equivalentTo(machine):
            raise RuntimeError("Existing controller setup machine changed")
    else:
        setup_input = cam.setups.createInput(adsk.cam.OperationTypes.MillingOperation)
        setup_input.name = "Silta CNC setup"
        setup_input.models = targets
        setup = cam.setups.add(setup_input)
        if not setup.attributes.add("silta", "controller_setup", "v1"):
            raise RuntimeError("Could not record controller setup ownership")
        setup.machine = machine
    collection = adsk.core.ObjectCollection.create()
    for body in targets:
        collection.add(body)
    setup.models = collection
    setup.fixtureEnabled = True
    collection = adsk.core.ObjectCollection.create()
    collection.add(fixtures[0])
    setup.fixtures = collection
    for name, expression in parameters.items():
        parameter = setup.parameters.itemByName(name)
        if parameter is None:
            raise RuntimeError(f"Missing fixed setup parameter: {name}")
        parameter.expression = expression
    if not setup.activate():
        raise RuntimeError("Could not activate controller setup")
    setup.visibilityManager.machineVisible = True
    dimensions = [
        setup.parameters.itemByName(f"job_stockInfoDimension{a}").value.value * 10 for a in "XYZ"
    ]
    expected = inputs["setup"]["stock"]["dimensions_mm"]
    if any(abs(a - b) > 1e-5 for a, b in zip(dimensions, expected, strict=True)):
        raise RuntimeError("Actual stock dimensions differ from fixed inputs")
    offsets = [
        setup.parameters.itemByName(f"job_position{a}Offset").value.value * 10 for a in "XYZ"
    ]
    expected_offsets = inputs["setup"]["machine_position"]["translation_mm"]
    if any(abs(a - b) > 1e-5 for a, b in zip(offsets, expected_offsets, strict=True)):
        raise RuntimeError("Actual machine placement differs from fixed inputs")
    wcs = setup.workCoordinateSystem.asArray()
    if any(abs(a - b) > 1e-8 for a, b in zip(wcs, identity, strict=True)):
        raise RuntimeError("Actual work coordinates differ from fixed G54 model-origin frame")
    work_offset = setup.parameters.itemByName("job_workOffset").value.value
    if work_offset != 1:
        raise RuntimeError("Actual post work offset differs from required G54 offset 1")
    return {
        "setup_name": setup.name,
        "setup_index": 0,
        "target_body_count": len(targets),
        "fixture_count": len(setup.fixtures),
        "fixture_body_count": len(fixture_bodies),
        "machine_model": setup.machine.model,
        "has_simulation_model": setup.machine.hasSimulationModel,
        "wcs": wcs,
        "work_offset": work_offset,
        "stock_dimensions_mm": dimensions,
        "machine_position_mm": offsets,
        "settings": {
            name: {
                "expression": setup.parameters.itemByName(name).expression,
                "value": setup.parameters.itemByName(name).value.value,
            }
            for name in parameters
        },
    }
