from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from silta.cnc.benchmarks import (
    BenchmarkRunner,
    capture_case,
    register_dataset,
    validate_case,
)
from silta.cnc.controller import Controller
from silta.cnc.evaluation import VersionStore
from silta.cnc.models import (
    Artifact,
    Candidate,
    CheckResult,
    JobContext,
    JobInputs,
    SupervisorDecision,
    Target,
    VerificationResult,
)


class FixtureMain:
    def __init__(self, target, initially_bad=False, seconds=100):
        self.target, self.initially_bad, self.seconds = target, initially_bad, seconds
        self.establish_calls = 0

    def establish_target(self, inputs, workspace):
        self.establish_calls += 1
        return self.target

    def propose(self, context, previous, feedback, instructions, attempt):
        path = Path(context.job_directory) / f"program-{attempt}.nc"
        path.write_text("G1 X10 F100")
        return Candidate.from_paths(
            f"candidate-{attempt}",
            context.target.digest,
            {"nc": str(path)},
            {"bad": self.initially_bad and attempt == 1, "seconds": self.seconds},
        )


class FixtureChecks:
    def __init__(self, version, detect_bad=False):
        self.version, self.detect_bad = version, detect_bad

    def run(self, candidate, context):
        passed = not (self.detect_bad and candidate.parameters["bad"])
        return CheckResult(passed, () if passed else ("fixture intersection",), 0.01, self.version)


class FixtureVerifier:
    def __init__(self):
        self.calls = 0

    def verify(self, candidate, context):
        self.calls += 1
        bad = candidate.parameters["bad"]
        path = Path(context.job_directory) / f"verdict-{self.calls}.json"
        path.write_text("unit-test verification evidence")
        return VerificationResult(
            "failed" if bad else "passed",
            True,
            context.input_digest,
            candidate.digest,
            "fixture-verifier-v1",
            (Artifact.from_path(path),),
            "fixture-test-coverage",
            ("collision",) if bad else (),
            candidate.parameters["seconds"],
            10,
        )


class FixtureSupervisor:
    def decide(self, *args):
        return SupervisorDecision("stop")


@pytest.fixture
def recorded(tmp_path):
    drawing = tmp_path / "drawing.pdf"
    drawing.write_text("unit-test drawing fixture")
    cad = tmp_path / "cad.step"
    cad.write_text("unit-test cad fixture")
    implementation = tmp_path / "verifier.py"
    implementation.write_text("# fixture verifier implementation")
    inputs = JobInputs(
        (Artifact.from_path(drawing),),
        {"machine": "test"},
        {"tools": [1]},
        {"stock": "test"},
        {"tolerance": 0.1},
        {"rate": 60},
    )
    target = Target.from_paths({"step": str(cad)}, "unit-test acceptance")
    store = VersionStore(tmp_path / "versions")
    versions = {
        kind: store.put(kind, "baseline") for kind in ("main_prompt", "supervisor_prompt", "checks")
    }
    versions["verifier"] = "fixture-verifier-v1"
    controller = Controller(
        FixtureMain(target, initially_bad=True),
        FixtureChecks(versions["checks"]),
        FixtureVerifier(),
        FixtureSupervisor(),
    )
    job = controller.run(inputs, tmp_path / "source", "source", versions)
    assert job.status == "completed"
    identity = {
        "version": "fixture-verifier-v1",
        "coverage": "fixture-test-coverage",
        "artifacts": [asdict(Artifact.from_path(implementation))],
        "configuration": {"r": 0.1},
    }
    context = JobContext(inputs, target, inputs.digest, versions, str(tmp_path))
    return store, job, identity, context, tmp_path


def test_capture_preserves_actual_valid_and_invalid_attempts(recorded):
    store, job, identity, _, _ = recorded
    invalid = capture_case(job.manifest_path, 1, identity)
    valid = capture_case(job.manifest_path, 2, identity)
    assert invalid["label"] == "invalid"
    assert valid["label"] == "valid"
    assert invalid["input_hash"] != valid["input_hash"]
    ref = register_dataset(store, [invalid, valid])
    assert store.get(ref)["content"] == [invalid, valid]


@pytest.mark.parametrize("change", ["stock", "candidate", "target", "verifier", "failed_evidence"])
def test_every_cached_dependency_is_rechecked_including_failed_evidence(recorded, change):
    _, job, identity, _, _ = recorded
    case = capture_case(job.manifest_path, 1, identity)
    if change == "stock":
        case["inputs"]["setup"]["stock"] = "other"
    else:
        artifact = {
            "candidate": next(iter(case["candidate"]["artifacts"].values())),
            "target": next(iter(case["target"]["artifacts"].values())),
            "verifier": case["verifier_identity"]["artifacts"][0],
            "failed_evidence": case["verification"]["evidence"][0],
        }[change]
        path = Path(artifact["path"])
        path.chmod(0o644)
        path.write_text("changed")
    with pytest.raises(ValueError):
        validate_case(case)


def test_copied_label_hash_cannot_hide_changed_verdict(recorded):
    _, job, identity, _, _ = recorded
    case = capture_case(job.manifest_path, 1, identity)
    case["label"] = "valid"
    with pytest.raises(ValueError, match="contradicts"):
        validate_case(case)
    case = capture_case(job.manifest_path, 1, identity)
    case["verification"]["completed"] = False
    with pytest.raises(ValueError, match="completed simulation"):
        validate_case(case)


def test_check_replay_does_not_call_simulation(recorded):
    store, job, identity, context, root = recorded
    cases = [capture_case(job.manifest_path, i, identity) for i in (1, 2)]

    def forbidden_factory(*args, **kwargs):
        raise AssertionError("Check replay must not call a controller or simulator")

    runner = BenchmarkRunner(
        store,
        root / "benchmarks",
        forbidden_factory,
        lambda version: FixtureChecks(version, detect_bad=True),
    )
    results = runner("checks", context.versions["checks"], cases, context)
    assert [row["passed"] for row in results] == [False, True]
    assert all(row["runtime_ms"] == 10 for row in results)
    assert all(row["version_ref"] == context.versions["checks"] for row in results)


def test_loop_runs_real_controller_reuses_target_and_disables_recursive_learning(recorded):
    store, job, identity, context, root = recorded
    cases = [capture_case(job.manifest_path, 2, identity, kind="loop")]
    created = []

    def make_controller(versions, evaluation_enabled):
        assert evaluation_enabled is False
        main = FixtureMain(context.target, seconds=80)
        controller = Controller(
            main,
            FixtureChecks(versions["checks"]),
            FixtureVerifier(),
            FixtureSupervisor(),
            learner=object(),
            evaluation=object(),
        )
        created.append(controller)
        return controller

    runner = BenchmarkRunner(store, root / "benchmarks", make_controller, None)
    result = runner("main_prompt", context.versions["main_prompt"], cases, context)[0]
    assert result["verified"]
    assert result["machining_seconds"] == 80
    assert result["cost"] == 10
    assert Path(result["manifest_path"]).is_file()
    assert created[0].main.establish_calls == 0  # Accepted CAD was reused.
    assert created[0].learner is not None  # Factory's controller was not mutated.


def test_incomplete_loop_with_best_plan_is_not_a_completed_benchmark(recorded):
    store, job, identity, context, root = recorded
    cases = [capture_case(job.manifest_path, 2, identity, kind="loop")]

    class KeepTrying:
        def decide(self, *args):
            return SupervisorDecision("improve", "Try another CAM ordering")

    def make_controller(versions, evaluation_enabled):
        return Controller(
            FixtureMain(context.target),
            FixtureChecks(versions["checks"]),
            FixtureVerifier(),
            KeepTrying(),
        )

    runner = BenchmarkRunner(store, root / "benchmarks", make_controller, None, max_attempts=1)
    result = runner("main_prompt", context.versions["main_prompt"], cases, context)[0]
    assert not result["verified"]
    assert result["cost"] is None
    assert result["machining_seconds"] is None
    assert result["simulation_attempts"] == 1


def test_missing_cost_is_not_invented(recorded):
    store, job, identity, context, root = recorded
    cases = [capture_case(job.manifest_path, 2, identity, kind="loop")]

    class NoCost(FixtureVerifier):
        def verify(self, candidate, context):
            from dataclasses import replace

            return replace(super().verify(candidate, context), estimated_cost=None)

    def make_controller(versions, evaluation_enabled):
        return Controller(
            FixtureMain(context.target),
            FixtureChecks(versions["checks"]),
            NoCost(),
            FixtureSupervisor(),
        )

    with pytest.raises(ValueError, match="estimated_cost"):
        BenchmarkRunner(store, root / "benchmarks", make_controller, None)(
            "main_prompt", context.versions["main_prompt"], cases, context
        )


def test_verifier_change_invalidates_replay(recorded):
    store, job, identity, context, root = recorded
    cases = [capture_case(job.manifest_path, 2, identity)]
    context = deepcopy(context)
    context.versions["verifier"] = "new-verifier"
    with pytest.raises(ValueError, match="Current verifier"):
        BenchmarkRunner(store, root / "benchmarks", None, None)(
            "checks", context.versions["checks"], cases, context
        )
