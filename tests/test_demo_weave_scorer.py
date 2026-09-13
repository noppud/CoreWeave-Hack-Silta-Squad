"""Evidence truth and Fusion-only selection for native programmatic scoring."""

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/demo/score_fusion_runs.py"
SPEC = importlib.util.spec_from_file_location("score_fusion_runs", PATH)
scoring = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scoring)


def sample(tmp_path):
    artifact_path = tmp_path / "actual-evidence.json"
    artifact_path.write_text('{"recorded":true}')
    artifact = {"path": str(artifact_path), "sha256": scoring.sha(artifact_path)}
    candidate = {
        "id": "candidate-1",
        "target_digest": "target",
        "artifacts": {"f3d": artifact},
        "parameters": {},
    }
    digest = scoring.Candidate(
        "candidate-1", "target", {"f3d": scoring.Artifact(**artifact)}
    ).digest
    verdict = {
        "status": "passed",
        "completed": True,
        "candidate_digest": digest,
        "input_digest": "input",
        "verifier_version": "fusion-fixed-test",
        "evidence": [artifact],
        "issues": [],
        "coverage": "Fusion verification",
        "machining_seconds": 120.5,
        "estimated_cost": 13.0,
        "feedback": {
            "configured_coverage": dict.fromkeys(scoring.REQUIRED_COVERAGE, True),
            "summary": {"percent": 100, "errors": 0, "process_errors": 0},
            "target_stock_comparison": {"status": "passed"},
        },
    }
    result = {
        "job_id": "test-fusion",
        "status": "completed",
        "best_candidate": candidate,
        "best_verification": verdict,
        "reason": "done",
    }
    return {
        **copy.deepcopy(result),
        "result": result,
        "input_digest": "input",
        "target_digest": "target",
        "inputs": {
            "machine": {"simulation_geometry": artifact},
            "setup": {"fixture": {"artifact": artifact}},
        },
        "events": [{"event": "verification_completed", "verification": verdict}],
    }


def score(manifest):
    return scoring.score_output(manifest["result"], scoring.evidence_audit(manifest))


def test_valid_completed_fusion_evidence(tmp_path):
    result = score(sample(tmp_path))
    assert result["verified_best"] is True
    assert result["false_completion"] is False
    assert result["machining_seconds"] == 120.5
    assert result["illustrative_estimated_cost"] == 13


@pytest.mark.parametrize(
    "change",
    [
        {"status": "unknown", "completed": False},
        {"status": "failed", "issues": ["collision"]},
        {"evidence": []},
        {"candidate_digest": "wrong"},
        {"input_digest": "wrong"},
        {"verifier_version": "custom-simulator"},
        {"coverage": ""},
        {"issues": ["collision"]},
    ],
)
def test_unverified_evidence_never_scores_as_success_or_free(tmp_path, change):
    manifest = sample(tmp_path)
    manifest["best_verification"].update(change)
    manifest["result"]["best_verification"].update(change)
    result = score(manifest)
    assert result["verified_best"] is False
    assert result["false_completion"] is True
    assert result["machining_seconds"] is None
    assert result["illustrative_estimated_cost"] is None


def test_changed_artifact_fails_integrity(tmp_path):
    manifest = sample(tmp_path)
    Path(manifest["best_verification"]["evidence"][0]["path"]).write_text("changed")
    result = score(manifest)
    assert result["verified_best"] is False
    assert result["artifact_errors"]


def test_coverage_or_stock_comparison_cannot_be_omitted(tmp_path):
    for field in ["configured_coverage", "target_stock_comparison", "summary"]:
        manifest = sample(tmp_path)
        manifest["result"]["best_verification"]["feedback"].pop(field)
        assert score(manifest)["verified_best"] is False


def test_incomplete_result_is_not_false_completion_or_zero_cost(tmp_path):
    manifest = sample(tmp_path)
    manifest.update(status="incomplete", best_candidate=None, best_verification=None)
    manifest["result"].update(status="incomplete", best_candidate=None, best_verification=None)
    manifest["events"] = [
        {
            "event": "verification_completed",
            "verification": {"status": "unknown", "completed": False},
        }
    ]
    result = score(manifest)
    assert result["incomplete_collection"] is True
    assert result["false_completion"] is False
    assert result["machining_seconds"] is None


def test_campaign_selection_never_scans_other_project_jobs(tmp_path):
    (tmp_path / "unrelated").mkdir()
    (tmp_path / "unrelated/manifest.json").write_text("{}")
    campaign = tmp_path / "campaign.json"
    campaign.write_text(
        json.dumps(
            {
                "parts": [
                    {
                        "manifest_path": "chosen/manifest.json",
                        "recovery_sources": ["prior/manifest.json"],
                    }
                ]
            }
        )
    )
    assert scoring.discover(campaign) == [
        tmp_path / "chosen/manifest.json",
        tmp_path / "prior/manifest.json",
    ]


def test_receipt_and_server_root_binding(tmp_path):
    manifest = sample(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="receipt"):
        scoring.eligible_record(path)
    receipt = {
        "job_id": manifest["job_id"],
        "weave_project": scoring.PROJECT,
        "weave_call_id": "root",
        "weave_recorded": True,
    }
    (tmp_path / "run-receipt.json").write_text(json.dumps(receipt))
    scoring.eligible_record(path)
    call = SimpleNamespace(
        id="root", parent_id=None, ended_at="now", exception=None, output=manifest["result"]
    )
    scoring.validate_server_call(call, manifest, receipt)
    call.parent_id = "parent"
    with pytest.raises(ValueError, match="finalized root"):
        scoring.validate_server_call(call, manifest, receipt)
    call.parent_id = None
    call.output = {"job_id": "another"}
    with pytest.raises(ValueError, match="differs"):
        scoring.validate_server_call(call, manifest, receipt)


def test_custom_simulator_input_rejected_even_with_receipt(tmp_path):
    manifest = sample(tmp_path)
    manifest["inputs"]["machine"].pop("simulation_geometry")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    (tmp_path / "run-receipt.json").write_text(
        json.dumps(
            {
                "job_id": manifest["job_id"],
                "weave_project": scoring.PROJECT,
                "weave_call_id": "root",
                "weave_recorded": True,
            }
        )
    )
    with pytest.raises(ValueError, match="Not a Fusion"):
        scoring.eligible_record(path)


def test_versioned_native_scorer_is_deterministic(tmp_path):
    manifest = sample(tmp_path)
    scorer = scoring.FusionOutcomeScorer()
    assert len(scorer.source_sha256) == 64
    assert scorer.score(manifest["result"], scoring.evidence_audit(manifest)) == score(manifest)


def test_weave_boxed_metrics_are_stored_as_plain_numbers(tmp_path):
    from weave.trace.box import BoxedFloat, BoxedStr

    manifest = sample(tmp_path)
    manifest["result"]["job_id"] = BoxedStr(manifest["job_id"])
    manifest["result"]["best_verification"]["machining_seconds"] = BoxedFloat(120.5)
    result = score(manifest)
    assert type(result["machining_seconds"]) is float
    assert type(result["job_id"]) is str


def test_missing_machining_metric_cannot_support_a_verified_best(tmp_path):
    manifest = sample(tmp_path)
    manifest["result"]["best_verification"]["machining_seconds"] = None
    result = score(manifest)
    assert result["verified_best"] is False
    assert result["machining_seconds"] is None


@pytest.mark.parametrize("recorded_status", ["passed", "failed"])
def test_collection_warning_preserves_history(tmp_path, recorded_status):
    manifest = sample(tmp_path)
    manifest["events"][-1]["verification"]["status"] = recorded_status
    manifest["collection_warning"] = "Partial stock regeneration; fresh collection required."
    original = copy.deepcopy(manifest)
    result = score(manifest)
    assert result["collection_invalidated"] is True
    assert result["latest_verification_status"] == "unknown"
    assert result["recorded_latest_verification_status"] == recorded_status
    assert result["latest_verification_completed"] is False
    assert result["incomplete_collection"] is True
    assert result["verified_best"] is False
    assert result["machining_seconds"] is None
    assert manifest == original
