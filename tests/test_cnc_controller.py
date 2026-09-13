"""Controller contract tests use explicit doubles, not live manufacturing evidence."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from silta.cnc.controller import Controller
from silta.cnc.models import (
    Artifact,
    Candidate,
    CheckResult,
    JobInputs,
    PromotionResult,
    ReusableProposal,
    SupervisorDecision,
    Target,
    VerificationResult,
)


@pytest.fixture
def inputs(tmp_path):
    drawing = tmp_path / "drawing.pdf"
    drawing.write_text("test drawing placeholder")
    return JobInputs(
        (Artifact.from_path(drawing),),
        {"axes": 3},
        {"T1": {}},
        {"stock": "test stock"},
        {"linear_mm": 0.1},
    )


class MainDouble:
    def __init__(self):
        self.calls = []
        self.change_target = False

    def establish_target(self, inputs, workspace):
        cad = Path(workspace) / "accepted.step"
        cad.write_text("accepted test geometry")
        return Target.from_paths({"step": str(cad)}, "test-double acceptance")

    def propose(self, context, previous, feedback, instructions, attempt):
        self.calls.append((previous, feedback, instructions))
        nc = Path(context.job_directory) / "workspace" / "candidate.nc"
        nc.write_text(f"G1 X{attempt}\n")
        return Candidate.from_paths(
            f"candidate-{attempt}",
            "wrong" if self.change_target else context.target.digest,
            {"nc": str(nc)},
            {"attempt": attempt},
        )


class ChecksDouble:
    def __init__(self, failures=()):
        self.failures = failures

    def run(self, candidate, context):
        failed = candidate.parameters["attempt"] in self.failures
        return CheckResult(not failed, ("bad check",) if failed else (), version="checks-v1")


class FusionDouble:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def verify(self, candidate, context):
        status, seconds = next(self.outcomes)
        self.calls.append(candidate)
        evidence = Path(context.job_directory) / "workspace" / "verification.txt"
        evidence.write_text(f"test evidence {candidate.id} {status}")
        return VerificationResult(
            status,
            status != "unknown",
            context.input_digest,
            candidate.digest,
            "test-verifier-v1",
            (Artifact.from_path(evidence),),
            "test internal CAM",
            ("collision",) if status == "failed" else (),
            seconds,
        )


class SupervisorDouble:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.calls = []

    def decide(self, context, candidate, verification, history):
        self.calls.append(candidate)
        return SupervisorDecision(next(self.actions), "try shorter linking paths")


def run(
    tmp_path,
    inputs,
    main=None,
    checks=None,
    fusion=None,
    supervisor=None,
    learner=None,
    evaluation=None,
    max_attempts=5,
    check_runner_factory=None,
):
    return Controller(
        main or MainDouble(),
        checks or ChecksDouble(),
        fusion or FusionDouble([("passed", 100)]),
        supervisor or SupervisorDouble(["stop"]),
        learner,
        evaluation,
        check_runner_factory,
    ).run(inputs, tmp_path / "jobs", "job", {"checks": "checks-v1"}, max_attempts)


def test_repairs_checks_then_simulation_then_supervisor_and_preserves_best(tmp_path, inputs):
    main = MainDouble()
    fusion = FusionDouble([("failed", 0), ("passed", 100), ("passed", 120)])
    supervisor = SupervisorDouble(["improve", "stop"])
    result = run(tmp_path, inputs, main, ChecksDouble([1]), fusion, supervisor)
    assert result.status == "completed"
    assert result.attempts == 4 and result.simulations == 3
    assert [x.id for x in supervisor.calls] == ["candidate-3", "candidate-4"]
    assert main.calls[1][1]["stage"] == "checks"
    assert main.calls[2][1]["stage"] == "simulation"
    assert main.calls[3][2] == "try shorter linking paths"
    assert result.best_candidate.id == "candidate-3"
    assert result.best_verification.machining_seconds == 100
    assert Path(result.best_candidate.artifacts["nc"].path).read_text() == "G1 X3\n"
    result.best_verification.evidence[0].verify()
    manifest = json.loads(Path(result.manifest_path).read_text())
    assert manifest["status"] == "completed"
    assert manifest["input_digest"] == inputs.digest


def test_target_change_never_reaches_simulation(tmp_path, inputs):
    main = MainDouble()
    main.change_target = True
    fusion = FusionDouble([])
    result = run(tmp_path, inputs, main=main, fusion=fusion, max_attempts=2)
    assert result.status == "incomplete"
    assert not fusion.calls and result.best_candidate is None


@pytest.mark.parametrize("defect", ["unknown", "unfinished", "stale", "no_evidence", "no_metric"])
def test_unproven_verification_never_reaches_supervisor(tmp_path, inputs, defect):
    class BadFusion(FusionDouble):
        def verify(self, candidate, context):
            result = super().verify(candidate, context)
            return {
                "unknown": replace(result, status="unknown"),
                "unfinished": replace(result, completed=False),
                "stale": replace(result, candidate_digest="another-candidate"),
                "no_evidence": replace(result, evidence=()),
                "no_metric": replace(result, machining_seconds=None),
            }[defect]

    supervisor = SupervisorDouble([])
    result = run(tmp_path, inputs, fusion=BadFusion([("passed", 100)]), supervisor=supervisor)
    assert result.status == "incomplete"
    assert not supervisor.calls and result.best_candidate is None


def test_limit_retains_incumbent_but_never_reports_completed(tmp_path, inputs):
    result = run(tmp_path, inputs, supervisor=SupervisorDouble(["improve"]), max_attempts=1)
    assert result.status == "incomplete"
    assert result.best_candidate is not None
    assert "limit" in result.reason


@pytest.mark.parametrize("promoted", [True, False])
def test_simulation_learned_checks_apply_to_next_attempt_only(tmp_path, inputs, promoted):
    observed_checks = []
    created_runners = []

    class VersionChecks:
        def __init__(self, ref):
            self.ref = ref

        def run(self, candidate, context):
            observed_checks.append((candidate.id, self.ref, dict(context.versions)))
            failed = self.ref == "checks-v2" and candidate.parameters["attempt"] == 2
            return CheckResult(
                not failed,
                ("learned fixture check",) if failed else (),
                version=self.ref,
            )

    def factory(ref):
        created_runners.append(ref)
        return VersionChecks(ref)

    class Learner:
        def propose_checks(self, context, candidate, verification):
            assert verification.status == "failed"
            return (
                ReusableProposal(
                    "p1",
                    "checks",
                    "checks-v1",
                    "checks-v2",
                    "check.py",
                    "prevent fixture collision",
                ),
            )

    class Gate:
        def evaluate(self, proposal, context):
            context.versions["checks"] = "checks-v2"
            context.versions["verifier"] = "do-not-adopt-this-unproposed-change"
            return PromotionResult(
                proposal.id,
                promoted,
                "paired test evaluation",
                ("weave://test",),
            )

    fusion = FusionDouble([("failed", 0), ("passed", 100)])
    main = MainDouble()
    result = run(
        tmp_path,
        inputs,
        main=main,
        checks=VersionChecks("checks-v1"),
        fusion=fusion,
        learner=Learner(),
        evaluation=Gate(),
        check_runner_factory=factory,
    )
    assert result.status == "completed"
    manifest = json.loads(Path(result.manifest_path).read_text())
    assert manifest["versions"]["checks"] == "checks-v1"
    expected = "checks-v2" if promoted else "checks-v1"
    assert manifest["current_versions"] == {"checks": expected}
    assert created_runners == (["checks-v2"] if promoted else [])
    assert observed_checks[0][1:] == ("checks-v1", {"checks": "checks-v1"})
    assert all(row[1:] == (expected, {"checks": expected}) for row in observed_checks[1:])
    assert result.attempts == (3 if promoted else 2)
    assert [candidate.id for candidate in fusion.calls] == [
        "candidate-1",
        "candidate-3" if promoted else "candidate-2",
    ]
    if promoted:
        assert main.calls[2][1]["stage"] == "checks"
    candidate_events = [e for e in manifest["events"] if e["event"] == "candidate_created"]
    assert candidate_events[0]["versions"] == {"checks": "checks-v1"}
    assert candidate_events[1]["versions"] == {"checks": expected}
    assert any(e["event"] == "promotion_evaluated" for e in manifest["events"])


def test_promoted_main_and_supervisor_prompts_apply_to_subsequent_calls(tmp_path, inputs):
    pins = {
        "checks": "checks-v1",
        "main_prompt": "main-v1",
        "supervisor_prompt": "supervisor-v1",
        "verifier": "test-verifier-v1",
    }
    main_contexts, supervisor_contexts = [], []

    class Main(MainDouble):
        def propose(self, context, *args):
            main_contexts.append(context)
            return super().propose(context, *args)

    class Supervisor:
        def decide(self, context, candidate, verification, history):
            supervisor_contexts.append(context)
            proposals = (
                tuple(
                    ReusableProposal(kind, kind, old, new, "prompt.md", "shorter paths")
                    for kind, old, new in (
                        ("main_prompt", "main-v1", "main-v2"),
                        ("supervisor_prompt", "supervisor-v1", "supervisor-v2"),
                    )
                )
                if len(supervisor_contexts) == 1
                else ()
            )
            return SupervisorDecision(
                "improve" if proposals else "stop",
                "try a different toolpath",
                proposals,
            )

    class Gate:
        def evaluate(self, proposal, context):
            return PromotionResult(proposal.id, True, "paired evaluation passed", ("weave://test",))

    result = Controller(
        Main(),
        ChecksDouble(),
        FusionDouble([("passed", 100), ("passed", 90)]),
        Supervisor(),
        evaluation=Gate(),
    ).run(inputs, tmp_path / "jobs", "job", pins)
    assert result.status == "completed"
    expected = {**pins, "main_prompt": "main-v2", "supervisor_prompt": "supervisor-v2"}
    assert [context.versions for context in main_contexts] == [pins, expected]
    assert [context.versions for context in supervisor_contexts] == [pins, expected]
    assert main_contexts[0].target.digest == main_contexts[1].target.digest
    assert all(context.input_digest == inputs.digest for context in main_contexts)
    assert pins["main_prompt"] == "main-v1"
    manifest = json.loads(Path(result.manifest_path).read_text())
    assert manifest["versions"] == pins
    assert manifest["current_versions"] == expected
    decisions = [e for e in manifest["events"] if e["event"] == "supervisor_decision"]
    assert [e["versions"] for e in decisions] == [pins, expected]


@pytest.mark.parametrize("defect", ["missing_evidence", "wrong_base", "verifier_change"])
def test_invalid_promotion_cannot_change_running_versions(tmp_path, inputs, defect):
    class Learner:
        def propose_checks(self, context, candidate, verification):
            return (
                ReusableProposal(
                    "proposal",
                    "verifier" if defect == "verifier_change" else "checks",
                    "wrong-base" if defect == "wrong_base" else "checks-v1",
                    "checks-v2",
                    "change.py",
                    "test proposal",
                ),
            )

    class Gate:
        def evaluate(self, proposal, context):
            return PromotionResult(
                proposal.id,
                True,
                "test gate",
                () if defect == "missing_evidence" else ("weave://test",),
            )

    factories = []
    result = run(
        tmp_path,
        inputs,
        fusion=FusionDouble([("failed", 0)]),
        learner=Learner(),
        evaluation=Gate(),
        check_runner_factory=lambda ref: factories.append(ref),
    )
    assert result.status == "incomplete"
    assert result.attempts == 1
    assert factories == []
    manifest = json.loads(Path(result.manifest_path).read_text())
    assert manifest["current_versions"] == {"checks": "checks-v1"}
    assert not any(e["event"] == "promoted_change_applied" for e in manifest["events"])


def test_adapter_failure_persists_failure_and_best_so_far(tmp_path, inputs):
    result = run(tmp_path, inputs, supervisor=SupervisorDouble(["improve"]))
    assert result.status == "incomplete"
    assert result.best_candidate is not None
    assert "StopIteration" in result.reason
    assert json.loads(Path(result.manifest_path).read_text())["status"] == "incomplete"


def test_input_mutation_cannot_be_hidden_by_adapter(tmp_path, inputs):
    class Mutator(MainDouble):
        def propose(self, context, *args):
            context.inputs.machine["axes"] = 5
            return super().propose(context, *args)

    result = run(tmp_path, inputs, main=Mutator())
    assert result.status == "completed"
    assert inputs.machine["axes"] == 3
    manifest = json.loads(Path(result.manifest_path).read_text())
    assert manifest["inputs"]["machine"]["axes"] == 3


def test_duplicate_job_does_not_repeat_external_operations(tmp_path, inputs):
    run(tmp_path, inputs)
    main = MainDouble()
    with pytest.raises(FileExistsError):
        run(tmp_path, inputs, main=main)
    assert not main.calls


def test_faster_result_with_changed_verification_scope_cannot_replace_incumbent(tmp_path, inputs):
    class ChangedScope(FusionDouble):
        def verify(self, candidate, context):
            result = super().verify(candidate, context)
            if len(self.calls) > 1:
                return replace(result, coverage="weaker coverage")
            return result

    supervisor = SupervisorDouble(["improve"])
    result = run(
        tmp_path,
        inputs,
        fusion=ChangedScope([("passed", 100), ("passed", 1)]),
        supervisor=supervisor,
    )
    assert result.status == "incomplete"
    assert result.best_verification.machining_seconds == 100
    assert len(supervisor.calls) == 1
    assert "not comparable" in result.reason


def test_two_file_learning_applies_now_and_survives_next_part(tmp_path, inputs):
    """Exercise direct learning with fake simulation, not manufacturing evidence."""
    from silta.cnc.learning import BASIC_PROMPT, SharedLearning

    learning = SharedLearning(tmp_path / "learning")
    assert len(list(learning.root.iterdir())) == 2
    initial = learning.active()
    observed_prompts = []

    class Main(MainDouble):
        def propose(self, context, *args):
            observed_prompts.append(learning.get(context.versions["main_prompt"])["content"])
            return super().propose(context, *args)

    class Learner:
        def propose_checks(self, context, candidate, verification):
            # Fixture-only rule: the next part's first candidate must be caught.
            source = (
                "def check(data):\n"
                '    bad = data["candidate"]["parameters"]["attempt"] == 1\n'
                '    return {"passed": not bad, "issues": ["test issue"] if bad else []}\n'
            )
            ref = learning.put("checks", source)
            return (
                ReusableProposal(
                    "learn-check",
                    "checks",
                    context.versions["checks"],
                    ref,
                    "test-proposal",
                    "test failure",
                ),
            )

    class Judge:
        def __init__(self):
            self.calls = 0

        def decide(self, context, candidate, verification, history):
            self.calls += 1
            if self.calls > 1:
                return SupervisorDecision("stop")
            ref = learning.put("main_prompt", BASIC_PROMPT + "\nA reusable test lesson.\n")
            return SupervisorDecision(
                "improve",
                "test a shorter path",
                (
                    ReusableProposal(
                        "learn-prompt",
                        "main_prompt",
                        context.versions["main_prompt"],
                        ref,
                        "test-proposal",
                        "judge instruction",
                    ),
                ),
            )

    def controller(outcomes, judge, learner=None):
        return Controller(
            Main(),
            learning.make_checks(learning.active()["checks"]),
            FusionDouble(outcomes),
            judge,
            learner=learner,
            learning=learning,
            check_runner_factory=learning.make_checks,
        )

    first = controller([("failed", 0), ("passed", 100), ("passed", 90)], Judge(), Learner()).run(
        inputs,
        tmp_path / "jobs",
        "part-a",
        initial,
    )
    assert first.status == "completed", first.reason
    assert observed_prompts[:2] == [BASIC_PROMPT, BASIC_PROMPT]
    assert "reusable test lesson" in observed_prompts[2]
    assert learning.active() != initial
    manifest = json.loads(Path(first.manifest_path).read_text())
    assert sum(e["event"] == "learning_change_saved" for e in manifest["events"]) == 2
    assert not any(e["event"] == "promotion_evaluated" for e in manifest["events"])
    # A later process can inspect exactly what changed without the in-memory store.
    sources = manifest["learning_sources"]
    assert len(sources) == 4
    assert Path(sources[initial["main_prompt"]]["path"]).read_text() == BASIC_PROMPT
    final_ref = manifest["current_versions"]["main_prompt"]
    assert "reusable test lesson" in Path(sources[final_ref]["path"]).read_text()
    for item in sources.values():
        Artifact(item["path"], item["sha256"]).verify()

    # Simulate a process restart: only the same two files provide learned state.
    learning = SharedLearning(learning.root)
    assert len(list(learning.root.iterdir())) == 2
    second = controller([("passed", 80)], SupervisorDouble(["stop"])).run(
        inputs,
        tmp_path / "jobs",
        "part-b",
        learning.active(),
    )
    assert second.status == "completed", second.reason
    assert second.attempts == 2
    assert second.simulations == 1  # learned check caught attempt 1 before simulation
    assert "reusable test lesson" in observed_prompts[-1]
    assert len(list(learning.root.iterdir())) == 2


def test_completed_toolpath_failure_returns_to_main_without_simulation(tmp_path, inputs):
    from silta.cnc.models import CandidateGenerationError

    class Main(MainDouble):
        def propose(self, context, previous, feedback, instructions, attempt):
            if attempt == 1:
                raise CandidateGenerationError(
                    {
                        "stage": "toolpath_generation",
                        "issues": ["empty toolpath"],
                        "source": "failed source",
                    }
                )
            assert feedback["stage"] == "toolpath_generation"
            assert feedback["source"] == "failed source"
            return super().propose(context, previous, feedback, instructions, attempt)

    result = run(tmp_path, inputs, main=Main(), fusion=FusionDouble([("passed", 100)]))
    assert result.status == "completed"
    assert result.attempts == 2 and result.simulations == 1


def test_resume_retains_verified_incumbent_when_trial_is_slower(tmp_path, inputs):
    first = Controller(
        MainDouble(), ChecksDouble(), FusionDouble([("passed", 100)]), SupervisorDouble(["stop"])
    ).run(inputs, tmp_path, "first", {})
    judge = SupervisorDouble(["stop"])
    result = Controller(MainDouble(), ChecksDouble(), FusionDouble([("passed", 120)]), judge).run(
        inputs,
        tmp_path,
        "resumed",
        {},
        verified_incumbent=(
            first.best_candidate,
            first.best_verification,
        ),
    )
    assert result.status == "completed"
    assert result.best_verification.machining_seconds == 100
    assert result.simulations == 1
    assert Path(result.best_candidate.artifacts["nc"].path).parent.name == "attempt-0000"
    manifest = json.loads(Path(result.manifest_path).read_text())
    assert manifest["best_candidate"] == manifest["result"]["best_candidate"]
    assert manifest["best_verification"] == manifest["result"]["best_verification"]
    result.best_candidate.verify()
    assert judge.calls[0].digest == first.best_candidate.digest


def test_resume_rejects_mismatched_verification_before_new_candidate(tmp_path, inputs):
    first = Controller(
        MainDouble(), ChecksDouble(), FusionDouble([("passed", 100)]), SupervisorDouble(["stop"])
    ).run(inputs, tmp_path, "first", {})
    main = MainDouble()
    result = Controller(main, ChecksDouble(), FusionDouble([]), SupervisorDouble([])).run(
        inputs,
        tmp_path,
        "resumed",
        {},
        verified_incumbent=(
            first.best_candidate,
            replace(first.best_verification, input_digest="other-setup"),
        ),
    )
    assert result.status == "incomplete"
    assert "does not match" in result.reason
    assert not main.calls


def test_unresolved_improvement_returns_verified_incumbent_to_supervisor(tmp_path, inputs):
    from silta.cnc.models import CandidateProposalUnresolved

    class Main(MainDouble):
        def propose(self, context, previous, feedback, instructions, attempt):
            if attempt == 2:
                raise CandidateProposalUnresolved(["Entry stock clearance is not established"])
            return super().propose(context, previous, feedback, instructions, attempt)

    class Judge(SupervisorDouble):
        def decide(self, context, candidate, verification, history):
            if self.calls:
                assert history[-1]["event"] == "cam_proposal_unresolved"
                assert "Entry stock" in history[-1]["issues"][0]
                assert candidate.digest == self.calls[0].digest
                assert verification.status == "passed" and verification.completed
            return super().decide(context, candidate, verification, history)

    fusion = FusionDouble([("passed", 100)])
    judge = Judge(["improve", "stop"])
    result = run(tmp_path, inputs, main=Main(), fusion=fusion, supervisor=judge)
    assert result.status == "completed"
    assert result.best_verification.machining_seconds == 100
    assert result.attempts == 2 and result.simulations == 1
    assert len(judge.calls) == 2 and len(fusion.calls) == 1
    events = json.loads(Path(result.manifest_path).read_text())["events"]
    assert sum(e["event"] == "candidate_created" for e in events) == 1


def test_unresolved_first_cam_never_reaches_supervisor(tmp_path, inputs):
    from silta.cnc.models import CandidateProposalUnresolved

    class Main(MainDouble):
        def propose(self, *args):
            raise CandidateProposalUnresolved(["Required dimension is missing"])

    judge, fusion = SupervisorDouble([]), FusionDouble([])
    result = run(tmp_path, inputs, main=Main(), fusion=fusion, supervisor=judge)
    assert result.status == "incomplete" and result.best_candidate is None
    assert not judge.calls and not fusion.calls
