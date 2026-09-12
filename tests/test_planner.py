"""Test deterministic planner and model draft validation."""

import pytest

from silta.checks import blocking, run_preflight_checks
from silta.domain import CheckResult, CheckStage, CheckStatus, Severity
from silta.fixtures import DEMO_SHOP, DEMO_SPEC
from silta.planner import (
    DeterministicPlanner,
    OperationDraft,
    PlanDraft,
    PlanRequest,
    _draft_to_plan,
)
from silta.policy import POLICY_V0
from silta.simulation import simulate
from silta.toolpaths import compile_plan


class TestDeterministicPlanner:
    """Test the deterministic fallback planner."""

    def test_deterministic_planner_output_passes_preflight(self):
        """The deterministic planner must produce a plan that passes preflight checks."""
        planner = DeterministicPlanner(DEMO_SPEC, DEMO_SHOP)
        plan = planner.plan(previous=None, failures=())

        results = run_preflight_checks(DEMO_SPEC, DEMO_SHOP, plan)
        failures = blocking(results)

        assert len(failures) == 0, f"Deterministic plan should pass preflight, got: {failures}"

    def test_deterministic_planner_simulates_to_pass(self):
        """The deterministic planner's output must simulate successfully."""
        planner = DeterministicPlanner(DEMO_SPEC, DEMO_SHOP)
        plan = planner.plan(previous=None, failures=())

        # Compile and simulate
        trajectory = compile_plan(DEMO_SPEC, DEMO_SHOP, plan)
        result, _ = simulate(DEMO_SPEC, DEMO_SHOP, plan, trajectory, stop_on_first_collision=False)

        assert result.passed, f"Deterministic plan should pass simulation, got: {result.status}"

    def test_deterministic_planner_repairs_tool_reach(self):
        """Given a reach failure, the deterministic planner must swap to a longer tool."""
        from silta.fixtures import naive_plan

        planner = DeterministicPlanner(DEMO_SPEC, DEMO_SHOP)

        # Create a reach failure for pocket_1
        reach_failure = CheckResult(
            check_id="tool_cutting_reach",
            stage=CheckStage.PREFLIGHT,
            status=CheckStatus.FAIL,
            severity=Severity.BLOCKING,
            message="Reach failed",
            operation_id="op_pocket_1",
            feature_id="pocket_1",
            actual=8.0,  # short tool
            required=12.0,  # pocket depth
            units="mm",
            repair_hint="Select a longer tool",
        )

        previous = naive_plan()
        repaired = planner.plan(previous=previous, failures=(reach_failure,))

        # The repaired plan should use EM6-L instead of EM6-S
        pocket_op = next(o for o in repaired.operations if o.feature_id == "pocket_1")
        assert pocket_op.tool_id == "EM6-L", f"Expected EM6-L, got {pocket_op.tool_id}"

    def test_deterministic_planner_repairs_clearance_from_fixture_evidence(self):
        """Given a fixture clearance failure, the planner must raise clearance."""
        planner = DeterministicPlanner(DEMO_SPEC, DEMO_SHOP)

        # Create a fixture clearance failure
        clearance_failure = CheckResult(
            check_id="path_fixture_envelope",
            stage=CheckStage.PATH,
            status=CheckStatus.FAIL,
            severity=Severity.BLOCKING,
            message="Collision with fixture",
            segment_id="s0010",
            actual=-2.0,  # negative gap = collision
            required=3.0,
            units="mm",
            evidence={"fixture_id": "clamp_front", "fixture_top_mm": 12.0},
            repair_hint="Raise clearance",
        )

        from silta.fixtures import reach_repaired_plan

        previous = reach_repaired_plan()  # clearance=5.0
        repaired = planner.plan(previous=previous, failures=(clearance_failure,))

        # The repaired clearance should be above the fixture
        # fixture_top_mm=12.0 + min_clearance=3.0 = 15.0
        expected_clearance = 12.0 + DEMO_SHOP.min_fixture_clearance_mm
        assert repaired.clearance_mm >= expected_clearance, (
            f"Expected clearance >= {expected_clearance}, got {repaired.clearance_mm}"
        )


class TestModelDraftValidation:
    """Test that model drafts are validated strictly."""

    def test_model_draft_with_unknown_tool_rejected(self):
        """A draft naming an unknown tool must be rejected."""
        draft = PlanDraft(
            setups=[{"setup_id": "s1", "description": "Test"}],
            operations=[
                OperationDraft(
                    operation_id="op1",
                    feature_id="pocket_1",
                    tool_id="UNKNOWN_TOOL",  # not in inventory
                    kind="pocket_raster",
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry="plunge",
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ],
            clearance_mm=15.0,
        )

        request = PlanRequest(
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            policy=POLICY_V0,
            previous_plan=None,
            failures=(),
            attempt_index=0,
        )

        with pytest.raises(ValueError, match="unknown tool"):
            _draft_to_plan(draft, request)

    def test_model_draft_with_unknown_feature_rejected(self):
        """A draft naming an unknown feature must be rejected."""
        draft = PlanDraft(
            setups=[{"setup_id": "s1", "description": "Test"}],
            operations=[
                OperationDraft(
                    operation_id="op1",
                    feature_id="UNKNOWN_FEATURE",  # not in spec
                    tool_id="EM6-L",
                    kind="pocket_raster",
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry="plunge",
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ],
            clearance_mm=15.0,
        )

        request = PlanRequest(
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            policy=POLICY_V0,
            previous_plan=None,
            failures=(),
            attempt_index=0,
        )

        with pytest.raises(ValueError, match="unknown feature"):
            _draft_to_plan(draft, request)

    def test_model_cannot_set_spec_design_hash(self):
        """The model cannot set spec_design_hash; it is always stamped from the spec."""
        draft = PlanDraft(
            setups=[{"setup_id": "setup_1", "description": "Test"}],
            operations=[
                OperationDraft(
                    operation_id="op1",
                    feature_id="pocket_1",
                    tool_id="EM6-L",
                    kind="pocket_raster",
                    stepdown_mm=2.0,
                    stepover_mm=3.0,
                    entry="plunge",
                    feed_mm_min=700.0,
                    spindle_rpm=6500.0,
                ),
            ],
            clearance_mm=15.0,
        )

        request = PlanRequest(
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            policy=POLICY_V0,
            previous_plan=None,
            failures=(),
            attempt_index=0,
        )

        plan = _draft_to_plan(draft, request)

        # The plan's hashes must match the spec and shop, not any draft field
        assert plan.spec_design_hash == DEMO_SPEC.design_hash
        assert plan.shop_hash == DEMO_SHOP.shop_hash
