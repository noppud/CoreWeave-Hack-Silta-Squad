"""Frozen demonstration fixtures.

The geometry below is a synthetic, team-authored demonstration part. Expected
values in `fixtures/demo/oracle.json` are calculated independently of the CAD
builder so that the builder cannot certify itself. These are demonstration
assumptions, not machining advice.
"""

from __future__ import annotations

import math

from silta.domain import (
    DrillTipConvention,
    EntryStrategy,
    Feature,
    FeatureKind,
    FixtureSolid,
    Operation,
    OperationKind,
    PartSpec,
    ProcessPlan,
    Setup,
    ShopProfile,
    Tool,
    ToolKind,
    Units,
    utc_now,
)

DEMO_POLICY_V0 = "policy-v0"
DEMO_POLICY_V1 = "policy-v1"

# --------------------------------------------------------------------- the part

DEMO_SPEC = PartSpec(
    spec_id="fixture-block-01",
    revision=1,
    units=Units.MM,
    material="6061-T6 aluminium",
    stock_x_mm=80.0,
    stock_y_mm=60.0,
    stock_z_mm=20.0,
    confirmed_at=None,
    features=(
        Feature(
            feature_id="pocket_1",
            kind=FeatureKind.POCKET_RECT_ROUNDED,
            x_min_mm=20.0,
            x_max_mm=60.0,
            y_min_mm=20.0,
            y_max_mm=40.0,
            corner_radius_mm=3.0,
            depth_mm=12.0,
            drawing_refs=("A1", "A2", "A3"),
        ),
        *(
            Feature(
                feature_id=f"hole_{i + 1}",
                kind=FeatureKind.HOLE_BLIND,
                center_x_mm=cx,
                center_y_mm=cy,
                diameter_mm=6.0,
                depth_mm=8.0,
                drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                drill_point_angle_deg=118.0,
                drawing_refs=(f"B{i + 1}",),
            )
            for i, (cx, cy) in enumerate([(10.0, 10.0), (70.0, 10.0), (10.0, 50.0), (70.0, 50.0)])
        ),
    ),
)

# ---------------------------------------------------------------------- the shop

EM6_SHORT = Tool(
    tool_id="EM6-S",
    kind=ToolKind.END_MILL,
    diameter_mm=6.0,
    cutting_length_mm=8.0,
    stickout_mm=22.0,
    shank_diameter_mm=6.0,
    holder_diameter_mm=26.0,
    center_cutting=True,
    allowed_operations=(OperationKind.POCKET_RASTER,),
    feed_mm_min=900.0,
    spindle_rpm=7000.0,
)

EM6_LONG = Tool(
    tool_id="EM6-L",
    kind=ToolKind.END_MILL,
    diameter_mm=6.0,
    cutting_length_mm=18.0,
    stickout_mm=34.0,
    shank_diameter_mm=6.0,
    holder_diameter_mm=26.0,
    center_cutting=True,
    allowed_operations=(OperationKind.POCKET_RASTER,),
    feed_mm_min=700.0,
    spindle_rpm=6500.0,
)

DR6 = Tool(
    tool_id="DR6",
    kind=ToolKind.DRILL,
    diameter_mm=6.0,
    cutting_length_mm=25.0,
    stickout_mm=40.0,
    shank_diameter_mm=6.0,
    holder_diameter_mm=26.0,
    center_cutting=True,
    point_angle_deg=118.0,
    allowed_operations=(OperationKind.DRILL,),
    feed_mm_min=250.0,
    spindle_rpm=3200.0,
)

DEMO_SHOP = ShopProfile(
    shop_id="shop-3axis-01",
    display_name="Three-axis mill, bench vise with two top clamps",
    envelope_x_mm=400.0,
    envelope_y_mm=300.0,
    envelope_z_mm=250.0,
    max_feed_mm_min=4000.0,
    max_spindle_rpm=12000.0,
    tools=(EM6_SHORT, EM6_LONG, DR6),
    fixtures=(
        FixtureSolid(
            fixture_id="clamp_front",
            x_min_mm=34.0,
            x_max_mm=46.0,
            y_min_mm=-6.0,
            y_max_mm=6.0,
            z_min_mm=0.0,
            z_max_mm=12.0,
        ),
        FixtureSolid(
            fixture_id="clamp_back",
            x_min_mm=34.0,
            x_max_mm=46.0,
            y_min_mm=54.0,
            y_max_mm=66.0,
            z_min_mm=0.0,
            z_max_mm=12.0,
        ),
    ),
    home_x_mm=40.0,
    home_y_mm=-20.0,
    home_z_mm=25.0,
    min_fixture_clearance_mm=3.0,
    rapid_feed_mm_min=8000.0,
)


def _operations(tool_pocket: str) -> tuple[Operation, ...]:
    ops = [
        Operation(
            operation_id="op_pocket_1",
            setup_id="setup_1",
            feature_id="pocket_1",
            tool_id=tool_pocket,
            kind=OperationKind.POCKET_RASTER,
            stepdown_mm=2.0,
            stepover_mm=3.0,
            entry=EntryStrategy.PLUNGE,
            feed_mm_min=700.0,
            spindle_rpm=6500.0,
        )
    ]
    for i in range(1, 5):
        ops.append(
            Operation(
                operation_id=f"op_hole_{i}",
                setup_id="setup_1",
                feature_id=f"hole_{i}",
                tool_id="DR6",
                kind=OperationKind.DRILL,
                stepdown_mm=4.0,
                stepover_mm=1.0,
                entry=EntryStrategy.PLUNGE,
                feed_mm_min=250.0,
                spindle_rpm=3200.0,
                peck_depth_mm=4.0,
            )
        )
    return tuple(ops)


def naive_plan() -> ProcessPlan:
    """Explicitly labelled naive starting recipe: short tool, low traverse.

    It is the seed of attempt 0 in the demonstration, not a model output.
    """
    return ProcessPlan(
        plan_id="plan-naive-0",
        policy_version="naive-seed",
        spec_design_hash=DEMO_SPEC.design_hash,
        shop_hash=DEMO_SHOP.shop_hash,
        setups=(Setup(setup_id="setup_1", description="Top access, stock clamped at Y edges"),),
        operations=_operations("EM6-S"),
        clearance_mm=5.0,
        notes="Naive seed recipe supplied as the starting point; not validated.",
    )


def reach_repaired_plan() -> ProcessPlan:
    """Long tool, clearance still too low: passes preflight, collides in simulation."""
    return ProcessPlan(
        plan_id="plan-reach-fixed",
        policy_version=DEMO_POLICY_V0,
        spec_design_hash=DEMO_SPEC.design_hash,
        shop_hash=DEMO_SHOP.shop_hash,
        setups=(Setup(setup_id="setup_1", description="Top access, stock clamped at Y edges"),),
        operations=_operations("EM6-L"),
        clearance_mm=5.0,
        notes="Tool reach repaired.",
    )


def valid_plan() -> ProcessPlan:
    """Independently authored known-valid recipe."""
    return ProcessPlan(
        plan_id="plan-valid",
        policy_version=DEMO_POLICY_V0,
        spec_design_hash=DEMO_SPEC.design_hash,
        shop_hash=DEMO_SHOP.shop_hash,
        setups=(Setup(setup_id="setup_1", description="Top access, stock clamped at Y edges"),),
        operations=_operations("EM6-L"),
        clearance_mm=15.0,
        notes="Known-valid reference recipe authored by hand from the drawing.",
    )


def expected_geometry() -> dict:
    """Analytic oracle, derived from the drawing rather than from the CAD builder."""
    pocket = DEMO_SPEC.features[0]
    width = pocket.x_max_mm - pocket.x_min_mm
    height = pocket.y_max_mm - pocket.y_min_mm
    r = pocket.corner_radius_mm
    # Rounded rectangle area = full rectangle minus the four corner offcuts.
    pocket_area = width * height - (4 - math.pi) * r * r
    pocket_volume = pocket_area * pocket.depth_mm

    hole = DEMO_SPEC.features[1]
    radius = hole.diameter_mm / 2
    tip_extra = radius / math.tan(math.radians(hole.drill_point_angle_deg / 2))
    hole_volume = math.pi * radius**2 * hole.depth_mm + (math.pi * radius**2 * tip_extra) / 3
    stock_volume = DEMO_SPEC.stock_x_mm * DEMO_SPEC.stock_y_mm * DEMO_SPEC.stock_z_mm
    return {
        "stock_volume_mm3": stock_volume,
        "pocket_volume_mm3": pocket_volume,
        "hole_volume_mm3": hole_volume,
        "hole_count": 4,
        "tip_extra_mm": tip_extra,
        "part_volume_mm3": stock_volume - pocket_volume - 4 * hole_volume,
        "bbox_mm": [DEMO_SPEC.stock_x_mm, DEMO_SPEC.stock_y_mm, DEMO_SPEC.stock_z_mm],
    }


def confirmed_demo_spec() -> PartSpec:
    return DEMO_SPEC.model_copy(update={"confirmed_at": utc_now()})
