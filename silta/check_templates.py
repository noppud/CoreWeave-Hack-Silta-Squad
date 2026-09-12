"""Trusted template registry for constrained check proposals.

The model supplies a template ID and bounded parameters; it never supplies code,
imports or expressions. Per §4: start with exactly one template family, the
parameterized generalization of the existing path_fixture_envelope check.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from silta.domain import (
    CheckResult,
    CheckStage,
    CheckStatus,
    MotionKind,
    PartSpec,
    ProcessPlan,
    Segment,
    Severity,
    ShopProfile,
    Trajectory,
)
from silta.simulation import tool_parts


class TemplateId(StrEnum):
    """Known template identifiers. Only these may be used in proposals."""

    SWEPT_FIXTURE_CLEARANCE = "swept_fixture_clearance_v1"


TEMPLATE_VERSION = "templates-1"


class SweptFixtureClearanceParams(BaseModel):
    """Parameters for the swept non-cutting tool/fixture clearance template.

    This is the parameterized generalization of the path_fixture_envelope check v2.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    clearance_margin_mm: float = Field(ge=0.0, le=50.0)
    check_cutter: bool = True
    check_shank: bool = True
    check_holder: bool = True
    only_non_cutting: bool = True

    def validate_bounds(self) -> tuple[bool, str | None]:
        """Validate parameter bounds and consistency. Returns (valid, error_msg)."""
        if not (self.check_cutter or self.check_shank or self.check_holder):
            return False, "At least one tool part must be checked"
        if self.clearance_margin_mm < 0:
            return False, "Clearance margin must be non-negative"
        return True, None


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


def apply_swept_fixture_clearance(
    spec: PartSpec,
    shop: ShopProfile,
    plan: ProcessPlan,
    trajectory: Trajectory,
    params: SweptFixtureClearanceParams,
    check_id: str = "swept_fixture_clearance",
) -> list[CheckResult]:
    """Apply the swept fixture clearance template with the given parameters.

    This is a direct parameterization of the path_fixture_envelope check v2 from
    silta/checks.py lines 474-563. Each tool part is tested at its own radius AND
    its own height above the tool tip.
    """
    if not shop.fixtures:
        return []

    required = params.clearance_margin_mm
    parts_to_check = []
    if params.check_cutter:
        parts_to_check.append(0)
    if params.check_shank:
        parts_to_check.append(1)
    if params.check_holder:
        parts_to_check.append(2)

    worst: tuple[float, Segment, object, str] | None = None
    for segment in trajectory.segments:
        if params.only_non_cutting and segment.cutting:
            continue
        if params.only_non_cutting and segment.kind is MotionKind.TOOL_CHANGE:
            continue

        tool = shop.tool(segment.tool_id) if segment.tool_id else None
        if tool is None:
            continue

        low_z, high_z = _segment_tip_z_range(segment)
        all_parts = tool_parts(tool)

        for part_idx in parts_to_check:
            if part_idx >= len(all_parts):
                continue
            part = all_parts[part_idx]

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
        return [
            CheckResult(
                check_id=check_id,
                check_version="1",
                stage=CheckStage.PATH,
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                message="No non-cutting traverse passes over a fixture.",
            )
        ]

    gap, segment, box, part_name = worst
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
            f"{gap:.1f} mm at the {part_name}; required {required:.1f} mm. "
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
            check_version="1",
            stage=CheckStage.PATH,
            status=status,
            severity=severity,
            message=message,
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


# Template registry
_TEMPLATES = {
    TemplateId.SWEPT_FIXTURE_CLEARANCE: {
        "id": TemplateId.SWEPT_FIXTURE_CLEARANCE,
        "version": "1",
        "description": "Swept non-cutting tool/fixture clearance with declared envelope and margin",
        "param_type": SweptFixtureClearanceParams,
        "apply_fn": apply_swept_fixture_clearance,
    }
}


def get_template(template_id: TemplateId) -> dict:
    """Get a template by ID. Raises KeyError if not found."""
    if template_id not in _TEMPLATES:
        raise KeyError(f"Unknown template ID: {template_id}")
    return _TEMPLATES[template_id]


def list_templates() -> list[dict]:
    """List all available templates."""
    return [
        {
            "id": t["id"],
            "version": t["version"],
            "description": t["description"],
        }
        for t in _TEMPLATES.values()
    ]


def validate_params(template_id: TemplateId, params: dict) -> tuple[bool, str | None]:
    """Validate parameters for a template. Returns (valid, error_msg)."""
    template = get_template(template_id)
    param_type = template["param_type"]
    try:
        parsed = param_type(**params)
        return parsed.validate_bounds()
    except Exception as e:
        return False, str(e)
