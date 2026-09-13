"""Deterministic preflight, executed by the configured check runner.

Passing means these limited checks found no issue, never manufacturability proof.
Input: check-runner JSON; analysis is the trusted Fusion inspection artifact.
"""

import json
import math
from pathlib import Path


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def check(data):
    issues = []
    constraints = data.get("constraints", {})
    machine = constraints.get("machine", {})
    tools = constraints.get("tools", {})
    setup = constraints.get("setup", {})
    if setup.get("unresolved"):
        issues.append("configuration_unresolved")
    max_rpm = machine.get("spindle_max_rpm")
    max_feed = machine.get("feed_max_mm_min")
    if not _positive(max_rpm) or not _positive(max_feed):
        issues.append("machine_cutting_limits_missing")
    entries = tools.get("entries", [])
    allowed = {entry["number"]: entry for entry in entries}
    if (
        not entries
        or len(allowed) != len(entries)
        or any(type(n) is not int or n <= 0 for n in allowed)
    ):
        issues.append("tool_library_missing_or_duplicate_numbers")
    artifacts = data.get("candidate", {}).get("artifacts", {})
    if "analysis" not in artifacts:
        return {"passed": False, "issues": issues + ["missing_fusion_analysis"]}
    analysis = json.loads(Path(artifacts["analysis"]["path"]).read_text())
    if analysis.get("input_digest") != data.get("input_digest"):
        issues.append("analysis_input_mismatch")
    if analysis.get("generation", {}).get("completed") is not True:
        issues.append("toolpath_generation_not_completed")
    inspection = analysis.get("inspection", {})
    operations = inspection.get("operations", [])
    if not operations:
        issues.append("missing_cam_operations")
    for index, operation in enumerate(operations):
        prefix = f"operation_{index}:"
        if operation.get("has_toolpath") is not True:
            issues.append(prefix + "missing_toolpath")
        if operation.get("has_error") is True or operation.get("errors"):
            issues.append(prefix + "fusion_operation_error")
        tool = operation.get("tool") or {}
        number = tool.get("post-process", {}).get("number")
        expected = allowed.get(number)
        if expected and expected.get("enabled") is False:
            issues.append(prefix + "tool_disabled_for_this_setup")
        if expected is None or tool.get("product-id") != expected.get("product_id"):
            issues.append(prefix + "tool_not_in_fixed_library")
        elif tool.get("unit") != expected.get("unit"):
            issues.append(prefix + "tool_units_differ")
        else:
            actual_geometry = tool.get("geometry", {})
            for key in ("DC", "LCF", "OAL", "SFDM", "NOF"):
                target = expected.get("geometry", {}).get(key)
                value = actual_geometry.get(key)
                if target is not None and (
                    not _positive(value) or not math.isclose(value, target, rel_tol=1e-9)
                ):
                    issues.append(prefix + "tool_geometry_differs:" + key)
        rates = operation.get("cutting_parameters", {})
        for key, limit in (("spindle_rpm", max_rpm), ("feed_mm_min", max_feed)):
            value = rates.get(key)
            if not _positive(value):
                issues.append(prefix + key + "_missing_or_invalid")
            elif _positive(limit) and value > limit:
                issues.append(prefix + key + "_exceeds_machine_limit")
        if expected:
            bounds = expected.get("cutting_limits")
            if not bounds:
                issues.append(prefix + "material_tool_cutting_limits_missing")
            else:
                for key, limit in bounds.items():
                    if key in ("spindle_rpm", "feed_mm_min") and _positive(rates.get(key)):
                        if not _positive(limit):
                            issues.append(prefix + "invalid_tool_limit:" + key)
                        elif rates[key] > limit:
                            issues.append(prefix + "exceeds_tool_limit:" + key)
    if not any(name.startswith("nc-") for name in artifacts):
        issues.append("missing_posted_nc_artifact")
    # No regex G-code execution model: controller modes/cycles need the verifier.
    return {"passed": not issues, "issues": issues}
