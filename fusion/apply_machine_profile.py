"""Prepare and load the selected VF-2 profile through the installed Fusion API.

Run `apply(app, payload)` on the bridge main thread. This never marks the job
configuration ready and never changes fixture transforms or tool assemblies.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _walk(parts):
    for part in parts:
        yield part
        yield from _walk(part.get("parts", []))


def prepare(config_path, output_directory):
    """Local deterministic file work only; source geometry and transforms retained."""
    config_path = Path(config_path).resolve(strict=True)
    config = json.loads(config_path.read_text())
    selected = config["machine"]
    source = Path(selected["definition"]["path"]).resolve(strict=True)
    if _sha(source) != selected["definition"]["sha256"]:
        raise ValueError("Machine source changed")
    if selected["axes"] != 3:
        raise ValueError("Helper is scoped to the selected three-axis VF-2")
    rpm = selected["spindle_max_rpm"]
    timing = selected["time_estimation"]
    for value in (rpm, timing["tool_change_seconds"], timing["feed_scale_percent"]):
        if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
            raise ValueError("Machine settings must be finite and positive")
    original = json.loads(source.read_text())
    updated = copy.deepcopy(original)
    if updated["kinematics"]["default"]["units"]["length"] != "mm":
        raise ValueError("Unexpected machine definition length unit")
    spindles = [
        p["spindle"] for p in _walk(updated["kinematics"]["default"]["parts"]) if "spindle" in p
    ]
    if len(spindles) != 1:
        raise ValueError("Expected exactly one spindle")
    spindles[0]["max_speed"] = rpm
    updated["tooling"]["default"]["number_of_tools"] = selected["tool_capacity"]
    updated["machining"]["default"]["tool_change_time"] = timing["tool_change_seconds"]
    updated["machining"]["default"]["feedrate_ratio"] = timing["feed_scale_percent"] / 100
    # Source controller fields have no declared speed units and no supported
    # installed API accessor. Preserve rather than guess mm/min versus cm/s.
    directory = Path(output_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    prepared = directory / "haas-vf-2-configured-input.mch"
    if prepared.exists():
        raise FileExistsError("Use a fresh output directory; do not overwrite machine evidence")
    prepared.write_text(json.dumps(updated, indent=2) + "\n")
    return {
        "input_path": str(prepared),
        "input_sha256": _sha(prepared),
        "source_sha256": _sha(source),
        "config_sha256": _sha(config_path),
        "spindle_max_rpm": rpm,
        "tool_capacity": selected["tool_capacity"],
        "tool_change_seconds": timing["tool_change_seconds"],
        "controller_enforced_feed_max_mm_min": selected["feed_max_mm_min"],
        "time_estimation_rapid_feed_cm_s": timing["rapid_feed_cm_s"],
        "remaining": [
            "Machine-definition feed/rapid fields require UI/API unit verification; "
            "fixed checks and CAM.getMachiningTime retain the explicit configured limits."
        ],
        "fixture_modified": False,
    }


def apply(app, payload):
    """Actual Fusion execution. Optional setup_index explicitly assigns machine."""
    import adsk.cam

    report = prepare(payload["config_path"], payload["output_directory"])
    machine_input = adsk.cam.MachineFromFileInput.create(report["input_path"])
    machine_input.ignoreSimulationModel = False
    machine = adsk.cam.Machine.create(machine_input)
    if machine is None:
        raise RuntimeError("Fusion rejected configured machine")
    # Fusion 2705.1.15 returns isValid=False for an unattached Machine even
    # though its properties and save work. Require an actual export/readback
    # below; retain this diagnostic instead of mistaking it for simulation proof.
    report["unattached_machine_is_valid"] = machine.isValid
    output = Path(payload["output_directory"]).resolve() / "haas-vf-2-fusion-export.mch"
    # Present in installed API; Autodesk explicitly labels save unsupported.
    if not machine.save(adsk.cam.LibraryLocations.LocalLibraryLocation, str(output)):
        raise RuntimeError("Installed Fusion Machine.save returned false")
    exported = json.loads(output.read_text())
    heads = [
        p["spindle"] for p in _walk(exported["kinematics"]["default"]["parts"]) if "spindle" in p
    ]
    if len(heads) != 1 or heads[0]["max_speed"] != report["spindle_max_rpm"]:
        raise RuntimeError("Fusion did not preserve configured spindle maximum")
    if exported["tooling"]["default"]["number_of_tools"] != report["tool_capacity"]:
        raise RuntimeError("Fusion did not preserve tool capacity")
    if not math.isclose(
        exported["machining"]["default"]["tool_change_time"], report["tool_change_seconds"]
    ):
        raise RuntimeError("Fusion did not preserve tool-change estimate")
    report.update(
        export_path=str(output),
        export_sha256=_sha(output),
        fusion_version=app.version,
        has_simulation_model=machine.hasSimulationModel,
        machine_id=machine.id,
        assigned_to_setup=False,
        export_api_status="Machine.save present but not officially supported",
    )
    if "setup_index" in payload:
        if not app.activeDocument:
            raise RuntimeError("No active document for explicit machine assignment")
        cam = adsk.cam.CAM.cast(app.activeDocument.products.itemByProductType("CAMProductType"))
        index = payload["setup_index"]
        if type(index) is not int or index < 0 or not cam or index >= cam.setups.count:
            raise ValueError("Explicit setup index is invalid")
        setup = cam.setups.item(index)
        setup.machine = machine
        if not setup.machine or not setup.machine.equivalentTo(machine):
            raise RuntimeError("Setup machine assignment did not persist")
        report.update(assigned_to_setup=True, setup_name=setup.name)
    report["verification_status"] = "not_run"
    report_path = output.parent / "machine-application-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report
