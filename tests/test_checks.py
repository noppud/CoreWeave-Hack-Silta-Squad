"""Test preflight and path checking deterministic validators."""

from silta.checks import run_preflight_checks
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan


class TestPreflightChecks:
    """Test recipe validation before compilation."""

    def test_tool_not_in_inventory_fails(self):
        """A plan naming a tool absent from the inventory must fail tool_available."""
        from silta.domain import EntryStrategy, Operation, OperationKind, ProcessPlan, Setup

        bad_plan = ProcessPlan(
            plan_id="bad-tool-plan",
            policy_version="test",
            spec_design_hash=DEMO_SPEC.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            setups=(Setup(setup_id="s1", description="Test"),),
            operations=(
                Operation(
                    operation_id="op1",
                    setup_id="s1",
                    feature_id="pocket_1",
                    tool_id="NONEXISTENT",  # invalid
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

        results = run_preflight_checks(DEMO_SPEC, DEMO_SHOP, bad_plan)
        failures = [r for r in results if r.check_id == "tool_available" and r.blocking_failure]

        assert len(failures) > 0, "tool_available check must fail for unknown tool"
        assert failures[0].actual == "NONEXISTENT"

    def test_design_hash_mismatch_fails(self):
        """A plan whose spec_design_hash differs from confirmed spec must fail design_unchanged."""
        plan = naive_plan()

        # Tamper with the design hash
        from silta.domain import ProcessPlan

        tampered = ProcessPlan(**{**plan.model_dump(), "spec_design_hash": "wrong_hash"})

        results = run_preflight_checks(DEMO_SPEC, DEMO_SHOP, tampered)
        failures = [r for r in results if r.check_id == "design_unchanged" and r.blocking_failure]

        assert len(failures) > 0, "design_unchanged check must fail for mismatched hash"
        assert failures[0].required == DEMO_SPEC.design_hash[:12]

    def test_naive_plan_reach_failure(self):
        """The naive plan with the short tool must fail tool_cutting_reach.

        The short tool EM6-S has cutting_length_mm=8.0, but pocket_1 needs 12.0mm depth.
        The check must report actual=8.0, required=12.0.
        """
        plan = naive_plan()

        # Confirm the plan uses the short tool
        pocket_op = next(o for o in plan.operations if o.feature_id == "pocket_1")
        assert pocket_op.tool_id == "EM6-S"

        results = run_preflight_checks(DEMO_SPEC, DEMO_SHOP, plan)
        reach_failures = [
            r for r in results if r.check_id == "tool_cutting_reach" and r.blocking_failure
        ]

        assert len(reach_failures) > 0, "naive_plan must fail tool_cutting_reach"
        failure = reach_failures[0]
        assert failure.feature_id == "pocket_1"
        assert failure.actual == 8.0  # short tool cutting length
        assert failure.required == 12.0  # pocket depth

    def test_valid_plan_passes_preflight(self):
        """A known-valid plan must pass all preflight checks."""
        from silta.fixtures import valid_plan

        plan = valid_plan()
        results = run_preflight_checks(DEMO_SPEC, DEMO_SHOP, plan)

        blocking = [r for r in results if r.blocking_failure]
        assert len(blocking) == 0, f"valid_plan must pass preflight, but got: {blocking}"
