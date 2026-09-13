"""Selection tests use synthetic records; they are not machining evidence."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.demo.plot_verified_improvements import select_pairs


def fixture_report(tmp_path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}")
    ref = {"path": str(evidence), "sha256": hashlib.sha256(b"{}").hexdigest()}
    verdicts = []
    rows = []
    manifest = tmp_path / "manifest.json"
    for index, (seconds, version) in enumerate(
        ((100.0, "fusion-fixed-a"), (90.0, "fusion-fixed-a"), (10.0, "fusion-fixed-b"))
    ):
        verdict = dict(
            status="passed",
            completed=True,
            evidence=[ref],
            coverage=["stock"],
            issues=[],
            machining_seconds=seconds,
            verifier_version=version,
            input_digest="input",
            candidate_digest=f"candidate{index}",
        )
        verdicts.append({"verification": verdict})
        rows.append(
            dict(
                manifest=str(manifest),
                event_index=index,
                at=str(index),
                input_digest="input",
                target_digest="target",
                candidate_digest=f"candidate{index}",
                verifier_version=version,
                machining_seconds=seconds,
            )
        )
    manifest.write_text(
        json.dumps(
            dict(
                target_digest="target",
                inputs={"drawings": [{"sha256": "drawing"}]},
                events=verdicts,
            )
        )
    )
    return {
        "parts": [
            dict(
                part="TEST",
                any_completed_job=True,
                drawing_sha256="drawing",
                verified_candidates=rows,
            )
        ]
    }


def test_best_never_uses_faster_different_verifier(tmp_path):
    pairs = select_pairs(fixture_report(tmp_path), ["TEST"])
    assert pairs[0]["best_valid"]["machining_seconds"] == 90
    assert pairs[0]["reduction_percent"] == pytest.approx(10)
    assert pairs[0]["excluded_other_identity_candidates"] == 1


def test_incomplete_drawing_rejected(tmp_path):
    report = fixture_report(tmp_path)
    report["parts"][0]["any_completed_job"] = False
    with pytest.raises(ValueError, match="no completed"):
        select_pairs(report, ["TEST"])


def test_changed_evidence_rejected(tmp_path):
    report = fixture_report(tmp_path)
    (tmp_path / "evidence.json").write_text("changed")
    with pytest.raises(ValueError, match="verification no longer valid"):
        select_pairs(report, ["TEST"])


def test_changed_report_metric_rejected(tmp_path):
    report = fixture_report(tmp_path)
    report["parts"][0]["verified_candidates"][0]["machining_seconds"] = 5
    with pytest.raises(ValueError, match="disagrees"):
        select_pairs(report, ["TEST"])


def test_collection_warning_rejects_previously_reported_pass(tmp_path):
    report = fixture_report(tmp_path)
    path = Path(report["parts"][0]["verified_candidates"][0]["manifest"])
    data = json.loads(path.read_text())
    data["collection_warning"] = "Incomplete stock export"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="collection-invalidated"):
        select_pairs(report, ["TEST"])


def test_manual_trial_is_labeled_from_retained_source(tmp_path):
    report = fixture_report(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "manual-trial-nomination.json").write_text(
        json.dumps({"candidate_digest": "candidate1", "manual_nomination": True})
    )
    with pytest.raises(ValueError, match="attribution differs"):
        select_pairs(report, ["TEST"])
    report["parts"][0]["verified_candidates"][1]["manual_nomination"] = True
    pair = select_pairs(report, ["TEST"])[0]
    assert pair["manual_nomination"] is True
    assert "Operator-nominated" in pair["attribution"]
