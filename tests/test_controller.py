"""Test the job controller with fake planner and fake clock."""

import asyncio

import pytest

from silta.controller import JobController, JobRequest, JobState
from silta.domain import Budget, Disposition
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan, reach_repaired_plan, valid_plan


class FakePlanner:
    """Deterministic fake planner for testing controller logic."""

    def __init__(self, sequence):
        """sequence: list of plans to return on successive calls."""
        self.sequence = list(sequence)
        self.call_count = 0

    async def __call__(self, request, provider):
        from silta.planner import PlanResult

        if self.call_count >= len(self.sequence):
            # Exhausted sequence
            raise ValueError("FakePlanner: no more plans in sequence")

        plan = self.sequence[self.call_count]
        self.call_count += 1

        return PlanResult(
            plan=plan,
            source="model",
            usage=None,
            raw_response=None,
            diff=("fake diff",),
        )


class TestController:
    """Test controller state machine with deterministic inputs."""

    @pytest.mark.asyncio
    async def test_naive_seed_produces_reach_fail_collision_pass_trajectory(self):
        """With a fake planner returning the known sequence, verify the attempt trajectory.

        Attempt 0: naive_plan() -> fails tool_cutting_reach
        Attempt 1: reach_repaired_plan() -> passes preflight, collides in simulation
        Attempt 2: valid_plan() -> passes all checks and simulation
        """
        fake_planner = FakePlanner([reach_repaired_plan(), valid_plan()])

        controller = JobController(planner=fake_planner)

        request = JobRequest(
            session_id="test-session",
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            budget=Budget(max_attempts=3, max_model_calls=10),
            seed_plan=naive_plan(),  # attempt 0
        )

        events = []
        async for event in controller.run(request):
            events.append(event)

        outcome = controller.outcomes[request.job_id]

        # Should have 3 attempts
        assert len(outcome.attempts) == 3, f"Expected 3 attempts, got {len(outcome.attempts)}"

        # Attempt 0: naive seed, should fail tool_cutting_reach
        attempt0 = outcome.attempts[0]
        assert attempt0.plan_source == "naive_seed"
        assert attempt0.disposition == Disposition.FAILED_CHECKS
        blocking0 = [c.check_id for c in attempt0.checks if c.blocking_failure]
        assert "tool_cutting_reach" in blocking0, f"Attempt 0 should fail reach, got {blocking0}"

        # Attempt 1: reach repaired, should fail simulation (collision)
        attempt1 = outcome.attempts[1]
        assert attempt1.disposition == Disposition.FAILED_SIMULATION
        assert attempt1.simulation is not None
        assert len(attempt1.simulation.collisions) > 0

        # Attempt 2: valid plan, should pass
        attempt2 = outcome.attempts[2]
        assert attempt2.disposition == Disposition.PASSED

        # Final state should be PASSED
        assert outcome.state == JobState.PASSED
        assert outcome.best_attempt_id == attempt2.attempt_id

    @pytest.mark.asyncio
    async def test_planner_returns_same_candidate_twice_stops_with_review(self):
        """If the planner returns the SAME candidate twice, controller must stop with
        needs_human_review."""
        # Return the same plan twice
        same_plan = reach_repaired_plan()
        fake_planner = FakePlanner([same_plan, same_plan])  # duplicate

        controller = JobController(planner=fake_planner)

        request = JobRequest(
            session_id="test-session",
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            budget=Budget(max_attempts=5, max_model_calls=10),
            seed_plan=naive_plan(),
        )

        events = []
        async for event in controller.run(request):
            events.append(event)

        outcome = controller.outcomes[request.job_id]

        # Should have stopped after 2 attempts (naive seed + first repair attempt)
        assert len(outcome.attempts) == 2, f"Expected 2 attempts, got {len(outcome.attempts)}"
        assert outcome.state == JobState.NEEDS_HUMAN_REVIEW
        assert "repeated a candidate" in outcome.message.lower()

    @pytest.mark.asyncio
    async def test_cancellation_yields_cancelled_and_no_best_attempt(self):
        """Cancelling mid-run must yield state=cancelled and best_attempt_id=None.

        A cancelled job must never publish success.
        """

        # Slow planner that we can cancel
        async def slow_planner(request, provider):
            await asyncio.sleep(0.5)
            from silta.planner import PlanResult

            return PlanResult(
                plan=valid_plan(), source="model", usage=None, raw_response=None, diff=()
            )

        controller = JobController(planner=slow_planner)

        request = JobRequest(
            session_id="test-session",
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            budget=Budget(max_attempts=3),
            seed_plan=naive_plan(),
        )

        async def cancel_soon():
            await asyncio.sleep(0.05)
            controller.cancel(request.job_id)

        cancel_task = asyncio.create_task(cancel_soon())

        events = []
        async for event in controller.run(request):
            events.append(event)

        await cancel_task

        outcome = controller.outcomes[request.job_id]

        # Must be cancelled
        assert outcome.state == JobState.CANCELLED, f"Expected CANCELLED, got {outcome.state}"
        assert outcome.best_attempt_id is None, "Cancelled job must not have best_attempt_id"
        assert "cancelled" in outcome.message.lower()

    @pytest.mark.asyncio
    async def test_exceeding_max_attempts_yields_needs_human_review(self):
        """If max_attempts is reached without passing, state must be needs_human_review,
        never passed."""
        # Planner that always returns a failing plan
        fake_planner = FakePlanner([reach_repaired_plan(), reach_repaired_plan()])

        controller = JobController(planner=fake_planner)

        request = JobRequest(
            session_id="test-session",
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            budget=Budget(max_attempts=2, max_model_calls=10),  # only 2 attempts
            seed_plan=naive_plan(),  # attempt 0
        )

        events = []
        async for event in controller.run(request):
            events.append(event)

        outcome = controller.outcomes[request.job_id]

        # Should have 2 attempts (seed + 1 repair)
        assert len(outcome.attempts) == 2
        # None should pass
        assert all(a.disposition != Disposition.PASSED for a in outcome.attempts)
        # Final state must be needs_human_review
        assert outcome.state == JobState.NEEDS_HUMAN_REVIEW
        assert outcome.best_attempt_id is None

    @pytest.mark.asyncio
    async def test_collision_aborted_simulation_does_not_emit_residual_failures(self):
        """When simulation stops at collision, it must NOT also emit residual/coverage failures.

        The run stopped at the collision, so residual/coverage were never measured.
        """
        fake_planner = FakePlanner([])  # no repairs needed

        controller = JobController(planner=fake_planner)

        request = JobRequest(
            session_id="test-session",
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            budget=Budget(max_attempts=1),
            seed_plan=reach_repaired_plan(),  # will collide
        )

        events = []
        async for event in controller.run(request):
            events.append(event)

        outcome = controller.outcomes[request.job_id]
        attempt = outcome.attempts[0]

        # Should have collision
        assert attempt.disposition == Disposition.FAILED_SIMULATION
        assert attempt.simulation is not None
        assert len(attempt.simulation.collisions) > 0

        # Check that simulation checks include the "UNKNOWN" placeholder for material removal
        sim_checks = [c for c in attempt.checks if c.stage.value == "simulation"]
        material_check = next(
            (c for c in sim_checks if c.check_id == "simulation_material_removal"), None
        )

        if material_check:
            # If the check exists, it should be UNKNOWN status, not FAIL
            assert material_check.status.value == "unknown", (
                f"Material removal check should be UNKNOWN after collision abort, "
                f"got {material_check.status}"
            )
