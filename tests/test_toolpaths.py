"""Test trajectory compilation from ProcessPlan."""

import math

import pytest

from silta.domain import MotionKind
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, valid_plan
from silta.toolpaths import CompileError, compile_plan


class TestCompiler:
    """Test the deterministic compiler."""

    def test_segment_endpoints_are_continuous(self):
        """All segments must form a continuous path from the initial pose."""
        plan = valid_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        # Initial pose
        previous = (trajectory.initial_x_mm, trajectory.initial_y_mm, trajectory.initial_z_mm)

        for seg in trajectory.segments:
            start = (seg.start_x_mm, seg.start_y_mm, seg.start_z_mm)
            # Must start where previous ended
            assert math.dist(previous, start) < 1e-6, (
                f"Segment {seg.segment_id} does not start where previous ended: "
                f"{previous} -> {start}"
            )
            previous = (seg.end_x_mm, seg.end_y_mm, seg.end_z_mm)

    def test_rapid_feed_retract_semantics(self):
        """Rapid/feed/retract motion kinds must have correct semantics."""
        plan = valid_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        for seg in trajectory.segments:
            if seg.kind == MotionKind.RAPID:
                # Rapids use rapid_feed_mm_min and are never cutting
                assert seg.feed_mm_min == DEMO_SHOP.rapid_feed_mm_min
                assert seg.cutting is False
            elif seg.kind == MotionKind.FEED:
                # Feeds use operation feed and may be cutting or positioning
                assert seg.feed_mm_min <= DEMO_SHOP.max_feed_mm_min
            elif seg.kind == MotionKind.RETRACT:
                # Retracts use rapid feed and are never cutting
                assert seg.feed_mm_min == DEMO_SHOP.rapid_feed_mm_min
                assert seg.cutting is False

    def test_pocket_raster_tool_centre_inset(self):
        """A pocket raster's tool-centre limits must be inset by exactly the tool radius.

        For pocket_1 (x: 20-60, y: 20-40) with a 6mm diameter tool (radius 3mm),
        the tool centre should be limited to x: 23-57, y: 23-37.
        """
        plan = valid_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        # Find pocket_1 operation segments
        pocket_op_id = next(o.operation_id for o in plan.operations if o.feature_id == "pocket_1")
        pocket_segs = [s for s in trajectory.segments if s.operation_id == pocket_op_id]

        # Tool is EM6-L with diameter 6mm, radius 3mm
        tool = DEMO_SHOP.tool("EM6-L")
        radius = tool.diameter_mm / 2

        # Feature bounds
        pocket = next(f for f in DEMO_SPEC.features if f.feature_id == "pocket_1")
        x_min_tool = pocket.x_min_mm + radius
        x_max_tool = pocket.x_max_mm - radius
        y_min_tool = pocket.y_min_mm + radius
        y_max_tool = pocket.y_max_mm - radius

        # Check cutting segments stay within tool-centre limits
        for seg in pocket_segs:
            if seg.cutting:
                assert x_min_tool - 1e-6 <= seg.start_x_mm <= x_max_tool + 1e-6, (
                    f"Tool centre X {seg.start_x_mm} outside [{x_min_tool}, {x_max_tool}]"
                )
                assert x_min_tool - 1e-6 <= seg.end_x_mm <= x_max_tool + 1e-6
                assert y_min_tool - 1e-6 <= seg.start_y_mm <= y_max_tool + 1e-6
                assert y_min_tool - 1e-6 <= seg.end_y_mm <= y_max_tool + 1e-6

    def test_drill_reaches_total_tip_depth(self):
        """Drilling must reach total_tip_depth (cylindrical + cone), not just cylindrical.

        For a 6mm drill with 118-degree point drilling to 8mm cylindrical depth,
        the tip extra is (3mm / tan(59deg)) = 1.8025... mm.
        Total tip depth = 8.0 + 1.8025... = 9.8025... mm.
        The deepest Z in the drill operation must be approximately -9.8025mm.
        """
        plan = valid_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        # Find a hole operation
        hole = next(f for f in DEMO_SPEC.features if f.kind.value == "hole_blind")
        hole_op_id = next(
            o.operation_id for o in plan.operations if o.feature_id == hole.feature_id
        )
        hole_segs = [s for s in trajectory.segments if s.operation_id == hole_op_id]

        # The deepest Z in cutting segments should be the total tip depth
        cutting_z = [min(s.start_z_mm, s.end_z_mm) for s in hole_segs if s.cutting]
        deepest = min(cutting_z) if cutting_z else 0

        expected_depth = hole.total_tip_depth_mm
        assert math.isclose(-deepest, expected_depth, abs_tol=1e-6), (
            f"Drill depth {-deepest} does not match total tip depth {expected_depth}"
        )

    def test_operation_feature_kind_mismatch_raises(self):
        """An operation kind that cannot machine its feature kind must raise CompileError."""
        from silta.domain import (
            EntryStrategy,
            Feature,
            FeatureKind,
            Operation,
            OperationKind,
            PartSpec,
            ProcessPlan,
            Setup,
            Units,
        )

        # Create a spec with a pocket
        spec = PartSpec(
            spec_id="mismatch-test",
            revision=1,
            units=Units.MM,
            material="aluminium",
            stock_x_mm=100.0,
            stock_y_mm=100.0,
            stock_z_mm=20.0,
            features=(
                Feature(
                    feature_id="p1",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=20.0,
                    x_max_mm=40.0,
                    y_min_mm=20.0,
                    y_max_mm=40.0,
                    corner_radius_mm=3.0,
                    depth_mm=10.0,
                ),
            ),
        )

        # Create a plan that tries to DRILL a pocket (mismatch)
        bad_plan = ProcessPlan(
            plan_id="bad-kind",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            setups=(Setup(setup_id="s1", description="Test"),),
            operations=(
                Operation(
                    operation_id="op1",
                    setup_id="s1",
                    feature_id="p1",
                    tool_id="DR6",
                    kind=OperationKind.DRILL,  # wrong for pocket
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=250.0,
                    spindle_rpm=3200.0,
                    peck_depth_mm=4.0,
                ),
            ),
            clearance_mm=15.0,
        )

        with pytest.raises(CompileError, match="cannot machine"):
            compile_plan(spec, DEMO_SHOP, bad_plan)
