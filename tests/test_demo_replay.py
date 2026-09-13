"""Prepared demo must not dispatch a model job or blindly toggle Fusion playback."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from silta.cnc.control_center import Center
from silta.cnc.demo_replay import PDF_HASH, DemoReplay, demo_match


def test_recognition_is_exact_hash_not_filename():
    assert demo_match(PDF_HASH)["run_id"] == "demo-umc-umc-12-recovery1"
    assert demo_match("silta-clevis-demo.pdf") is None
    assert demo_match("0" * 64) is None


def test_fresh_start_cannot_execute_matched_demo(tmp_path):
    center = Center(tmp_path)
    key = "drawing-" + "a" * 12
    folder = center.inputs / key
    folder.mkdir(parents=True)
    (folder / "intake.json").write_text(json.dumps({"id": key, "demo": demo_match(PDF_HASH)}))
    with pytest.raises(ValueError, match="Start demo replay"):
        center.start(key)
    assert center.process is None


def test_demo_does_not_overlap_running_worker(tmp_path):
    center = Center(tmp_path)
    center.process = SimpleNamespace(poll=lambda: None)
    with pytest.raises(ValueError, match="already working"):
        center.start_demo("drawing-" + "a" * 12)
    assert center.demo.session is None


def test_play_requires_ready_and_repeated_request_never_toggles(tmp_path):
    demo = DemoReplay(tmp_path, None)
    demo.evidence = tmp_path / "evidence"
    demo.session = {"id": "example", "status": "preparing"}
    with pytest.raises(ValueError, match="ready"):
        demo.play("example")
    assert not demo.play_event.is_set()
    demo.session["status"] = "ready"
    assert demo.play("example")["status"] == "playing"
    assert demo.play_event.is_set()
    demo.play_event.clear()
    assert demo.play("example")["status"] == "playing"
    assert not demo.play_event.is_set()


def test_changed_uploaded_bytes_cannot_open_retained_program(tmp_path):
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"%PDF-wrong")
    assert hashlib.sha256(path.read_bytes()).hexdigest() != PDF_HASH
    demo = DemoReplay(tmp_path, None)
    with pytest.raises(ValueError, match="has changed"):
        demo.start({"id": "drawing-" + "a" * 12, "drawing": str(path), "sha256": PDF_HASH})
    assert demo.thread is None


def test_finished_live_badge_expires_when_capture_is_stale(tmp_path):
    import time

    demo = DemoReplay(tmp_path, None)
    demo.session = {"id": "example", "status": "completed", "phase": "finished"}
    folder = tmp_path / ".private/fusion-live-gateway"
    folder.mkdir(parents=True)
    (folder / "frame.jpg").write_bytes(b"jpeg")
    capture = {
        "status": "live",
        "window_title": "Silta CAM 4-1d539c135f80 - Autodesk Fusion",
        "captured_at": time.time(),
        "heartbeat": time.time(),
    }
    (folder / "status.json").write_text(json.dumps(capture))
    assert demo.public("example")["live"]
    capture["captured_at"] -= 10
    (folder / "status.json").write_text(json.dumps(capture))
    assert not demo.public("example")["live"]
    capture["captured_at"] = time.time()
    capture["window_title"] = "Different part - Autodesk Fusion"
    (folder / "status.json").write_text(json.dumps(capture))
    assert not demo.public("example")["live"]
