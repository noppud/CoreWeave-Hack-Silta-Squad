"""The job state machine: budgets, permissions, cancellation and repair.

The controller owns state. Models propose; deterministic tools decide. A model
may never edit a threshold, a dimension or a check result, and a cancelled or
budget-exhausted job can never publish success.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path

from silta.cad import CadResult, build_and_export
from silta.checks import blocking, run_path_checks, run_preflight_checks
from silta.domain import (
    ACTIVE_STATES,
    Attempt,
    Budget,
    CheckResult,
    CheckStage,
    CheckStatus,
    Disposition,
    JobState,
    ModelUsage,
    PartSpec,
    ProcessPlan,
    RunEvent,
    Severity,
    ShopProfile,
    SimulationResult,
    Trajectory,
    stable_hash,
    utc_now,
)
from silta.measurements import measurement_for
from silta.memory import LearningMemory
from silta.policy import Policy, get_policy
from silta.simulation import simulate
from silta.telemetry import Telemetry
from silta.toolpaths import CompileError, compile_plan, estimated_seconds


class Cancelled(Exception):
    """Raised inside the pipeline when the session cancels the job."""


@dataclass(frozen=True)
class JobRequest:
    session_id: str
    spec: PartSpec
    shop: ShopProfile
    policy_version: str = "policy-v0"
    budget: Budget = field(default_factory=Budget)
    origin: str = "live"
    seed_plan: ProcessPlan | None = None
    job_id: str = field(default_factory=lambda: f"job-{uuid.uuid4().hex[:12]}")
    idempotency_key: str | None = None
    expected_spec_revision: int | None = None
    artifact_dir: Path | None = None
    commit: str | None = None
    memory_enabled: bool = True


@dataclass
class JobOutcome:
    job_id: str
    state: JobState
    attempts: list[Attempt] = field(default_factory=list)
    cad: CadResult | None = None
    best_attempt_id: str | None = None
    trajectories: dict[str, Trajectory] = field(default_factory=dict)
    replays: dict[str, dict] = field(default_factory=dict)
    message: str = ""

    @property
    def best_attempt(self) -> Attempt | None:
        if self.best_attempt_id is None:
            return None
        return next((a for a in self.attempts if a.attempt_id == self.best_attempt_id), None)


class JobController:
    """Runs one job to completion, publishing every state change as an event."""

    def __init__(
        self,
        *,
        planner: Callable | None = None,
        provider=None,
        telemetry: Telemetry | None = None,
        simulate_fn=simulate,
        memory: LearningMemory | None = None,
    ) -> None:
        self._memory = memory
        self._planner = planner
        self._provider = provider
        self._telemetry = telemetry or Telemetry.from_env()
        self._simulate = simulate_fn
        self._cancelled: set[str] = set()
        # Per-instance: a class-level dict would be shared by every controller.
        self.outcomes: dict[str, JobOutcome] = {}
        self._sequence: dict[str, int] = {}

    # ------------------------------------------------------------------ control

    def cancel(self, job_id: str) -> None:
        self._cancelled.add(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled

    def _check_cancelled(self, job_id: str) -> None:
        if job_id in self._cancelled:
            raise Cancelled(job_id)

    def _event(self, job_id: str, type_: str, payload: dict, attempt_id: str | None = None):
        sequence = self._sequence.get(job_id, 0)
        self._sequence[job_id] = sequence + 1
        return RunEvent(
            sequence=sequence,
            job_id=job_id,
            attempt_id=attempt_id,
            type=type_,  # type: ignore[arg-type]
            timestamp=utc_now(),
            payload=payload,
        )

    # --------------------------------------------------------------------- run

    async def run(self, request: JobRequest) -> AsyncIterator[RunEvent]:
        job_id = request.job_id
        self._sequence.setdefault(job_id, 0)
        outcome = JobOutcome(job_id=job_id, state=JobState.CONFIRMED)
        self.outcomes[job_id] = outcome
        policy = get_policy(request.policy_version)
        deadline = time.monotonic() + request.budget.job_deadline_s
        calls_used = 0

        async def state(new: JobState, **payload):
            outcome.state = new
            return self._event(job_id, "state_changed", {"state": new.value, **payload})

        try:
            with self._telemetry.span("job", job_id=job_id, policy=policy.version):
                # ---------------------------------------------------------- CAD
                yield await state(JobState.CAD_BUILDING)
                self._check_cancelled(job_id)
                artifact_dir = request.artifact_dir or Path("artifacts") / job_id
                with self._telemetry.span("cad_build"):
                    cad = await asyncio.to_thread(build_and_export, request.spec, artifact_dir)
                outcome.cad = cad
                yield self._event(
                    job_id,
                    "artifact_ready",
                    {
                        "kind": "cad",
                        "step_sha256": cad.step_sha256,
                        "mesh_sha256": cad.mesh_sha256,
                        "volume_mm3": round(cad.volume_mm3, 4),
                        "reimported_volume_mm3": round(cad.reimported_volume_mm3, 4),
                        "bbox_mm": [round(v, 4) for v in cad.bbox_mm],
                        "builder_version": cad.builder_version,
                    },
                )

                previous_plan: ProcessPlan | None = None
                failures: tuple[CheckResult, ...] = ()
                seen_fingerprints: set[str] = set()

                for index in range(request.budget.max_attempts):
                    self._check_cancelled(job_id)
                    if time.monotonic() > deadline:
                        outcome.state = JobState.BUDGET_EXHAUSTED
                        outcome.message = "Job deadline reached before a feasible plan was found."
                        break

                    attempt_id = f"{job_id}-a{index}"
                    started = utc_now()
                    yield await state(
                        JobState.PLANNING if index == 0 else JobState.REPAIRING,
                        attempt=index,
                    )

                    memory_recall = None
                    if self._memory and request.memory_enabled:
                        try:
                            memory_recall = await asyncio.to_thread(
                                self._memory.recall,
                                request.session_id,
                                request.spec,
                                request.shop,
                                policy,
                            )
                            yield self._event(
                                job_id,
                                "memory_read",
                                {
                                    "context": memory_recall.context,
                                    "scope": memory_recall.scope,
                                    "episode_ids": list(memory_recall.episode_ids),
                                    "lesson_ids": list(memory_recall.lesson_ids),
                                    "recipe_episode_id": memory_recall.recipe_episode_id,
                                },
                                attempt_id,
                            )
                        except Exception as exc:
                            yield self._event(
                                job_id,
                                "memory_unavailable",
                                {"operation": "read", "error_type": type(exc).__name__},
                            )

                    # ------------------------------------------------ candidate
                    usage: ModelUsage | None = None
                    diff: tuple[str, ...] = ()
                    source = "naive_seed"
                    if index == 0 and memory_recall and memory_recall.recipe:
                        plan = memory_recall.recipe
                        source = "memory_recipe"
                        diff = (
                            f"Recalled recipe from {memory_recall.recipe_episode_id}; "
                            "revalidate now",
                        )
                    elif index == 0 and request.seed_plan is not None:
                        plan = request.seed_plan
                    else:
                        remaining = request.budget.max_model_calls - calls_used
                        try:
                            with self._telemetry.span("plan", attempt=index):
                                result = await self._propose(
                                    request,
                                    policy,
                                    previous_plan,
                                    failures,
                                    index,
                                    remaining,
                                    memory_recall,
                                )
                        except Exception as exc:  # provider or schema failure
                            outcome.state = JobState.NEEDS_HUMAN_REVIEW
                            outcome.message = f"Planner could not produce a candidate: {exc}"
                            yield self._event(
                                job_id,
                                "attempt_completed",
                                {"attempt": index, "error": str(exc)},
                                attempt_id,
                            )
                            break
                        plan, source, usage, diff, fallback_reason = result
                        if time.monotonic() > deadline:
                            # Planning itself can overrun. Say the deadline was hit
                            # rather than reporting "no feasible plan was found".
                            outcome.state = JobState.BUDGET_EXHAUSTED
                            outcome.message = (
                                "Job deadline reached while planning candidate "
                                f"{index}; no result was published."
                            )
                            break
                        if fallback_reason:
                            # A configured model that did not produce a plan is a
                            # downgrade, not a detail. Say so in the run's own record.
                            yield self._event(
                                job_id,
                                "planner_fallback",
                                {
                                    "attempt": index,
                                    "reason": fallback_reason,
                                    "used": "deterministic planner",
                                },
                                attempt_id,
                            )
                        if usage is not None:
                            calls_used += usage.calls

                    if plan.fingerprint in seen_fingerprints:
                        outcome.state = JobState.NEEDS_HUMAN_REVIEW
                        outcome.message = (
                            "The planner repeated a candidate that was already rejected."
                        )
                        break
                    seen_fingerprints.add(plan.fingerprint)
                    if diff:
                        yield self._event(job_id, "repair_diff", {"diff": list(diff)}, attempt_id)

                    # --------------------------------------------------- checks
                    yield await state(JobState.CHECKING, attempt=index)
                    with self._telemetry.span("preflight_checks", attempt=index):
                        checks = run_preflight_checks(request.spec, request.shop, plan)
                    for result in checks:
                        yield self._event(
                            job_id, "check_completed", result.model_dump(mode="json"), attempt_id
                        )

                    trajectory: Trajectory | None = None
                    simulation: SimulationResult | None = None
                    replay: dict | None = None

                    if not blocking(checks):
                        # ------------------------------------------ compilation
                        yield await state(JobState.COMPILING, attempt=index)
                        try:
                            trajectory = compile_plan(request.spec, request.shop, plan)
                        except CompileError as exc:
                            checks = [
                                *checks,
                                CheckResult(
                                    check_id="path_compilation",
                                    stage=CheckStage.PATH,
                                    status=CheckStatus.FAIL,
                                    severity=Severity.BLOCKING,
                                    message=str(exc),
                                    repair_hint="Choose tooling and parameters the compiler "
                                    "can expand for this feature family.",
                                ),
                            ]
                        else:
                            outcome.trajectories[attempt_id] = trajectory
                            yield await state(JobState.PATH_CHECKING, attempt=index)
                            with self._telemetry.span("path_checks", attempt=index):
                                path_results = run_path_checks(
                                    request.spec, request.shop, plan, trajectory, policy
                                )
                            checks = [*checks, *path_results]
                            for result in path_results:
                                yield self._event(
                                    job_id,
                                    "check_completed",
                                    result.model_dump(mode="json"),
                                    attempt_id,
                                )

                    if not blocking(checks) and trajectory is not None:
                        # ------------------------------------------- simulation
                        yield await state(JobState.SIMULATING, attempt=index)
                        yield self._event(
                            job_id,
                            "simulation_started",
                            {"segments": len(trajectory.segments)},
                            attempt_id,
                        )
                        self._check_cancelled(job_id)
                        with self._telemetry.span("simulation", attempt=index):
                            simulation, replay = await asyncio.to_thread(
                                self._simulate, request.spec, request.shop, plan, trajectory
                            )
                        outcome.replays[attempt_id] = replay
                        for collision in simulation.collisions:
                            yield self._event(
                                job_id,
                                "collision_detected",
                                collision.model_dump(mode="json"),
                                attempt_id,
                            )
                        checks = [*checks, *_simulation_checks(simulation)]

                    # ------------------------------------------------ disposition
                    failing = blocking(checks)
                    if not failing and simulation is not None and simulation.passed:
                        disposition = Disposition.PASSED
                    elif simulation is not None and not simulation.passed:
                        disposition = Disposition.FAILED_SIMULATION
                    else:
                        disposition = Disposition.FAILED_CHECKS

                    attempt = Attempt(
                        attempt_id=attempt_id,
                        job_id=job_id,
                        index=index,
                        parent_attempt_id=f"{job_id}-a{index - 1}" if index else None,
                        policy_version=policy.version,
                        origin=request.origin,  # type: ignore[arg-type]
                        plan=plan,
                        plan_source=source,  # type: ignore[arg-type]
                        checks=tuple(checks),
                        trajectory_hash=trajectory.trajectory_hash if trajectory else None,
                        simulation=simulation,
                        usage=usage,
                        disposition=disposition,
                        repair_diff=diff,
                        memory_episode_ids=memory_recall.episode_ids if memory_recall else (),
                        memory_lesson_ids=memory_recall.lesson_ids if memory_recall else (),
                        memory_recipe_episode_id=memory_recall.recipe_episode_id
                        if memory_recall and source == "memory_recipe"
                        else None,
                        started_at=started,
                        finished_at=utc_now(),
                    )
                    outcome.attempts.append(attempt)
                    async for memory_event in self._remember(request, policy, attempt):
                        yield memory_event
                    self._telemetry.log_attempt(request, attempt)
                    yield self._event(
                        job_id,
                        "attempt_completed",
                        {
                            "attempt": index,
                            "disposition": disposition.value,
                            "blocking": [c.check_id for c in failing],
                            "simulation": simulation.status.value if simulation else None,
                            "estimated_seconds": round(
                                estimated_seconds(trajectory, request.shop, plan), 1
                            )
                            if trajectory
                            else None,
                            "measurements": measurement_for(
                                attempt, trajectory, request.shop
                            ).model_dump(mode="json"),
                        },
                        attempt_id,
                    )

                    if disposition is Disposition.PASSED:
                        if not request.budget.supervised_loop_enabled:
                            # Original behavior: first pass ends the job immediately
                            outcome.state = JobState.PASSED
                            outcome.best_attempt_id = attempt_id
                            break
                        else:
                            # Supervised loop: break to enter optimization phase
                            break

                    previous_plan = plan
                    failures = tuple(failing)
                    if index == request.budget.max_attempts - 1:
                        outcome.state = JobState.NEEDS_HUMAN_REVIEW
                        outcome.message = (
                            f"No feasible plan within {request.budget.max_attempts} candidates."
                        )
                    elif calls_used >= request.budget.max_model_calls and self._provider:
                        outcome.state = JobState.BUDGET_EXHAUSTED
                        outcome.message = "Model call budget exhausted."
                        break
                else:
                    if outcome.state in ACTIVE_STATES:
                        outcome.state = JobState.NEEDS_HUMAN_REVIEW

                # ============================================================
                # OPTIMIZATION PHASE (supervised loop only)
                # ============================================================
                if request.budget.supervised_loop_enabled and outcome.state in ACTIVE_STATES:
                    from silta.domain import OptimizationObjective
                    from silta.selection import choose_best, is_feasible, metrics_for
                    from silta.supervisor import supervise

                    # Find all feasible attempts and compute their metrics
                    self._check_cancelled(job_id)
                    incumbent = None
                    objective = OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS

                    for attempt in outcome.attempts:
                        if is_feasible(attempt):
                            trajectory = outcome.trajectories.get(attempt.attempt_id)
                            metrics = metrics_for(attempt, trajectory, request.shop, attempt.plan)
                            incumbent = choose_best(incumbent, metrics, objective)

                    if incumbent is None:
                        # No feasible candidate: already handled by loop above
                        pass
                    else:
                        # We have at least one feasible candidate: supervise
                        yield await state(JobState.SUPERVISING)
                        self._check_cancelled(job_id)

                        optimization_attempts_used = 0
                        max_optimization = request.budget.max_optimization_attempts

                        while optimization_attempts_used < max_optimization:
                            if time.monotonic() > deadline:
                                outcome.state = JobState.BUDGET_EXHAUSTED
                                outcome.message = (
                                    "Deadline reached during optimization; "
                                    "returning best verified candidate."
                                )
                                outcome.best_attempt_id = incumbent.attempt_id
                                yield self._event(
                                    job_id,
                                    "plan_selected",
                                    {
                                        "incumbent_id": incumbent.attempt_id,
                                        "stop_reason": "optimization_incomplete",
                                    },
                                )
                                break

                            if calls_used >= request.budget.max_model_calls:
                                outcome.state = JobState.BUDGET_EXHAUSTED
                                outcome.message = (
                                    "Model calls exhausted during optimization; "
                                    "returning best verified candidate."
                                )
                                outcome.best_attempt_id = incumbent.attempt_id
                                yield self._event(
                                    job_id,
                                    "plan_selected",
                                    {
                                        "incumbent_id": incumbent.attempt_id,
                                        "stop_reason": "budget_limit",
                                    },
                                )
                                break

                            self._check_cancelled(job_id)

                            # Call supervisor
                            budget_remaining = {
                                "model_calls": request.budget.max_model_calls - calls_used,
                                "optimization_attempts": max_optimization
                                - optimization_attempts_used,
                                "time_remaining_s": max(0, deadline - time.monotonic()),
                            }

                            try:
                                with self._telemetry.span("supervision"):
                                    decision = await supervise(
                                        attempts=[
                                            (
                                                a.attempt_id,
                                                metrics_for(
                                                    a,
                                                    outcome.trajectories.get(a.attempt_id),
                                                    request.shop,
                                                    a.plan,
                                                ),
                                            )
                                            for a in outcome.attempts
                                        ],
                                        incumbent=incumbent,
                                        objective=objective,
                                        budget_remaining=budget_remaining,
                                        provider=self._provider,
                                    )
                                    if decision.action.value in ("improve", "finish"):
                                        calls_used += 1  # Supervisor call counts

                                yield self._event(
                                    job_id,
                                    "supervisor_decision",
                                    {
                                        "action": decision.action.value,
                                        "explanation": decision.explanation,
                                        "stop_reason": decision.stop_reason.value
                                        if decision.stop_reason
                                        else None,
                                    },
                                )

                                if decision.action.value == "finish":
                                    # Supervisor says stop
                                    yield await state(JobState.FINALIZING)
                                    outcome.state = JobState.PASSED
                                    outcome.best_attempt_id = incumbent.attempt_id
                                    yield self._event(
                                        job_id,
                                        "plan_selected",
                                        {
                                            "incumbent_id": incumbent.attempt_id,
                                            "stop_reason": decision.stop_reason.value
                                            if decision.stop_reason
                                            else "finished",
                                        },
                                    )
                                    break

                                # Supervisor says improve: create one more attempt
                                yield await state(JobState.OPTIMIZING)
                                optimization_attempts_used += 1
                                index = len(outcome.attempts)
                                attempt_id = f"{job_id}-a{index}"
                                started = utc_now()

                                yield self._event(
                                    job_id,
                                    "optimization_started",
                                    {
                                        "attempt": index,
                                        "instruction": decision.planning_instruction,
                                    },
                                    attempt_id,
                                )

                                # Repair a rejected optimization, otherwise improve the incumbent.
                                latest = outcome.attempts[-1]
                                base_attempt = (
                                    latest
                                    if latest.disposition is not Disposition.PASSED
                                    else next(
                                        a
                                        for a in outcome.attempts
                                        if a.attempt_id == incumbent.attempt_id
                                    )
                                )
                                try:
                                    remaining = request.budget.max_model_calls - calls_used
                                    with self._telemetry.span("optimize_plan", attempt=index):
                                        result = await self._propose(
                                            request,
                                            policy,
                                            base_attempt.plan,
                                            base_attempt.blocking_failures,
                                            index,
                                            remaining,
                                            memory_recall,
                                            planning_instruction=decision.planning_instruction,
                                        )
                                    plan, source, usage, diff, fallback_reason = result
                                    if fallback_reason:
                                        yield self._event(
                                            job_id,
                                            "planner_fallback",
                                            {
                                                "attempt": index,
                                                "reason": fallback_reason,
                                                "used": "deterministic planner",
                                            },
                                            attempt_id,
                                        )
                                    if usage is not None:
                                        calls_used += usage.calls
                                except Exception as exc:
                                    # Optimization failed: keep incumbent
                                    outcome.state = JobState.PASSED
                                    outcome.best_attempt_id = incumbent.attempt_id
                                    outcome.message = (
                                        f"Optimization planning failed: {exc}; "
                                        "returning best verified candidate."
                                    )
                                    yield self._event(
                                        job_id,
                                        "plan_selected",
                                        {
                                            "incumbent_id": incumbent.attempt_id,
                                            "stop_reason": "optimization_incomplete",
                                        },
                                    )
                                    break

                                # Check for repeated fingerprint
                                if plan.fingerprint in seen_fingerprints:
                                    # Repeated: stop optimization
                                    outcome.state = JobState.PASSED
                                    outcome.best_attempt_id = incumbent.attempt_id
                                    yield self._event(
                                        job_id,
                                        "plan_selected",
                                        {
                                            "incumbent_id": incumbent.attempt_id,
                                            "stop_reason": "repeated_candidate",
                                        },
                                    )
                                    break
                                seen_fingerprints.add(plan.fingerprint)

                                # Run full evaluation
                                yield await state(JobState.CHECKING, attempt=index)
                                with self._telemetry.span("preflight_checks", attempt=index):
                                    checks = run_preflight_checks(request.spec, request.shop, plan)
                                for result in checks:
                                    yield self._event(
                                        job_id,
                                        "check_completed",
                                        result.model_dump(mode="json"),
                                        attempt_id,
                                    )

                                trajectory_opt: Trajectory | None = None
                                simulation_opt: SimulationResult | None = None
                                replay_opt: dict | None = None

                                if not blocking(checks):
                                    yield await state(JobState.COMPILING, attempt=index)
                                    try:
                                        trajectory_opt = compile_plan(
                                            request.spec, request.shop, plan
                                        )
                                    except CompileError as exc:
                                        checks = [
                                            *checks,
                                            CheckResult(
                                                check_id="path_compilation",
                                                stage=CheckStage.PATH,
                                                status=CheckStatus.FAIL,
                                                severity=Severity.BLOCKING,
                                                message=str(exc),
                                                repair_hint="Compiler error during optimization.",
                                            ),
                                        ]
                                    else:
                                        outcome.trajectories[attempt_id] = trajectory_opt
                                        yield await state(JobState.PATH_CHECKING, attempt=index)
                                        with self._telemetry.span("path_checks", attempt=index):
                                            path_results = run_path_checks(
                                                request.spec,
                                                request.shop,
                                                plan,
                                                trajectory_opt,
                                                policy,
                                            )
                                        checks = [*checks, *path_results]
                                        for result in path_results:
                                            yield self._event(
                                                job_id,
                                                "check_completed",
                                                result.model_dump(mode="json"),
                                                attempt_id,
                                            )

                                if not blocking(checks) and trajectory_opt is not None:
                                    yield await state(JobState.SIMULATING, attempt=index)
                                    self._check_cancelled(job_id)
                                    with self._telemetry.span("simulation", attempt=index):
                                        simulation_opt, replay_opt = await asyncio.to_thread(
                                            self._simulate,
                                            request.spec,
                                            request.shop,
                                            plan,
                                            trajectory_opt,
                                        )
                                    outcome.replays[attempt_id] = replay_opt
                                    checks = [*checks, *_simulation_checks(simulation_opt)]

                                # Determine disposition
                                failing_opt = blocking(checks)
                                if (
                                    not failing_opt
                                    and simulation_opt is not None
                                    and simulation_opt.passed
                                ):
                                    disposition_opt = Disposition.PASSED
                                elif simulation_opt is not None and not simulation_opt.passed:
                                    disposition_opt = Disposition.FAILED_SIMULATION
                                else:
                                    disposition_opt = Disposition.FAILED_CHECKS

                                attempt_opt = Attempt(
                                    attempt_id=attempt_id,
                                    job_id=job_id,
                                    index=index,
                                    parent_attempt_id=base_attempt.attempt_id,
                                    policy_version=policy.version,
                                    origin=request.origin,  # type: ignore[arg-type]
                                    plan=plan,
                                    plan_source=source,  # type: ignore[arg-type]
                                    checks=tuple(checks),
                                    trajectory_hash=trajectory_opt.trajectory_hash
                                    if trajectory_opt
                                    else None,
                                    simulation=simulation_opt,
                                    usage=usage,
                                    disposition=disposition_opt,
                                    repair_diff=diff,
                                    started_at=started,
                                    finished_at=utc_now(),
                                )
                                outcome.attempts.append(attempt_opt)
                                async for memory_event in self._remember(
                                    request, policy, attempt_opt
                                ):
                                    yield memory_event
                                self._telemetry.log_attempt(request, attempt_opt)
                                yield self._event(
                                    job_id,
                                    "attempt_completed",
                                    {
                                        "attempt": index,
                                        "disposition": disposition_opt.value,
                                        "blocking": [c.check_id for c in failing_opt],
                                        "simulation": simulation_opt.status.value
                                        if simulation_opt
                                        else None,
                                        "measurements": measurement_for(
                                            attempt_opt, trajectory_opt, request.shop
                                        ).model_dump(mode="json"),
                                    },
                                    attempt_id,
                                )

                                # Update incumbent if this candidate is better
                                if is_feasible(attempt_opt):
                                    new_metrics = metrics_for(
                                        attempt_opt, trajectory_opt, request.shop, plan
                                    )
                                    new_incumbent = choose_best(incumbent, new_metrics, objective)
                                    if new_incumbent.attempt_id != incumbent.attempt_id:
                                        incumbent = new_incumbent
                                        yield self._event(
                                            job_id,
                                            "incumbent_updated",
                                            {
                                                "new_incumbent_id": incumbent.attempt_id,
                                                "objective_value": (
                                                    incumbent.estimated_total_machining_seconds
                                                ),
                                            },
                                        )
                                # Continue supervision loop

                            except Exception as exc:
                                # Supervision failed: finish with incumbent
                                outcome.state = JobState.PASSED
                                outcome.best_attempt_id = incumbent.attempt_id
                                outcome.message = f"Supervision error: {exc}"
                                yield self._event(
                                    job_id,
                                    "plan_selected",
                                    {
                                        "incumbent_id": incumbent.attempt_id,
                                        "stop_reason": "optimization_incomplete",
                                    },
                                )
                                break

                        else:
                            # Optimization loop completed normally
                            if outcome.state in ACTIVE_STATES:
                                yield await state(JobState.FINALIZING)
                                outcome.state = JobState.PASSED
                                outcome.best_attempt_id = incumbent.attempt_id
                                yield self._event(
                                    job_id,
                                    "plan_selected",
                                    {
                                        "incumbent_id": incumbent.attempt_id,
                                        "stop_reason": "optimization_complete",
                                    },
                                )

        except Cancelled:
            outcome.state = JobState.CANCELLED
            outcome.message = "Cancelled by the session. No result was published."
            outcome.best_attempt_id = None
        except Exception as exc:  # pragma: no cover - defensive
            outcome.state = JobState.FAILED
            outcome.message = f"{type(exc).__name__}: {exc}"

        # A cancelled or exhausted job never publishes success.
        if outcome.state is not JobState.PASSED:
            outcome.best_attempt_id = None
        yield self._event(
            job_id,
            "job_completed",
            {
                "state": outcome.state.value,
                "message": outcome.message,
                "attempts": len(outcome.attempts),
                "best_attempt_id": outcome.best_attempt_id,
            },
        )

    # ----------------------------------------------------------------- planner

    async def _remember(self, request, policy, attempt):
        if not self._memory or not request.memory_enabled or self.is_cancelled(request.job_id):
            return
        try:
            record = await asyncio.to_thread(
                self._memory.record, request.session_id, request.spec, request.shop, policy, attempt
            )
            yield self._event(request.job_id, "memory_written", record, attempt.attempt_id)
        except Exception as exc:
            yield self._event(
                request.job_id,
                "memory_unavailable",
                {"operation": "write", "error_type": type(exc).__name__},
            )

    async def _propose(
        self,
        request,
        policy: Policy,
        previous,
        failures,
        index,
        remaining,
        memory_recall=None,
        *,
        planning_instruction=None,
    ):
        from silta.planner import PlanRequest, propose_plan

        plan_request = PlanRequest(
            spec=request.spec,
            shop=request.shop,
            policy=policy,
            previous_plan=previous,
            failures=failures,
            attempt_index=index,
            memory_instructions=memory_recall.instructions if memory_recall else (),
            memory_episode_ids=memory_recall.episode_ids if memory_recall else (),
            memory_observations=memory_recall.observations if memory_recall else (),
            call_timeout_s=request.budget.call_timeout_s,
            max_output_tokens=request.budget.max_output_tokens,
            max_model_calls=max(0, remaining),
            planning_instruction=planning_instruction,
            measurements=tuple(
                measurement_for(
                    a, self.outcomes[request.job_id].trajectories.get(a.attempt_id), request.shop
                )
                for a in self.outcomes[request.job_id].attempts[-5:]
            ),
        )
        provider = self._provider if remaining > 0 else None
        planner = self._planner or propose_plan
        result = await planner(plan_request, provider)
        return (
            result.plan,
            result.source,
            result.usage,
            result.diff,
            getattr(result, "fallback_reason", None),
        )


def _simulation_checks(simulation: SimulationResult) -> list[CheckResult]:
    """Turn the simulator's verdict into the same structured evidence the planner reads."""
    results: list[CheckResult] = []
    for collision in simulation.collisions[:3]:
        results.append(
            CheckResult(
                check_id="simulation_collision",
                stage=CheckStage.SIMULATION,
                status=CheckStatus.FAIL,
                severity=Severity.BLOCKING,
                message=(
                    f"The {collision.colliding_part} struck {collision.obstacle_id} during "
                    f"segment {collision.segment_id} at "
                    f"({collision.x_mm}, {collision.y_mm}, {collision.z_mm}) mm."
                ),
                segment_id=collision.segment_id,
                operation_id=collision.operation_id,
                actual=collision.penetration_mm,
                required=0.0,
                units="mm",
                evidence={
                    "obstacle_kind": collision.obstacle_kind,
                    "obstacle_id": collision.obstacle_id,
                    "colliding_part": collision.colliding_part,
                    "tool_z_mm": collision.z_mm,
                },
                repair_hint="Raise the clearance plane above every fixture the tool traverses, "
                "or reorder the motion. Do not move the fixture or change the part.",
            )
        )
    if results:
        # The run stopped at the first collision, so coverage and residual were never
        # measured. Reporting them as failures would feed the planner false evidence.
        results.append(
            CheckResult(
                check_id="simulation_material_removal",
                stage=CheckStage.SIMULATION,
                status=CheckStatus.UNKNOWN,
                severity=Severity.INFO,
                message="Stock removal was not evaluated: the run stopped at the collision.",
            )
        )
        return results
    if simulation.max_residual_mm > simulation.residual_threshold_mm:
        results.append(
            CheckResult(
                check_id="simulation_residual_stock",
                stage=CheckStage.SIMULATION,
                status=CheckStatus.FAIL,
                severity=Severity.BLOCKING,
                message=f"{simulation.max_residual_mm:.3f} mm of material was left behind.",
                actual=simulation.max_residual_mm,
                required=simulation.residual_threshold_mm,
                units="mm",
                repair_hint="Reduce the stepover or stepdown, or cover the feature fully.",
            )
        )
    if simulation.max_gouge_mm > simulation.gouge_threshold_mm:
        results.append(
            CheckResult(
                check_id="simulation_gouge",
                stage=CheckStage.SIMULATION,
                status=CheckStatus.FAIL,
                severity=Severity.BLOCKING,
                message=f"The tool cut {simulation.max_gouge_mm:.3f} mm past the target surface.",
                actual=simulation.max_gouge_mm,
                required=simulation.gouge_threshold_mm,
                units="mm",
                repair_hint="Correct the depth or the cutter compensation.",
            )
        )
    for coverage in simulation.coverage:
        if coverage.removed_fraction < 0.999:
            results.append(
                CheckResult(
                    check_id="simulation_feature_coverage",
                    stage=CheckStage.SIMULATION,
                    status=CheckStatus.FAIL,
                    severity=Severity.BLOCKING,
                    message=(
                        f"Feature {coverage.feature_id} reached only "
                        f"{coverage.removed_fraction * 100:.1f}% of its target surface."
                    ),
                    feature_id=coverage.feature_id,
                    actual=coverage.removed_fraction,
                    required=1.0,
                    repair_hint="Extend the toolpath to cover the whole feature.",
                )
            )
    if not results:
        if not simulation.passed:
            return [
                CheckResult(
                    check_id="simulation_incomplete",
                    stage=CheckStage.SIMULATION,
                    status=CheckStatus.FAIL,
                    severity=Severity.BLOCKING,
                    message=f"Simulation did not verify this plan: {simulation.status.value}.",
                    repair_hint="Inspect the simulator limitation; do not treat missing "
                    "measurements as a pass or change the target to satisfy it.",
                )
            ]
        results.append(
            CheckResult(
                check_id="simulation_pass",
                stage=CheckStage.SIMULATION,
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                message=(
                    f"Stock removal complete with no collisions at a {simulation.grid_mm} mm grid "
                    f"({simulation.method})."
                ),
                evidence={
                    "grid_mm": simulation.grid_mm,
                    "residual_mm": simulation.max_residual_mm,
                    "gouge_mm": simulation.max_gouge_mm,
                },
            )
        )
    return results


def outcome_digest(outcome: JobOutcome) -> str:
    return stable_hash(
        {
            "job": outcome.job_id,
            "state": outcome.state.value,
            "attempts": [a.attempt_id for a in outcome.attempts],
        }
    )
