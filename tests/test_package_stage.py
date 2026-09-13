"""Synthetic packaging selection tests, not manufacturing evidence."""

import hashlib
import json
import os

import pytest

from scripts.demo import package_evidence as package


class Inventory:
    def __init__(self):
        self.files = []

    def add(self, source, relative, *args, expected=None):
        self.files.append(str(relative))
        if expected:
            assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
        return {"path": str(relative)}

    def refs(self, *args):
        pass


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    job = "stage-example"
    runs = tmp_path / "runs"
    run = runs / job
    run.mkdir(parents=True)
    main = tmp_path / "learning"
    shadow = runs / f"{job}-shadow-learning"
    main.mkdir()
    shadow.mkdir()
    for folder in (main, shadow):
        (folder / "checks.py").write_text("check")
    (run / "manifest.json").write_text(
        json.dumps(
            dict(
                status="completed",
                input_digest="input",
                inputs={},
                events=[],
                best_verification={"machining_seconds": 338.6},
            )
        )
    )
    receipt = dict(
        no_main_learning_promotion=True,
        input_digest="input",
        learning_source=str(main),
        shadow_learning_directory=str(shadow),
        ending_learning_sha256={"checks.py": hashlib.sha256(b"check").hexdigest()},
        preparation_started_at="2026-09-13T01:00:00+00:00",
        prepared_at="2026-09-13T01:07:00+00:00",
        presentation_pause_seconds=42,
        verifications=[{"verification_wall_seconds": 28}],
        playbacks=[{"tool_motion_observed": True}],
    )
    (runs / f"{job}-presentation.json").write_text(json.dumps(receipt))
    return main, shadow


def test_rehearsal_separate_category_and_phase_times(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    row = package.add_stage_rehearsals(Inventory())[0]
    assert row["counted_in_campaign_completed_drawings"] is False
    assert row["preparation_wall_seconds"] == 420
    assert row["presenter_pause_seconds"] == 42
    assert row["verifications"][0]["verification_wall_seconds"] == 28
    assert row["best_estimated_machining_seconds"] == 338.6
    assert row["observed_motion_playbacks"] == 1


def test_shadow_hardlink_rejected(tmp_path, monkeypatch):
    main, shadow = fixture(tmp_path, monkeypatch)
    (shadow / "checks.py").unlink()
    os.link(main / "checks.py", shadow / "checks.py")
    with pytest.raises(ValueError, match="aliases main"):
        package.add_stage_rehearsals(Inventory())


def test_changed_shadow_source_rejected(tmp_path, monkeypatch):
    _, shadow = fixture(tmp_path, monkeypatch)
    (shadow / "checks.py").write_text("changed")
    with pytest.raises(AssertionError):
        package.add_stage_rehearsals(Inventory())


def recovery_fixture(tmp_path, monkeypatch):
    main, shadow = fixture(tmp_path, monkeypatch)
    (main / "cad_cam.md").write_text("prompt")
    (shadow / "cad_cam.md").write_text("prompt")
    source = tmp_path / "runs/stage-example/manifest.json"
    original = json.loads(source.read_text())
    original.update(job_id="stage-example", target_digest="target")
    source.write_text(json.dumps(original))
    run = tmp_path / "runs/stage-example-recovery1"
    (run / "workspace").mkdir(parents=True)
    refs, hashes = {}, {}
    for name, kind in (("checks.py", "checks"), ("cad_cam.md", "main_prompt")):
        copied = run / name
        copied.write_bytes((shadow / name).read_bytes())
        hashes[name] = hashlib.sha256(copied.read_bytes()).hexdigest()
        refs[kind] = dict(path=str(copied), sha256=hashes[name], kind=kind)
    manifest = dict(
        job_id=run.name,
        status="incomplete",
        input_digest="input",
        target_digest="target",
        inputs={},
        events=[],
        learning_sources=refs,
        versions={k: k for k in refs},
        current_versions={k: k for k in refs},
    )
    (run / "manifest.json").write_text(json.dumps(manifest))
    provenance = dict(
        source_manifest=str(source),
        source_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        learning_provenance=dict(
            learning_directory=str(shadow),
            uses_main_learning_directory=False,
            initial_file_sha256=hashes,
        ),
    )
    (run / "workspace/resume-provenance.json").write_text(json.dumps(provenance))
    return run, source


def test_recovery_without_presentation_preserves_chain_and_initial_learning(tmp_path, monkeypatch):
    run, source = recovery_fixture(tmp_path, monkeypatch)
    inventory = Inventory()
    row = package.add_stage_recoveries(inventory)[0]
    assert row["category"] == "stage_recovery_shadow_learning"
    assert row["counted_in_campaign_completed_drawings"] is False
    assert row["fresh_preparation_or_presentation"] is False
    assert row["source_chain"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert row["initial_learning_sha256"]["checks.py"] == hashlib.sha256(b"check").hexdigest()
    assert row["status"] == "incomplete"
    assert row["best_estimated_machining_seconds"] is None
    assert f"stage-recoveries/{run.name}/initial-learning/cad_cam.md" in inventory.files


def test_recovery_rejects_changed_source(tmp_path, monkeypatch):
    _, source = recovery_fixture(tmp_path, monkeypatch)
    source.write_text(source.read_text() + " ")
    with pytest.raises(ValueError, match="source changed"):
        package.add_stage_recoveries(Inventory())


def test_recovery_rejects_different_target_even_when_hash_rebound(tmp_path, monkeypatch):
    run, source = recovery_fixture(tmp_path, monkeypatch)
    data = json.loads(source.read_text())
    data["target_digest"] = "different"
    source.write_text(json.dumps(data))
    path = run / "workspace/resume-provenance.json"
    provenance = json.loads(path.read_text())
    provenance["source_manifest_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    path.write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="input or target differs"):
        package.add_stage_recoveries(Inventory())


def test_recovery_rejects_main_learning_alias(tmp_path, monkeypatch):
    run, _ = recovery_fixture(tmp_path, monkeypatch)
    provenance = json.loads((run / "workspace/resume-provenance.json").read_text())
    shadow = package.Path(provenance["learning_provenance"]["learning_directory"])
    (shadow / "checks.py").unlink()
    os.link(tmp_path / "learning/checks.py", shadow / "checks.py")
    with pytest.raises(ValueError, match="aliases main"):
        package.add_stage_recoveries(Inventory())


def test_second_recovery_preserves_two_hop_source_chain(tmp_path, monkeypatch):
    run, origin = recovery_fixture(tmp_path, monkeypatch)
    next_run = run.with_name("stage-example-recovery2")
    (next_run / "workspace").mkdir(parents=True)
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["job_id"] = next_run.name
    (next_run / "manifest.json").write_text(json.dumps(manifest))
    provenance = json.loads((run / "workspace/resume-provenance.json").read_text())
    source = run / "manifest.json"
    provenance.update(
        source_manifest=str(source),
        source_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    (next_run / "workspace/resume-provenance.json").write_text(json.dumps(provenance))
    rows = package.add_stage_recoveries(Inventory())
    assert [item["path"] for item in rows[1]["source_chain"]] == [str(source), str(origin)]


def test_motion_does_not_hide_cleanup_failure():
    summary = package.playback_summary(
        dict(
            candidate_id="candidate-0001",
            status="tool_motion_observed",
            tool_motion_observed=True,
            stop_error="menu missing",
            simulation_stop_error="request timed out",
        )
    )
    assert summary["recorded_status"] == "tool_motion_observed"
    assert summary["tool_motion_observed"] is True
    assert summary["cleanup_completed"] is False
    assert summary["cleanup_errors"]["stop_error"] == "menu missing"


def test_recovery_retains_embedded_and_external_playbacks_with_cleanup(tmp_path, monkeypatch):
    run, _ = recovery_fixture(tmp_path, monkeypatch)
    clean = dict(
        candidate_id="candidate-0003",
        status="tool_motion_observed",
        tool_motion_observed=True,
        simulation_stop=dict(status="ok", completed=True),
        target_display_before=dict(states_before={"body": True}),
        target_display_restore=dict(
            status="ok", completed=True, result=dict(states_after={"body": True})
        ),
    )
    (run / "run-receipt.json").write_text(json.dumps(dict(presentation_playbacks=[clean])))
    external = tmp_path / "runs" / f"{run.name}-playback" / "candidate-0003"
    (external / "ui").mkdir(parents=True)
    (external / "presentation-playback.json").write_text(json.dumps(clean))
    (external / "operator-cleanup.json").write_text('{"recorded": true}')
    (external / "ui/001-inspect.json").write_text('{"actual": "snapshot"}')
    inventory = Inventory()
    row = package.add_stage_recoveries(inventory)[0]
    playback = row["playback_evidence"]
    assert playback["embedded_playbacks"][0]["cleanup_completed"] is True
    assert playback["external_playbacks"][0]["cleanup_completed"] is True
    assert playback["external_playbacks"][0]["candidate_id"] == "candidate-0003"
    assert (
        f"stage-recoveries/{run.name}/playback/candidate-0003/operator-cleanup.json"
        in inventory.files
    )
    assert (
        f"stage-recoveries/{run.name}/playback/candidate-0003/ui/001-inspect.json"
        in inventory.files
    )


def test_external_playback_survives_before_final_run_receipt(tmp_path, monkeypatch):
    run, _ = recovery_fixture(tmp_path, monkeypatch)
    external = tmp_path / "runs" / f"{run.name}-playback" / "candidate-0001"
    external.mkdir(parents=True)
    (external / "presentation-playback.json").write_text(
        json.dumps(
            dict(
                candidate_id="candidate-0001",
                status="presentation_failed",
                tool_motion_observed=True,
                target_display_restore_error="not restored",
            )
        )
    )
    row = package.add_stage_recoveries(Inventory())[0]
    assert row["playback_evidence"]["embedded_playbacks"] == []
    assert row["playback_evidence"]["external_playbacks"][0]["cleanup_completed"] is False
    assert row["status"] == "incomplete"


def test_preadded_sources_keep_actual_deduplicated_stage_links(tmp_path, monkeypatch):
    run, original_manifest = recovery_fixture(tmp_path, monkeypatch)
    original_presentation = tmp_path / "runs/stage-example-presentation.json"
    original_weave = original_manifest.parent / "run-receipt.json"
    resumed_weave = run / "run-receipt.json"
    original_weave.write_text('{"weave_recorded": true}')
    resumed_weave.write_text('{"presentation_playbacks": []}')
    external = tmp_path / "runs" / f"{run.name}-playback/candidate-0001"
    external.mkdir(parents=True)
    playback_path = external / "presentation-playback.json"
    playback_path.write_text('{"candidate_id": "candidate-0001", "status": "pending"}')
    output = tmp_path / "bundle"
    bundle = package.Bundle(output)
    sources = {
        "original-record": original_manifest,
        "original-presentation": original_presentation,
        "original-weave": original_weave,
        "recovery-record": run / "manifest.json",
        "recovery-provenance": run / "workspace/resume-provenance.json",
        "recovery-weave": resumed_weave,
        "recovery-playback": playback_path,
    }
    expected = {}
    for label, source in sources.items():
        item = bundle.add(source, package.Path("already-added") / f"{label}.json")
        expected[label] = item["path"]
    rehearsal = package.add_stage_rehearsals(bundle)[0]
    recovery = package.add_stage_recoveries(bundle)[0]
    assert rehearsal["record_path"] == expected["original-record"]
    assert rehearsal["presentation_receipt"] == expected["original-presentation"]
    assert rehearsal["weave_receipt"] == expected["original-weave"]
    assert recovery["record_path"] == expected["recovery-record"]
    assert recovery["resume_provenance"] == expected["recovery-provenance"]
    assert recovery["original_presentation"] == expected["original-presentation"]
    assert recovery["weave_receipt"] == expected["recovery-weave"]
    assert (
        recovery["playback_evidence"]["external_playbacks"][0]["receipt_path"]
        == expected["recovery-playback"]
    )
    for relative in expected.values():
        assert (output / relative).is_file()


def test_recovery_allows_new_separate_shadow_with_pinned_initial_sources(tmp_path, monkeypatch):
    run, _ = recovery_fixture(tmp_path, monkeypatch)
    path = run / "workspace/resume-provenance.json"
    provenance = json.loads(path.read_text())
    original = package.Path(provenance["learning_provenance"]["learning_directory"])
    fresh = tmp_path / "runs/fresh-recovery-shadow"
    fresh.mkdir()
    for name in ("checks.py", "cad_cam.md"):
        (fresh / name).write_bytes((original / name).read_bytes())
    provenance["learning_provenance"]["learning_directory"] = str(fresh)
    path.write_text(json.dumps(provenance))
    row = package.add_stage_recoveries(Inventory())[0]
    assert row["origin_shadow_learning_directory"] == str(original.relative_to(tmp_path))
    assert row["recovery_shadow_learning_directory"] == str(fresh.relative_to(tmp_path))
    assert row["fresh_preparation"] is False
    (fresh / "checks.py").unlink()
    os.link(tmp_path / "learning/checks.py", fresh / "checks.py")
    with pytest.raises(ValueError, match="aliases main"):
        package.add_stage_recoveries(Inventory())
