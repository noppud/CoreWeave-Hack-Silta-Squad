"""Terminal previews must preserve evidence boundaries and source provenance."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "live_terminal", Path(__file__).resolve().parents[1] / "scripts/demo/live_terminal.py"
)
viewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(viewer)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def retained_source(directory, kind, content):
    ref = hashlib.sha256((kind + "\0" + content).encode()).hexdigest()
    path = directory / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return ref, {
        "kind": kind,
        "path": str(path),
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
    }


def fixture_campaign(tmp_path):
    before = "def check():\n    return False\n"
    after = "def check():\n    return True\n"
    old_ref, old_source = retained_source(tmp_path, "checks", before)
    new_ref, new_source = retained_source(tmp_path, "checks", after)
    prompt_ref, prompt_source = retained_source(
        tmp_path, "main_prompt", "Use only validated results.\n"
    )
    old = {"checks": old_ref, "main_prompt": prompt_ref}
    new = {"checks": new_ref, "main_prompt": prompt_ref}
    manifest = {
        "job_id": "part-a",
        "status": "running",
        "versions": old,
        "current_versions": new,
        "learning_sources": {old_ref: old_source, new_ref: new_source, prompt_ref: prompt_source},
        "events": [{"event": "verification_started", "attempt": 1, "at": "2026-09-12T12:34:56Z"}],
    }
    path = write_json(tmp_path / "part-a/manifest.json", manifest)
    campaign = {
        "campaign_id": "test",
        "current_part_id": "a",
        "status": "running",
        "initial_versions": old,
        "learning_directory": str(tmp_path / "learning"),
        "parts": [{"part_id": "a", "job_id": "part-a", "manifest_path": str(path)}],
    }
    campaign_path = write_json(tmp_path / "campaign.json", campaign)
    return campaign_path, path, manifest


def test_missing_campaign_has_clear_empty_state(tmp_path):
    output = viewer.render(viewer.load_snapshot(tmp_path / "missing.json"))
    assert "Best verified time (recorded): none yet" in output
    assert "READ ERROR: Campaign unavailable" in output
    assert "No job events" in output
    assert "\x1b" not in output


@pytest.mark.parametrize(
    "verdict",
    [
        {},
        {"status": "failed", "completed": True, "machining_seconds": 0},
        {
            "status": "passed",
            "completed": False,
            "evidence": ["e"],
            "coverage": ["c"],
            "machining_seconds": 0,
        },
        {
            "status": "passed",
            "completed": True,
            "evidence": [],
            "coverage": ["c"],
            "machining_seconds": 0,
        },
        {
            "status": "passed",
            "completed": True,
            "evidence": ["e"],
            "coverage": ["c"],
            "issues": ["collision"],
            "machining_seconds": 0,
        },
    ],
)
def test_incomplete_or_failed_verdict_never_becomes_best(tmp_path, verdict):
    campaign_path, path, manifest = fixture_campaign(tmp_path)
    manifest.update(best_candidate={"id": "candidate"}, best_verification=verdict)
    write_json(path, manifest)
    output = viewer.render(viewer.load_snapshot(campaign_path))
    assert "Best verified time (recorded): none yet" in output
    assert "Best verified time (recorded): 0.00s" not in output


def test_recorded_best_and_candidate_estimate_distinguished(tmp_path):
    campaign_path, path, manifest = fixture_campaign(tmp_path)
    manifest.update(
        best_candidate={"id": "accepted"},
        best_verification={
            "status": "passed",
            "completed": True,
            "evidence": ["actual-result.json"],
            "coverage": ["collision"],
            "issues": [],
            "machining_seconds": 371.053684,
        },
    )
    manifest["events"].append(
        {
            "event": "candidate_created",
            "candidate": {
                "id": "unverified-new",
                "parameters": {"estimated_metrics": {"machining_seconds": 250}},
            },
        }
    )
    write_json(path, manifest)
    output = viewer.render(viewer.load_snapshot(campaign_path))
    assert "Best verified time (recorded): 371.05s" in output
    assert "250.00s [UNVERIFIED estimate]" in output


def test_exact_source_diff_and_unapplied_disk_version(tmp_path):
    campaign_path, _, _ = fixture_campaign(tmp_path)
    learning = tmp_path / "learning"
    learning.mkdir()
    (learning / "checks.py").write_text("def check():\n    raise RuntimeError('not loaded')\n")
    snapshot = viewer.load_snapshot(campaign_path)
    output = viewer.render(snapshot)
    assert "-    return False" in output
    assert "+    return True" in output
    assert "not this job's current pin" in output
    assert "raise RuntimeError" not in output


def test_corrupt_retained_source_is_not_presented_as_original(tmp_path):
    campaign_path, _, manifest = fixture_campaign(tmp_path)
    ref = manifest["current_versions"]["checks"]
    Path(manifest["learning_sources"][ref]["path"]).write_text("tampered source\n")
    snapshot = viewer.load_snapshot(campaign_path)
    assert snapshot["sources"]["checks"]["after"] is None
    assert "Recorded source hash mismatch" in snapshot["sources"]["checks"]["warnings"]
    assert "tampered source" not in viewer.render(snapshot)


def test_real_nc_and_cam_excerpts_are_read_without_execution(tmp_path):
    campaign_path, path, manifest = fixture_campaign(tmp_path)
    nc = tmp_path / "part.nc"
    nc.write_text("%\nO1001\n(comment)\nG90 G17\nG1 X12 Y3 F400\n")
    cam = path.parent / "workspace/cam_generated.py"
    cam.parent.mkdir()
    cam.write_text("raise RuntimeError('must never run')\n")
    manifest["events"].append(
        {
            "event": "candidate_created",
            "candidate": {
                "artifacts": {
                    "nc-0": {
                        "path": str(nc),
                        "sha256": hashlib.sha256(nc.read_bytes()).hexdigest(),
                    },
                }
            },
        }
    )
    write_json(path, manifest)
    output = viewer.render(viewer.load_snapshot(campaign_path))
    assert "G1 X12 Y3 F400" in output
    assert "raise RuntimeError('must never run')" in output
    assert "not NC verification" in output


def test_viewport_and_plain_once(tmp_path, capsys):
    campaign_path, path, manifest = fixture_campaign(tmp_path)
    manifest["events"] *= 30
    manifest["events"][-1] = {
        "event": "cam_generation_failed",
        "feedback": {"error": "x" * 400 + "\x1b[2J"},
    }
    write_json(path, manifest)
    output = viewer.render(viewer.load_snapshot(campaign_path))
    assert len(output.splitlines()) <= 40
    assert all(len(line) <= 120 for line in output.splitlines())
    assert "\x1b" not in output
    assert viewer.main(["--campaign", str(campaign_path), "--once"]) == 0
    assert "\x1b" not in capsys.readouterr().out


def test_job_selection_supports_campaign_id_and_explicit_manifest(tmp_path):
    campaign_path, path, _ = fixture_campaign(tmp_path)
    assert viewer.load_snapshot(campaign_path, "a")["manifest_path"] == str(path)
    assert viewer.load_snapshot(campaign_path, str(path))["manifest_path"] == str(path)


def test_unchanged_check_preview_shows_actual_check_function():
    source = '"""Documentation."""\nimport json\n\ndef check(data):\n    return data["ok"]\n'
    lines = viewer.snippet(source, source, code=True)
    assert lines[0] == "  4 def check(data):"
    assert 'return data["ok"]' in lines[1]


def test_machining_excerpt_skips_wrapper_and_preserves_embedded_line_numbers():
    plan = (
        "import adsk.cam\n\n"
        "# Existing accepted operations\n"
        "for op in setup.operations:\n"
        "    p = op.parameters.itemByName('rampClearanceHeight')\n"
        "    p.expression = '0.2 mm'\n"
        "    assert p.value.value == 0.02\n"
    )
    wrapper = (
        "# deterministic setup\nsetup = get_setup()\n"
        f"exec(compile({plan!r}, '<silta-machining-plan>', 'exec'), globals())\n"
    )
    lines, label = viewer.machining_excerpt(wrapper)
    assert label == "CAM EXCERPT / embedded plan lines (file L3)"
    assert lines == [
        "  5     p = op.parameters.itemByName('rampClearanceHeight')",
        "  6     p.expression = '0.2 mm'",
        "  7     assert p.value.value == 0.02",
    ]


def test_machining_excerpt_prioritizes_actual_operation_creation():
    source = (
        "import adsk.cam\nsetup = get_setup()\n\n"
        "# machining decisions\nop = setup.operations.createInput('pocket2d')\n"
        "op.tool = tools[1]\n"
    )
    lines, label = viewer.machining_excerpt(source)
    assert label == "CAM SOURCE EXCERPT / file lines"
    assert "  5 op = setup.operations.createInput('pocket2d')" in lines
    assert not any("get_setup" in line for line in lines)


def test_machining_excerpt_fallback_does_not_execute_dynamic_source():
    source = "raise RuntimeError('never execute')\nexec(compile(dynamic(), 'plan', 'exec'))\n"
    lines, label = viewer.machining_excerpt(source)
    assert lines[0] == "  1 raise RuntimeError('never execute')"
    assert label == "CAM SOURCE EXCERPT / file lines"


def test_explicit_job_uses_own_initial_versions_and_shadow_files(tmp_path):
    campaign_path, path, manifest = fixture_campaign(tmp_path)
    manifest["versions"] = dict(manifest["current_versions"])
    write_json(path, manifest)
    shadow = tmp_path / "part-a-shadow-learning"
    shadow.mkdir()
    (shadow / "checks.py").write_text("def check():\n    return True\n")
    (shadow / "cad_cam.md").write_text("Use only validated results.\n")
    write_json(tmp_path / "part-a-presentation.json", {"shadow_learning_directory": str(shadow)})
    snapshot = viewer.load_snapshot(campaign_path, job="part-a")
    source = snapshot["sources"]["checks"]
    assert source["initial"] == source["current"]
    assert source["live_ref"] == source["current"]
    assert Path(source["path"]) == shadow / "checks.py"
    campaign_snapshot = viewer.load_snapshot(campaign_path)
    assert campaign_snapshot["sources"]["checks"]["initial"] != source["current"]


def test_latest_created_candidate_pass_does_not_label_next_generation(tmp_path):
    from silta.cnc.models import digest_json

    campaign_path, path, manifest = fixture_campaign(tmp_path)
    candidate = {
        "id": "candidate-0005",
        "target_digest": "target",
        "artifacts": {"nc": {"sha256": "abc"}},
        "parameters": {"estimated_metrics": {"machining_seconds": 1515.2}},
    }
    digest = digest_json(
        {"target": "target", "artifacts": {"nc": "abc"}, "parameters": candidate["parameters"]}
    )
    verdict = {
        "status": "passed",
        "completed": True,
        "candidate_digest": digest,
        "evidence": [{"path": "receipt"}],
        "issues": [],
        "coverage": "actual",
    }
    events = [
        {"event": "candidate_created", "attempt": 3, "candidate": candidate},
        {"event": "verification_completed", "attempt": 3, "verification": verdict},
        {"event": "candidate_generation_started", "attempt": 4},
    ]
    assert viewer.latest_candidate_verification(events, candidate) == verdict
    events.append(
        {
            "event": "candidate_created",
            "attempt": 4,
            "candidate": {**candidate, "id": "candidate-0006"},
        }
    )
    assert viewer.latest_candidate_verification(events, events[-1]["candidate"]) is None
    events[1]["verification"] = {**verdict, "candidate_digest": "different"}
    assert viewer.latest_candidate_verification(events[:3], candidate) is None
