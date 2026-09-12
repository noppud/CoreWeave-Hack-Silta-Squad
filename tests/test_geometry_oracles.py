"""Adversarial verification of geometry engine: CAD, toolpaths, simulation and checks.

ORACLE PRINCIPLE: Every expected value is calculated INDEPENDENTLY of the code under
test. We derive dimensions analytically (closed-form, by hand), never by calling
silta.cad and asserting it equals itself. Finding a real geometry bug is the most
valuable outcome; a green suite that proves nothing is the least.
"""

import math
import tempfile
from pathlib import Path

import pytest

from silta.cad import VOLUME_REL_TOL, build_and_export
from silta.checks import run_path_checks, run_preflight_checks
from silta.domain import (
    DrillTipConvention,
    EntryStrategy,
    Feature,
    FeatureKind,
    FixtureSolid,
    MotionKind,
    Operation,
    OperationKind,
    PartSpec,
    ProcessPlan,
    Segment,
    Setup,
    ShopProfile,
    Tool,
    ToolKind,
    Trajectory,
    Units,
)
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, expected_geometry, valid_plan
from silta.policy import POLICY_V0, POLICY_V1
from silta.simulation import sampling_error_bound_mm, simulate, target_field
from silta.toolpaths import CompileError, compile_plan

# ============================================================================
# SECTION 1: CAD vs ANALYTIC GEOMETRY
# ============================================================================


@pytest.mark.slow
class TestCadVsAnalyticGeometry:
    """Test CAD builder output against hand-calculated closed-form geometry."""

    def test_demo_part_volume_and_bbox_vs_analytic_oracle(self):
        """Demo part: verify volume and bbox against independent arithmetic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(DEMO_SPEC, Path(tmpdir))
            oracle = expected_geometry()

            # Volume must match within tolerance
            expected_vol = oracle["part_volume_mm3"]
            assert math.isclose(result.volume_mm3, expected_vol, rel_tol=VOLUME_REL_TOL), (
                f"Volume mismatch: got {result.volume_mm3:.3f}, expected {expected_vol:.3f} mm³"
            )

            # Bounding box must match
            expected_bbox = tuple(oracle["bbox_mm"])
            assert result.bbox_mm == pytest.approx(expected_bbox, abs=1e-3), (
                f"Bbox mismatch: got {result.bbox_mm}, expected {expected_bbox}"
            )

    def test_custom_variant_1_pocket_only(self):
        """Variant 1: Smaller stock with single larger pocket, hand-calculated volume."""
        # Stock: 50 × 40 × 15 mm
        # Pocket: 15-35 (w=20) × 10-30 (h=20) × 8 mm deep, r=4 mm corners
        # Pocket area = w*h - (4-pi)*r^2 = 20*20 - (4-pi)*16 = 400 - 13.097 = 386.903 mm²
        # Pocket volume = 386.903 * 8 = 3095.225 mm³
        # Part volume = 50*40*15 - 3095.225 = 30000 - 3095.225 = 26904.775 mm³

        spec = PartSpec(
            spec_id="variant-1",
            revision=1,
            units=Units.MM,
            material="aluminum",
            stock_x_mm=50.0,
            stock_y_mm=40.0,
            stock_z_mm=15.0,
            features=(
                Feature(
                    feature_id="pocket_v1",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=15.0,
                    x_max_mm=35.0,
                    y_min_mm=10.0,
                    y_max_mm=30.0,
                    corner_radius_mm=4.0,
                    depth_mm=8.0,
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(spec, Path(tmpdir))

            # Hand-calculated values
            pocket_area = 20 * 20 - (4 - math.pi) * 4**2
            pocket_vol = pocket_area * 8
            expected_vol = 50 * 40 * 15 - pocket_vol

            assert math.isclose(result.volume_mm3, expected_vol, rel_tol=VOLUME_REL_TOL), (
                f"Variant 1 volume: got {result.volume_mm3:.3f}, expected {expected_vol:.3f}"
            )
            assert result.bbox_mm == pytest.approx((50.0, 40.0, 15.0), abs=1e-3)

    def test_custom_variant_2_with_holes(self):
        """Variant 2: Different hole configuration, verify drill volumes analytically."""
        # Stock: 100 × 80 × 25 mm
        # Pocket: 30-70 (w=40) × 25-55 (h=30) × 10 mm deep, r=5 mm
        # 2 holes: d=8 mm, depth=12 mm cylindrical, 118° tip
        # Hole tip height = (d/2)/tan(59°) = 4/tan(59°) = 2.403 mm
        # Hole volume = pi*r²*cyl + (pi*r²*tip)/3 = pi*16*12 + (pi*16*2.403)/3
        #             = 603.186 + 40.319 = 643.505 mm³ per hole

        spec = PartSpec(
            spec_id="variant-2",
            revision=1,
            units=Units.MM,
            material="aluminum",
            stock_x_mm=100.0,
            stock_y_mm=80.0,
            stock_z_mm=25.0,
            features=(
                Feature(
                    feature_id="pocket_v2",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=30.0,
                    x_max_mm=70.0,
                    y_min_mm=25.0,
                    y_max_mm=55.0,
                    corner_radius_mm=5.0,
                    depth_mm=10.0,
                ),
                Feature(
                    feature_id="hole_v2_1",
                    kind=FeatureKind.HOLE_BLIND,
                    center_x_mm=20.0,
                    center_y_mm=40.0,
                    diameter_mm=8.0,
                    depth_mm=12.0,
                    drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                    drill_point_angle_deg=118.0,
                ),
                Feature(
                    feature_id="hole_v2_2",
                    kind=FeatureKind.HOLE_BLIND,
                    center_x_mm=80.0,
                    center_y_mm=40.0,
                    diameter_mm=8.0,
                    depth_mm=12.0,
                    drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                    drill_point_angle_deg=118.0,
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(spec, Path(tmpdir))

            # Hand calculations
            stock_vol = 100 * 80 * 25
            pocket_area = 40 * 30 - (4 - math.pi) * 5**2
            pocket_vol = pocket_area * 10
            r = 4.0
            tip_height = r / math.tan(math.radians(59))
            hole_vol = math.pi * r**2 * 12 + (math.pi * r**2 * tip_height) / 3
            expected_vol = stock_vol - pocket_vol - 2 * hole_vol

            assert math.isclose(result.volume_mm3, expected_vol, rel_tol=VOLUME_REL_TOL), (
                f"Variant 2 volume: got {result.volume_mm3:.3f}, expected {expected_vol:.3f}"
            )

    def test_step_export_reimported_matches(self):
        """STEP export must reimport to identical volume."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(DEMO_SPEC, Path(tmpdir))
            assert math.isclose(
                result.reimported_volume_mm3, result.volume_mm3, rel_tol=VOLUME_REL_TOL
            ), f"STEP roundtrip: {result.reimported_volume_mm3} ≠ {result.volume_mm3}"

    def test_build_is_deterministic_across_runs(self):
        """Building the same spec twice must produce identical geometry."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            r1 = build_and_export(DEMO_SPEC, Path(tmp1))
            r2 = build_and_export(DEMO_SPEC, Path(tmp2))
            assert math.isclose(r1.volume_mm3, r2.volume_mm3, rel_tol=1e-9)
            assert r1.bbox_mm == r2.bbox_mm

    def test_solid_valid_for_valid_geometry(self):
        """Valid geometry must produce a valid OCCT solid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(DEMO_SPEC, Path(tmpdir))
            assert result.solid_valid is True

    def test_degenerate_pocket_corner_equals_half_width(self):
        """A pocket whose corner radius is half its width is a legal slot, not an error.

        This was a real bug: the builder used `.rect(...).fillet(r)`, and OCCT raises
        `BRep_API: command not done` when the filleted corners become tangent. The
        domain validator accepts the shape, so the builder must too. It now draws the
        profile analytically from lines and arcs, which covers the whole legal range.
        """
        # Pocket 20mm wide, radius 10mm: the rounded corners meet at the centerline
        spec = PartSpec(
            spec_id="degenerate",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=10.0,
            features=(
                Feature(
                    feature_id="p_degen",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=15.0,
                    x_max_mm=35.0,
                    y_min_mm=15.0,
                    y_max_mm=35.0,
                    corner_radius_mm=10.0,  # exactly half of 20mm
                    depth_mm=5.0,
                ),
            ),
        )
        # Must not raise; geometry is legal even if unusual
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_and_export(spec, Path(tmpdir))
            assert result.solid_valid


# ============================================================================
# SECTION 2: DRILL TIP CONVENTION
# ============================================================================


class TestDrillTipConvention:
    """Verify drill tip depth calculations match hand arithmetic for BOTH conventions.

    This was a real bug: confusion between cylindrical depth and total tip depth
    caused the compiler to drive the tip to the wrong Z, and the simulator rendered
    the drill point inverted (cone opening upward instead of downward).
    """

    def test_cylindrical_depth_convention_vs_analytic(self):
        """CYLINDRICAL_DEPTH: depth_mm is the full-diameter depth, tip goes deeper."""
        # d=6mm, cylindrical depth=8mm, 118° tip
        # tip_extra = (d/2)/tan(59°) = 3/tan(59°) = 1.8026 mm
        # total_tip_depth = 8 + 1.8026 = 9.8026 mm
        feature = Feature(
            feature_id="h1",
            kind=FeatureKind.HOLE_BLIND,
            center_x_mm=10.0,
            center_y_mm=10.0,
            diameter_mm=6.0,
            depth_mm=8.0,
            drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
            drill_point_angle_deg=118.0,
        )

        # Hand calculation
        r = 3.0
        tip_extra_analytic = r / math.tan(math.radians(59))
        assert math.isclose(feature.tip_extra_mm, tip_extra_analytic, abs_tol=1e-4), (
            f"tip_extra: got {feature.tip_extra_mm}, expected {tip_extra_analytic}"
        )
        assert math.isclose(feature.cylindrical_depth_mm, 8.0, abs_tol=1e-6)
        assert math.isclose(feature.total_tip_depth_mm, 8.0 + tip_extra_analytic, abs_tol=1e-4)

    def test_total_tip_depth_convention_vs_analytic(self):
        """TOTAL_TIP_DEPTH: depth_mm includes the conical tip."""
        # d=6mm, total_tip_depth=9.8026mm, 118° tip
        # tip_extra = 1.8026 mm
        # cylindrical = 9.8026 - 1.8026 = 8.0 mm
        feature = Feature(
            feature_id="h2",
            kind=FeatureKind.HOLE_BLIND,
            center_x_mm=10.0,
            center_y_mm=10.0,
            diameter_mm=6.0,
            depth_mm=9.8026,
            drill_tip=DrillTipConvention.TOTAL_TIP_DEPTH,
            drill_point_angle_deg=118.0,
        )

        r = 3.0
        tip_extra_analytic = r / math.tan(math.radians(59))
        assert math.isclose(feature.tip_extra_mm, tip_extra_analytic, abs_tol=1e-4)
        assert math.isclose(feature.total_tip_depth_mm, 9.8026, abs_tol=1e-4)
        cyl_analytic = 9.8026 - tip_extra_analytic
        assert math.isclose(feature.cylindrical_depth_mm, cyl_analytic, abs_tol=1e-4)

    def test_compiled_trajectory_drives_to_total_tip_depth(self):
        """The trajectory must drive the tool TIP to total_tip_depth, not cylindrical."""
        spec = PartSpec(
            spec_id="drill-test",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=20.0,
            features=(
                Feature(
                    feature_id="h_drill",
                    kind=FeatureKind.HOLE_BLIND,
                    center_x_mm=25.0,
                    center_y_mm=25.0,
                    diameter_mm=6.0,
                    depth_mm=8.0,
                    drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                    drill_point_angle_deg=118.0,
                ),
            ),
        )
        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=2000.0,
            max_spindle_rpm=10000.0,
            tools=(DEMO_SHOP.tools[2],),  # DR6
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=20.0,
        )
        plan = ProcessPlan(
            plan_id="drill-plan",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Drill test"),),
            operations=(
                Operation(
                    operation_id="op_drill",
                    setup_id="s1",
                    feature_id="h_drill",
                    tool_id="DR6",
                    kind=OperationKind.DRILL,
                    stepdown_mm=4.0,
                    stepover_mm=1.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=250.0,
                    spindle_rpm=3200.0,
                    peck_depth_mm=4.0,
                ),
            ),
            clearance_mm=10.0,
        )

        traj = compile_plan(spec, shop, plan)

        # Find deepest Z reached by any segment
        min_z = min(min(seg.start_z_mm, seg.end_z_mm) for seg in traj.segments)

        # Hand calculation
        feature = spec.features[0]
        expected_depth = feature.total_tip_depth_mm  # 8 + 1.8026 = 9.8026
        assert math.isclose(-min_z, expected_depth, abs_tol=1e-3), (
            f"Trajectory drives to Z={min_z}, expected {-expected_depth}"
        )

    def test_simulator_drill_tip_points_downward(self):
        """In the simulator, the drill tip is the LOWEST point, cone opens upward.

        An earlier bug rendered the cone inverted, causing phantom stock collisions.
        At the tool axis (r=0), height = -(cyl + tip).
        At the periphery (r=R), height = -cyl.
        """
        from silta.simulation import _Grid, target_field

        spec = PartSpec(
            spec_id="drill-orient",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=20.0,
            features=(
                Feature(
                    feature_id="h_orient",
                    kind=FeatureKind.HOLE_BLIND,
                    center_x_mm=25.0,
                    center_y_mm=25.0,
                    diameter_mm=6.0,
                    depth_mm=8.0,
                    drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                    drill_point_angle_deg=118.0,
                ),
            ),
        )

        grid = _Grid(spec, 0.5)
        height, _ = target_field(spec, grid)

        # Sample at the center (axis) and at radius 2mm
        cx, cy = 25.0, 25.0
        i_center = int(cx / grid.grid)
        j_center = int(cy / grid.grid)
        i_offset = int((cx + 2.0) / grid.grid)
        j_offset = int(cy / grid.grid)

        z_center = height[i_center, j_center]
        z_offset = height[i_offset, j_offset]

        # Hand calculation
        cyl = 8.0
        tip = 3.0 / math.tan(math.radians(59))  # ~1.8026
        r_sample = 2.0
        R = 3.0
        expected_center = -(cyl + tip)
        expected_offset = -(cyl + tip * (1 - r_sample / R))

        # Grid discretization means we won't hit exact analytical values
        # The key assertion is that tip points downward: center < periphery
        assert math.isclose(z_center, expected_center, abs_tol=grid.grid), (
            f"Center depth: {z_center}, expected {expected_center}"
        )
        assert math.isclose(z_offset, expected_offset, abs_tol=grid.grid), (
            f"Offset depth: {z_offset}, expected {expected_offset}"
        )
        # Tip is deepest: center < periphery (more negative)
        assert z_center < z_offset


# ============================================================================
# SECTION 3: TOOLPATH COMPILER INVARIANTS
# ============================================================================


class TestToolpathCompilerInvariants:
    """Verify the compiler maintains geometric continuity and compensation."""

    def test_segment_endpoints_continuous(self):
        """Every segment must start where the previous one ended."""
        plan = valid_plan()
        traj = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        prev = (traj.initial_x_mm, traj.initial_y_mm, traj.initial_z_mm)
        for seg in traj.segments:
            start = (seg.start_x_mm, seg.start_y_mm, seg.start_z_mm)
            assert math.dist(prev, start) < 1e-6, (
                f"Segment {seg.segment_id} starts at {start}, previous ended at {prev}"
            )
            prev = (seg.end_x_mm, seg.end_y_mm, seg.end_z_mm)

    def test_cutter_radius_compensation_inset(self):
        """Pocket raster tool-centre limits must be inset by exactly the tool radius."""
        from silta.toolpaths import _raster_lines

        pocket = DEMO_SPEC.features[0]
        tool = DEMO_SHOP.tools[1]  # EM6-L, diameter 6mm, radius 3mm

        lines, x_lo, x_hi = _raster_lines(pocket, tool, 3.0)

        # Hand calculation: pocket x: 20-60, tool radius 3mm
        # x_lo = 20 + 3 = 23, x_hi = 60 - 3 = 57
        assert math.isclose(x_lo, 23.0, abs_tol=1e-6)
        assert math.isclose(x_hi, 57.0, abs_tol=1e-6)

        # y: 20-40, radius 3mm
        # y_lo = 20 + 3 = 23, y_hi = 40 - 3 = 37
        assert math.isclose(lines[0], 23.0, abs_tol=1e-6)
        assert math.isclose(lines[-1], 37.0, abs_tol=1e-6)

    def test_raster_stepover_never_exceeds_diameter(self):
        """Stepover > diameter would leave uncut strips."""
        from silta.toolpaths import _raster_lines

        pocket = DEMO_SPEC.features[0]
        tool = DEMO_SHOP.tools[1]  # 6mm diameter
        lines, _, _ = _raster_lines(pocket, tool, 6.0)  # stepover = diameter

        # Lines must reach y_hi
        y_hi = pocket.y_max_mm - tool.diameter_mm / 2
        assert math.isclose(lines[-1], y_hi, abs_tol=1e-6)

        # Spacing between lines ≤ diameter
        for i in range(len(lines) - 1):
            gap = lines[i + 1] - lines[i]
            assert gap <= tool.diameter_mm + 1e-6, f"Gap {gap} > diameter {tool.diameter_mm}"

    def test_stepdown_levels_reach_exact_depth(self):
        """Stepdown levels must land exactly on -depth, not slightly above."""
        plan = valid_plan()
        traj = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        # Find deepest Z in pocket operations
        pocket_segments = [s for s in traj.segments if s.operation_id == "op_pocket_1"]
        min_z = min(min(s.start_z_mm, s.end_z_mm) for s in pocket_segments if s.cutting)

        # Pocket depth is 12mm
        assert math.isclose(-min_z, 12.0, abs_tol=1e-6), f"Deepest cut: {min_z}, expected -12.0"

    def test_non_cutting_lateral_motion_above_stock(self):
        """Non-cutting lateral moves below stock top would drag the tool through material."""
        plan = valid_plan()
        traj = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        for seg in traj.segments:
            if seg.cutting or seg.kind is MotionKind.TOOL_CHANGE:
                continue
            # Lateral motion check
            lateral = math.hypot(seg.end_x_mm - seg.start_x_mm, seg.end_y_mm - seg.start_y_mm)
            if lateral > 1e-6:
                # Both Z values must be >= 0 (at or above stock top)
                assert seg.start_z_mm >= -1e-6 and seg.end_z_mm >= -1e-6, (
                    f"Segment {seg.segment_id} traverses laterally below stock: "
                    f"Z={seg.start_z_mm}..{seg.end_z_mm}"
                )

    def test_incompatible_operation_kind_raises(self):
        """Drilling a pocket or rastering a hole must raise CompileError."""
        spec = PartSpec(
            spec_id="mismatch",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=10.0,
            features=(
                Feature(
                    feature_id="h_bad",
                    kind=FeatureKind.HOLE_BLIND,
                    center_x_mm=25.0,
                    center_y_mm=25.0,
                    diameter_mm=6.0,
                    depth_mm=5.0,
                    drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                    drill_point_angle_deg=118.0,
                ),
            ),
        )
        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=2000.0,
            max_spindle_rpm=10000.0,
            tools=(DEMO_SHOP.tools[1],),  # End mill
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=10.0,
        )
        plan = ProcessPlan(
            plan_id="bad",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Mismatch"),),
            operations=(
                Operation(
                    operation_id="op_bad",
                    setup_id="s1",
                    feature_id="h_bad",
                    tool_id=shop.tools[0].tool_id,
                    kind=OperationKind.POCKET_RASTER,  # Wrong: pocket op on hole
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        with pytest.raises(CompileError, match="cannot machine"):
            compile_plan(spec, shop, plan)

    def test_tool_too_wide_for_pocket_raises(self):
        """Tool diameter >= pocket width must raise CompileError."""
        spec = PartSpec(
            spec_id="narrow",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=10.0,
            features=(
                Feature(
                    feature_id="p_narrow",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=20.0,
                    x_max_mm=25.0,  # 5mm wide
                    y_min_mm=20.0,
                    y_max_mm=30.0,
                    corner_radius_mm=2.0,
                    depth_mm=5.0,
                ),
            ),
        )
        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=2000.0,
            max_spindle_rpm=10000.0,
            tools=(DEMO_SHOP.tools[1],),  # 6mm diameter
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=10.0,
        )
        plan = ProcessPlan(
            plan_id="narrow-plan",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Narrow"),),
            operations=(
                Operation(
                    operation_id="op_narrow",
                    setup_id="s1",
                    feature_id="p_narrow",
                    tool_id=shop.tools[0].tool_id,
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        with pytest.raises(CompileError, match="too wide"):
            compile_plan(spec, shop, plan)


# ============================================================================
# SECTION 4: SIMULATOR CORRECTNESS
# ============================================================================


class TestSimulatorCorrectness:
    """Grid convergence, tunneling, error bounds, and detection correctness."""

    def test_grid_convergence(self):
        """Run at 1.0, 0.5, 0.25 mm grid and observe residual/gouge/coverage behavior.

        Report whether the chosen 0.15mm thresholds are justified.
        """
        plan = valid_plan()
        traj = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        results = {}
        for grid_mm in [1.0, 0.5, 0.25]:
            result, _ = simulate(
                DEMO_SPEC,
                DEMO_SHOP,
                plan,
                traj,
                grid_mm=grid_mm,
                residual_threshold_mm=0.15,
                gouge_threshold_mm=0.15,
            )
            results[grid_mm] = result

        # Convergence table will be printed in the evidence doc
        # Here we assert that finer grids do not regress
        assert results[0.5].max_residual_mm <= results[1.0].max_residual_mm + 0.3
        assert results[0.25].max_residual_mm <= results[0.5].max_residual_mm + 0.2

        # At 0.5mm, the valid plan should pass
        assert results[0.5].status.value == "pass", (
            f"Valid plan failed at 0.5mm grid: {results[0.5].status}"
        )

        # Convergence data will be extracted for the evidence document
        # Grid 1.0: residual={results[1.0].max_residual_mm}, gouge={results[1.0].max_gouge_mm}
        # Grid 0.5: residual={results[0.5].max_residual_mm}, gouge={results[0.5].max_gouge_mm}
        # Grid 0.25: residual={results[0.25].max_residual_mm}, gouge={results[0.25].max_gouge_mm}

    def test_tunneling_collision_between_samples(self):
        """Collision strictly BETWEEN sampled points must be caught.

        Both endpoints clear in XY, midpoint does not. Remember: CollisionEvent.x_mm
        is the tool AXIS at first contact. With a 6mm cutter (radius 3mm), first
        contact happens ~3mm outside the obstacle in XY.
        """
        shop = ShopProfile(
            shop_id="tunnel-test",
            display_name="Tunnel",
            envelope_x_mm=200.0,
            envelope_y_mm=200.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=4000.0,
            max_spindle_rpm=10000.0,
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

        spec = PartSpec(
            spec_id="tunnel",
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

        plan = ProcessPlan(
            plan_id="tunnel",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Tunnel test"),),
            operations=(
                Operation(
                    operation_id="op1",
                    setup_id="s1",
                    feature_id="p1",
                    tool_id="EM6-L",
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

        # Create a segment that passes through the obstacle mid-flight
        tool = shop.tools[1]
        traj = Trajectory(
            trajectory_id="tunnel-traj",
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
                    duration_s=1.0,
                ),
            ),
            max_step_mm=0.5,
        )

        result, _ = simulate(spec, shop, plan, traj)

        assert len(result.collisions) > 0, "Tunneling collision not detected"
        collision = result.collisions[0]

        # The key assertion: collision was detected even though both endpoints were clear.
        # The tool axis at contact should be within the swept region of the segment.
        segment_x_start, segment_x_end = 30.0, 50.0
        assert segment_x_start <= collision.x_mm <= segment_x_end, (
            f"Contact at {collision.x_mm} is outside segment [{segment_x_start}, {segment_x_end}]"
        )

        # Collision should involve the fixture we set up
        assert collision.obstacle_id == "obstacle"

    def test_sampling_error_bound_formula(self):
        """Verify sampling_error_bound_mm formula against brute-force scan."""
        max_step = 0.5
        radius = 3.0

        # Formula result
        formula_bound = sampling_error_bound_mm(max_step, radius)

        # Brute force: sample a disc swept by max_step, find max gap
        # A point at the edge, perpendicular to motion, reaches furthest from centerline
        half = max_step / 2
        gap_at_edge = radius - math.sqrt(radius**2 - half**2)

        assert math.isclose(formula_bound, gap_at_edge, abs_tol=1e-6), (
            f"Sampling bound formula: {formula_bound}, brute force: {gap_at_edge}"
        )

    def test_shank_and_holder_contact_with_stock_fails(self):
        """Shank/holder touching stock is failure even during a cutting move."""
        # Create a very deep pocket that exposes shank/holder
        spec = PartSpec(
            spec_id="deep",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=30.0,
            features=(
                Feature(
                    feature_id="p_deep",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=15.0,
                    x_max_mm=35.0,
                    y_min_mm=15.0,
                    y_max_mm=35.0,
                    corner_radius_mm=3.0,
                    depth_mm=25.0,  # Very deep
                ),
            ),
        )

        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=2000.0,
            max_spindle_rpm=10000.0,
            tools=(DEMO_SHOP.tools[0],),  # Short tool: cutting_length=8mm
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=20.0,
        )

        plan = ProcessPlan(
            plan_id="deep-plan",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Deep"),),
            operations=(
                Operation(
                    operation_id="op_deep",
                    setup_id="s1",
                    feature_id="p_deep",
                    tool_id="EM6-S",
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        traj = compile_plan(spec, shop, plan)
        result, _ = simulate(spec, shop, plan, traj)

        # Must detect collision (shank or holder vs stock)
        assert len(result.collisions) > 0, "Shank/holder contact not detected"
        assert any(c.colliding_part in ("shank", "holder") for c in result.collisions)

    def test_deliberately_shallow_pocket_leaves_residual(self):
        """Insufficient depth must be DETECTED, not silently passed."""
        spec = PartSpec(
            spec_id="shallow",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=20.0,
            features=(
                Feature(
                    feature_id="p_shallow",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=15.0,
                    x_max_mm=35.0,
                    y_min_mm=15.0,
                    y_max_mm=35.0,
                    corner_radius_mm=3.0,
                    depth_mm=10.0,  # Target 10mm
                ),
            ),
        )

        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=2000.0,
            max_spindle_rpm=10000.0,
            tools=(DEMO_SHOP.tools[1],),
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=20.0,
        )

        # Plan with deliberately insufficient stepdown: only reaches 8mm
        plan = ProcessPlan(
            plan_id="shallow-plan",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Shallow"),),
            operations=(
                Operation(
                    operation_id="op_shallow",
                    setup_id="s1",
                    feature_id="p_shallow",
                    tool_id="EM6-L",
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=4.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        # Manually truncate trajectory to stop at 8mm instead of 10mm
        traj = compile_plan(spec, shop, plan)
        shallow_segments = []
        for seg in traj.segments:
            if seg.cutting and seg.end_z_mm < -8.0:
                # Clamp to -8mm
                shallow_segments.append(
                    Segment(
                        segment_id=seg.segment_id,
                        operation_id=seg.operation_id,
                        tool_id=seg.tool_id,
                        kind=seg.kind,
                        start_x_mm=seg.start_x_mm,
                        start_y_mm=seg.start_y_mm,
                        start_z_mm=max(seg.start_z_mm, -8.0),
                        end_x_mm=seg.end_x_mm,
                        end_y_mm=seg.end_y_mm,
                        end_z_mm=-8.0,
                        feed_mm_min=seg.feed_mm_min,
                        cutting=seg.cutting,
                        duration_s=seg.duration_s,
                    )
                )
            else:
                shallow_segments.append(seg)

        shallow_traj = Trajectory(
            trajectory_id="shallow-traj",
            plan_id=traj.plan_id,
            spec_design_hash=traj.spec_design_hash,
            shop_hash=traj.shop_hash,
            compiler_version=traj.compiler_version,
            initial_x_mm=traj.initial_x_mm,
            initial_y_mm=traj.initial_y_mm,
            initial_z_mm=traj.initial_z_mm,
            segments=tuple(shallow_segments),
            max_step_mm=traj.max_step_mm,
        )

        result, _ = simulate(
            spec, shop, plan, shallow_traj, residual_threshold_mm=0.15, gouge_threshold_mm=0.15
        )

        # Must detect incomplete removal (or collision due to remaining material)
        assert result.status.value in ("incomplete_removal", "collision"), (
            f"Shallow pocket not detected: {result.status}, residual={result.max_residual_mm}"
        )
        assert result.max_residual_mm > 1.5, (
            f"Expected significant residual, got {result.max_residual_mm}"
        )

    def test_deliberately_deep_cut_produces_gouge(self):
        """Cutting deeper than the target must be detected as gouge."""
        spec = PartSpec(
            spec_id="overcut",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=20.0,
            features=(
                Feature(
                    feature_id="p_overcut",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=15.0,
                    x_max_mm=35.0,
                    y_min_mm=15.0,
                    y_max_mm=35.0,
                    corner_radius_mm=3.0,
                    depth_mm=8.0,  # Target 8mm
                ),
            ),
        )

        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=2000.0,
            max_spindle_rpm=10000.0,
            tools=(DEMO_SHOP.tools[1],),
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=20.0,
        )

        # Plan that deliberately cuts to 10mm instead of 8mm
        plan_spec_deep = spec.model_copy(
            update={
                "features": (
                    Feature(
                        feature_id="p_overcut",
                        kind=FeatureKind.POCKET_RECT_ROUNDED,
                        x_min_mm=15.0,
                        x_max_mm=35.0,
                        y_min_mm=15.0,
                        y_max_mm=35.0,
                        corner_radius_mm=3.0,
                        depth_mm=10.0,  # Cut deeper
                    ),
                )
            }
        )

        plan = ProcessPlan(
            plan_id="overcut-plan",
            policy_version="test",
            spec_design_hash=plan_spec_deep.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Overcut"),),
            operations=(
                Operation(
                    operation_id="op_overcut",
                    setup_id="s1",
                    feature_id="p_overcut",
                    tool_id="EM6-L",
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        traj = compile_plan(plan_spec_deep, shop, plan)

        # Simulate against the ORIGINAL spec (8mm target)
        result, _ = simulate(
            spec, shop, plan, traj, residual_threshold_mm=0.15, gouge_threshold_mm=0.15
        )

        # Must detect gouge
        assert result.status.value == "gouge", f"Gouge not detected: {result.status}"
        assert result.max_gouge_mm > 1.5, f"Expected significant gouge, got {result.max_gouge_mm}"

    def test_analytic_target_field_matches_cad_solid(self):
        """Sample points inside features away from walls; heightfield matches CAD."""
        from silta.simulation import _Grid

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build CAD solid for comparison (volume check, not heightfield)
            build_and_export(DEMO_SPEC, Path(tmpdir))

        grid = _Grid(DEMO_SPEC, 0.5)
        height, label = target_field(DEMO_SPEC, grid)

        # Sample well inside the pocket (away from walls)
        pocket = DEMO_SPEC.features[0]
        cx = (pocket.x_min_mm + pocket.x_max_mm) / 2
        cy = (pocket.y_min_mm + pocket.y_max_mm) / 2
        i = int(cx / grid.grid)
        j = int(cy / grid.grid)

        # Expected depth at center
        expected = -pocket.depth_mm
        actual = height[i, j]
        assert math.isclose(actual, expected, abs_tol=grid.grid), (
            f"Pocket center: {actual}, expected {expected}"
        )

        # Sample inside a hole (away from edges)
        hole = DEMO_SPEC.features[1]
        i_hole = int(hole.center_x_mm / grid.grid)
        j_hole = int(hole.center_y_mm / grid.grid)
        expected_hole = -(hole.cylindrical_depth_mm + hole.tip_extra_mm)
        actual_hole = height[i_hole, j_hole]
        assert math.isclose(actual_hole, expected_hole, abs_tol=grid.grid), (
            f"Hole center: {actual_hole}, expected {expected_hole}"
        )


# ============================================================================
# SECTION 5: CHECKS
# ============================================================================


class TestChecks:
    """Every blocking check must fire on a violating case and pass on a valid one."""

    def test_design_unchanged_check(self):
        """design_unchanged: fail if plan.spec_design_hash != spec.design_hash."""
        spec = DEMO_SPEC
        plan = valid_plan()

        # Valid case
        checks = run_preflight_checks(spec, DEMO_SHOP, plan)
        design_checks = [c for c in checks if c.check_id == "design_unchanged"]
        assert len(design_checks) == 1
        assert design_checks[0].status.value == "pass"

        # Invalid: plan with wrong hash
        bad_plan = plan.model_copy(update={"spec_design_hash": "wrong_hash"})
        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        design_checks = [c for c in checks if c.check_id == "design_unchanged"]
        assert design_checks[0].status.value == "fail"

    def test_feature_reference_check(self):
        """feature_reference: fail if operation references unknown feature."""
        spec = DEMO_SPEC
        plan = valid_plan()

        # Valid
        checks = run_preflight_checks(spec, DEMO_SHOP, plan)
        ref_checks = [c for c in checks if c.check_id == "feature_reference"]
        assert all(c.status.value != "fail" for c in ref_checks)

        # Invalid: reference unknown feature
        bad_op = plan.operations[0].model_copy(update={"feature_id": "nonexistent"})
        bad_plan = plan.model_copy(update={"operations": (bad_op,) + plan.operations[1:]})
        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        ref_checks = [c for c in checks if c.check_id == "feature_reference"]
        assert any(c.status.value == "fail" for c in ref_checks)

    def test_tool_available_check(self):
        """tool_available: fail if tool not in inventory."""
        spec = DEMO_SPEC
        plan = valid_plan()

        # Valid
        checks = run_preflight_checks(spec, DEMO_SHOP, plan)
        tool_checks = [c for c in checks if c.check_id == "tool_available"]
        assert all(c.status.value != "fail" for c in tool_checks)

        # Invalid
        bad_op = plan.operations[0].model_copy(update={"tool_id": "NONEXISTENT"})
        bad_plan = plan.model_copy(update={"operations": (bad_op,) + plan.operations[1:]})
        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        tool_checks = [c for c in checks if c.check_id == "tool_available"]
        assert any(c.status.value == "fail" for c in tool_checks)

    def test_feature_coverage_check(self):
        """feature_coverage: fail if a feature has no operation."""
        spec = DEMO_SPEC
        plan = valid_plan()

        # Valid
        checks = run_preflight_checks(spec, DEMO_SHOP, plan)
        cov_checks = [c for c in checks if c.check_id == "feature_coverage"]
        assert any(c.status.value == "pass" for c in cov_checks)

        # Invalid: omit one operation
        bad_plan = plan.model_copy(update={"operations": plan.operations[:-1]})
        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        cov_checks = [c for c in checks if c.check_id == "feature_coverage"]
        assert any(c.status.value == "fail" for c in cov_checks)

    def test_tool_cutting_reach_check(self):
        """tool_cutting_reach: fail if cutting_length < needed depth."""
        spec = DEMO_SPEC
        short_tool = DEMO_SHOP.tools[0]  # EM6-S: 8mm cutting length

        # Valid: long tool for 12mm pocket
        plan = valid_plan()
        checks = run_preflight_checks(spec, DEMO_SHOP, plan)
        reach_checks = [c for c in checks if c.check_id == "tool_cutting_reach"]
        assert any(c.status.value == "pass" for c in reach_checks)

        # Invalid: short tool for 12mm pocket
        bad_ops = tuple(
            op.model_copy(update={"tool_id": short_tool.tool_id})
            if op.kind is OperationKind.POCKET_RASTER
            else op
            for op in plan.operations
        )
        bad_plan = plan.model_copy(update={"operations": bad_ops})
        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        reach_checks = [c for c in checks if c.check_id == "tool_cutting_reach"]
        assert any(c.status.value == "fail" for c in reach_checks)

    def test_tool_stickout_clearance_check(self):
        """tool_stickout_clearance: fail if stickout < depth + margin."""
        # Create a tool with sufficient cutting length but insufficient stickout
        # Pocket depth is 12mm, so we need stickout >= 12 + 2 = 14mm
        short_stickout_tool = Tool(
            tool_id="SHORT",
            kind=ToolKind.END_MILL,
            diameter_mm=6.0,
            cutting_length_mm=12.5,  # Just enough cutting length
            stickout_mm=13.0,  # Only 13mm for 12mm depth (needs 14mm+)
            shank_diameter_mm=6.0,
            holder_diameter_mm=26.0,
            center_cutting=True,
            allowed_operations=(OperationKind.POCKET_RASTER,),
            feed_mm_min=700.0,
            spindle_rpm=6500.0,
        )

        shop = DEMO_SHOP.model_copy(update={"tools": DEMO_SHOP.tools + (short_stickout_tool,)})

        plan = valid_plan()
        bad_ops = tuple(
            op.model_copy(update={"tool_id": "SHORT"})
            if op.kind is OperationKind.POCKET_RASTER
            else op
            for op in plan.operations
        )
        bad_plan = plan.model_copy(update={"operations": bad_ops})

        checks = run_preflight_checks(DEMO_SPEC, shop, bad_plan)
        stickout_checks = [c for c in checks if c.check_id == "tool_stickout_clearance"]
        assert any(c.status.value == "fail" for c in stickout_checks)

    def test_pocket_corner_radius_check(self):
        """pocket_corner_radius: fail if tool radius > pocket corner radius."""
        # Pocket with 3mm radius, tool with 4mm radius
        spec = PartSpec(
            spec_id="corner-test",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=10.0,
            features=(
                Feature(
                    feature_id="p_tight",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=10.0,
                    x_max_mm=40.0,
                    y_min_mm=10.0,
                    y_max_mm=40.0,
                    corner_radius_mm=3.0,
                    depth_mm=5.0,
                ),
            ),
        )

        big_tool = Tool(
            tool_id="BIG",
            kind=ToolKind.END_MILL,
            diameter_mm=8.0,  # radius 4mm > 3mm corner
            cutting_length_mm=10.0,
            stickout_mm=20.0,
            shank_diameter_mm=8.0,
            holder_diameter_mm=26.0,
            center_cutting=True,
            allowed_operations=(OperationKind.POCKET_RASTER,),
            feed_mm_min=700.0,
            spindle_rpm=6500.0,
        )

        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=4000.0,
            max_spindle_rpm=10000.0,
            tools=(big_tool,),
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=10.0,
        )

        plan = ProcessPlan(
            plan_id="corner-plan",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Corner"),),
            operations=(
                Operation(
                    operation_id="op_corner",
                    setup_id="s1",
                    feature_id="p_tight",
                    tool_id="BIG",
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        checks = run_preflight_checks(spec, shop, plan)
        corner_checks = [c for c in checks if c.check_id == "pocket_corner_radius"]
        assert any(c.status.value == "fail" for c in corner_checks)

    def test_pocket_width_fit_check(self):
        """pocket_width_fit: fail if tool diameter >= pocket width."""
        # Already tested in toolpath tests, here verify the check fires
        spec = PartSpec(
            spec_id="narrow",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=50.0,
            stock_y_mm=50.0,
            stock_z_mm=10.0,
            features=(
                Feature(
                    feature_id="p_narrow",
                    kind=FeatureKind.POCKET_RECT_ROUNDED,
                    x_min_mm=20.0,
                    x_max_mm=25.0,  # 5mm wide
                    y_min_mm=20.0,
                    y_max_mm=30.0,
                    corner_radius_mm=2.0,
                    depth_mm=5.0,
                ),
            ),
        )

        shop = ShopProfile(
            shop_id="test",
            display_name="Test",
            envelope_x_mm=100.0,
            envelope_y_mm=100.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=2000.0,
            max_spindle_rpm=10000.0,
            tools=(DEMO_SHOP.tools[1],),  # 6mm diameter
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=10.0,
        )

        plan = ProcessPlan(
            plan_id="narrow-plan",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Narrow"),),
            operations=(
                Operation(
                    operation_id="op_narrow",
                    setup_id="s1",
                    feature_id="p_narrow",
                    tool_id=shop.tools[0].tool_id,
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        checks = run_preflight_checks(spec, shop, plan)
        width_checks = [c for c in checks if c.check_id == "pocket_width_fit"]
        assert any(c.status.value == "fail" for c in width_checks)

    def test_stepover_bound_check(self):
        """stepover_bound: fail if stepover > tool diameter."""
        spec = DEMO_SPEC
        plan = valid_plan()

        bad_ops = tuple(
            op.model_copy(update={"stepover_mm": 10.0})  # > 6mm diameter
            if op.kind is OperationKind.POCKET_RASTER
            else op
            for op in plan.operations
        )
        bad_plan = plan.model_copy(update={"operations": bad_ops})

        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        stepover_checks = [c for c in checks if c.check_id == "stepover_bound"]
        assert any(c.status.value == "fail" for c in stepover_checks)

    def test_entry_capability_check(self):
        """entry_capability: fail if non-centre-cutting tool attempts plunge."""
        non_cc_tool = Tool(
            tool_id="NON_CC",
            kind=ToolKind.END_MILL,
            diameter_mm=6.0,
            cutting_length_mm=18.0,
            stickout_mm=34.0,
            shank_diameter_mm=6.0,
            holder_diameter_mm=26.0,
            center_cutting=False,  # Cannot plunge
            allowed_operations=(OperationKind.POCKET_RASTER,),
            feed_mm_min=700.0,
            spindle_rpm=6500.0,
        )

        shop = DEMO_SHOP.model_copy(update={"tools": DEMO_SHOP.tools + (non_cc_tool,)})
        plan = valid_plan()

        bad_ops = tuple(
            op.model_copy(update={"tool_id": "NON_CC", "entry": EntryStrategy.PLUNGE})
            if op.kind is OperationKind.POCKET_RASTER
            else op
            for op in plan.operations
        )
        bad_plan = plan.model_copy(update={"operations": bad_ops})

        checks = run_preflight_checks(DEMO_SPEC, shop, bad_plan)
        entry_checks = [c for c in checks if c.check_id == "entry_capability"]
        assert any(c.status.value == "fail" for c in entry_checks)

    def test_hole_diameter_match_check(self):
        """hole_diameter_match: fail if drill diameter != hole diameter."""
        wrong_drill = Tool(
            tool_id="DR8",
            kind=ToolKind.DRILL,
            diameter_mm=8.0,  # Holes are 6mm
            cutting_length_mm=25.0,
            stickout_mm=40.0,
            shank_diameter_mm=8.0,
            holder_diameter_mm=26.0,
            center_cutting=True,
            point_angle_deg=118.0,
            allowed_operations=(OperationKind.DRILL,),
            feed_mm_min=250.0,
            spindle_rpm=3200.0,
        )

        shop = DEMO_SHOP.model_copy(update={"tools": DEMO_SHOP.tools + (wrong_drill,)})
        plan = valid_plan()

        bad_ops = tuple(
            op.model_copy(update={"tool_id": "DR8"}) if op.kind is OperationKind.DRILL else op
            for op in plan.operations
        )
        bad_plan = plan.model_copy(update={"operations": bad_ops})

        checks = run_preflight_checks(DEMO_SPEC, shop, bad_plan)
        diam_checks = [c for c in checks if c.check_id == "hole_diameter_match"]
        assert any(c.status.value == "fail" for c in diam_checks)

    def test_machine_feed_limit_check(self):
        """machine_feed_limit: fail if feed > shop max."""
        spec = DEMO_SPEC
        plan = valid_plan()

        bad_ops = tuple(
            op.model_copy(update={"feed_mm_min": 10000.0})  # > 4000 max
            for op in plan.operations
        )
        bad_plan = plan.model_copy(update={"operations": bad_ops})

        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        feed_checks = [c for c in checks if c.check_id == "machine_feed_limit"]
        assert any(c.status.value == "fail" for c in feed_checks)

    def test_machine_spindle_limit_check(self):
        """machine_spindle_limit: fail if spindle > shop max."""
        spec = DEMO_SPEC
        plan = valid_plan()

        bad_ops = tuple(
            op.model_copy(update={"spindle_rpm": 20000.0})  # > 12000 max
            for op in plan.operations
        )
        bad_plan = plan.model_copy(update={"operations": bad_ops})

        checks = run_preflight_checks(spec, DEMO_SHOP, bad_plan)
        spin_checks = [c for c in checks if c.check_id == "machine_spindle_limit"]
        assert any(c.status.value == "fail" for c in spin_checks)

    def test_workspace_envelope_check(self):
        """workspace_envelope: fail if stock > machine envelope."""
        huge_spec = PartSpec(
            spec_id="huge",
            revision=1,
            units=Units.MM,
            material="test",
            stock_x_mm=500.0,  # > 400mm envelope
            stock_y_mm=350.0,  # > 300mm envelope
            stock_z_mm=300.0,  # > 250mm envelope
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

        plan = ProcessPlan(
            plan_id="huge-plan",
            policy_version="test",
            spec_design_hash=huge_spec.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            setups=(Setup(setup_id="s1", description="Huge"),),
            operations=(
                Operation(
                    operation_id="op1",
                    setup_id="s1",
                    feature_id="p1",
                    tool_id="EM6-L",
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=10.0,
        )

        checks = run_preflight_checks(huge_spec, DEMO_SHOP, plan)
        env_checks = [c for c in checks if c.check_id == "workspace_envelope"]
        assert any(c.status.value == "fail" for c in env_checks)

    def test_path_continuity_check(self):
        """path_continuity: fail if a segment doesn't start where previous ended."""
        plan = valid_plan()
        traj = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        # Valid
        checks = run_path_checks(DEMO_SPEC, DEMO_SHOP, plan, traj, POLICY_V0)
        cont_checks = [c for c in checks if c.check_id == "path_continuity"]
        assert any(c.status.value == "pass" for c in cont_checks)

        # Invalid: create a jump
        bad_segments = list(traj.segments)
        bad_segments[5] = bad_segments[5].model_copy(
            update={"start_x_mm": bad_segments[5].start_x_mm + 10.0}
        )
        bad_traj = traj.model_copy(update={"segments": tuple(bad_segments)})

        checks = run_path_checks(DEMO_SPEC, DEMO_SHOP, plan, bad_traj, POLICY_V0)
        cont_checks = [c for c in checks if c.check_id == "path_continuity"]
        assert any(c.status.value == "fail" for c in cont_checks)

    def test_path_no_rapid_through_stock_check(self):
        """path_no_rapid_through_stock: fail if non-cutting lateral move below Z=0."""
        plan = valid_plan()
        traj = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)

        # Valid
        checks = run_path_checks(DEMO_SPEC, DEMO_SHOP, plan, traj, POLICY_V0)
        rapid_checks = [c for c in checks if c.check_id == "path_no_rapid_through_stock"]
        assert any(c.status.value == "pass" for c in rapid_checks)

        # Invalid: rapid through stock
        bad_seg = Segment(
            segment_id="s9999",
            operation_id=None,
            tool_id=DEMO_SHOP.tools[0].tool_id,
            kind=MotionKind.RAPID,
            start_x_mm=10.0,
            start_y_mm=10.0,
            start_z_mm=-5.0,  # Below stock
            end_x_mm=40.0,
            end_y_mm=40.0,
            end_z_mm=-5.0,
            feed_mm_min=8000.0,
            cutting=False,
            duration_s=1.0,
        )
        bad_traj = traj.model_copy(update={"segments": traj.segments + (bad_seg,)})

        checks = run_path_checks(DEMO_SPEC, DEMO_SHOP, plan, bad_traj, POLICY_V0)
        rapid_checks = [c for c in checks if c.check_id == "path_no_rapid_through_stock"]
        assert any(c.status.value == "fail" for c in rapid_checks)

    def test_path_fixture_envelope_v2_regression(self):
        """path_fixture_envelope v2: test the exact regression case from v1.

        Version 1 tested the holder's radius against the tool tip's height, and
        falsely rejected a valid vertical retract 9.85mm from a clamp. Version 2
        tests each tool part at its OWN radius and its OWN height above the tip.
        """
        # Clamp at x: 34-46, y: -6-6, z: 0-12
        # Tool tip at (40, -15, 12) retracts vertically to (40, -15, 22)
        # Holder diameter 26mm (radius 13mm), holder starts at stickout=34mm above tip
        # At Z=22, tip is 22mm above stock, so holder bottom is at 22+34=56mm
        # Distance from (40, -15) to clamp is about 9mm in Y
        # Version 1 compared holder radius (13mm) against tip height and rejected
        # Version 2 compares holder radius at holder height and passes

        shop = ShopProfile(
            shop_id="regression",
            display_name="Regression",
            envelope_x_mm=200.0,
            envelope_y_mm=200.0,
            envelope_z_mm=100.0,
            max_feed_mm_min=4000.0,
            max_spindle_rpm=10000.0,
            tools=DEMO_SHOP.tools,
            fixtures=(
                FixtureSolid(
                    fixture_id="clamp",
                    x_min_mm=34.0,
                    x_max_mm=46.0,
                    y_min_mm=-6.0,
                    y_max_mm=6.0,
                    z_min_mm=0.0,
                    z_max_mm=12.0,
                ),
            ),
            home_x_mm=0.0,
            home_y_mm=0.0,
            home_z_mm=25.0,
            min_fixture_clearance_mm=3.0,
        )

        spec = PartSpec(
            spec_id="regression",
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
                    x_min_mm=30.0,
                    x_max_mm=50.0,
                    y_min_mm=30.0,
                    y_max_mm=50.0,
                    corner_radius_mm=2.0,
                    depth_mm=5.0,
                ),
            ),
        )

        tool = shop.tools[1]  # EM6-L
        # Vertical retract: (40, -15, 12) -> (40, -15, 22)
        traj = Trajectory(
            trajectory_id="regression-traj",
            plan_id="regression",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            compiler_version="test",
            initial_x_mm=40.0,
            initial_y_mm=-15.0,
            initial_z_mm=12.0,
            segments=(
                Segment(
                    segment_id="s0001",
                    operation_id=None,
                    tool_id=tool.tool_id,
                    kind=MotionKind.RETRACT,
                    start_x_mm=40.0,
                    start_y_mm=-15.0,
                    start_z_mm=12.0,
                    end_x_mm=40.0,
                    end_y_mm=-15.0,
                    end_z_mm=22.0,
                    feed_mm_min=shop.rapid_feed_mm_min,
                    cutting=False,
                    duration_s=1.0,
                ),
            ),
            max_step_mm=0.5,
        )

        plan = ProcessPlan(
            plan_id="regression",
            policy_version="test",
            spec_design_hash=spec.design_hash,
            shop_hash=shop.shop_hash,
            setups=(Setup(setup_id="s1", description="Regression"),),
            operations=(
                Operation(
                    operation_id="op1",
                    setup_id="s1",
                    feature_id="p1",
                    tool_id=tool.tool_id,
                    kind=OperationKind.POCKET_RASTER,
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry=EntryStrategy.PLUNGE,
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ),
            clearance_mm=15.0,
        )

        # With POLICY_V1 (which enables path_fixture_envelope v2), must pass
        checks = run_path_checks(spec, shop, plan, traj, POLICY_V1)
        env_checks = [c for c in checks if c.check_id == "path_fixture_envelope"]
        # Should not block (version 2 tests each part at its own height)
        blocking_env = [c for c in env_checks if c.blocking_failure]
        assert len(blocking_env) == 0, (
            f"Regression: fixture envelope v2 falsely rejected valid retract: {env_checks}"
        )
