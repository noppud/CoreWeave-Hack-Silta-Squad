import json
import subprocess
import sys
from dataclasses import replace

from silta.controller import JobController, JobRequest
from silta.domain import Budget, Disposition
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan, reach_repaired_plan, valid_plan
from silta.learning_sandbox import VALIDATION_SCRIPT, WandbLessonValidator
from silta.memory import LearningMemory
from silta.planner import PlanRequest, PlanResult, _build_prompt
from silta.policy import POLICY_V0, POLICY_V1
from silta.storage import LocalStorage


async def test_cold_then_warm_survives_new_controller_and_rechecks(tmp_path):
    memory = LearningMemory(LocalStorage(tmp_path / "store"))
    calls = []

    async def planner(request, provider):
        calls.append(request)
        plan = reach_repaired_plan() if len(calls) == 1 else valid_plan()
        return PlanResult(plan, "repair", None, None, ())

    cold = JobRequest(
        session_id="judge-one",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        seed_plan=naive_plan(),
        artifact_dir=tmp_path / "cold",
        budget=Budget(max_attempts=3),
    )
    controller = JobController(planner=planner, memory=memory)
    cold_events = [e async for e in controller.run(cold)]
    outcome = controller.outcomes[cold.job_id]
    assert [a.disposition for a in outcome.attempts] == [
        Disposition.FAILED_CHECKS,
        Disposition.FAILED_SIMULATION,
        Disposition.PASSED,
    ]
    assert len([e for e in cold_events if e.type == "memory_written"]) == 3
    assert calls[0].memory_episode_ids == (outcome.attempts[0].attempt_id,)
    restarted = LearningMemory(LocalStorage(tmp_path / "store"))
    # Exact synthetic demo can be recalled by a new judge; other input never shares.
    recall = restarted.recall("judge-two", DEMO_SPEC, DEMO_SHOP, POLICY_V0)
    assert recall.recipe is not None
    assert recall.instructions == (), "unvalidated advice must stay pending"
    warm = replace(cold, session_id="judge-two", job_id="warm-job", artifact_dir=tmp_path / "warm")
    fresh = JobController(planner=planner, memory=restarted)
    warm_events = [e async for e in fresh.run(warm)]
    warm_outcome = fresh.outcomes[warm.job_id]
    assert len(warm_outcome.attempts) == 1
    assert warm_outcome.attempts[0].plan_source == "memory_recipe"
    assert warm_outcome.attempts[0].disposition is Disposition.PASSED
    assert any(e.type == "simulation_started" for e in warm_events)
    assert len(calls) == 2, "warm recall avoids new model calls, not verification"
    assert warm_outcome.attempts[0].plan.spec_design_hash == DEMO_SPEC.design_hash
    assert restarted.recall("judge-two", DEMO_SPEC, DEMO_SHOP, POLICY_V1).recipe is None
    changed = DEMO_SPEC.model_copy(update={"material": "steel"})
    assert restarted.recall("judge-two", changed, DEMO_SHOP, POLICY_V0).recipe is None


def test_private_scopes_and_validator_revision_invalidate_recall(tmp_path, monkeypatch):
    memory = LearningMemory(LocalStorage(tmp_path))
    private = DEMO_SPEC.model_copy(update={"material": "private-material"})
    one = memory.namespace("one", private, DEMO_SHOP, POLICY_V0)
    two = memory.namespace("two", private, DEMO_SHOP, POLICY_V0)
    assert one[0] != two[0]
    uploaded = DEMO_SPEC.model_copy(update={"source_asset_ids": ("customer-upload",)})
    assert memory.namespace("one", uploaded, DEMO_SHOP, POLICY_V0)[0] != "public-demo"
    named = DEMO_SPEC.model_copy(update={"spec_id": "customer-copy"})
    assert memory.namespace("one", named, DEMO_SHOP, POLICY_V0)[0] != "public-demo"
    before = memory.namespace("one", DEMO_SPEC, DEMO_SHOP, POLICY_V0)
    monkeypatch.setattr("silta.memory.validator_fingerprint", lambda: "new-validator")
    assert before[1] != memory.namespace("one", DEMO_SPEC, DEMO_SHOP, POLICY_V0)[1]


def test_sandbox_template_and_prompt_consumption():
    result = subprocess.run(
        [sys.executable, "-c", VALIDATION_SCRIPT, json.dumps({"template": "fixture_clearance_v1"})],
        capture_output=True,
        text=True,
        check=True,
    )
    evidence = json.loads(result.stdout)
    assert evidence["passed"] and len(evidence["cases"]) == 6
    request = PlanRequest(
        DEMO_SPEC,
        DEMO_SHOP,
        POLICY_V0,
        None,
        (),
        0,
        memory_instructions=("Use the proven fixture clearance.",),
        memory_episode_ids=("evidence-1",),
    )
    _, prompt = _build_prompt(request)
    assert "Use the proven fixture clearance." in prompt and "evidence-1" in prompt


def test_unavailable_sandbox_never_claims_pass(monkeypatch):
    from wandb.sandbox import Sandbox

    def reject(*args, **kwargs):
        raise PermissionError("no organization access")

    monkeypatch.setattr(Sandbox, "run", reject)
    report = WandbLessonValidator().validate({"lesson_id": "lesson-test"})
    assert report["status"] == "unavailable"
    assert report["error_type"] == "PermissionError"


async def test_pending_advice_requires_a_persisted_passed_validation(tmp_path):
    memory = LearningMemory(LocalStorage(tmp_path / "store"))
    controller = JobController(memory=memory)
    request = JobRequest(
        session_id="one",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        seed_plan=reach_repaired_plan(),
        budget=Budget(max_attempts=1),
        artifact_dir=tmp_path / "job",
    )
    _ = [e async for e in controller.run(request)]
    assert memory.recall("one", DEMO_SPEC, DEMO_SHOP, POLICY_V0).instructions == ()

    class Runner:
        def __init__(self, status):
            self.status = status

        def validate(self, lesson):
            return {
                "report_id": "report-" + self.status,
                "lesson_id": lesson["lesson_id"],
                "status": self.status,
                "backend": "test",
            }

    memory.validate("one", DEMO_SPEC, DEMO_SHOP, POLICY_V0, Runner("unavailable"))
    assert memory.recall("one", DEMO_SPEC, DEMO_SHOP, POLICY_V0).instructions == ()
    memory.validate("one", DEMO_SPEC, DEMO_SHOP, POLICY_V0, Runner("passed"))
    recall = LearningMemory(LocalStorage(tmp_path / "store")).recall(
        "one", DEMO_SPEC, DEMO_SHOP, POLICY_V0
    )
    assert len(recall.instructions) == 1
    assert "simulation_collision" in recall.observations[0]


async def test_failed_remembered_recipe_is_rejected_by_fresh_simulation(tmp_path):
    from silta.domain import SimulationStatus
    from silta.simulation import simulate

    memory = LearningMemory(LocalStorage(tmp_path / "store"))
    cold = JobRequest(
        session_id="one",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        seed_plan=valid_plan(),
        budget=Budget(max_attempts=1),
        artifact_dir=tmp_path / "cold",
    )
    controller = JobController(memory=memory)
    _ = [e async for e in controller.run(cold)]

    def failing_sim(*args):
        result, replay = simulate(*args)
        return result.model_copy(
            update={"status": SimulationStatus.INCOMPLETE_REMOVAL, "max_residual_mm": 12.0}
        ), replay

    warm = replace(cold, job_id="warm-rejected", artifact_dir=tmp_path / "warm")
    another = JobController(memory=memory, simulate_fn=failing_sim)
    _ = [e async for e in another.run(warm)]
    outcome = another.outcomes[warm.job_id]
    assert outcome.attempts[0].plan_source == "memory_recipe"
    assert outcome.best_attempt is None
    assert outcome.attempts[0].disposition is Disposition.FAILED_SIMULATION
