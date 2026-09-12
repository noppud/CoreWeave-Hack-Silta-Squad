"""Deterministic checks. A model opinion can never turn a failure green.

Checks run in cost order and carry structured evidence and a repair hint so the
planner is repaired by facts, not by prose.
"""

from __future__ import annotations

import math

from silta.domain import (
    CheckResult,
    CheckStage,
    CheckStatus,
    EntryStrategy,
    FeatureKind,
    MotionKind,
    PartSpec,
    ProcessPlan,
    Segment,
    Severity,
    ShopProfile,
    Trajectory,
)
from silta.policy import Policy

CHECKS_VERSION = "checks-1"


def _fail(check_id: str, stage: CheckStage, message: str, **kw) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        stage=stage,
        status=CheckStatus.FAIL,
        severity=Severity.BLOCKING,
        message=message,
        **kw,
    )


def _ok(check_id: str, stage: CheckStage, message: str, **kw) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        stage=stage,
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        message=message,
        **kw,
    )


# ------------------------------------------------------------------- preflight


def run_preflight_checks(spec: PartSpec, shop: ShopProfile, plan: ProcessPlan) -> list[CheckResult]:
    results: list[CheckResult] = []
    features = {f.feature_id: f for f in spec.features}

    # 1. Frozen design and shop identity. Repair may never move this.
    if plan.spec_design_hash != spec.design_hash:
        results.append(
            _fail(
                "design_unchanged",
                CheckStage.SCHEMA,
                "The recipe was written against a different part design.",
                actual=plan.spec_design_hash[:12],
                required=spec.design_hash[:12],
                repair_hint="Re-plan against the confirmed specification; "
                "do not change the design.",
            )
        )
    else:
        results.append(
            _ok("design_unchanged", CheckStage.SCHEMA, "Confirmed design hash is unchanged.")
        )
    if plan.shop_hash != shop.shop_hash:
        results.append(
            _fail(
                "shop_unchanged",
                CheckStage.SCHEMA,
                "The recipe was written against a different shop profile.",
                repair_hint="Re-plan against the current machine and tool inventory.",
            )
        )

    # 2. References and coverage.
    for op in plan.operations:
        if op.feature_id not in features:
            results.append(
                _fail(
                    "feature_reference",
                    CheckStage.SCHEMA,
                    f"Operation {op.operation_id} references unknown feature {op.feature_id}.",
                    operation_id=op.operation_id,
                    repair_hint="Reference only feature IDs from the confirmed specification.",
                )
            )
        if shop.tool(op.tool_id) is None:
            results.append(
                _fail(
                    "tool_available",
                    CheckStage.PREFLIGHT,
                    f"Tool {op.tool_id} is not in the shop inventory.",
                    operation_id=op.operation_id,
                    actual=op.tool_id,
                    required=", ".join(t.tool_id for t in shop.tools),
                    repair_hint="Select a tool ID from the inventory; do not invent tools.",
                )
            )

    covered: dict[str, list[str]] = {}
    for op in plan.operations:
        covered.setdefault(op.feature_id, []).append(op.operation_id)
    for feature_id in features:
        ops = covered.get(feature_id, [])
        if not ops:
            results.append(
                _fail(
                    "feature_coverage",
                    CheckStage.PREFLIGHT,
                    f"Feature {feature_id} has no operation.",
                    feature_id=feature_id,
                    repair_hint="Add exactly one operation for every feature.",
                )
            )
        elif len(ops) > 1:
            results.append(
                CheckResult(
                    check_id="feature_coverage",
                    stage=CheckStage.PREFLIGHT,
                    status=CheckStatus.FAIL,
                    severity=Severity.WARNING,
                    message=f"Feature {feature_id} is machined by {len(ops)} operations.",
                    feature_id=feature_id,
                    repair_hint="Use one operation per feature in this part family.",
                )
            )
    if all(r.check_id != "feature_coverage" for r in results):
        results.append(
            _ok(
                "feature_coverage",
                CheckStage.PREFLIGHT,
                f"All {len(features)} features are covered by exactly one operation.",
            )
        )

    # 3-6. Per-operation tool, reach, geometry and parameter checks.
    for op in plan.operations:
        feature = features.get(op.feature_id)
        tool = shop.tool(op.tool_id)
        if feature is None or tool is None:
            continue

        if op.kind not in tool.allowed_operations:
            results.append(
                _fail(
                    "tool_operation_compatible",
                    CheckStage.PREFLIGHT,
                    f"Tool {tool.tool_id} is not permitted for {op.kind.value}.",
                    operation_id=op.operation_id,
                    feature_id=feature.feature_id,
                    actual=op.kind.value,
                    required=", ".join(k.value for k in tool.allowed_operations),
                    repair_hint="Match the operation kind to a tool that permits it.",
                )
            )

        needed = (
            feature.depth_mm
            if feature.kind is FeatureKind.POCKET_RECT_ROUNDED
            else feature.total_tip_depth_mm
        )
        if tool.cutting_length_mm < needed - 1e-9:
            results.append(
                _fail(
                    "tool_cutting_reach",
                    CheckStage.PREFLIGHT,
                    f"Reach failed: {needed:.1f} mm depth exceeds "
                    f"{tool.cutting_length_mm:.1f} mm cutting length of {tool.tool_id}.",
                    operation_id=op.operation_id,
                    feature_id=feature.feature_id,
                    actual=tool.cutting_length_mm,
                    required=needed,
                    units="mm",
                    evidence={"tool_id": tool.tool_id, "feature_kind": feature.kind.value},
                    repair_hint="Select an available tool with sufficient cutting reach; "
                    "preserve the requested depth.",
                )
            )
        elif tool.stickout_mm < needed + 2.0:
            results.append(
                _fail(
                    "tool_stickout_clearance",
                    CheckStage.PREFLIGHT,
                    f"Holder would enter the stock: {tool.tool_id} stickout "
                    f"{tool.stickout_mm:.1f} mm for {needed:.1f} mm of depth.",
                    operation_id=op.operation_id,
                    feature_id=feature.feature_id,
                    actual=tool.stickout_mm,
                    required=needed + 2.0,
                    units="mm",
                    repair_hint="Select a tool with longer stickout above the cutting length.",
                )
            )

        if feature.kind is FeatureKind.POCKET_RECT_ROUNDED:
            radius = tool.diameter_mm / 2
            if radius > feature.corner_radius_mm + 1e-9:
                results.append(
                    _fail(
                        "pocket_corner_radius",
                        CheckStage.PREFLIGHT,
                        f"Tool radius {radius:.2f} mm cannot produce the "
                        f"{feature.corner_radius_mm:.2f} mm internal corner radius.",
                        operation_id=op.operation_id,
                        feature_id=feature.feature_id,
                        actual=radius,
                        required=feature.corner_radius_mm,
                        units="mm",
                        repair_hint="Select a smaller-diameter end mill for this pocket.",
                    )
                )
            narrow = min(feature.x_max_mm - feature.x_min_mm, feature.y_max_mm - feature.y_min_mm)
            if tool.diameter_mm >= narrow - 1e-9:
                results.append(
                    _fail(
                        "pocket_width_fit",
                        CheckStage.PREFLIGHT,
                        f"Tool diameter {tool.diameter_mm:.2f} mm does not fit the "
                        f"{narrow:.2f} mm pocket width.",
                        operation_id=op.operation_id,
                        feature_id=feature.feature_id,
                        actual=tool.diameter_mm,
                        required=narrow,
                        units="mm",
                        repair_hint="Select a smaller-diameter end mill.",
                    )
                )
            if op.stepover_mm > tool.diameter_mm + 1e-9:
                results.append(
                    _fail(
                        "stepover_bound",
                        CheckStage.PREFLIGHT,
                        f"Stepover {op.stepover_mm:.2f} mm exceeds tool diameter "
                        f"{tool.diameter_mm:.2f} mm and would leave uncut material.",
                        operation_id=op.operation_id,
                        feature_id=feature.feature_id,
                        actual=op.stepover_mm,
                        required=tool.diameter_mm,
                        units="mm",
                        repair_hint="Reduce the stepover to at most the tool diameter.",
                    )
                )
            if op.entry is EntryStrategy.PLUNGE and not tool.center_cutting:
                results.append(
                    _fail(
                        "entry_capability",
                        CheckStage.PREFLIGHT,
                        f"Tool {tool.tool_id} is not centre-cutting and cannot plunge.",
                        operation_id=op.operation_id,
                        repair_hint="Use a ramp entry or a centre-cutting tool.",
                    )
                )
        else:
            if abs(tool.diameter_mm - feature.diameter_mm) > 1e-6:
                results.append(
                    _fail(
                        "hole_diameter_match",
                        CheckStage.PREFLIGHT,
                        f"Drill diameter {tool.diameter_mm:.2f} mm does not produce a "
                        f"{feature.diameter_mm:.2f} mm hole.",
                        operation_id=op.operation_id,
                        feature_id=feature.feature_id,
                        actual=tool.diameter_mm,
                        required=feature.diameter_mm,
                        units="mm",
                        repair_hint="Select a drill matching the drawing diameter.",
                    )
                )
            if tool.point_angle_deg is not None and feature.drill_point_angle_deg is not None:
                if abs(tool.point_angle_deg - feature.drill_point_angle_deg) > 1e-6:
                    results.append(
                        CheckResult(
                            check_id="drill_point_angle",
                            stage=CheckStage.PREFLIGHT,
                            status=CheckStatus.FAIL,
                            severity=Severity.WARNING,
                            message="Drill point angle differs from the drawing convention.",
                            operation_id=op.operation_id,
                            feature_id=feature.feature_id,
                            actual=tool.point_angle_deg,
                            required=feature.drill_point_angle_deg,
                            units="deg",
                        )
                    )

        if op.feed_mm_min > shop.max_feed_mm_min:
            results.append(
                _fail(
                    "machine_feed_limit",
                    CheckStage.PREFLIGHT,
                    f"Feed {op.feed_mm_min:.0f} mm/min exceeds the machine limit "
                    f"{shop.max_feed_mm_min:.0f} mm/min.",
                    operation_id=op.operation_id,
                    actual=op.feed_mm_min,
                    required=shop.max_feed_mm_min,
                    units="mm/min",
                    repair_hint="Lower the feed to the machine limit.",
                )
            )
        if op.spindle_rpm > shop.max_spindle_rpm:
            results.append(
                _fail(
                    "machine_spindle_limit",
                    CheckStage.PREFLIGHT,
                    f"Spindle {op.spindle_rpm:.0f} rpm exceeds the machine limit.",
                    operation_id=op.operation_id,
                    actual=op.spindle_rpm,
                    required=shop.max_spindle_rpm,
                    units="rpm",
                    repair_hint="Lower the spindle speed to the machine limit.",
                )
            )

    # 7. Workspace.
    if (
        spec.stock_x_mm > shop.envelope_x_mm
        or spec.stock_y_mm > shop.envelope_y_mm
        or spec.stock_z_mm > shop.envelope_z_mm
    ):
        results.append(
            _fail(
                "workspace_envelope",
                CheckStage.PREFLIGHT,
                "The stock does not fit the machine envelope.",
                repair_hint="This part cannot be run on this machine; human review required.",
            )
        )

    if not any(r.check_id == "tool_cutting_reach" for r in results):
        results.append(
            _ok("tool_cutting_reach", CheckStage.PREFLIGHT, "Every tool reaches its full depth.")
        )
    return results


# ------------------------------------------------------------------ path stage


def _segment_xy_distance_to_box(segment: Segment, box) -> float:
    """Minimum XY distance from the segment's centreline to an axis-aligned box."""
    best = math.inf
    span = math.hypot(segment.end_x_mm - segment.start_x_mm, segment.end_y_mm - segment.start_y_mm)
    steps = max(2, int(span / 0.25) + 1)
    for i in range(steps + 1):
        t = i / steps
        x = segment.start_x_mm + t * (segment.end_x_mm - segment.start_x_mm)
        y = segment.start_y_mm + t * (segment.end_y_mm - segment.start_y_mm)
        dx = max(box.x_min_mm - x, 0.0, x - box.x_max_mm)
        dy = max(box.y_min_mm - y, 0.0, y - box.y_max_mm)
        best = min(best, math.hypot(dx, dy))
    return best


def _segment_tip_z_range(segment: Segment) -> tuple[float, float]:
    return (
        min(segment.start_z_mm, segment.end_z_mm),
        max(segment.start_z_mm, segment.end_z_mm),
    )


def run_path_checks(
    spec: PartSpec,
    shop: ShopProfile,
    plan: ProcessPlan,
    trajectory: Trajectory,
    policy: Policy,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    # Endpoint continuity: a path with a jump is not a path.
    previous = (trajectory.initial_x_mm, trajectory.initial_y_mm, trajectory.initial_z_mm)
    for segment in trajectory.segments:
        start = (segment.start_x_mm, segment.start_y_mm, segment.start_z_mm)
        if math.dist(previous, start) > 1e-6:
            results.append(
                _fail(
                    "path_continuity",
                    CheckStage.PATH,
                    f"Segment {segment.segment_id} does not start where the previous one ended.",
                    segment_id=segment.segment_id,
                    repair_hint="Compiler defect: report it; do not change the part.",
                )
            )
            break
        previous = (segment.end_x_mm, segment.end_y_mm, segment.end_z_mm)
    else:
        results.append(_ok("path_continuity", CheckStage.PATH, "Path endpoints are continuous."))

    # Travel bounds.
    for segment in trajectory.segments:
        for z in (segment.start_z_mm, segment.end_z_mm):
            if z > shop.envelope_z_mm or z < -spec.stock_z_mm - 5.0:
                results.append(
                    _fail(
                        "path_travel_bounds",
                        CheckStage.PATH,
                        f"Segment {segment.segment_id} leaves the permitted Z travel.",
                        segment_id=segment.segment_id,
                        actual=z,
                        units="mm",
                        repair_hint="Reduce the clearance plane or retract height.",
                    )
                )
                break
        else:
            continue
        break

    # Non-cutting lateral motion may not pass through stock material.
    for segment in trajectory.segments:
        if segment.cutting or segment.kind is MotionKind.TOOL_CHANGE:
            continue
        low_z = min(segment.start_z_mm, segment.end_z_mm)
        if low_z >= -1e-9:
            continue
        # A purely vertical move in place is a retract or an in-hole peck: it cannot
        # sweep sideways through material. Only lateral motion below the stock top can
        # tunnel, and the simulator remains the backstop for plunges.
        lateral = math.hypot(
            segment.end_x_mm - segment.start_x_mm, segment.end_y_mm - segment.start_y_mm
        )
        if lateral < 1e-9:
            continue
        results.append(
            _fail(
                "path_no_rapid_through_stock",
                CheckStage.PATH,
                f"Non-cutting segment {segment.segment_id} travels laterally below the "
                "stock top and would drag the tool through material.",
                segment_id=segment.segment_id,
                operation_id=segment.operation_id,
                actual=low_z,
                required=0.0,
                units="mm",
                repair_hint="Retract to the clearance plane before traversing.",
            )
        )
        break
    else:
        results.append(
            _ok(
                "path_no_rapid_through_stock",
                CheckStage.PATH,
                "Every traverse stays at or above the stock top.",
            )
        )

    # Promoted check (policy dependent): traverse envelope against fixtures.
    envelope = _fixture_envelope_check(shop, trajectory, policy)
    results.extend(envelope)
    return results


def _feature_of(plan: ProcessPlan, operation_id: str | None) -> str | None:
    if operation_id is None:
        return None
    for op in plan.operations:
        if op.operation_id == operation_id:
            return op.feature_id
    return None


def _fixture_envelope_check(
    shop: ShopProfile, trajectory: Trajectory, policy: Policy
) -> list[CheckResult]:
    """Cheap pre-simulation envelope test for non-cutting traverses over fixtures.

    Promoted out of the simulator. It reuses the simulator's own tool model, so the
    two cannot disagree about where the cutter, shank and holder actually are: each
    part is tested at its own radius AND its own height above the tool tip. Testing
    the widest radius against the tip height instead would reject valid paths, which
    is what the boundary fixtures exist to catch.

    It is deliberately asymmetric. A definite geometric overlap fails. A clearance
    that is merely thinner than the shop's declared minimum warns and defers to the
    simulator rather than rejecting a path that may well be fine.
    """
    from silta.simulation import tool_parts

    check_id = "path_fixture_envelope"
    if not shop.fixtures:
        return []
    enabled = policy.enabled(check_id)

    worst: tuple[float, Segment, object, str] | None = None
    for segment in trajectory.segments:
        if segment.cutting or segment.kind is MotionKind.TOOL_CHANGE:
            continue
        tool = shop.tool(segment.tool_id) if segment.tool_id else None
        if tool is None:
            continue
        low_z, high_z = _segment_tip_z_range(segment)
        for part in tool_parts(tool):
            for box in shop.fixtures:
                if _segment_xy_distance_to_box(segment, box) >= part.radius_mm:
                    continue  # this part never passes over the fixture
                part_bottom_lowest = low_z + part.bottom_offset_mm
                part_top_highest = high_z + part.top_offset_mm
                if part_top_highest <= box.z_min_mm:
                    continue  # the whole part stays below the fixture
                gap = part_bottom_lowest - box.z_max_mm
                if worst is None or gap < worst[0]:
                    worst = (gap, segment, box, part.name)

    if worst is None:
        return [_ok(check_id, CheckStage.PATH, "No non-cutting traverse passes over a fixture.")]

    gap, segment, box, part_name = worst
    required = shop.min_fixture_clearance_mm
    if gap < 0:
        status, severity = CheckStatus.FAIL, Severity.BLOCKING
        message = (
            f"Traverse {segment.segment_id} carries the {part_name} "
            f"{abs(gap):.1f} mm below the top of {box.fixture_id}."
        )
    elif gap < required - 1e-9:
        status, severity = CheckStatus.FAIL, Severity.WARNING
        message = (
            f"Traverse {segment.segment_id} clears {box.fixture_id} by only "
            f"{gap:.1f} mm at the {part_name}; the shop requires {required:.1f} mm. "
            "Deferring to simulation."
        )
    else:
        status, severity = CheckStatus.PASS, Severity.INFO
        message = (
            f"Every traverse clears the fixtures it crosses; the tightest is "
            f"{gap:.1f} mm at the {part_name} over {box.fixture_id}."
        )
    return [
        CheckResult(
            check_id=check_id,
            check_version="2",
            stage=CheckStage.PATH,
            status=status if enabled else CheckStatus.NOT_APPLICABLE,
            severity=severity if enabled else Severity.INFO,
            message=message
            if enabled
            else f"Check not promoted in {policy.version}; the simulator decides.",
            segment_id=segment.segment_id,
            operation_id=segment.operation_id,
            actual=round(gap, 3),
            required=required,
            units="mm",
            evidence={
                "fixture_id": box.fixture_id,
                "fixture_top_mm": box.z_max_mm,
                "tool_part": part_name,
            },
            repair_hint="Raise the clearance plane above every fixture the tool "
            "traverses, keeping the declared minimum fixture clearance.",
        )
    ]


def blocking(results: list[CheckResult]) -> list[CheckResult]:
    return [r for r in results if r.blocking_failure]
