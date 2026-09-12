"""Main-agent repairs are driven by measured evidence, with fresh verification."""

import json
from types import SimpleNamespace

import pytest

from silta.controller import JobController, JobRequest
from silta.domain import Budget, JobState, SupervisorAction
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan, valid_plan
from silta.planner import PlanRequest, propose_plan
from silta.policy import POLICY_V0
from silta.providers import Completion, ProviderError
from silta.telemetry import Telemetry


def section(prompt, heading):
    return json.JSONDecoder().raw_decode(prompt.split(heading, 1)[1].lstrip())[0]


def draft_from(plan):
    return {k: plan[k] for k in ("setups", "operations", "clearance_mm", "notes")}


def completion(payload):
    return Completion(
        text=json.dumps(payload),
        parsed=payload,
        provider="test",
        model="feedback-model",
        prompt_tokens=10,
        completion_tokens=10,
        latency_s=0.01,
        finish_reason="stop",
        request_id="test",
        cost_usd=None,
        cost_status="unknown",
    )


class MeasurementRepairProvider:
    def __init__(self):
        self.calls = []

    async def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        prompt = kwargs["user"]
        previous = section(prompt, "Previous CAM plan to revise:")
        history = section(prompt, "Measured attempt history (latest five; fixed target):")
        latest = history[-1]
        draft = draft_from(previous)
        failures = [c for c in latest["checks"] if c["status"] == "fail"]
        for failure in failures:
            if failure["check_id"] == "tool_cutting_reach":
                for op in draft["operations"]:
                    if op["operation_id"] == failure["operation_id"]:
                        op["tool_id"] = "EM6-L"
            elif failure["check_id"] == "simulation_collision":
                assert latest["collisions"][0]["obstacle_kind"] == "fixture"
                draft["clearance_mm"] = (
                    max(f.z_max_mm for f in DEMO_SHOP.fixtures) + DEMO_SHOP.min_fixture_clearance_mm
                )
        return completion(draft)


@pytest.mark.asyncio
async def test_main_agent_measures_and_repairs_cam_until_verified(tmp_path):
    provider = MeasurementRepairProvider()
    controller = JobController(provider=provider, telemetry=Telemetry())
    request = JobRequest(
        session_id="measured-repair",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        seed_plan=naive_plan(),
        memory_enabled=False,
        artifact_dir=tmp_path,
        budget=Budget(max_attempts=3, max_model_calls=2, max_output_tokens=1234),
    )
    events = [e async for e in controller.run(request)]
    outcome = controller.outcomes[request.job_id]
    assert outcome.state is JobState.PASSED, outcome.message
    assert len(provider.calls) == 2
    assert all(c["max_tokens"] == 1234 for c in provider.calls)
    assert all(a.plan.spec_design_hash == DEMO_SPEC.design_hash for a in outcome.attempts)
    assert all(a.plan_source == "repair" for a in outcome.attempts[1:])
    measurements = [e.payload["measurements"] for e in events if e.type == "attempt_completed"]
    assert measurements[0]["simulation_status"] is None
    assert measurements[0]["estimated_machining_seconds"] is None
    assert measurements[1]["collision_count"] > 0
    assert measurements[1]["max_residual_mm"] is None
    assert measurements[1]["max_gouge_mm"] is None
    assert measurements[1]["coverage"] == []
    assert measurements[2]["material_removal_measured"] is True
    assert measurements[2]["estimated_machining_seconds"] > 0
    assert len(measurements[2]["coverage"]) == len(DEMO_SPEC.features)
    assert measurements[1]["trajectory_hash"] != measurements[2]["trajectory_hash"]
    assert any("clearance" in d for d in outcome.best_attempt.repair_diff)


@pytest.mark.asyncio
async def test_real_deterministic_repair_uses_collision_evidence(tmp_path):
    controller = JobController(telemetry=Telemetry())
    request = JobRequest(
        session_id="fallback-repair",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        seed_plan=naive_plan(),
        memory_enabled=False,
        artifact_dir=tmp_path,
    )
    _events = [e async for e in controller.run(request)]
    outcome = controller.outcomes[request.job_id]
    assert outcome.state is JobState.PASSED, outcome.message
    assert len(outcome.attempts) == 3
    assert outcome.best_attempt.plan.clearance_mm == (
        max(f.z_max_mm for f in DEMO_SHOP.fixtures) + DEMO_SHOP.min_fixture_clearance_mm
    )


@pytest.mark.asyncio
async def test_invalid_tool_is_repaired_within_remaining_call_budget():
    class InvalidThenValid:
        def __init__(self):
            self.calls = []

        async def complete_json(self, **kwargs):
            self.calls.append(kwargs)
            draft = draft_from(valid_plan().model_dump(mode="json"))
            if len(self.calls) == 1:
                draft["operations"][0]["tool_id"] = "invented-tool"
            return completion(draft)

    request = PlanRequest(
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        policy=POLICY_V0,
        previous_plan=None,
        failures=(),
        attempt_index=0,
        max_model_calls=2,
    )
    provider = InvalidThenValid()
    result = await propose_plan(request, provider)
    assert result.source == "model"
    assert result.usage.calls == 2
    assert "unknown tool invented-tool" in provider.calls[1]["user"]
    provider = InvalidThenValid()
    from dataclasses import replace

    result = await propose_plan(replace(request, max_model_calls=1), provider)
    assert len(provider.calls) == 1
    assert result.usage.calls == 1
    assert result.source == "deterministic_planner"
    assert result.fallback_reason


@pytest.mark.asyncio
async def test_supervisor_instruction_reaches_main_agent_with_incumbent(tmp_path, monkeypatch):
    async def improve(**kwargs):
        return SimpleNamespace(
            action=SupervisorAction.IMPROVE,
            explanation="Try a modest feed increase.",
            stop_reason=None,
            planning_instruction="Increase pocket feed by ten percent.",
        )

    monkeypatch.setattr("silta.supervisor.supervise", improve)
    captured = []

    class Optimizer:
        async def complete_json(self, **kwargs):
            captured.append(kwargs["user"])
            previous = section(kwargs["user"], "Previous CAM plan to revise:")
            draft = draft_from(previous)
            draft["operations"][0]["feed_mm_min"] *= 1.1
            return completion(draft)

    controller = JobController(provider=Optimizer(), telemetry=Telemetry())
    request = JobRequest(
        session_id="optimize-measured",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        seed_plan=valid_plan(),
        memory_enabled=False,
        artifact_dir=tmp_path,
        budget=Budget(supervised_loop_enabled=True, max_optimization_attempts=1),
    )
    events = [e async for e in controller.run(request)]
    outcome = controller.outcomes[request.job_id]
    assert outcome.state is JobState.PASSED, outcome.message
    assert len(outcome.attempts) == 2
    assert "Increase pocket feed by ten percent." in captured[0]
    assert outcome.attempts[1].parent_attempt_id == outcome.attempts[0].attempt_id
    measured = [e.payload["measurements"] for e in events if e.type == "attempt_completed"]
    assert measured[1]["estimated_machining_seconds"] < measured[0]["estimated_machining_seconds"]
    assert outcome.best_attempt_id == outcome.attempts[1].attempt_id
    assert any("feed_mm_min" in d for d in outcome.best_attempt.repair_diff)


def test_unsupported_fallback_does_not_blindly_raise_clearance():
    from silta.domain import CheckResult, CheckStage, CheckStatus, Severity
    from silta.planner import DeterministicPlanner

    failure = CheckResult(
        check_id="simulation_gouge",
        stage=CheckStage.SIMULATION,
        status=CheckStatus.FAIL,
        severity=Severity.BLOCKING,
        message="Gouge detected",
        actual=2.0,
        required=0.05,
        units="mm",
    )
    with pytest.raises(ProviderError, match="No supported deterministic repair"):
        DeterministicPlanner(DEMO_SPEC, DEMO_SHOP).plan(valid_plan(), (failure,))


def test_incomplete_simulator_does_not_emit_a_pass_check():
    from silta.controller import _simulation_checks
    from silta.domain import SimulationResult

    result = SimulationResult(
        simulation_id="unsupported-test",
        trajectory_hash="test",
        status="unsupported",
        grid_mm=1,
        max_residual_mm=0,
        max_gouge_mm=0,
        residual_threshold_mm=0.1,
        gouge_threshold_mm=0.1,
        elapsed_s=0,
        keyframe_count=0,
    )
    checks = _simulation_checks(result)
    assert len(checks) == 1
    assert checks[0].check_id == "simulation_incomplete"
    assert checks[0].blocking_failure
