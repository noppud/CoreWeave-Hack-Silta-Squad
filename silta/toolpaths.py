"""Recipe -> trajectory. Fixed templates only; the model never emits motion.

The trajectory is a replay and verification format in engineering coordinates.
It is not G-code: no postprocessor, controller dialect or machine execution is
in scope, and the estimated duration is an arithmetic estimate, not measured
cycle time.
"""

from __future__ import annotations

from silta.domain import (
    EntryStrategy,
    Feature,
    FeatureKind,
    MotionKind,
    Operation,
    OperationKind,
    PartSpec,
    ProcessPlan,
    Segment,
    ShopProfile,
    Tool,
    Trajectory,
)

COMPILER_VERSION = "compiler-1"

# Height above the stock top at which a rapid switches to a controlled feed.
APPROACH_Z_MM = 1.0
MAX_STEP_MM = 0.25


class CompileError(ValueError):
    """A recipe that cannot be expanded into a path at all."""


class _Builder:
    def __init__(self, shop: ShopProfile, clearance_mm: float) -> None:
        self.shop = shop
        self.clearance = clearance_mm
        self.segments: list[Segment] = []
        self.x = shop.home_x_mm
        self.y = shop.home_y_mm
        self.z = shop.home_z_mm
        self.tool: Tool | None = None

    def _emit(
        self,
        kind: MotionKind,
        x: float,
        y: float,
        z: float,
        *,
        feed: float,
        cutting: bool,
        operation_id: str | None,
        duration_override: float | None = None,
    ) -> None:
        length = ((x - self.x) ** 2 + (y - self.y) ** 2 + (z - self.z) ** 2) ** 0.5
        if duration_override is not None:
            duration = duration_override
        elif feed > 0:
            duration = length / feed * 60.0
        else:
            duration = 0.0
        self.segments.append(
            Segment(
                segment_id=f"s{len(self.segments):04d}",
                operation_id=operation_id,
                tool_id=self.tool.tool_id if self.tool else None,
                kind=kind,
                start_x_mm=round(self.x, 6),
                start_y_mm=round(self.y, 6),
                start_z_mm=round(self.z, 6),
                end_x_mm=round(x, 6),
                end_y_mm=round(y, 6),
                end_z_mm=round(z, 6),
                feed_mm_min=feed,
                cutting=cutting,
                duration_s=duration,
            )
        )
        self.x, self.y, self.z = x, y, z

    def rapid(self, x: float, y: float, z: float, operation_id: str | None = None) -> None:
        self._emit(
            MotionKind.RAPID,
            x,
            y,
            z,
            feed=self.shop.rapid_feed_mm_min,
            cutting=False,
            operation_id=operation_id,
        )

    def retract(self, operation_id: str | None = None) -> None:
        if abs(self.z - self.clearance) < 1e-9:
            return
        self._emit(
            MotionKind.RETRACT,
            self.x,
            self.y,
            self.clearance,
            feed=self.shop.rapid_feed_mm_min,
            cutting=False,
            operation_id=operation_id,
        )

    def feed(
        self, x: float, y: float, z: float, feed: float, operation_id: str, cutting: bool = True
    ) -> None:
        self._emit(MotionKind.FEED, x, y, z, feed=feed, cutting=cutting, operation_id=operation_id)

    def change_tool(self, tool: Tool) -> None:
        self.retract()
        safe_z = max(self.shop.home_z_mm, self.clearance)
        self.rapid(self.shop.home_x_mm, self.shop.home_y_mm, safe_z)
        previous = self.tool
        self.tool = tool
        self._emit(
            MotionKind.TOOL_CHANGE,
            self.x,
            self.y,
            self.z,
            feed=0.0,
            cutting=False,
            operation_id=None,
            duration_override=0.0 if previous is None else self.shop.tool_change_seconds,
        )


def _raster_lines(
    feature: Feature, tool: Tool, stepover_mm: float
) -> tuple[list[float], float, float]:
    """Tool-centre limits after cutter radius compensation, plus the Y raster lines."""
    radius = tool.diameter_mm / 2
    x_lo = feature.x_min_mm + radius
    x_hi = feature.x_max_mm - radius
    y_lo = feature.y_min_mm + radius
    y_hi = feature.y_max_mm - radius
    if x_hi <= x_lo or y_hi <= y_lo:
        raise CompileError(f"Tool {tool.tool_id} is too wide for pocket {feature.feature_id}.")
    lines = [y_lo]
    while lines[-1] < y_hi - 1e-9:
        lines.append(min(lines[-1] + stepover_mm, y_hi))
    return lines, x_lo, x_hi


def _compile_pocket(builder: _Builder, op: Operation, feature: Feature, tool: Tool) -> None:
    lines, x_lo, x_hi = _raster_lines(feature, tool, op.stepover_mm)
    depth = feature.depth_mm
    levels: list[float] = []
    z = -op.stepdown_mm
    while z > -depth + 1e-9:
        levels.append(z)
        z -= op.stepdown_mm
    levels.append(-depth)

    builder.retract(op.operation_id)
    builder.rapid(x_lo, lines[0], builder.clearance, op.operation_id)
    previous_level = 0.0
    for level in levels:
        builder.rapid(x_lo, lines[0], APPROACH_Z_MM, op.operation_id)
        if op.entry is EntryStrategy.PLUNGE:
            builder.feed(x_lo, lines[0], level, op.feed_mm_min / 3.0, op.operation_id)
        else:  # ramp in along the first raster line
            builder.feed(x_hi, lines[0], level, op.feed_mm_min / 2.0, op.operation_id)
        left_to_right = op.entry is EntryStrategy.PLUNGE
        for index, y in enumerate(lines):
            if index > 0:
                builder.feed(builder.x, y, level, op.feed_mm_min, op.operation_id)
            target_x = x_hi if left_to_right else x_lo
            builder.feed(target_x, y, level, op.feed_mm_min, op.operation_id)
            left_to_right = not left_to_right
        builder.retract(op.operation_id)
        builder.rapid(x_lo, lines[0], builder.clearance, op.operation_id)
        previous_level = level
    del previous_level


def _compile_drill(builder: _Builder, op: Operation, feature: Feature, tool: Tool) -> None:
    total = feature.total_tip_depth_mm
    peck = op.peck_depth_mm or total
    builder.retract(op.operation_id)
    builder.rapid(feature.center_x_mm, feature.center_y_mm, builder.clearance, op.operation_id)
    builder.rapid(feature.center_x_mm, feature.center_y_mm, APPROACH_Z_MM, op.operation_id)
    reached = 0.0
    while reached < total - 1e-9:
        reached = min(reached + peck, total)
        builder.feed(
            feature.center_x_mm, feature.center_y_mm, -reached, op.feed_mm_min, op.operation_id
        )
        if reached < total - 1e-9:
            builder.rapid(feature.center_x_mm, feature.center_y_mm, APPROACH_Z_MM, op.operation_id)
    builder.rapid(feature.center_x_mm, feature.center_y_mm, APPROACH_Z_MM, op.operation_id)
    builder.retract(op.operation_id)


def compile_plan(spec: PartSpec, shop: ShopProfile, plan: ProcessPlan) -> Trajectory:
    features = {f.feature_id: f for f in spec.features}
    builder = _Builder(shop, plan.clearance_mm)
    builder.rapid(shop.home_x_mm, shop.home_y_mm, max(shop.home_z_mm, plan.clearance_mm))

    for op in plan.operations:
        feature = features.get(op.feature_id)
        tool = shop.tool(op.tool_id)
        if feature is None:
            raise CompileError(f"Operation {op.operation_id} references unknown feature.")
        if tool is None:
            raise CompileError(f"Operation {op.operation_id} references unknown tool.")
        if builder.tool is None or builder.tool.tool_id != tool.tool_id:
            builder.change_tool(tool)
        if op.kind is OperationKind.POCKET_RASTER:
            if feature.kind is not FeatureKind.POCKET_RECT_ROUNDED:
                raise CompileError(f"{op.kind} cannot machine {feature.kind}.")
            _compile_pocket(builder, op, feature, tool)
        elif op.kind is OperationKind.DRILL:
            if feature.kind is not FeatureKind.HOLE_BLIND:
                raise CompileError(f"{op.kind} cannot machine {feature.kind}.")
            _compile_drill(builder, op, feature, tool)
        else:  # pragma: no cover - the enum is closed
            raise CompileError(f"Unsupported operation kind {op.kind}.")

    builder.retract()
    builder.rapid(shop.home_x_mm, shop.home_y_mm, max(shop.home_z_mm, plan.clearance_mm))

    return Trajectory(
        trajectory_id=f"traj-{plan.plan_id}",
        plan_id=plan.plan_id,
        spec_design_hash=spec.design_hash,
        shop_hash=shop.shop_hash,
        compiler_version=COMPILER_VERSION,
        initial_x_mm=shop.home_x_mm,
        initial_y_mm=shop.home_y_mm,
        initial_z_mm=shop.home_z_mm,
        segments=tuple(builder.segments),
        max_step_mm=MAX_STEP_MM,
    )


def estimated_seconds(trajectory: Trajectory, shop: ShopProfile, plan: ProcessPlan) -> float:
    """Motion time plus declared per-setup constants. Assumptions are explicit."""
    return trajectory.estimated_seconds + shop.setup_seconds * len(plan.setups)
