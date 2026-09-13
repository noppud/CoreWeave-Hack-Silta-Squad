"""Acceptance must not conflate status strings, verified candidates, and targets."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_demo", ROOT / "scripts/demo/verify_demo.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_false_completed_without_pass_is_not_ready():
    result = module.assess_manifest({"job_id": "pretend", "status": "completed"})
    assert result["completed"] is False
    assert result["has_verified_best"] is False
    assert "Completed status lacks" in result["errors"][0]


@pytest.mark.skipif(
    not (ROOT / "runs/umc-actuator-v5/manifest.json").is_file(),
    reason="Requires retained local Fusion evidence, which is not distributed with source",
)
def test_incomplete_retained_pass_is_candidate_not_completed_job():
    path = ROOT / "runs/umc-actuator-v5/manifest.json"
    manifest = json.loads(path.read_text())
    assert manifest["status"] == "incomplete"
    result = module.assess_manifest(manifest, path)
    assert result["has_verified_best"] is True
    assert result["completed"] is False
    assert not result["errors"]


def test_hash_tamper_is_detected(tmp_path):
    artifact = tmp_path / "evidence.txt"
    artifact.write_text("actual")
    errors = module.check_hashes({"evidence": [{"path": str(artifact), "sha256": "0" * 64}]})
    assert len(errors) == 1 and "hash mismatch" in errors[0]


def test_retries_do_not_increase_distinct_target_count():
    jobs = [{"target_identity": "same-drawing", "has_verified_best": True, "completed": True}] * 12
    jobs.append({"target_identity": "new-drawing", "has_verified_best": False, "completed": False})
    count = module.summarize_targets(jobs)
    assert count["distinct_verified"] == 1
    assert count["remaining"] == 9


def test_running_manifest_is_not_a_completed_target():
    result = module.assess_manifest({"job_id": "live", "status": "running", "events": []})
    assert not result["completed"] and not result["has_verified_best"]
    assert result["target_identity"] is None


def test_retained_pass_still_needs_job_completion():
    count = module.summarize_targets(
        [{"target_identity": "part", "has_verified_best": True, "completed": False}], required=1
    )
    assert count["distinct_verified"] == 1
    assert count["remaining"] == 1
