"""Test specification contracts and domain models."""

import math

import pytest
from pydantic import ValidationError

from silta.domain import (
    DrillTipConvention,
    Feature,
    FeatureKind,
    PartSpec,
    Units,
    to_mm,
)


class TestUnitsConversion:
    """Test the to_mm conversion boundary."""

    def test_mm_passthrough(self):
        assert to_mm(100.0, Units.MM) == 100.0

    def test_inch_conversion(self):
        assert to_mm(1.0, Units.INCH) == 25.4

    def test_unknown_units_rejected(self):
        with pytest.raises(ValueError, match="Unknown units must be clarified"):
            to_mm(10.0, Units.UNKNOWN)

    def test_nonfinite_rejected(self):
        with pytest.raises(ValueError, match="Non-finite dimension"):
            to_mm(float("inf"), Units.MM)

        with pytest.raises(ValueError, match="Non-finite dimension"):
            to_mm(float("nan"), Units.MM)


class TestPartSpecValidation:
    """Test that PartSpec correctly validates geometry constraints."""

    def test_known_drawing_dimensions_roundtrip(self):
        """A valid spec preserves its dimensions exactly."""
        from silta.fixtures import DEMO_SPEC

        assert DEMO_SPEC.stock_x_mm == 80.0
        assert DEMO_SPEC.stock_y_mm == 60.0
        assert DEMO_SPEC.stock_z_mm == 20.0
        assert len(DEMO_SPEC.features) == 5
        pocket = DEMO_SPEC.features[0]
        assert pocket.x_max_mm - pocket.x_min_mm == 40.0
        assert pocket.depth_mm == 12.0

    def test_missing_units_proposal_cannot_be_confirmed(self):
        """A proposal with UNKNOWN units cannot become a confirmed spec."""
        with pytest.raises(ValidationError, match="unknown units"):
            PartSpec(
                spec_id="test",
                revision=1,
                units=Units.UNKNOWN,
                material="aluminium",
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

    def test_feature_outside_stock_rejected(self):
        """A feature entirely or partially outside the stock must fail."""
        with pytest.raises(ValidationError, match="lies outside the stock"):
            PartSpec(
                spec_id="test",
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
                        x_min_mm=90.0,
                        x_max_mm=110.0,  # exceeds stock
                        y_min_mm=10.0,
                        y_max_mm=20.0,
                        corner_radius_mm=1.0,
                        depth_mm=5.0,
                    ),
                ),
            )

    def test_duplicate_feature_ids_rejected(self):
        """Duplicate feature IDs must be rejected."""
        with pytest.raises(ValidationError, match="Duplicate feature IDs"):
            PartSpec(
                spec_id="test",
                revision=1,
                units=Units.MM,
                material="aluminium",
                stock_x_mm=100.0,
                stock_y_mm=100.0,
                stock_z_mm=20.0,
                features=(
                    Feature(
                        feature_id="dup",
                        kind=FeatureKind.POCKET_RECT_ROUNDED,
                        x_min_mm=10.0,
                        x_max_mm=20.0,
                        y_min_mm=10.0,
                        y_max_mm=20.0,
                        corner_radius_mm=1.0,
                        depth_mm=5.0,
                    ),
                    Feature(
                        feature_id="dup",  # duplicate
                        kind=FeatureKind.POCKET_RECT_ROUNDED,
                        x_min_mm=30.0,
                        x_max_mm=40.0,
                        y_min_mm=10.0,
                        y_max_mm=20.0,
                        corner_radius_mm=1.0,
                        depth_mm=5.0,
                    ),
                ),
            )

    def test_through_breaking_depth_rejected(self):
        """A feature deeper than stock thickness must be rejected."""
        with pytest.raises(ValidationError, match="breaks through the stock bottom"):
            PartSpec(
                spec_id="test",
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
                        x_min_mm=10.0,
                        x_max_mm=20.0,
                        y_min_mm=10.0,
                        y_max_mm=20.0,
                        corner_radius_mm=1.0,
                        depth_mm=25.0,  # exceeds 20mm stock
                    ),
                ),
            )

    def test_nonfinite_dimension_rejected(self):
        """NaN or inf dimensions must be rejected by the field validator."""
        with pytest.raises(ValidationError):
            Feature(
                feature_id="p1",
                kind=FeatureKind.POCKET_RECT_ROUNDED,
                x_min_mm=10.0,
                x_max_mm=float("nan"),  # NaN
                y_min_mm=10.0,
                y_max_mm=20.0,
                corner_radius_mm=1.0,
                depth_mm=5.0,
            )

        with pytest.raises(ValidationError):
            Feature(
                feature_id="h1",
                kind=FeatureKind.HOLE_BLIND,
                center_x_mm=50.0,
                center_y_mm=50.0,
                diameter_mm=float("inf"),  # inf
                depth_mm=10.0,
                drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                drill_point_angle_deg=118.0,
            )

    def test_drill_tip_convention_depth_computation(self):
        """Test the drill tip depth conventions are computed correctly."""
        hole_cyl = Feature(
            feature_id="h1",
            kind=FeatureKind.HOLE_BLIND,
            center_x_mm=50.0,
            center_y_mm=50.0,
            diameter_mm=6.0,
            depth_mm=10.0,
            drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
            drill_point_angle_deg=118.0,
        )

        tip_extra = (6.0 / 2) / math.tan(math.radians(118.0 / 2))
        assert math.isclose(hole_cyl.tip_extra_mm, tip_extra, rel_tol=1e-6)
        assert math.isclose(hole_cyl.cylindrical_depth_mm, 10.0, rel_tol=1e-9)
        assert math.isclose(hole_cyl.total_tip_depth_mm, 10.0 + tip_extra, rel_tol=1e-6)

        hole_total = Feature(
            feature_id="h2",
            kind=FeatureKind.HOLE_BLIND,
            center_x_mm=50.0,
            center_y_mm=50.0,
            diameter_mm=6.0,
            depth_mm=10.0,
            drill_tip=DrillTipConvention.TOTAL_TIP_DEPTH,
            drill_point_angle_deg=118.0,
        )

        assert math.isclose(hole_total.total_tip_depth_mm, 10.0, rel_tol=1e-9)
        assert math.isclose(hole_total.cylindrical_depth_mm, 10.0 - tip_extra, rel_tol=1e-6)
