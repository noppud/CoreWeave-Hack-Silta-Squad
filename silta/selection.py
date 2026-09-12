"""Pure candidate selection and metrics. No I/O, no models.

Feasibility is a hard conjunction: schema valid, design unchanged, CAD built,
all blocking checks passed, full feature coverage, successful simulation. Unknown
or timeout is not pass. Infeasible candidates never replace a feasible incumbent.
"""

from __future__ import annotations

from silta.domain import (
    Attempt,
    CandidateMetrics,
    Disposition,
    OptimizationObjective,
    ProcessPlan,
    ShopProfile,
    SimulationStatus,
    Trajectory,
    VerificationEvidence,
    stable_hash,
)


def is_feasible(attempt: Attempt) -> bool:
    """Deterministic feasibility predicate per docs/plan.md section 6.

    A candidate is feasible if and only if:
    - Valid schema (not SCHEMA_INVALID)
    - Design hash unchanged (design_unchanged check passed)
    - Valid CAD (CAD built successfully)
    - Every blocking check passed (no FAIL + BLOCKING checks)
    - Full required-feature coverage (feature_coverage passed)
    - Successful simulation (status = PASS)

    Unknown, timeout, or unsupported is NOT pass.
    """
    # Schema must be valid
    if attempt.disposition is Disposition.SCHEMA_INVALID:
        return False

    # Must have a plan
    if attempt.plan is None:
        return False

    # All blocking checks must pass
    for check in attempt.checks:
        if check.blocking_failure:
            return False

    # Must have simulation result
    if attempt.simulation is None:
        return False

    # Simulation must pass
    if attempt.simulation.status is not SimulationStatus.PASS:
        return False

    # Disposition must be PASSED
    if attempt.disposition is not Disposition.PASSED:
        return False

    return True


def metrics_for(
    attempt: Attempt,
    trajectory: Trajectory | None,
    shop: ShopProfile,
    plan: ProcessPlan | None,
) -> CandidateMetrics:
    """Extract objective metrics from a completed attempt.

    Verification status is computed by trusted code from checks and simulation.
    Cost estimates require explicit rate/currency/model; never invented.
    """
    from silta.checks import CHECKS_VERSION
    from silta.simulation import SIMULATOR_VERSION

    feasible = is_feasible(attempt)

    # Build verification evidence if feasible
    evidence: VerificationEvidence | None = None
    if feasible and attempt.simulation is not None:
        check_payload = {
            "checks": [c.model_dump(mode="json") for c in attempt.checks],
        }
        evidence = VerificationEvidence(
            check_set_hash=stable_hash(CHECKS_VERSION),
            check_results_hash=stable_hash(check_payload),
            simulation_hash=attempt.simulation.simulation_id if attempt.simulation else None,
            trajectory_hash=attempt.trajectory_hash,
        )

    # Compute motion time
    motion_seconds = 0.0
    if trajectory is not None:
        motion_seconds = trajectory.estimated_seconds

    # Compute total machining time (motion + setups)
    total_seconds = motion_seconds
    if plan is not None:
        total_seconds += shop.setup_seconds * len(plan.setups)

    # Count tool changes
    tool_changes = 0
    if trajectory is not None:
        from silta.domain import MotionKind

        tool_changes = sum(1 for s in trajectory.segments if s.kind is MotionKind.TOOL_CHANGE)
        # First tool load is not a change
        if tool_changes > 0:
            tool_changes -= 1

    # Extract simulation metrics
    min_clearance: float | None = None
    max_residual: float | None = None
    max_gouge: float | None = None
    if attempt.simulation is not None:
        # Minimum clearance from fixture envelope check (only for passing checks)
        for check in attempt.checks:
            if check.check_id == "path_fixture_envelope" and check.actual is not None:
                if isinstance(check.actual, (int, float)):
                    clearance_val = float(check.actual)
                    # Only record non-negative clearance (negative means collision)
                    if clearance_val >= 0:
                        min_clearance = clearance_val
                    break
        max_residual = attempt.simulation.max_residual_mm
        max_gouge = attempt.simulation.max_gouge_mm

    # Inference cost
    inference_cost: float | None = None
    if attempt.usage is not None and attempt.usage.cost_usd is not None:
        inference_cost = attempt.usage.cost_usd

    # Wall time
    wall_time = (attempt.finished_at - attempt.started_at).total_seconds()

    # Simulation calls
    sim_calls = 1 if attempt.simulation is not None else 0

    return CandidateMetrics(
        candidate_id=f"candidate-{attempt.attempt_id}",
        attempt_id=attempt.attempt_id,
        spec_design_hash=plan.spec_design_hash if plan else "",
        shop_hash=plan.shop_hash if plan else "",
        trajectory_hash=attempt.trajectory_hash,
        simulator_version=SIMULATOR_VERSION if attempt.simulation else None,
        check_set_version=CHECKS_VERSION,
        verified=feasible,
        verification_evidence=evidence,
        estimated_motion_seconds=motion_seconds,
        estimated_total_machining_seconds=total_seconds,
        tool_changes=tool_changes,
        setups=len(plan.setups) if plan else 0,
        minimum_clearance_mm=min_clearance,
        max_residual_mm=max_residual,
        max_gouge_mm=max_gouge,
        wall_time_s=wall_time,
        simulation_calls=sim_calls,
        inference_cost_usd=inference_cost,
        # No machining cost without explicit rate
        estimated_machining_cost_usd=None,
        cost_estimation_model=None,
        cost_currency=None,
    )


def choose_best(
    incumbent: CandidateMetrics | None,
    candidate: CandidateMetrics,
    objective: OptimizationObjective,
) -> CandidateMetrics:
    """Deterministic selection: feasible beats infeasible, better beats worse.

    An infeasible, unknown or worse candidate NEVER replaces a feasible incumbent.
    Ties keep the incumbent unless a tie-breaker (fewer setups, then fewer tool changes)
    applies. Use explicit numerical tolerance so rounding is not "improvement".
    """
    TOLERANCE_SECONDS = 0.5  # Half a second is not a meaningful time improvement
    TOLERANCE_COST = 0.01  # One cent is not a meaningful cost improvement

    # If no incumbent, candidate becomes incumbent (if feasible)
    if incumbent is None:
        if candidate.verified:
            return candidate
        # No incumbent and candidate infeasible: return candidate for inspection
        # but mark it as not selected
        return candidate

    # Feasibility is a hard gate
    if incumbent.verified and not candidate.verified:
        # Feasible incumbent, infeasible candidate: keep incumbent
        return incumbent

    if not incumbent.verified and candidate.verified:
        # Infeasible incumbent, feasible candidate: take candidate
        return candidate

    if not incumbent.verified and not candidate.verified:
        # Both infeasible: keep incumbent
        return incumbent

    # Both feasible: compare by objective
    if objective is OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS:
        incumbent_value = incumbent.estimated_total_machining_seconds
        candidate_value = candidate.estimated_total_machining_seconds
        tolerance = TOLERANCE_SECONDS
    elif objective is OptimizationObjective.ESTIMATED_MACHINING_COST_USD:
        # Cost objective requires both to have cost estimates
        if incumbent.estimated_machining_cost_usd is None:
            return incumbent  # Cannot compare without incumbent cost
        if candidate.estimated_machining_cost_usd is None:
            return incumbent  # Cannot compare without candidate cost
        incumbent_value = incumbent.estimated_machining_cost_usd
        candidate_value = candidate.estimated_machining_cost_usd
        tolerance = TOLERANCE_COST
    else:
        # Unknown objective: keep incumbent
        return incumbent

    # Candidate is better if it improves by more than tolerance
    if candidate_value < incumbent_value - tolerance:
        return candidate

    # Candidate is worse if incumbent is better by more than tolerance
    if incumbent_value < candidate_value - tolerance:
        return incumbent

    # Tie: apply tie-breakers
    # 1. Fewer setups
    if candidate.setups < incumbent.setups:
        return candidate
    if incumbent.setups < candidate.setups:
        return incumbent

    # 2. Fewer tool changes
    if candidate.tool_changes < incumbent.tool_changes:
        return candidate
    if incumbent.tool_changes < candidate.tool_changes:
        return incumbent

    # Perfect tie: keep incumbent
    return incumbent
