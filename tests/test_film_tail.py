"""Receipt validation uses synthetic metadata; no Fusion or film rendering."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def film(monkeypatch):
    # Rendering is outside these selection tests; optional ffmpeg is not invoked.
    monkeypatch.setitem(
        sys.modules, "imageio_ffmpeg", SimpleNamespace(get_ffmpeg_exe=lambda: "unused")
    )
    path = Path(__file__).resolve().parents[1] / "scripts/demo/presentation_film.py"
    spec = importlib.util.spec_from_file_location("film_tail_test_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def receipt(tmp_path):
    def pin(name):
        path = tmp_path / name
        path.write_bytes(b"test fixture, not media")
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    source = pin("manifest.json")
    video = pin("finished-stock-orbit.mp4")
    reference = {"document_name": "TEST"}
    data = dict(
        status="recorded_requires_visual_review",
        errors=[],
        geometry_matches=True,
        source_manifest_unchanged=True,
        source_manifest=source,
        media=[video],
        evidence=[],
        implementation_sources=[],
        source_job="test",
        candidate_id="c1",
        candidate_digest="digest",
        verified_seconds=100,
        reference=reference,
        orbit={
            "recorder": {"status": "recorded", "document": "TEST"},
            "camera": {"status": "completed", "document_identity": {"name": "TEST"}},
            "tool_position_unchanged": True,
            "before": {"tool_position": {"x": 0, "y": 0, "z": 0}},
            "after": {"tool_position": {"x": 0, "y": 0, "z": 0}},
        },
        machine_playback={
            "status": "recorded",
            "errors": [],
            "playback_end_observed": True,
            "tool_position_changed": True,
        },
        target_display_hidden={"states_after": {"target": False}},
        target_display_before={"states_before": {"target": True}},
        target_display_restored={"states_after": {"target": True}},
    )
    path = tmp_path / "capture-receipt.json"
    path.write_text(json.dumps(data))

    def loader(path):
        return (
            {"job_id": "test", "best_verification": {"machining_seconds": 100}},
            SimpleNamespace(id="c1", digest="digest"),
            reference,
            None,
            None,
        )

    return path, data, loader


@pytest.mark.parametrize(("count", "durations"), [(1, [10]), (2, [5, 5]), (3, [4, 3, 3])])
def test_tail_budget_is_always_ten_seconds(film, tmp_path, count, durations):
    path, _, loader = receipt(tmp_path)
    shots = film.validated_tail_shots([path] * count, visually_reviewed=True, source_loader=loader)
    assert [s["duration_s"] for s in shots] == durations


def test_requires_visual_review(film, tmp_path):
    path, _, loader = receipt(tmp_path)
    with pytest.raises(ValueError, match="visual review"):
        film.validated_tail_shots([path], source_loader=loader)


def test_candidate_mismatch_rejected(film, tmp_path):
    path, data, loader = receipt(tmp_path)
    data["candidate_digest"] = "other"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="bound"):
        film.validated_tail_shots([path], visually_reviewed=True, source_loader=loader)


def test_media_mutation_rejected(film, tmp_path):
    path, data, loader = receipt(tmp_path)
    Path(data["media"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash changed"):
        film.validated_tail_shots([path], visually_reviewed=True, source_loader=loader)


def test_capture_failure_rejected(film, tmp_path):
    path, data, loader = receipt(tmp_path)
    data["errors"] = ["restoration failed"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="did not finish"):
        film.validated_tail_shots([path], visually_reviewed=True, source_loader=loader)
