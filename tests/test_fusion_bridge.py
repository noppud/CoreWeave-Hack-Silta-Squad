import json
import runpy
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from silta.cnc.fusion import FusionBridge


def test_blank_fusion_document_ping_and_inspect_do_not_require_cam(monkeypatch):
    empty = SimpleNamespace(count=0)
    design = SimpleNamespace(rootComponent=SimpleNamespace(bRepBodies=empty))
    products = SimpleNamespace(count=1, item=lambda i: design)
    app = SimpleNamespace(
        version="test-fusion", activeDocument=SimpleNamespace(name="Blank", products=products)
    )
    core = SimpleNamespace()
    fusion = SimpleNamespace(Design=SimpleNamespace(cast=lambda p: p if p is design else None))
    cam = SimpleNamespace(CAM=SimpleNamespace(cast=lambda p: None))
    adsk = SimpleNamespace(core=core, fusion=fusion, cam=cam)
    for name, module in {
        "adsk": adsk,
        "adsk.core": core,
        "adsk.fusion": fusion,
        "adsk.cam": cam,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    operations = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "fusion/SiltaBridge/operations.py")
    )
    assert operations["dispatch"](app, "ping", {})["result"]["document"] == "Blank"
    assert operations["dispatch"](app, "inspect", {})["result"] == {
        "fusion_version": "test-fusion",
        "document": "Blank",
        "bodies": [],
    }


def respond(directory, *, corrupt=False):
    while not list((directory / "requests").glob("*.json")):
        time.sleep(0.01)
    path = next((directory / "requests").glob("*.json"))
    request = json.loads(path.read_text())
    response = {key: request[key] for key in ("request_id", "candidate_digest", "input_digest")}
    response["status"] = "unknown"
    if corrupt:
        response["candidate_digest"] = "another-candidate"
    (directory / "responses").mkdir()
    (directory / "responses" / path.name).write_text(json.dumps(response))


def test_exact_response_binding(tmp_path):
    thread = threading.Thread(target=respond, args=(tmp_path,))
    thread.start()
    result = FusionBridge(tmp_path).request(
        "simulation", candidate_hash="candidate", input_digest="setup", timeout=2
    )
    thread.join()
    assert result["status"] == "unknown"


def test_other_candidate_response_rejected(tmp_path):
    thread = threading.Thread(target=respond, args=(tmp_path,), kwargs={"corrupt": True})
    thread.start()
    with pytest.raises(ValueError, match="candidate_digest mismatch"):
        FusionBridge(tmp_path).request(
            "simulation", candidate_hash="candidate", input_digest="setup", timeout=2
        )
    thread.join()


def test_timeout_preserves_single_request_without_retry(tmp_path):
    with pytest.raises(TimeoutError, match="do not blindly retry"):
        FusionBridge(tmp_path).request("run_script", {"source": "result = 1"}, timeout=0.01)
    assert len(list((tmp_path / "requests").glob("*.json"))) == 1


def test_api_verifier_cannot_promote_forged_pass(tmp_path, monkeypatch):
    bridge = FusionBridge(tmp_path)
    monkeypatch.setattr(
        bridge,
        "request",
        lambda *a, **kw: {
            "status": "passed",
            "completed": True,
            "evidence": [],
        },
    )
    candidate = SimpleNamespace(digest="candidate", verify=lambda: None)
    context = SimpleNamespace(input_digest="setup")
    verdict = bridge.verify(candidate, context)
    assert verdict.status == "unknown"
    assert verdict.completed is False
    assert verdict.issues == ("needs_ui_verification",)
