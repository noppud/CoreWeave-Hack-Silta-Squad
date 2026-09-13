"""Build and round-trip the two enabled cutter/holder assemblies in Fusion.

`prepare` only writes proposed JSON. `apply(app, payload)` runs through the bridge
on Fusion's main thread, using transient Tool/ToolLibrary objects, never a Hub
library. It changes no setup or operation and never marks job inputs ready.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

MILLING_PRESET_FEEDS = (
    "v_f",
    "v_f_leadIn",
    "v_f_leadOut",
    "v_f_plunge",
    "v_f_ramp",
    "v_f_transition",
)
DIMENSIONS = ("DC", "LB", "LCF", "OAL", "SFDM", "shoulder-diameter", "shoulder-length")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return value


def _close(actual, expected, name):
    if (
        type(actual) not in (int, float)
        or not math.isfinite(actual)
        or not math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-7)
    ):
        raise ValueError(f"Fusion readback mismatch: {name}: {actual!r} != {expected!r}")


def _pinned(reference):
    path = Path(reference["path"]).resolve(strict=True)
    if _sha(path) != reference["sha256"]:
        raise ValueError(f"Pinned tool source changed: {path.name}")
    return json.loads(path.read_text())


def _one(items, predicate, name):
    found = [item for item in items if predicate(item)]
    if len(found) != 1:
        raise ValueError(f"Expected one {name}, found {len(found)}")
    return found[0]


def prepare(config_path, output_directory):
    """Select pinned cutters, combine pinned holder, retain one constrained preset."""
    config_path = Path(config_path).resolve(strict=True)
    config = json.loads(config_path.read_text())
    selected = config["tools"]
    # After live assembly readback, library points to the configured export.
    # Rebuild from the original catalog, never from already processed presets.
    source_reference = selected.get("source_library", selected["library"])
    cutters = _pinned(source_reference)
    holders = _pinned(selected["holder_library"])
    enabled = [entry for entry in selected["entries"] if entry.get("enabled") is True]
    if sorted(e["number"] for e in enabled) != [1, 2]:
        raise ValueError("This helper requires exactly enabled end mills 1 and 2")
    prepared = []
    for entry in sorted(enabled, key=lambda e: e["number"]):
        tool = copy.deepcopy(
            _one(
                cutters["data"],
                lambda t, entry=entry: (
                    t["product-id"] == entry["product_id"]
                    and t["post-process"]["number"] == entry["number"]
                ),
                "selected cutter",
            )
        )
        holder = copy.deepcopy(
            _one(
                holders["data"],
                lambda h, entry=entry: h["product-id"] == entry["holder_product_id"],
                "selected holder",
            )
        )
        if (
            tool["type"] != "flat end mill"
            or tool["unit"] != "inches"
            or holder["unit"] != "inches"
        ):
            raise ValueError("Helper is scoped to selected inch flat end mills and holder")
        source_geometry = entry.get("source_geometry", entry["geometry"])
        if tool["geometry"] != source_geometry:
            raise ValueError("Configured geometry differs from pinned cutter")
        geometry = tool["geometry"]
        stickout = _positive(entry["stickout_below_holder_mm"], "stickout") / 25.4
        gauge = _positive(entry["assembled_gauge_length_mm"], "assembly gauge") / 25.4
        _close(stickout, geometry["LB"], "source length below holder")
        _close(gauge, stickout + holder["gaugeLength"], "assembly gauge sum")
        if not geometry["LCF"] <= stickout < geometry["OAL"]:
            raise ValueError("Flutes must be exposed and shank must enter holder")
        if not holder["segments"]:
            raise ValueError("Holder has no simulation segments")
        for segment in holder["segments"]:
            for key in ("height", "lower-diameter", "upper-diameter"):
                _positive(segment[key], f"holder segment {key}")
        geometry["LB"] = stickout
        geometry["assemblyGaugeLength"] = gauge
        tool["holder"] = holder
        preset = copy.deepcopy(
            _one(
                tool["start-values"]["presets"],
                lambda p, entry=entry: p["guid"] == entry["selected_preset_source"]["guid"],
                "selected preset",
            )
        )
        rpm = _positive(entry["cutting_limits"]["spindle_rpm"], "RPM")
        feed = _positive(entry["cutting_limits"]["feed_mm_min"], "feed") / 25.4
        if (
            rpm > config["machine"]["spindle_max_rpm"]
            or feed * 25.4 > config["machine"]["feed_max_mm_min"]
        ):
            raise ValueError("Tool cutting limits exceed selected machine")
        original_feed = _positive(preset["v_f"], "source feed")
        # Preserve supplier lead/ramp/plunge proportions while constraining every
        # feed to the explicit job limit. These remain simulation assumptions.
        for key in MILLING_PRESET_FEEDS:
            preset[key] = feed * min(1.0, _positive(preset[key], key) / original_feed)
        preset["n"] = rpm
        preset["n_ramp"] = rpm
        preset["f_z"] = feed / (rpm * geometry["NOF"])
        # Fusion 2705.1.15 omits v_f_retract from these milling presets and
        # normalizes f_n to f_z. Neither establishes operation retract behavior.
        # Keep the operative milling chipload; let Fusion serialize the derived field.
        preset.pop("v_f_retract", None)
        preset.pop("f_n", None)
        preset["v_c"] = math.pi * geometry["DC"] * rpm / 12.0
        preset["name"] = f"Silta AL6061 T{entry['number']} simulation limits"
        tool["start-values"]["presets"] = [preset]
        prepared.append(tool)
    directory = Path(output_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "tools-assembled-input.json"
    # Exclusive write: retain evidence from every attempt.
    with path.open("x") as stream:
        json.dump({"data": prepared, "version": cutters["version"]}, stream, indent=2)
        stream.write("\n")
    return {
        "input_path": str(path),
        "input_sha256": _sha(path),
        "config_sha256": _sha(config_path),
        "cutter_source_path": str(Path(source_reference["path"]).resolve()),
        "cutter_source_sha256": source_reference["sha256"],
        "cutter_source_version": cutters["version"],
        "holder_source_sha256": selected["holder_library"]["sha256"],
        "status": "prepared_not_run_in_fusion",
        "assigned_to_operations": False,
        "manufacturing_verified": False,
    }


def verify_readback(expected, actual):
    """Compare actual Fusion serialization, accepting harmless extra fields only."""
    for key in ("unit", "type", "product-id"):
        if actual.get(key) != expected[key]:
            raise ValueError(f"Fusion changed tool {key}")
    for key in ("number", "length-offset", "diameter-offset", "manual-tool-change"):
        if actual.get("post-process", {}).get(key) != expected["post-process"][key]:
            raise ValueError(f"Fusion changed post-process {key}")
    geometry = actual["geometry"]
    for key in (*DIMENSIONS, "NOF", "assemblyGaugeLength"):
        _close(geometry.get(key), expected["geometry"][key], f"geometry.{key}")
    holder, wanted = actual["holder"], expected["holder"]
    for key in ("unit", "type", "product-id"):
        if holder.get(key) != wanted[key]:
            raise ValueError(f"Fusion changed holder {key}")
    _close(holder.get("gaugeLength"), wanted["gaugeLength"], "holder gauge")
    segments = holder["segments"]
    if len(segments) != len(wanted["segments"]):
        raise ValueError("Fusion changed holder segment count")
    for index, (segment, original) in enumerate(zip(segments, wanted["segments"], strict=True)):
        for key in ("height", "lower-diameter", "upper-diameter"):
            _close(segment.get(key), original[key], f"holder segment {index} {key}")
    _close(
        geometry["assemblyGaugeLength"], geometry["LB"] + holder["gaugeLength"], "assembly relation"
    )
    presets = actual["start-values"]["presets"]
    if len(presets) != 1:
        raise ValueError("Fusion did not retain exactly one constrained preset")
    preset, expected_preset = presets[0], expected["start-values"]["presets"][0]
    for key in ("n", "n_ramp", "f_z", *MILLING_PRESET_FEEDS):
        _close(preset.get(key), expected_preset[key], f"preset.{key}")
    return {
        "number": actual["post-process"]["number"],
        "product_id": actual["product-id"],
        "diameter_mm": geometry["DC"] * 25.4,
        "flute_length_mm": geometry["LCF"] * 25.4,
        "stickout_below_holder_mm": geometry["LB"] * 25.4,
        "holder_gauge_length_mm": holder["gaugeLength"] * 25.4,
        "assembly_gauge_length_mm": geometry["assemblyGaugeLength"] * 25.4,
        "shank_inserted_mm": (geometry["OAL"] - geometry["LB"]) * 25.4,
        "holder_segments": segments,
        "holder_segment_unit": holder["unit"],
        "spindle_rpm": preset["n"],
        "feed_mm_min": preset["v_f"] * 25.4,
        "preset_readback": preset,
        "retract_verification": {
            "status": "deferred_to_operation_and_simulation",
            "reason": "Fusion omits v_f_retract for these milling tool presets",
            "required": "Verify actual operation retract feed or rapid motion and clearance",
        },
        "maximum_cut_depth_status": "requires_operation_engagement_and_clearance_verification",
    }


def apply(app, payload):
    """Round-trip actual Fusion tools and a transient library; no document writes."""
    import adsk.cam

    report = prepare(payload["config_path"], payload["output_directory"])
    directory = Path(payload["output_directory"]).resolve()
    proposed = json.loads(Path(report["input_path"]).read_text())
    # The version belongs to the LIBRARY envelope. Tool.createFromJson expects
    # a single tool object: passing this envelope produced an unspecified tool
    # with zero dimensions in live Fusion 2705.1.15 (tools-v1). Use the documented
    # library importer, preserving version 36 and retrieving actual Tool objects.
    library = adsk.cam.ToolLibrary.createFromJson(json.dumps(proposed))
    if library is None or library.count != len(proposed["data"]):
        raise RuntimeError("Fusion failed to import the complete transient tool library")
    readbacks = []
    for index, expected in enumerate(proposed["data"]):
        tool = library.item(index)
        if tool is None:
            raise RuntimeError("Fusion rejected cutter assembly")
        actual = json.loads(tool.toJson())
        path = directory / f"tool-{expected['post-process']['number']}-fusion-readback.json"
        path.write_text(json.dumps(actual, indent=2) + "\n")
        readbacks.append(verify_readback(expected, actual))
    output = directory / "tools-assembled-fusion-export.json"
    output.write_text(library.toJson())
    exported = json.loads(output.read_text())
    if len(exported["data"]) != len(proposed["data"]):
        raise RuntimeError("Fusion library changed tool count")
    for expected in proposed["data"]:
        actual = _one(
            exported["data"],
            lambda t, expected=expected: (
                t["post-process"]["number"] == expected["post-process"]["number"]
            ),
            "exported tool",
        )
        verify_readback(expected, actual)
    report.update(
        status="fusion_tool_library_roundtrip_passed_not_assigned",
        export_path=str(output),
        export_sha256=_sha(output),
        fusion_version=app.version,
        tools=readbacks,
    )
    report_path = directory / "tool-assembly-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    report["report_path"] = str(report_path)
    return report
