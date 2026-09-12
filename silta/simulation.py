"""Simplified 2.5D stock-removal and collision simulation.

This is a geometric stock-removal and collision simulator, not a physical machine
simulation. It cannot validate undercuts, five-axis motion, deflection, cutting
forces, chatter, thermal behaviour or machine dynamics. Results carry the method,
grid resolution and thresholds used to produce them.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from silta.domain import (
    CollisionEvent,
    Feature,
    FeatureCoverage,
    FeatureKind,
    FixtureSolid,
    PartSpec,
    ProcessPlan,
    Segment,
    ShopProfile,
    SimulationResult,
    SimulationStatus,
    Tool,
    ToolKind,
    Trajectory,
)

SIMULATOR_VERSION = "sim-1"
DEFAULT_GRID_MM = 0.5
DEFAULT_RESIDUAL_THRESHOLD_MM = 0.15
DEFAULT_GOUGE_THRESHOLD_MM = 0.15
HOLDER_LENGTH_MM = 60.0
KEYFRAME_COUNT = 12
KEYFRAME_GRID_MM = 1.0


@dataclass(frozen=True)
class ToolPart:
    name: str
    radius_mm: float
    bottom_offset_mm: float  # relative to the tool tip, positive upwards
    top_offset_mm: float
    conical_tip_mm: float = 0.0  # extra depth of the point below `bottom_offset`


def tool_parts(tool: Tool) -> tuple[ToolPart, ...]:
    tip = 0.0
    if tool.kind is ToolKind.DRILL and tool.point_angle_deg:
        tip = (tool.diameter_mm / 2) / math.tan(math.radians(tool.point_angle_deg / 2))
    return (
        ToolPart("cutter", tool.diameter_mm / 2, 0.0, tool.cutting_length_mm, tip),
        ToolPart("shank", tool.shank_diameter_mm / 2, tool.cutting_length_mm, tool.stickout_mm),
        ToolPart(
            "holder",
            tool.holder_diameter_mm / 2,
            tool.stickout_mm,
            tool.stickout_mm + HOLDER_LENGTH_MM,
        ),
    )


def _box_xy_distance(x: float, y: float, box: FixtureSolid) -> float:
    dx = max(box.x_min_mm - x, 0.0, x - box.x_max_mm)
    dy = max(box.y_min_mm - y, 0.0, y - box.y_max_mm)
    return math.hypot(dx, dy)


class _Grid:
    """Stock top surface as a heightfield. Z = 0 is the original stock top."""

    def __init__(self, spec: PartSpec, grid_mm: float) -> None:
        self.grid = grid_mm
        self.nx = int(math.ceil(spec.stock_x_mm / grid_mm))
        self.ny = int(math.ceil(spec.stock_y_mm / grid_mm))
        self.floor = -spec.stock_z_mm
        self.xs = (np.arange(self.nx) + 0.5) * grid_mm
        self.ys = (np.arange(self.ny) + 0.5) * grid_mm
        self.height = np.zeros((self.nx, self.ny), dtype=np.float64)
        self._xx = self.xs[:, None]
        self._yy = self.ys[None, :]

    def window(self, x: float, y: float, radius: float):
        i0 = max(0, int((x - radius) / self.grid))
        i1 = min(self.nx, int((x + radius) / self.grid) + 2)
        j0 = max(0, int((y - radius) / self.grid))
        j1 = min(self.ny, int((y + radius) / self.grid) + 2)
        if i0 >= i1 or j0 >= j1:
            return None
        dx = self.xs[i0:i1, None] - x
        dy = self.ys[None, j0:j1] - y
        dist = np.sqrt(dx * dx + dy * dy)
        mask = dist <= radius
        if not mask.any():
            return None
        return i0, i1, j0, j1, dist, mask


def target_field(spec: PartSpec, grid: _Grid) -> tuple[np.ndarray, np.ndarray]:
    """Analytic target surface and a per-cell feature label, from the spec alone."""
    height = np.zeros((grid.nx, grid.ny), dtype=np.float64)
    label = np.zeros((grid.nx, grid.ny), dtype=np.int16)
    xx, yy = grid._xx, grid._yy
    for index, feature in enumerate(spec.features, start=1):
        if feature.kind is FeatureKind.POCKET_RECT_ROUNDED:
            r = feature.corner_radius_mm
            cx = np.clip(xx, feature.x_min_mm + r, feature.x_max_mm - r)
            cy = np.clip(yy, feature.y_min_mm + r, feature.y_max_mm - r)
            inside = ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r + 1e-12
            height = np.where(inside, np.minimum(height, -feature.depth_mm), height)
            label = np.where(inside, index, label)
        else:
            radius = feature.diameter_mm / 2
            dist = np.sqrt((xx - feature.center_x_mm) ** 2 + (yy - feature.center_y_mm) ** 2)
            inside = dist <= radius + 1e-12
            cyl = feature.cylindrical_depth_mm
            tip = feature.tip_extra_mm
            bottom = -(cyl + tip * (1.0 - np.clip(dist / radius, 0.0, 1.0)))
            height = np.where(inside, np.minimum(height, bottom), height)
            label = np.where(inside, index, label)
    return height, label


def _clean_mask(spec: PartSpec, grid: _Grid, label: np.ndarray) -> np.ndarray:
    """Cells whose feature membership is constant within a margin of the cell.

    Boundary cells are excluded because a heightfield cannot resolve a wall to
    better than its own grid. Dimensional accuracy at feature walls is checked
    against the CAD solid, not against this grid.
    """
    margin = grid.grid * 1.5
    clean = np.ones_like(label, dtype=bool)
    for dx, dy in (
        (margin, 0),
        (-margin, 0),
        (0, margin),
        (0, -margin),
        (margin, margin),
        (-margin, -margin),
        (margin, -margin),
        (-margin, margin),
    ):
        shifted = _label_at(spec, grid._xx + dx, grid._yy + dy)
        clean &= shifted == label
    return clean


def _label_at(spec: PartSpec, xx: np.ndarray, yy: np.ndarray) -> np.ndarray:
    label = np.zeros(np.broadcast(xx, yy).shape, dtype=np.int16)
    for index, feature in enumerate(spec.features, start=1):
        if feature.kind is FeatureKind.POCKET_RECT_ROUNDED:
            r = feature.corner_radius_mm
            cx = np.clip(xx, feature.x_min_mm + r, feature.x_max_mm - r)
            cy = np.clip(yy, feature.y_min_mm + r, feature.y_max_mm - r)
            inside = ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r + 1e-12
        else:
            radius = feature.diameter_mm / 2
            dist = np.sqrt((xx - feature.center_x_mm) ** 2 + (yy - feature.center_y_mm) ** 2)
            inside = dist <= radius + 1e-12
        label = np.where(inside, index, label)
    return label


def _samples(segment: Segment, max_step_mm: float) -> list[tuple[float, float, float]]:
    length = segment.length_mm
    steps = max(1, int(math.ceil(length / max_step_mm)))
    points = []
    for i in range(steps + 1):
        t = i / steps
        points.append(
            (
                segment.start_x_mm + t * (segment.end_x_mm - segment.start_x_mm),
                segment.start_y_mm + t * (segment.end_y_mm - segment.start_y_mm),
                segment.start_z_mm + t * (segment.end_z_mm - segment.start_z_mm),
            )
        )
    return points


def simulate(
    spec: PartSpec,
    shop: ShopProfile,
    plan: ProcessPlan,
    trajectory: Trajectory,
    *,
    grid_mm: float = DEFAULT_GRID_MM,
    residual_threshold_mm: float = DEFAULT_RESIDUAL_THRESHOLD_MM,
    gouge_threshold_mm: float = DEFAULT_GOUGE_THRESHOLD_MM,
    keyframes: int = KEYFRAME_COUNT,
    stop_on_first_collision: bool = True,
) -> tuple[SimulationResult, dict]:
    """Run the trajectory against the stock and the fixtures.

    Returns the result and a replay payload (keyframes + collision markers) for
    the viewer. The viewer never recomputes any of this.
    """
    started = time.perf_counter()
    grid = _Grid(spec, grid_mm)
    target, label = target_field(spec, grid)
    collisions: list[CollisionEvent] = []
    tools = {t.tool_id: t for t in shop.tools}

    keyframe_every = max(1, len(trajectory.segments) // max(1, keyframes))
    replay_frames: list[dict] = []

    def capture(segment_index: int) -> None:
        step = max(1, int(round(KEYFRAME_GRID_MM / grid.grid)))
        coarse = grid.height[::step, ::step]
        replay_frames.append(
            {
                "segment_index": segment_index,
                "nx": int(coarse.shape[0]),
                "ny": int(coarse.shape[1]),
                "grid_mm": grid.grid * step,
                "height": [round(float(v), 3) for v in coarse.reshape(-1)],
            }
        )

    capture(-1)
    aborted = False
    aborted_segment_id: str | None = None
    for index, segment in enumerate(trajectory.segments):
        tool = tools.get(segment.tool_id) if segment.tool_id else None
        if tool is None:
            continue
        parts = tool_parts(tool)
        for x, y, z in _samples(segment, trajectory.max_step_mm):
            # 1. Fixture collision against every modelled part of the tool assembly.
            for part in parts:
                lo = z + part.bottom_offset_mm
                hi = z + part.top_offset_mm
                for box in shop.fixtures:
                    if hi <= box.z_min_mm or lo >= box.z_max_mm:
                        continue
                    distance = _box_xy_distance(x, y, box)
                    if distance >= part.radius_mm:
                        continue
                    collisions.append(
                        CollisionEvent(
                            segment_id=segment.segment_id,
                            operation_id=segment.operation_id,
                            obstacle_id=box.fixture_id,
                            obstacle_kind="fixture",
                            colliding_part=part.name,  # type: ignore[arg-type]
                            x_mm=round(x, 3),
                            y_mm=round(y, 3),
                            z_mm=round(z, 3),
                            penetration_mm=round(
                                min(part.radius_mm - distance, box.z_max_mm - lo), 3
                            ),
                        )
                    )
                    break
                if collisions:
                    break
            if collisions and stop_on_first_collision:
                aborted = True
                break

            cutter = parts[0]
            patch = grid.window(x, y, cutter.radius_mm)
            if patch is not None:
                i0, i1, j0, j1, dist, mask = patch
                if cutter.conical_tip_mm > 0:
                    # Tip at the axis, rising to the full diameter at the periphery.
                    bottom = z + cutter.conical_tip_mm * np.clip(dist / cutter.radius_mm, 0.0, 1.0)
                else:
                    bottom = np.full(dist.shape, z)
                view = grid.height[i0:i1, j0:j1]
                if segment.cutting:
                    np.copyto(
                        view,
                        np.maximum(np.minimum(view, bottom), grid.floor),
                        where=mask,
                    )
                else:
                    contact = mask & (view > bottom + 1e-9)
                    if contact.any():
                        depth = float(np.max((view - bottom)[contact]))
                        collisions.append(
                            CollisionEvent(
                                segment_id=segment.segment_id,
                                operation_id=segment.operation_id,
                                obstacle_id="stock",
                                obstacle_kind="stock",
                                colliding_part="cutter",
                                x_mm=round(x, 3),
                                y_mm=round(y, 3),
                                z_mm=round(z, 3),
                                penetration_mm=round(depth, 3),
                            )
                        )
                        if stop_on_first_collision:
                            aborted = True
                            break
            # 2. Shank and holder must never touch stock, cutting or not.
            for part in parts[1:]:
                lo = z + part.bottom_offset_mm
                sub = grid.window(x, y, part.radius_mm)
                if sub is None:
                    continue
                i0, i1, j0, j1, dist, mask = sub
                view = grid.height[i0:i1, j0:j1]
                contact = mask & (view > lo + 1e-9)
                if contact.any():
                    collisions.append(
                        CollisionEvent(
                            segment_id=segment.segment_id,
                            operation_id=segment.operation_id,
                            obstacle_id="stock",
                            obstacle_kind="stock",
                            colliding_part=part.name,  # type: ignore[arg-type]
                            x_mm=round(x, 3),
                            y_mm=round(y, 3),
                            z_mm=round(z, 3),
                            penetration_mm=round(float(np.max((view - lo)[contact])), 3),
                        )
                    )
                    if stop_on_first_collision:
                        aborted = True
                    break
            if aborted:
                break
        if index % keyframe_every == 0:
            capture(index)
        if aborted:
            aborted_segment_id = segment.segment_id
            capture(index)
            break
    if not aborted:
        capture(len(trajectory.segments) - 1)

    clean = _clean_mask(spec, grid, label)
    difference = grid.height - target
    residual = float(np.max(difference[clean])) if clean.any() else 0.0
    gouge = float(-np.min(difference[clean])) if clean.any() else 0.0
    residual = max(residual, 0.0) + 0.0
    gouge = max(gouge, 0.0) + 0.0

    coverage: list[FeatureCoverage] = []
    for index, feature in enumerate(spec.features, start=1):
        cells = clean & (label == index)
        total = int(cells.sum())
        if total == 0:
            coverage.append(
                FeatureCoverage(
                    feature_id=feature.feature_id,
                    target_depth_mm=_feature_depth(feature),
                    achieved_depth_mm=0.0,
                    removed_fraction=0.0,
                )
            )
            continue
        reached = int((difference[cells] <= residual_threshold_mm).sum())
        coverage.append(
            FeatureCoverage(
                feature_id=feature.feature_id,
                target_depth_mm=_feature_depth(feature),
                achieved_depth_mm=round(float(-np.min(grid.height[cells])), 4),
                removed_fraction=round(reached / total, 4),
            )
        )

    if collisions:
        status = SimulationStatus.COLLISION
    elif gouge > gouge_threshold_mm:
        status = SimulationStatus.GOUGE
    elif residual > residual_threshold_mm or any(c.removed_fraction < 0.999 for c in coverage):
        status = SimulationStatus.INCOMPLETE_REMOVAL
    else:
        status = SimulationStatus.PASS

    elapsed = time.perf_counter() - started
    result = SimulationResult(
        simulation_id=f"sim-{trajectory.trajectory_id}-{int(grid_mm * 1000)}",
        trajectory_hash=trajectory.trajectory_hash,
        status=status,
        method=f"{SIMULATOR_VERSION}/heightfield_2_5d",
        grid_mm=grid_mm,
        collisions=tuple(collisions[:8]),
        coverage=tuple(coverage),
        max_residual_mm=round(residual, 4),
        max_gouge_mm=round(gouge, 4),
        residual_threshold_mm=residual_threshold_mm,
        gouge_threshold_mm=gouge_threshold_mm,
        elapsed_s=round(elapsed, 3),
        keyframe_count=len(replay_frames),
    )
    replay = {
        "frames": replay_frames,
        "stock": {
            "x_mm": spec.stock_x_mm,
            "y_mm": spec.stock_y_mm,
            "z_mm": spec.stock_z_mm,
        },
        "collisions": [c.model_dump(mode="json") for c in result.collisions],
        "aborted_at_segment": aborted_segment_id,
    }
    return result, replay


def _feature_depth(feature: Feature) -> float:
    if feature.kind is FeatureKind.POCKET_RECT_ROUNDED:
        return feature.depth_mm
    return feature.total_tip_depth_mm


def sampling_error_bound_mm(max_step_mm: float, radius_mm: float) -> float:
    """Worst-case gap left between consecutive swept-disc samples."""
    half = max_step_mm / 2
    if half >= radius_mm:
        return radius_mm
    return radius_mm - math.sqrt(radius_mm * radius_mm - half * half)
