"""Control-center boundaries: real artifacts, PDF intake, and HTTP media serving."""

import hashlib
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from silta.cnc.control_center import Center, make_handler


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def center(tmp_path):
    profile = {
        "status": "ready",
        "unresolved": [],
        "drawings": [],
        "machine": {"name": "Test machine"},
        "setup": {
            "material": "AL6061",
            "stock": {"dimensions_mm": [80, 80, 70]},
            "simulation_assumptions": ["Fixed test setup"],
        },
    }
    write(tmp_path / "config/control-center-umc-profile.json", profile)
    return Center(tmp_path, enable_runs=False)


def test_unfamiliar_pdf_is_accepted_with_explicit_shop_context(center):
    pdf = b"%PDF-1.4\nnew drawing\n%%EOF"
    item = center.intake("new-part.pdf", pdf)
    assert item["status"] == "ready"
    assert item["profile"]["known_drawing"] is False
    assert item["profile"]["stock"] == [80, 80, 70]
    config = json.loads((center.inputs / item["id"] / "job.json").read_text())
    assert config["drawings"][0]["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert config["setup"]["simulation_assumptions"] == ["Fixed test setup"]
    assert center.process is None  # Upload alone does not execute anything.


def test_known_pdf_uses_its_matching_setup(center):
    pdf = b"%PDF-1.4\nknown drawing"
    write(
        center.root / "config/demo-campaign/known-job.json",
        {
            "status": "ready",
            "drawings": [{"sha256": hashlib.sha256(pdf).hexdigest()}],
            "machine": {"name": "Matching machine"},
            "setup": {"material": "Steel"},
        },
    )
    item = center.intake("known.pdf", pdf)
    assert item["profile"]["known_drawing"] is True
    assert item["profile"]["machine"] == "Matching machine"
    assert item["profile"]["material"] == "Steel"


def test_reject_non_pdf_without_launch(center):
    with pytest.raises(ValueError, match="PDF drawing"):
        center.intake("not.pdf", b"<html>not a drawing</html>")
    assert center.process is None


def test_review_only_cannot_start(center):
    item = center.intake("part.pdf", b"%PDF-1.4\nnew")
    with pytest.raises(ValueError, match="review-only"):
        center.start(item["id"])


def test_artifacts_cannot_escape_workspace_or_expose_private_files(center, tmp_path):
    catalog = center.catalog
    private = tmp_path / ".private/secret.json"
    write(private, {"secret": "not exposed"})
    assert catalog.asset(private) is None
    assert catalog.asset(tmp_path / "../outside.json") is None
    link = tmp_path / "runs/link.json"
    link.parent.mkdir()
    link.symlink_to(private)
    assert catalog.asset(link) is None


def test_detail_preserves_unknown_verdict_and_includes_actual_nc(center):
    job = center.root / "runs/example"
    nc = job / "candidate.nc"
    job.mkdir(parents=True)
    nc.write_text("G21\nG90\n")
    write(
        job / "manifest.json",
        {
            "job_id": "example",
            "status": "incomplete",
            "events": [],
            "best_candidate": {"artifacts": {"nc-0": {"path": str(nc)}}},
            "best_verification": {"status": "unknown", "completed": False},
        },
    )
    detail = center.catalog.detail("example")
    assert detail["verdict"]["status"] == "unknown"
    assert detail["summary"]["best_seconds"] is None
    assert detail["sources"][0]["content"] == "G21\nG90\n"
    assert detail["stock_mesh"] is None


def test_stopped_worker_has_explicit_placeholder_before_first_manifest(center):
    item = center.intake("part.pdf", b"%PDF-1.4\nnew")
    folder = center.inputs / item["id"]
    raw = json.loads((folder / "intake.json").read_text())
    raw["job"] = "control-test"
    write(folder / "intake.json", raw)
    detail = center.detail("control-test")
    assert detail["status"] == "stopped"
    assert detail["verdict"] == {}
    assert detail["summary"]["passes"] == 0
    assert detail["drawings"]


@pytest.fixture
def server(center):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(center))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def test_range_serving_supports_video_seeking(center, server):
    path = center.root / "output/video/test.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"0123456789")
    url = center.catalog.asset(path)
    with urlopen(Request(server + url, headers={"Range": "bytes=3-6"})) as response:
        assert response.status == 206
        assert response.headers["Content-Range"] == "bytes 3-6/10"
        assert response.read() == b"3456"
    with urlopen(Request(server + url, headers={"Range": "bytes=-3"})) as response:
        assert response.read() == b"789"


def test_unregistered_artifact_is_not_served(center, server):
    write(center.root / "runs/unregistered.json", {"unregistered": True})
    with pytest.raises(HTTPError) as error:
        urlopen(server + "/artifact/runs/unregistered.json")
    assert error.value.code == 404


def test_external_origin_cannot_start_or_upload(center, server):
    request = Request(
        server + "/api/upload",
        data=b"%PDF-1.4",
        method="POST",
        headers={"Origin": "https://other.example"},
    )
    with pytest.raises(HTTPError) as error:
        urlopen(request)
    assert error.value.code == 403
    assert not center.inputs.exists()


def test_start_launches_existing_runner_once_with_scoped_credentials(center, monkeypatch):
    center.enable_runs = True
    item = center.intake("part.pdf", b"%PDF-1.4\nfresh part")
    learning = center.root / "learning"
    learning.mkdir()
    (learning / "checks.py").write_text('def check(data): return {"passed": True}\n')
    (learning / "cad_cam.md").write_text("Retained shop guidance")
    monkeypatch.setattr("silta.cnc.cli.read_inputs", lambda path: object())
    monkeypatch.setattr(center, "ping", lambda: center.worker.update(status="ready"))
    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(poll=lambda: None, returncode=None)

    monkeypatch.setattr("silta.cnc.control_center.subprocess.Popen", launch)
    result = center.start(item["id"])
    assert result["status"] == "starting"
    assert commands[0][1:5] == ["exec", "--only", "COREWEAVE_WANDB_API_KEY", "--"]
    assert "silta.cnc.cli" in commands[0]
    assert "--max-attempts" in commands[0]
    assert (center.inputs / item["id"] / "learning/checks.py").read_text() == (
        learning / "checks.py"
    ).read_text()
    with pytest.raises(ValueError, match="already working"):
        center.start(item["id"])
    assert len(commands) == 1


def test_live_window_reuses_fresh_capture_without_exposing_pairing(center, monkeypatch):
    import time

    from silta.cnc.fusion import FusionBridge

    def no_bridge(*args, **kwargs):
        pytest.fail("Fresh companion capture should not call Fusion")

    monkeypatch.setattr(FusionBridge, "request", no_bridge)
    folder = center.root / ".private/fusion-live-gateway"
    write(
        folder / "status.json",
        {
            "status": "live",
            "heartbeat": time.time(),
            "captured_at": time.time(),
            "window_title": "Current Fusion document",
            "pairing_token": "not-public",
        },
    )
    (folder / "frame.jpg").write_bytes(b"jpeg-test-frame")
    result = center.capture_frame()
    assert result["document"] == "Current Fusion document"
    assert result["refresh_ms"] == 250
    assert "not-public" not in json.dumps(result)
    assert result["url"].startswith("/artifact/output/control-center/")
    assert (
        center.root / result["url"].removeprefix("/artifact/")
    ).read_bytes() == b"jpeg-test-frame"


def test_stale_window_is_not_reported_live(center, monkeypatch):
    from silta.cnc.fusion import FusionBridge

    def unavailable(*args, **kwargs):
        raise RuntimeError("No live bridge")

    monkeypatch.setattr(FusionBridge, "request", unavailable)
    folder = center.root / ".private/fusion-live-gateway"
    write(folder / "status.json", {"status": "live", "heartbeat": 1, "captured_at": 1})
    (folder / "frame.jpg").write_bytes(b"old-frame")
    with pytest.raises(ValueError, match="viewport unavailable"):
        center.capture_frame()


def test_uploaded_job_enters_part_library_from_real_manifest(center):
    item = center.intake("incoming.pdf", b"%PDF-1.4\nnew")
    intake_path = center.inputs / item["id"] / "intake.json"
    saved = json.loads(intake_path.read_text())
    saved["job"] = "control-incoming"
    write(intake_path, saved)
    write(
        center.root / "runs/control-incoming/manifest.json",
        {
            "job_id": "control-incoming",
            "status": "running",
            "events": [],
            "inputs": {"drawings": []},
        },
    )
    parts = center.state()["parts"]
    assert len(parts) == 1
    assert parts[0]["label"] == "incoming.pdf"
    assert parts[0]["verified"] is False


def test_packaged_viewer_assets_need_no_custom_simulator(center, server):
    center.root = Path(__file__).resolve().parents[1]
    for route in (
        "/",
        "/model.js",
        "/reference",
        "/vendor/three.module.js",
        "/vendor/three.core.js",
        "/vendor/OrbitControls.js",
        "/vendor/STLLoader.js",
    ):
        with urlopen(server + route) as response:
            assert response.status == 200
            assert response.read()
