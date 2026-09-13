import runpy
from pathlib import Path

import pytest

select = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/demo/resume_fusion_job.py")
)["retained_plan"]


def test_accepted_target_without_cam_can_resume():
    assert select(
        {
            "events": [{"event": "target_accepted"}],
            "result": {"best_candidate": None, "best_verification": None},
        }
    ) == (None, None)


def test_verified_best_wins_over_later_unverified_candidate():
    assert select(
        {
            "events": [{"event": "candidate_created", "candidate": {"id": "later"}}],
            "result": {"best_candidate": {"id": "best"}, "best_verification": {"status": "passed"}},
        }
    ) == ({"id": "best"}, {"status": "passed"})


def test_latest_unverified_candidate_is_reverified():
    assert select(
        {"events": [{"event": "candidate_created", "candidate": {"id": "latest"}}], "result": None}
    ) == ({"id": "latest"}, None)


def test_orphan_verdict_is_rejected():
    with pytest.raises(ValueError, match="no retained candidate"):
        select({"events": [], "best_verification": {"status": "passed"}})


@pytest.fixture
def trial_source(tmp_path):
    import json
    from dataclasses import asdict

    from silta.cnc.models import Candidate, Target

    target_file = tmp_path / "accepted.step"
    target_file.write_text("fixed target")
    target = Target.from_paths({"step": target_file}, "accepted test target")
    cam = tmp_path / "selected.f3d"
    cam.write_text("retained selected CAM")
    selected = Candidate.from_paths("candidate-0002", target.digest, {"f3d": cam})
    later = Candidate("candidate-0003", target.digest, selected.artifacts, {"later": True})
    data = {
        "job_id": "old-job",
        "input_digest": "input",
        "target_digest": target.digest,
        "target": asdict(target),
        "collection_warning": "Partial export: old verdict invalid.",
        "events": [
            {"event": "candidate_created", "candidate": asdict(selected)},
            {"event": "candidate_created", "candidate": asdict(later)},
        ],
        "result": {"best_candidate": asdict(later), "best_verification": {"status": "failed"}},
    }
    path = tmp_path / "old-manifest.json"
    path.write_text(json.dumps(data))
    return path, target, selected, data


def choose_trial(*args):
    return runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/resume_fusion_job.py")
    )["selected_trial"](*args)


def test_trial_selects_exact_event_not_latest_or_best(trial_source):
    import hashlib

    path, target, expected, _ = trial_source
    raw = path.read_bytes()
    candidate, provenance = choose_trial(path, expected.id, "input", target)
    assert candidate == expected
    assert provenance["source_event_index"] == 0
    assert provenance["source_manifest_sha256"] == hashlib.sha256(raw).hexdigest()
    assert provenance["candidate_digest"] == expected.digest
    assert provenance["manual_nomination"] and not provenance["old_verdict_inherited"]
    assert "Partial export" in provenance["collection_warning"]
    assert "best_verification" not in provenance
    assert path.read_bytes() == raw


def test_trial_rejects_different_input(trial_source):
    path, target, candidate, _ = trial_source
    with pytest.raises(ValueError, match="unchanged drawing"):
        choose_trial(path, candidate.id, "different-input", target)


def test_trial_rejects_different_fixed_target(trial_source, tmp_path):
    from silta.cnc.models import Target

    path, _, candidate, _ = trial_source
    other = tmp_path / "other.step"
    other.write_text("different target")
    with pytest.raises(ValueError, match="same accepted target"):
        choose_trial(path, candidate.id, "input", Target.from_paths({"step": other}, "accepted"))


@pytest.mark.parametrize(
    "kind", ["missing", "duplicate", "wrong_candidate_target", "changed_artifact"]
)
def test_trial_rejects_ambiguous_or_changed_candidate(trial_source, kind):
    import json

    path, target, candidate, data = trial_source
    if kind == "duplicate":
        data["events"].append(data["events"][0])
    elif kind == "wrong_candidate_target":
        data["events"][0]["candidate"]["target_digest"] = "wrong"
    elif kind == "changed_artifact":
        Path(candidate.artifacts["f3d"].path).write_text("changed CAM bytes")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        choose_trial(path, "missing-id" if kind == "missing" else candidate.id, "input", target)


def test_recovery_reuses_selected_shadow_and_preserves_other_learning(tmp_path):
    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/resume_fusion_job.py")
    )["recovery_learning"]
    main, shadow = tmp_path / "main", tmp_path / "shadow"
    for directory in (main, shadow):
        directory.mkdir()
        (directory / "checks.py").write_text("checks " + directory.name)
        (directory / "cad_cam.md").write_text("prompt " + directory.name)
    state, provenance = helper(shadow)
    assert state.root == shadow.resolve()
    assert state.paths["checks"].read_text() == "checks shadow"
    state.paths["checks"].write_text("shadow update")
    assert (main / "checks.py").read_text() == "checks main"
    assert provenance["recovery_not_fresh_preparation"] is True
    assert provenance["uses_main_learning_directory"] is False
    assert set(provenance["initial_file_sha256"]) == {"checks.py", "cad_cam.md"}


def test_missing_shadow_is_not_silently_initialized(tmp_path):
    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/resume_fusion_job.py")
    )["recovery_learning"]
    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="existing"):
        helper(missing)
    assert not missing.exists()


@pytest.mark.parametrize(
    "status,completed,expected",
    [("passed", True, 1), ("unknown", False, 0), ("passed", False, 0), ("failed", True, 0)],
)
def test_resume_playback_only_after_completed_pass(tmp_path, status, completed, expected):
    from types import SimpleNamespace

    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/resume_fusion_job.py")
    )["PlaybackVerifier"]
    verdict = SimpleNamespace(status=status, completed=completed)
    receipts = []
    candidate = SimpleNamespace(id="candidate-1")
    wrapper = helper(
        SimpleNamespace(verify=lambda *args: verdict),
        lambda *a, **k: {"observed": True},
        None,
        tmp_path,
        receipts,
    )
    assert wrapper.verify(candidate, None) is verdict
    assert len(receipts) == expected


def test_resume_presentation_exception_preserves_exact_verdict(tmp_path):
    from types import SimpleNamespace

    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/resume_fusion_job.py")
    )["PlaybackVerifier"]
    verdict = SimpleNamespace(status="passed", completed=True)

    def fail(*args, **kwargs):
        raise RuntimeError("display failed")

    receipts = []
    wrapper = helper(SimpleNamespace(verify=lambda *args: verdict), fail, None, tmp_path, receipts)
    assert wrapper.verify(SimpleNamespace(id="c1"), None) is verdict
    assert receipts[0]["status"] == "presentation_failed"
