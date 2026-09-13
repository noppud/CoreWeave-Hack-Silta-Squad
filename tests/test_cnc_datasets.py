"""CLI tests use labeled local fixtures, never actual machining performance claims."""

import json
from dataclasses import asdict

import pytest

from silta.cnc.datasets import main
from silta.cnc.evaluation import VersionStore
from silta.cnc.models import Artifact, Candidate, JobInputs, Target, VerificationResult


@pytest.fixture
def source(tmp_path):
    def artifact(name):
        path = tmp_path / name
        path.write_text(f"unit-test fixture {name}")
        return Artifact.from_path(path)

    implementation = artifact("verifier.py")
    identity = tmp_path / "identity.json"
    assert (
        main(
            [
                "identity",
                "--version",
                "test-v1",
                "--coverage",
                "unit-test coverage",
                "--artifact",
                implementation.path,
                "--output",
                str(identity),
            ]
        )
        == 0
    )
    inputs = JobInputs(
        (artifact("drawing.pdf"),),
        {"machine": "fixture"},
        {"tools": [1]},
        {"stock": "fixture"},
        {"tolerance": 0.1},
    )
    target = Target({"step": artifact("part.step")}, "unit-test accepted target")
    events = []
    for attempt, status in ((1, "failed"), (2, "passed")):
        candidate = Candidate(
            f"candidate-{attempt}", target.digest, {"nc": artifact(f"part-{attempt}.nc")}
        )
        verification = VerificationResult(
            status,
            True,
            inputs.digest,
            candidate.digest,
            "test-v1",
            (artifact(f"verdict-{attempt}.json"),),
            "unit-test coverage",
            ("collision",) if attempt == 1 else (),
            100,
            10,
        )
        events.extend(
            [
                {
                    "event": "candidate_created",
                    "attempt": attempt,
                    "candidate": asdict(candidate),
                    "candidate_digest": candidate.digest,
                },
                {
                    "event": "verification_started",
                    "attempt": attempt,
                    "at": f"2026-09-12T00:0{attempt}:00+00:00",
                },
                {
                    "event": "verification_completed",
                    "at": f"2026-09-12T00:0{attempt}:10+00:00",
                    "attempt": attempt,
                    "verification": asdict(verification),
                },
            ]
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "job_id": "fixture",
                "inputs": asdict(inputs),
                "input_digest": inputs.digest,
                "target": asdict(target),
                "target_digest": target.digest,
                "versions": {"verifier": "test-v1"},
                "events": events,
            }
        )
    )
    return tmp_path, identity, manifest


def capture(source, attempt, kind="checks"):
    root, identity, manifest = source
    output = root / f"case-{kind}-{attempt}.json"
    code = main(
        [
            "capture",
            "--manifest",
            str(manifest),
            "--attempt",
            str(attempt),
            "--identity",
            str(identity),
            "--kind",
            kind,
            "--output",
            str(output),
        ]
    )
    return code, output


def test_capture_register_inspect_pipeline(source, capsys):
    root, _, _ = source
    code, invalid = capture(source, 1)
    assert code == 0
    code, valid = capture(source, 2)
    assert code == 0
    store = root / "versions"
    capsys.readouterr()
    assert (
        main(["register", "--store", str(store), "--case", str(invalid), "--case", str(valid)]) == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["kind"] == "checks"
    assert result["labels"] == {"valid": 1, "invalid": 1}
    assert VersionStore(store).get(result["dataset_ref"])["kind"] == "dataset"
    assert main(["inspect", "--store", str(store), "--dataset", result["dataset_ref"]]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "validated"


def test_capture_will_not_overwrite_existing_case(source, capsys):
    assert capture(source, 1)[0] == 0
    assert capture(source, 1)[0] == 1
    assert json.loads(capsys.readouterr().err)["status"] == "error"


def test_unknown_verification_cannot_be_captured(source):
    _, _, manifest = source
    data = json.loads(manifest.read_text())
    event = next(e for e in data["events"] if e["event"] == "verification_completed")
    event["verification"].update(status="unknown", completed=False)
    manifest.write_text(json.dumps(data))
    code, output = capture(source, 1)
    assert code == 1
    assert not output.exists()


def test_stale_failed_evidence_is_rejected_before_registration(source):
    root, _, _ = source
    _, invalid = capture(source, 1)
    _, valid = capture(source, 2)
    (root / "verdict-1.json").write_text("changed evidence")
    assert (
        main(
            [
                "register",
                "--store",
                str(root / "versions"),
                "--case",
                str(invalid),
                "--case",
                str(valid),
            ]
        )
        == 1
    )
    assert not list((root / "versions" / "objects").glob("*.json"))


def test_check_dataset_requires_valid_and_invalid_cases(source):
    root, _, _ = source
    _, valid = capture(source, 2)
    assert main(["register", "--store", str(root / "versions"), "--case", str(valid)]) == 1


def test_loop_dataset_can_capture_one_fixed_target_case(source, capsys):
    root, _, _ = source
    _, case = capture(source, 2, kind="loop")
    capsys.readouterr()
    assert main(["register", "--store", str(root / "versions"), "--case", str(case)]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "loop"
