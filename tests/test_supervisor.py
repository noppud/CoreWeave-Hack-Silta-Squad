"""Test supervisor decision logic."""

import pytest

from silta.domain import CandidateMetrics, OptimizationObjective, VerificationEvidence
from silta.supervisor import supervise


@pytest.mark.asyncio
async def test_supervisor_with_no_provider_returns_finish():
    """When provider is None, supervisor returns deterministic finish."""
    incumbent = CandidateMetrics(
        candidate_id="c1",
        attempt_id="a1",
        spec_design_hash="hash1",
        shop_hash="shop1",
        trajectory_hash="traj1",
        simulator_version="sim-1",
        check_set_version="checks-1",
        verified=True,
        verification_evidence=VerificationEvidence(
            check_set_hash="check-hash",
            check_results_hash="results-hash",
            simulation_hash="sim-hash",
            trajectory_hash="traj-hash",
        ),
        estimated_motion_seconds=100.0,
        estimated_total_machining_seconds=220.0,
        tool_changes=2,
        setups=1,
        wall_time_s=10.0,
        simulation_calls=1,
    )

    decision = await supervise(
        attempts=[("a1", incumbent)],
        incumbent=incumbent,
        objective=OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS,
        budget_remaining={
            "model_calls": 5,
            "optimization_attempts": 1,
            "time_remaining_s": 60.0,
        },
        provider=None,
    )

    assert decision.action.value == "finish"
    assert decision.stop_reason is not None


@pytest.mark.asyncio
async def test_supervisor_with_no_incumbent_returns_finish():
    """When there is no incumbent, supervisor cannot optimize."""
    decision = await supervise(
        attempts=[],
        incumbent=None,
        objective=OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS,
        budget_remaining={
            "model_calls": 5,
            "optimization_attempts": 1,
            "time_remaining_s": 60.0,
        },
        provider=None,
    )

    assert decision.action.value == "finish"
    assert decision.stop_reason.value == "no_improvement"


@pytest.mark.asyncio
async def test_supervisor_with_zero_model_calls_returns_budget_limit():
    """When model call budget is exhausted, supervisor finishes."""
    incumbent = CandidateMetrics(
        candidate_id="c1",
        attempt_id="a1",
        spec_design_hash="hash1",
        shop_hash="shop1",
        trajectory_hash="traj1",
        simulator_version="sim-1",
        check_set_version="checks-1",
        verified=True,
        verification_evidence=None,
        estimated_motion_seconds=100.0,
        estimated_total_machining_seconds=220.0,
        tool_changes=2,
        setups=1,
        wall_time_s=10.0,
        simulation_calls=1,
    )

    decision = await supervise(
        attempts=[("a1", incumbent)],
        incumbent=incumbent,
        objective=OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS,
        budget_remaining={
            "model_calls": 0,  # exhausted
            "optimization_attempts": 1,
            "time_remaining_s": 60.0,
        },
        provider=None,
    )

    assert decision.action.value == "finish"
    assert decision.stop_reason.value == "budget_limit"


@pytest.mark.asyncio
async def test_supervisor_with_zero_optimization_attempts_returns_limit():
    """When optimization attempts exhausted, supervisor finishes."""
    incumbent = CandidateMetrics(
        candidate_id="c1",
        attempt_id="a1",
        spec_design_hash="hash1",
        shop_hash="shop1",
        trajectory_hash="traj1",
        simulator_version="sim-1",
        check_set_version="checks-1",
        verified=True,
        verification_evidence=None,
        estimated_motion_seconds=100.0,
        estimated_total_machining_seconds=220.0,
        tool_changes=2,
        setups=1,
        wall_time_s=10.0,
        simulation_calls=1,
    )

    decision = await supervise(
        attempts=[("a1", incumbent)],
        incumbent=incumbent,
        objective=OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS,
        budget_remaining={
            "model_calls": 5,
            "optimization_attempts": 0,  # exhausted
            "time_remaining_s": 60.0,
        },
        provider=None,
    )

    assert decision.action.value == "finish"
    assert decision.stop_reason.value == "optimization_limit"
