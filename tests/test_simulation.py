"""Test collision detection and stock removal simulation."""

import math

import pytest

from silta.domain import Feature, FeatureKind, FixtureSolid, MotionKind, Segment, Trajectory
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, reach_repaired_plan, valid_plan
from silta.simulation import sampling_error_bound_mm, simulate
from silta.toolpaths import compile_plan


class TestCollisionDetection:
    """Test that collisions are detected correctly."""

    def test_known_intersecting_path_collides(self):
        """A path that collides with a fixture must be caught.

        The reach_repaired_plan has clearance=5.0mm but fixtures go up to 12.0mm,
        so traverses at Z=5.0 will collide.
        """
        plan = reach_repaired_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)
        result, _ = simulate(DEMO_SPEC, DEMO_SHOP, plan, trajectory)

        assert len(result.collisions) > 0, "reach_repaired_plan must collide with fixtures"
        assert result.status.value == "collision"

    def test_known_clear_path_does_not_collide(self):
        """A path with sufficient clearance must not collide."""
        plan = valid_plan()  # clearance=15.0mm, above fixtures
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)
        result, _ = simulate(DEMO_SPEC, DEMO_SHOP, plan, trajectory)

        if result.status.value == "collision":
            # If it collided, report details for debugging
            pytest.fail(f"valid_plan should not collide, but got: {result.collisions}")

    def test_tunneling_between_samples_caught(self):
        """A collision strictly BETWEEN sampled endpoints must still be detected.

        Construct a segment that passes over a clamp mid-way with both endpoints clear in XY.
        The clamp is at x: 34-46, y: -6-6 (front) or 54-66 (back), z: 0-12.
        Create a traverse from (30, 30, 5) to (50, 30, 5) that passes through the front clamp's
        XY projection at around (40, 30). Both endpoints are clear but the middle is not.
        """
        from silta.domain import PartSpec, ProcessPlan, Setup, ShopProfile, Units

        # Create a minimal shop with just one fixture
        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=200.0,
            envelope_y_mm=200.0,
            envelope_z_mm=200.0,
            max_feed_mm_min=4000.0,
            max_spindle_rpm=12000.0,
            tools=DEMO_SHOP.tools,
            fixtures=(
                FixtureSolid(
                    fixture_id="obstacle",
                    x_min_mm=38.0,
                    x_max_mm=42.0,
                    y_min_mm=28.0,
                    y_max_mm=32.0,
                    z_min_mm=0.0,
                    z_max_mm=12.0,
                ),
            ),
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=20.0,
        )

        # Create a spec
        spec = PartSpec(
            spec_id="tunnel-test",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=100.0,
            stock_y_mm=100.0,
            stock_z_mm=20.0,
            features=(
                Feature(
                    feature_id="p1",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=10.0,
                    x_max_mm=20.0,
                    y_min_mm=10.0,
                    y_max_mm=20.0,
                    corner_radius_mm=1.0,
                    depth_mm=5.0,
                ),
            ),
        )

        from silta.domain import EntryStrategy, Operation, OperationKind

        plan = ProcessPlan(
            plan_id="tunnel",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Test"),),
            operations=(
                Operation(
                    operation_id="op1",
                    setup_id="s1",
                    feature_id="p1",
                    tool_id=shop.tools[0].tool_id,
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=20.0,
        )

        # Create a single segment that passes through the obstacle
        # Start at (30, 30, 5), end at (50, 30, 5)
        # The obstacle is at x: 38-42, y: 28-32, z: 0-12
        # The segment at Z=5 is below the top of the obstacle (12mm)
        # Both endpoints are clear, but the middle is not
        tool = shop.tools[0]
        trajectory = Trajectory(
            trajectory_id="tunnel-test",
            plan_id=plan.plan_id,
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            compiler_version="test",
            initial_x_mm=30.0,
            initial_y_mm=30.0,
            initial_z_mm=5.0,
            segments=(
                Segment(
                    segment_id="s0001",
                    operation_id=None,
                    tool_id=tool.tool_id,
                    kind=MotionKind.RAPID,
                    start_x_mm=30.0,
                    start_y_mm=30.0,
                    start_z_mm=5.0,
                    end_x_mm=50.0,
                    end_y_mm=30.0,
                    end_z_mm=5.0,
                    feed_mm_min=shop.rapid_feed_mm_min,
                    cutting=False,
                    duration_s=0.15,
                ),
            ),
            max_step_mm=0.25,
        )

        result, _ = simulate(spec, shop, plan, trajectory, stop_on_first_collision=True)

        # The tunnel collision must be caught
        assert len(result.collisions) > 0, "Tunneling collision between samples must be detected"
        collision = result.collisions[0]
        # collision.x_mm is the tool AXIS at first contact, not the contact point. A
        # 6 mm cutter touches the obstacle while its axis is still one radius clear, so
        # first contact is expected just outside the box, and strictly between the two
        # segment endpoints (30 and 50) — which is what "tunnelling" means here.
        radius = DEMO_SHOP.tool("EM6-L").diameter_mm / 2
        assert 38.0 - radius - 0.5 <= collision.x_mm <= 42.0 + radius + 0.5, (
            f"Collision X {collision.x_mm} should be within one tool radius of the obstacle"
        )
        assert 30.0 < collision.x_mm < 50.0, (
            "The collision must be found strictly between the sampled endpoints"
        )

    def test_sampling_error_bound_is_claimed_bound(self):
        """The sampling_error_bound_mm function must return the bound it claims.

        For a segment of length L sampled at max_step_mm intervals, the worst-case
        gap between consecutive swept-disc samples is the bound returned by the function.
        """
        max_step = 0.5
        radius = 3.0

        bound = sampling_error_bound_mm(max_step, radius)

        # The bound formula is: radius - sqrt(radius^2 - (max_step/2)^2)
        # For max_step=0.5, radius=3.0:
        half = max_step / 2
        expected = radius - math.sqrt(radius**2 - half**2) if half < radius else radius

        assert math.isclose(bound, expected, rel_tol=1e-9), (
            f"sampling_error_bound_mm returned {bound}, expected {expected}"
        )


class TestStockRemoval:
    """Test stock removal and coverage metrics."""

    def test_valid_plan_produces_zero_residual_and_gouge(self):
        """Simulating valid_plan() must result in residual=0 and gouge=0 within threshold."""
        plan = valid_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)
        result, _ = simulate(DEMO_SPEC, DEMO_SHOP, plan, trajectory, stop_on_first_collision=False)

        # Check that simulation passed
        assert result.status.value == "pass", f"valid_plan simulation failed: {result.status}"
        assert result.max_residual_mm <= result.residual_threshold_mm, (
            f"Residual {result.max_residual_mm} exceeds threshold {result.residual_threshold_mm}"
        )
        assert result.max_gouge_mm <= result.gouge_threshold_mm, (
            f"Gouge {result.max_gouge_mm} exceeds threshold {result.gouge_threshold_mm}"
        )

    def test_valid_plan_all_features_fully_removed(self):
        """Every feature must report removed_fraction=1.0 for valid_plan()."""
        plan = valid_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)
        result, _ = simulate(DEMO_SPEC, DEMO_SHOP, plan, trajectory, stop_on_first_collision=False)

        for cov in result.coverage:
            assert cov.removed_fraction >= 0.999, (
                f"Feature {cov.feature_id} removed_fraction {cov.removed_fraction} < 0.999"
            )

    def test_reduced_pocket_depth_leaves_measurable_residual(self):
        """A plan with incomplete coverage must leave residual material.

        Use a tool with large stepover that doesn't fully cover the pocket area.
        """
        from silta.domain import Feature, FeatureKind, PartSpec, ProcessPlan, Units

        # Create a simple pocket
        spec = PartSpec(
            spec_id="residual-test",
            revision=1,
            units=Units.MM,
            material="aluminium",
            stock_x_mm=80.0,
            stock_y_mm=60.0,
            stock_z_mm=20.0,
            features=(
                Feature(
                    feature_id="pocket_1",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=20.0,
                    x_max_mm=60.0,
                    y_min_mm=20.0,
                    y_max_mm=40.0,
                    corner_radius_mm=3.0,
                    depth_mm=10.0,
                ),
            ),
        )

        # Create a plan with HUGE stepover that won't cover the full pocket
        from silta.domain import EntryStrategy, Operation, OperationKind, Setup

        incomplete_plan = ProcessPlan(
            plan_id="incomplete-plan",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            setups=(Setup(setup_id="setup_1", description="Test"),),
            operations=(
                Operation(
                    operation_id="op_pocket_1",
                    setup_id="setup_1",
                    feature_id="pocket_1",
                    tool_id="EM6-L",
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=15.0,  # HUGE stepover leaves gaps
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=15.0,
        )

        trajectory = compile_plan(spec, DEMO_SHOP, incomplete_plan)
        result, _ = simulate(
            spec, DEMO_SHOP, incomplete_plan, trajectory, stop_on_first_collision=False
        )

        # Should have residual because stepover is too large
        assert result.max_residual_mm > 1.0, (
            f"Incomplete plan should leave residual, but got {result.max_residual_mm}"
        )

    def test_hole_depth_reflects_drill_cone(self):
        """The achieved hole depth grid cell is slightly shallower than analytic axis depth
        because no cell centre sits exactly on the axis. Assert that relationship holds.
        """
        plan = valid_plan()
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)
        result, _ = simulate(DEMO_SPEC, DEMO_SHOP, plan, trajectory, stop_on_first_collision=False)

        # Find a hole coverage
        hole = next(f for f in DEMO_SPEC.features if f.kind.value == "hole_blind")
        hole_cov = next(c for c in result.coverage if c.feature_id == hole.feature_id)

        # The analytic target depth
        analytic_depth = hole.total_tip_depth_mm

        # The achieved depth should be close but slightly shallower due to grid sampling
        # (no cell center exactly on the drill axis)
        assert hole_cov.achieved_depth_mm < analytic_depth + 0.1, (
            f"Achieved depth {hole_cov.achieved_depth_mm} should not exceed "
            f"analytic {analytic_depth}"
        )
        assert hole_cov.achieved_depth_mm > analytic_depth - result.grid_mm * 2, (
            f"Achieved depth {hole_cov.achieved_depth_mm} too shallow vs analytic {analytic_depth}"
        )
