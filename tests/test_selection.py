"""Test pure selection logic without I/O."""

from datetime import UTC, datetime

from silta.domain import (
    Attempt,
    CheckResult,
    CheckStage,
    CheckStatus,
    Disposition,
    Operation,
    OperationKind,
    OptimizationObjective,
    ProcessPlan,
    Segment,
    Setup,
    Severity,
    SimulationResult,
    SimulationStatus,
    Trajectory,
)
from silta.fixtures import DEMO_SHOP, DEMO_SPEC
from silta.selection import choose_best, is_feasible, metrics_for


def _make_attempt(
    *,
    attempt_id: str,
    disposition: Disposition,
    checks: list[CheckResult] | None = None,
    simulation: SimulationResult | None = None,
    plan: ProcessPlan | None = None,
) -> Attempt:
    """Helper to build test attempts."""
    return Attempt(
        attempt_id=attempt_id,
        job_id="test-job",
        index=0,
        parent_attempt_id=None,
        policy_version="test-v0",
        origin="fixture",
        plan=plan,
        plan_source="model",
        checks=tuple(checks or []),
        trajectory_hash="test-traj-hash" if simulation else None,
        simulation=simulation,
        usage=None,
        disposition=disposition,
        repair_diff=(),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )


def _passing_check(check_id: str = "test_pass") -> CheckResult:
    return CheckResult(
        check_id=check_id,
        stage=CheckStage.PREFLIGHT,
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        message="Passed",
    )


def _blocking_fail(check_id: str = "test_fail") -> CheckResult:
    return CheckResult(
        check_id=check_id,
        stage=CheckStage.PREFLIGHT,
        status=CheckStatus.FAIL,
        severity=Severity.BLOCKING,
        message="Failed",
    )


def _passing_simulation() -> SimulationResult:
    return SimulationResult(
        simulation_id="test-sim",
        trajectory_hash="test-traj",
        status=SimulationStatus.PASS,
        grid_mm=0.5,
        collisions=(),
        coverage=(),
        max_residual_mm=0.0,
        max_gouge_mm=0.0,
        residual_threshold_mm=0.15,
        gouge_threshold_mm=0.15,
        elapsed_s=1.0,
        keyframe_count=10,
    )


def _collision_simulation() -> SimulationResult:
    return SimulationResult(
        simulation_id="test-sim",
        trajectory_hash="test-traj",
        status=SimulationStatus.COLLISION,
        grid_mm=0.5,
        collisions=(),
        coverage=(),
        max_residual_mm=0.0,
        max_gouge_mm=0.0,
        residual_threshold_mm=0.15,
        gouge_threshold_mm=0.15,
        elapsed_s=1.0,
        keyframe_count=10,
    )


def _test_plan() -> ProcessPlan:
    return ProcessPlan(
        plan_id="test-plan",
        policy_version="test-v0",
        spec_design_hash=DEMO_SPEC.design_hash,
        shop_hash=DEMO_SHOP.shop_hash,
        setups=(Setup(setup_id="setup1", description="Test setup"),),
        operations=(
            Operation(
                operation_id="op1",
                setup_id="setup1",
                feature_id="feature1",
                tool_id="tool1",
                kind=OperationKind.POCKET_RASTER,
                stepdown_mm=2.0,
                stepover_mm=1.0,
                entry="plunge",
                feed_mm_min=500.0,
                spindle_rpm=10000.0,
            ),
        ),
        clearance_mm=20.0,
    )


class TestIsFeasible:
    """Test the feasibility predicate."""

    def test_passed_attempt_with_all_checks_passed_is_feasible(self):
        """Disposition PASSED with simulation PASS is feasible."""
        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=_test_plan(),
        )
        assert is_feasible(attempt) is True

    def test_failed_checks_is_not_feasible(self):
        """Any blocking check failure makes it infeasible."""
        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.FAILED_CHECKS,
            checks=[_blocking_fail()],
            simulation=None,
            plan=_test_plan(),
        )
        assert is_feasible(attempt) is False

    def test_failed_simulation_is_not_feasible(self):
        """Simulation collision makes it infeasible."""
        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.FAILED_SIMULATION,
            checks=[_passing_check()],
            simulation=_collision_simulation(),
            plan=_test_plan(),
        )
        assert is_feasible(attempt) is False

    def test_no_simulation_is_not_feasible(self):
        """Missing simulation result is infeasible."""
        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=None,
            plan=_test_plan(),
        )
        assert is_feasible(attempt) is False

    def test_no_plan_is_not_feasible(self):
        """Missing plan is infeasible."""
        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=None,
        )
        assert is_feasible(attempt) is False


class TestMetricsFor:
    """Test metrics extraction."""

    def test_metrics_computed_from_feasible_attempt(self):
        """A feasible attempt produces complete metrics."""
        plan = _test_plan()
        trajectory = Trajectory(
            trajectory_id="traj-1",
            plan_id="test-plan",
            spec_design_hash=DEMO_SPEC.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            compiler_version="test-1",
            initial_x_mm=0.0,
            initial_y_mm=0.0,
            initial_z_mm=30.0,
            segments=(
                Segment(
                    segment_id="s001",
                    operation_id="op1",
                    tool_id="tool1",
                    kind="feed",
                    start_x_mm=0.0,
                    start_y_mm=0.0,
                    start_z_mm=0.0,
                    end_x_mm=10.0,
                    end_y_mm=0.0,
                    end_z_mm=0.0,
                    feed_mm_min=500.0,
                    cutting=True,
                    duration_s=1.2,
                ),
            ),
            max_step_mm=0.25,
        )

        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=plan,
        )

        metrics = metrics_for(attempt, trajectory, DEMO_SHOP, plan)

        assert metrics.verified is True
        assert metrics.estimated_motion_seconds == trajectory.estimated_seconds
        assert metrics.setups == 1
        assert metrics.verification_evidence is not None

    def test_metrics_marks_infeasible_as_unverified(self):
        """An infeasible attempt has verified=False."""
        plan = _test_plan()
        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.FAILED_CHECKS,
            checks=[_blocking_fail()],
            simulation=None,
            plan=plan,
        )

        metrics = metrics_for(attempt, None, DEMO_SHOP, plan)

        assert metrics.verified is False
        assert metrics.verification_evidence is None


class TestChooseBest:
    """Test deterministic incumbent selection."""

    def test_feasible_candidate_replaces_no_incumbent(self):
        """First feasible candidate becomes incumbent."""
        plan = _test_plan()
        trajectory = Trajectory(
            trajectory_id="traj-1",
            plan_id="test-plan",
            spec_design_hash=DEMO_SPEC.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            compiler_version="test-1",
            initial_x_mm=0.0,
            initial_y_mm=0.0,
            initial_z_mm=30.0,
            segments=(
                Segment(
                    segment_id="s001",
                    operation_id="op1",
                    tool_id="tool1",
                    kind="feed",
                    start_x_mm=0.0,
                    start_y_mm=0.0,
                    start_z_mm=0.0,
                    end_x_mm=10.0,
                    end_y_mm=0.0,
                    end_z_mm=0.0,
                    feed_mm_min=500.0,
                    cutting=True,
                    duration_s=1.2,
                ),
            ),
            max_step_mm=0.25,
        )

        attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=plan,
        )

        candidate = metrics_for(attempt, trajectory, DEMO_SHOP, plan)
        objective = OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS

        chosen = choose_best(None, candidate, objective)
        assert chosen.attempt_id == "a1"

    def test_infeasible_candidate_never_replaces_feasible_incumbent(self):
        """Infeasible candidate cannot beat feasible incumbent."""
        plan = _test_plan()
        trajectory = Trajectory(
            trajectory_id="traj-1",
            plan_id="test-plan",
            spec_design_hash=DEMO_SPEC.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            compiler_version="test-1",
            initial_x_mm=0.0,
            initial_y_mm=0.0,
            initial_z_mm=30.0,
            segments=(
                Segment(
                    segment_id="s001",
                    operation_id="op1",
                    tool_id="tool1",
                    kind="feed",
                    start_x_mm=0.0,
                    start_y_mm=0.0,
                    start_z_mm=0.0,
                    end_x_mm=10.0,
                    end_y_mm=0.0,
                    end_z_mm=0.0,
                    feed_mm_min=500.0,
                    cutting=True,
                    duration_s=1.2,
                ),
            ),
            max_step_mm=0.25,
        )

        feasible_attempt = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=plan,
        )
        incumbent = metrics_for(feasible_attempt, trajectory, DEMO_SHOP, plan)

        infeasible_attempt = _make_attempt(
            attempt_id="a2",
            disposition=Disposition.FAILED_CHECKS,
            checks=[_blocking_fail()],
            simulation=None,
            plan=plan,
        )
        candidate = metrics_for(infeasible_attempt, None, DEMO_SHOP, plan)

        objective = OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS

        chosen = choose_best(incumbent, candidate, objective)
        assert chosen.attempt_id == "a1"  # incumbent unchanged

    def test_better_candidate_replaces_incumbent_by_objective(self):
        """Candidate with better objective value replaces incumbent."""
        plan_slow = _test_plan()
        plan_fast = plan_slow.model_copy()

        # Build trajectory with different times
        traj_slow = Trajectory(
            trajectory_id="traj-slow",
            plan_id="plan-slow",
            spec_design_hash=DEMO_SPEC.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            compiler_version="test-1",
            initial_x_mm=0.0,
            initial_y_mm=0.0,
            initial_z_mm=30.0,
            segments=(
                Segment(
                    segment_id="s001",
                    operation_id="op1",
                    tool_id="tool1",
                    kind="feed",
                    start_x_mm=0.0,
                    start_y_mm=0.0,
                    start_z_mm=0.0,
                    end_x_mm=10.0,
                    end_y_mm=0.0,
                    end_z_mm=0.0,
                    feed_mm_min=500.0,
                    cutting=True,
                    duration_s=10.0,  # slower
                ),
            ),
            max_step_mm=0.25,
        )

        traj_fast = Trajectory(
            trajectory_id="traj-fast",
            plan_id="plan-fast",
            spec_design_hash=DEMO_SPEC.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            compiler_version="test-1",
            initial_x_mm=0.0,
            initial_y_mm=0.0,
            initial_z_mm=30.0,
            segments=(
                Segment(
                    segment_id="s001",
                    operation_id="op1",
                    tool_id="tool1",
                    kind="feed",
                    start_x_mm=0.0,
                    start_y_mm=0.0,
                    start_z_mm=0.0,
                    end_x_mm=10.0,
                    end_y_mm=0.0,
                    end_z_mm=0.0,
                    feed_mm_min=500.0,
                    cutting=True,
                    duration_s=5.0,  # faster
                ),
            ),
            max_step_mm=0.25,
        )

        attempt_slow = _make_attempt(
            attempt_id="a-slow",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=plan_slow,
        )
        incumbent = metrics_for(attempt_slow, traj_slow, DEMO_SHOP, plan_slow)

        attempt_fast = _make_attempt(
            attempt_id="a-fast",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=plan_fast,
        )
        candidate = metrics_for(attempt_fast, traj_fast, DEMO_SHOP, plan_fast)

        objective = OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS

        chosen = choose_best(incumbent, candidate, objective)
        assert chosen.attempt_id == "a-fast"  # faster candidate wins

    def test_tie_keeps_incumbent(self):
        """When objective values are within tolerance, incumbent stays."""
        plan = _test_plan()
        trajectory = Trajectory(
            trajectory_id="traj-1",
            plan_id="test-plan",
            spec_design_hash=DEMO_SPEC.design_hash,
            shop_hash=DEMO_SHOP.shop_hash,
            compiler_version="test-1",
            initial_x_mm=0.0,
            initial_y_mm=0.0,
            initial_z_mm=30.0,
            segments=(
                Segment(
                    segment_id="s001",
                    operation_id="op1",
                    tool_id="tool1",
                    kind="feed",
                    start_x_mm=0.0,
                    start_y_mm=0.0,
                    start_z_mm=0.0,
                    end_x_mm=10.0,
                    end_y_mm=0.0,
                    end_z_mm=0.0,
                    feed_mm_min=500.0,
                    cutting=True,
                    duration_s=100.0,
                ),
            ),
            max_step_mm=0.25,
        )

        attempt1 = _make_attempt(
            attempt_id="a1",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=plan,
        )
        incumbent = metrics_for(attempt1, trajectory, DEMO_SHOP, plan)

        # Candidate differs by less than tolerance (0.5s)
        trajectory2 = trajectory.model_copy(
            update={
                "segments": (
                    Segment(
                        segment_id="s001",
                        operation_id="op1",
                        tool_id="tool1",
                        kind="feed",
                        start_x_mm=0.0,
                        start_y_mm=0.0,
                        start_z_mm=0.0,
                        end_x_mm=10.0,
                        end_y_mm=0.0,
                        end_z_mm=0.0,
                        feed_mm_min=500.0,
                        cutting=True,
                        duration_s=100.2,  # tiny difference
                    ),
                )
            }
        )

        attempt2 = _make_attempt(
            attempt_id="a2",
            disposition=Disposition.PASSED,
            checks=[_passing_check()],
            simulation=_passing_simulation(),
            plan=plan,
        )
        candidate = metrics_for(attempt2, trajectory2, DEMO_SHOP, plan)

        objective = OptimizationObjective.ESTIMATED_TOTAL_MACHINING_SECONDS

        chosen = choose_best(incumbent, candidate, objective)
        assert chosen.attempt_id == "a1"  # incumbent unchanged
