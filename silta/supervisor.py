"""Model-backed optimization supervisor with deterministic bounds enforcement.

The supervisor may propose improvements; the controller enforces all bounds.
The supervisor cannot assign correctness scores, disable checks, raise budgets,
or approve anything of its own.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from silta.domain import (
    CandidateMetrics,
    OptimizationObjective,
    SupervisorAction,
    SupervisorDecision,
    SupervisorStopReason,
)

if TYPE_CHECKING:
    from silta.providers import Provider


class SupervisorPrompt(BaseModel):
    """Structured input to the supervisor model."""

    objective: str
    incumbent: dict | None
    candidates: list[dict]
    budget_remaining: dict


class SupervisorOutput(BaseModel):
    """Structured output from the supervisor model."""

    action: str = Field(pattern=r"^(improve|finish)$")
    explanation: str = Field(min_length=10, max_length=500)
    stop_reason: str | None = None
    planning_instruction: str | None = Field(default=None, max_length=1000)
    expected_improvement: str | None = None


async def supervise(
    *,
    attempts: list[tuple[str, CandidateMetrics]],
    incumbent: CandidateMetrics | None,
    objective: OptimizationObjective,
    budget_remaining: dict,
    provider: Provider | None,
) -> SupervisorDecision:
    """Generate a supervision decision: improve or finish.

    When provider is None, returns a deterministic finish decision.
    The controller enforces all bounds; the supervisor cannot override them.
    """
    attempt_ids = tuple(aid for aid, _ in attempts)
    incumbent_id = incumbent.candidate_id if incumbent else None

    # No incumbent: must have at least one verified candidate to proceed
    if incumbent is None:
        return SupervisorDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:12]}",
            input_attempt_ids=attempt_ids,
            incumbent_id=None,
            objective=objective,
            action=SupervisorAction.FINISH,
            explanation="No feasible candidate found; cannot optimize.",
            stop_reason=SupervisorStopReason.NO_IMPROVEMENT,
        )

    # Check budget (before checking provider, so budget limits are respected)
    if budget_remaining.get("model_calls", 0) <= 0:
        return SupervisorDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:12]}",
            input_attempt_ids=attempt_ids,
            incumbent_id=incumbent_id,
            objective=objective,
            action=SupervisorAction.FINISH,
            explanation="Model call budget exhausted.",
            stop_reason=SupervisorStopReason.BUDGET_LIMIT,
        )

    if budget_remaining.get("optimization_attempts", 0) <= 0:
        return SupervisorDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:12]}",
            input_attempt_ids=attempt_ids,
            incumbent_id=incumbent_id,
            objective=objective,
            action=SupervisorAction.FINISH,
            explanation="Optimization attempt limit reached.",
            stop_reason=SupervisorStopReason.OPTIMIZATION_LIMIT,
        )

    # No provider: deterministic finish
    if provider is None:
        return SupervisorDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:12]}",
            input_attempt_ids=attempt_ids,
            incumbent_id=incumbent_id,
            objective=objective,
            action=SupervisorAction.FINISH,
            explanation="No inference provider configured; returning best verified candidate.",
            stop_reason=SupervisorStopReason.NO_PROMISING_CHANGE,
        )

    # Build prompt
    system_prompt = """You are a CNC machining optimization supervisor. Your job is to decide
whether to continue optimizing a manufacturing plan or finish with the current best candidate.

You are given:
- An objective to minimize (machining time or cost)
- The current best (incumbent) candidate with its metrics
- All attempted candidates so far
- Remaining budget for optimization

You must output JSON with:
- action: "improve" to request one more optimization attempt, or "finish" to stop
- explanation: brief reason for the decision (10-500 chars)
- stop_reason: when finishing, one of: objective_satisfied, no_promising_change,
  no_improvement, optimization_limit, budget_limit
- planning_instruction: when improving, specific bounded instruction (max 1000 chars)
- expected_improvement: when improving, what metric you expect to improve

Rules:
- You CANNOT change part geometry, material, fixtures, tools, or thresholds
- You CANNOT disable checks or increase budgets
- You can only suggest parameter changes within valid ranges:
  feed/spindle/stepdown/stepover/clearance
- Be specific and bounded in instructions
- If the incumbent is already very good, finish with objective_satisfied
- If no promising changes remain, finish with no_promising_change"""

    user_prompt = f"""Objective: Minimize {objective.value}

Current incumbent:
{_format_metrics(incumbent) if incumbent else "None"}

All candidates attempted: {len(attempts)}

Budget remaining:
- Model calls: {budget_remaining.get("model_calls", 0)}
- Optimization attempts: {budget_remaining.get("optimization_attempts", 0)}
- Time remaining: {budget_remaining.get("time_remaining_s", 0):.1f}s

Decide: improve (request one more optimization attempt) or finish (return current incumbent)?"""

    # Call model
    try:
        schema = SupervisorOutput.model_json_schema()
        completion = await provider.complete_json(
            system=system_prompt,
            user=user_prompt,
            schema=schema,
            max_tokens=800,
            timeout_s=15.0,
        )

        output = SupervisorOutput.model_validate(completion.parsed)

        # Map to domain types
        action = SupervisorAction.IMPROVE if output.action == "improve" else SupervisorAction.FINISH

        stop_reason_map = {
            "objective_satisfied": SupervisorStopReason.OBJECTIVE_SATISFIED,
            "no_promising_change": SupervisorStopReason.NO_PROMISING_CHANGE,
            "no_improvement": SupervisorStopReason.NO_IMPROVEMENT,
            "optimization_limit": SupervisorStopReason.OPTIMIZATION_LIMIT,
            "budget_limit": SupervisorStopReason.BUDGET_LIMIT,
        }
        stop_reason = (
            stop_reason_map.get(output.stop_reason, SupervisorStopReason.NO_PROMISING_CHANGE)
            if output.stop_reason
            else None
        )

        return SupervisorDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:12]}",
            input_attempt_ids=attempt_ids,
            incumbent_id=incumbent_id,
            objective=objective,
            evidence_refs=tuple(aid for aid, _ in attempts),
            action=action,
            explanation=output.explanation,
            planning_instruction=output.planning_instruction,
            expected_metric_improvement=output.expected_improvement,
            stop_reason=stop_reason,
        )

    except (ValidationError, KeyError, ValueError) as e:
        # Model failed to produce valid output: finish with incumbent
        return SupervisorDecision(
            decision_id=f"decision-{uuid.uuid4().hex[:12]}",
            input_attempt_ids=attempt_ids,
            incumbent_id=incumbent_id,
            objective=objective,
            action=SupervisorAction.FINISH,
            explanation=f"Supervisor output invalid: {type(e).__name__}",
            stop_reason=SupervisorStopReason.NO_PROMISING_CHANGE,
        )


def _format_metrics(metrics: CandidateMetrics) -> str:
    """Format metrics for display in prompt."""
    lines = [
        f"  Verified: {metrics.verified}",
        f"  Total machining time: {metrics.estimated_total_machining_seconds:.1f}s",
        f"  Motion time: {metrics.estimated_motion_seconds:.1f}s",
        f"  Tool changes: {metrics.tool_changes}",
        f"  Setups: {metrics.setups}",
    ]
    if metrics.minimum_clearance_mm is not None:
        lines.append(f"  Min clearance: {metrics.minimum_clearance_mm:.2f}mm")
    if metrics.estimated_machining_cost_usd is not None:
        lines.append(f"  Cost: ${metrics.estimated_machining_cost_usd:.2f}")
    return "\n".join(lines)
