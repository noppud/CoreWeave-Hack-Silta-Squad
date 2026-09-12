"""Deterministic pinned tool loading and controller-owned NC finalization.

Run inside Fusion. No tool-library persistence, machine/fixture/stock changes or
simulation. PostConfiguration.createFromContent is installed but officially
unsupported; expose that limitation in every finalization receipt.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

OWNER_GROUP = "silta"
OWNER_VALUE = "v1"
SETUP_TAG = "controller_setup"
NC_TAG = "controller_nc"


def _read_pinned(reference):
    data = Path(reference["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != reference["sha256"]:
        raise ValueError("Pinned CAM resource content changed: " + Path(reference["path"]).name)
    return data


def _matches(expected, actual, path):
    """Permit Fusion's extra serialization fields and harmless float rounding."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise ValueError("CAM resource mismatch: " + path)
        for key, value in expected.items():
            _matches(value, actual.get(key), path + "." + key)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise ValueError("CAM resource mismatch: " + path)
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            _matches(left, right, f"{path}[{index}]")
    elif type(expected) in (int, float):
        if (
            type(actual) not in (int, float)
            or not math.isfinite(actual)
            or not math.isclose(expected, actual, rel_tol=1e-7, abs_tol=1e-7)
        ):
            raise ValueError("CAM resource mismatch: " + path)
    elif expected != actual:
        raise ValueError("CAM resource mismatch: " + path)


def _assembly(expected, actual):
    for key in ("product-id", "unit", "type", "geometry", "holder"):
        _matches(expected[key], actual.get(key), key)
    for key in ("number", "length-offset", "diameter-offset", "manual-tool-change"):
        _matches(expected["post-process"][key], actual.get("post-process", {}).get(key), key)


def load_tools(app, payload):
    """Return actual tools by enabled number plus portable inventory; no globals."""
    import adsk.cam

    inputs = payload["inputs"]
    reference = inputs["tools"]["library"]
    raw = _read_pinned(reference)
    source = json.loads(raw)
    library = adsk.cam.ToolLibrary.createFromJson(raw.decode("utf-8"))
    if library is None or library.count != len(source["data"]):
        raise RuntimeError("Fusion did not load the complete pinned tool library")
    enabled = [entry for entry in inputs["tools"]["entries"] if entry.get("enabled") is True]
    numbers = [entry["number"] for entry in enabled]
    if not numbers or len(set(numbers)) != len(numbers):
        raise ValueError("Enabled tool numbers must be unique and nonempty")
    tools, inventory = {}, []
    for entry in enabled:
        matches = [
            (index, item)
            for index, item in enumerate(source["data"])
            if item["post-process"]["number"] == entry["number"]
        ]
        if len(matches) != 1:
            raise ValueError("Enabled tool missing or duplicated in pinned library")
        index, expected = matches[0]
        if expected["product-id"] != entry["product_id"]:
            raise ValueError("Enabled tool product disagrees with pinned library")
        _matches(entry["geometry"], expected["geometry"], "configured geometry")
        if expected.get("holder", {}).get("product-id") != entry["holder_product_id"]:
            raise ValueError("Enabled tool holder disagrees with pinned library")
        actual_tool = library.item(index)
        if actual_tool is None:
            raise RuntimeError("Fusion returned no tool for pinned entry")
        actual = json.loads(actual_tool.toJson())
        _assembly(expected, actual)
        tools[entry["number"]] = actual_tool
        scale = {"inches": 25.4, "millimeters": 1.0}[actual["unit"]]
        geometry = actual["geometry"]
        inventory.append(
            {
                "number": entry["number"],
                "product_id": actual["product-id"],
                "holder_product_id": actual["holder"]["product-id"],
                "diameter_mm": geometry["DC"] * scale,
                "flute_length_mm": geometry["LCF"] * scale,
                "stickout_mm": geometry["LB"] * scale,
                "assembly_gauge_length_mm": geometry["assemblyGaugeLength"] * scale,
            }
        )
    return {"tools": tools, "inventory": inventory, "sha256": reference["sha256"]}


def tool_for_number(inputs, number):
    """Convenience for generated scripts; prefer the prelude's already loaded tools."""
    if type(number) is not int:
        raise ValueError("Tool number must be an integer")
    tools = load_tools(None, {"inputs": inputs})["tools"]
    if number not in tools:
        raise ValueError("Tool is not enabled: " + str(number))
    return tools[number]


def _owned(item, tag):
    attribute = item.attributes.itemByName(OWNER_GROUP, tag)
    return attribute is not None and attribute.value == OWNER_VALUE


def _cutting_expressions(operation):
    result = {}
    for parameter in operation.parameters:
        if (
            parameter.name.startswith(
                ("tool_feed", "tool_spindle", "tool_rampSpindle", "tool_surface")
            )
            or parameter.name == "tool_coolant"
        ):
            result[parameter.name] = parameter.expression
    if not all(name in result for name in ("tool_feedCutting", "tool_spindleSpeed")):
        raise ValueError("Operation has no explicit milling feed/spindle parameters")
    return result


def finalize_nc(app, payload):
    """Restore pinned assemblies without changing chosen feeds; bind exact NC/CPS."""
    import adsk.cam

    inputs = payload["inputs"]
    cam = adsk.cam.CAM.cast(app.activeDocument.products.itemByProductType("CAMProductType"))
    if cam is None or cam.setups.count != 1:
        raise ValueError("Expected exactly one controller-owned setup")
    setup = cam.setups.item(0)
    if not _owned(setup, SETUP_TAG) or payload.get("setup_index", 0) != 0:
        raise ValueError("Actual setup is not the controller-owned setup")
    if cam.ncPrograms.count > 1:
        raise ValueError("Multiple NC programs are outside the controller scope")
    program = cam.ncPrograms.item(0) if cam.ncPrograms.count else None
    if program is not None and not _owned(program, NC_TAG):
        raise ValueError("Refusing to modify a foreign NC program")
    loaded = load_tools(app, payload)
    post_reference = inputs["setup"]["postprocessor"]
    content = _read_pinned(post_reference).decode("utf-8")
    # Installed SWIG API exposes this method with an unsupported-status notice.
    post = adsk.cam.PostConfiguration.createFromContent(content)
    if post is None:
        raise RuntimeError("Fusion could not load pinned CPS content")
    planned = []
    for base in setup.allOperations:
        operation = adsk.cam.Operation.cast(base)
        if operation is None:
            continue  # allOperations also includes folders and patterns.
        if operation.isSuppressed:
            continue
        if operation.tool is None:
            raise ValueError("Operation must choose an enabled tool")
        chosen = json.loads(operation.tool.toJson())
        number = chosen.get("post-process", {}).get("number")
        if number not in loaded["tools"]:
            raise ValueError("Operation selected a disabled or unknown tool")
        canonical = loaded["tools"][number]
        expected = json.loads(canonical.toJson())
        if chosen.get("product-id") != expected["product-id"]:
            raise ValueError("Operation tool number and product identity disagree")
        planned.append((operation, canonical, expected, _cutting_expressions(operation)))
    if not planned:
        raise ValueError("Controller setup has no active machining operations")
    receipts = []
    for operation, canonical, expected, cutting in planned:
        # Documented tool assignment resets to its default preset. Restore the
        # agent-selected cutting expressions afterwards; never overwrite paths.
        operation.tool = canonical
        for name, expression in cutting.items():
            parameter = operation.parameters.itemByName(name)
            if parameter is None:
                raise RuntimeError("Tool assignment removed cutting parameter: " + name)
            parameter.expression = expression
        for name, expression in cutting.items():
            if operation.parameters.itemByName(name).expression != expression:
                raise RuntimeError("Tool assignment changed chosen cutting expression: " + name)
        _assembly(expected, json.loads(operation.tool.toJson()))
        receipts.append(
            {
                "operation_id": operation.operationId,
                "name": operation.name,
                "tool_number": expected["post-process"]["number"],
                "cutting_expressions": cutting,
            }
        )
    operations = [row[0] for row in planned]
    if program is None:
        nc_input = cam.ncPrograms.createInput()
        nc_input.displayName = "Silta controller NC"
        nc_input.operations = operations
        program = cam.ncPrograms.add(nc_input)
        if program is None:
            raise RuntimeError("Fusion failed to create controller NC program")
        program.attributes.add(OWNER_GROUP, NC_TAG, OWNER_VALUE)
    else:
        program.operations = operations
    program.machine = setup.machine
    program.postConfiguration = post  # machine assignment can change default post.
    # Fusion returns different transient PostConfiguration wrappers for the same
    # post (both may report isValid=False). Read the actual bound post file from
    # the observed NC parameter and verify its bytes against the pinned CPS.
    parameter = program.parameters.itemByName("nc_program_post")
    actual_path = getattr(getattr(parameter, "value", None), "value", None)
    if not isinstance(actual_path, str) or not actual_path or not Path(actual_path).is_absolute():
        raise RuntimeError("NC program has no readable resolved post path")
    try:
        resolved_post = Path(actual_path).resolve(strict=True)
        actual_sha256 = hashlib.sha256(resolved_post.read_bytes()).hexdigest()
    except OSError as error:
        raise RuntimeError("Cannot read the NC program's resolved post file") from error
    if actual_sha256 != post_reference["sha256"]:
        raise RuntimeError("NC program resolved post bytes differ from pinned CPS")
    if [item.operationId for item in program.operations] != [op.operationId for op in operations]:
        raise RuntimeError("NC program operations differ from controller setup")
    if not _owned(program, NC_TAG):
        raise RuntimeError("NC ownership tag did not persist")
    return {
        "nc_program_index": 0,
        "sha256": actual_sha256,
        "resolved_post_path": str(resolved_post),
        "resolved_post_sha256": actual_sha256,
        "tools": loaded["inventory"],
        "tool_library_sha256": loaded["sha256"],
        "operations": receipts,
        "post_vendor": post.vendor,
        "post_description": post.description,
        "post_api_status": "createFromContent installed but not officially supported",
    }
