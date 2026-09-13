import json
import runpy
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from silta.cnc.fusion import FusionBridge


@pytest.fixture
def simulation_dispatch(monkeypatch):
    core = SimpleNamespace()
    fusion = SimpleNamespace()
    cam = SimpleNamespace(CAM=SimpleNamespace(cast=lambda product: product))
    for name, module in {
        "adsk": SimpleNamespace(core=core, fusion=fusion, cam=cam),
        "adsk.core": core,
        "adsk.fusion": fusion,
        "adsk.cam": cam,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    return runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "fusion/SiltaBridge/operations.py")
    )["dispatch"]


def test_simulation_dialog_preserves_raw_text_without_claiming_verification(simulation_dispatch):
    commands = []
    raw = "collisions, eDropDownEntry, Collisions, 54"
    app = SimpleNamespace(
        version="2705.1.15",
        activeDocument=SimpleNamespace(name="Candidate"),
        userInterface=SimpleNamespace(activeCommand="IronMachineSimulation"),
        executeTextCommand=lambda command: commands.append(command) or raw,
    )
    reply = simulation_dispatch(app, "simulation_dialog", {})
    assert commands == ["Toolkit.cmdDialog"]
    assert reply["result"]["raw_text"] == raw
    assert reply["result"]["active_command"] == "IronMachineSimulation"
    assert "status" not in reply and "completed" not in reply
    assert reply["coverage"] == ["simulation_dialog_text_only"]


def test_simulation_issues_does_not_exit_simulation_first(simulation_dispatch):
    calls = []
    command = SimpleNamespace(name="Issues", execute=lambda: calls.append("execute") or True)
    app = SimpleNamespace(
        userInterface=SimpleNamespace(
            commandDefinitions=SimpleNamespace(itemById=lambda name: calls.append(name) or command)
        )
    )
    reply = simulation_dispatch(app, "simulation_command", {"command_id": "SimulationIssues"})
    assert calls == ["SimulationIssues", "execute"]
    assert reply["result"]["verification_completed"] is False
    with pytest.raises(ValueError, match="Unsupported"):
        simulation_dispatch(app, "simulation_command", {"command_id": "SelectCommand"})


def test_machine_simulation_requires_explicit_setup_and_machine_model(simulation_dispatch):
    setup = SimpleNamespace(operationId=2, machine=SimpleNamespace(hasSimulationModel=False))
    cam = SimpleNamespace(setups=SimpleNamespace(count=1, item=lambda i: setup))
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(products=SimpleNamespace(itemByProductType=lambda _: cam)),
        userInterface=SimpleNamespace(),
    )
    for ids in ([], ["2", "2"]):
        with pytest.raises(ValueError, match="Explicit unique"):
            simulation_dispatch(
                app, "simulation_command", {"command_id": "IronMachineSimulation", "setup_ids": ids}
            )
    with pytest.raises(ValueError, match="missing"):
        simulation_dispatch(
            app, "simulation_command", {"command_id": "IronMachineSimulation", "setup_ids": ["3"]}
        )
    with pytest.raises(ValueError, match="full machine model"):
        simulation_dispatch(
            app, "simulation_command", {"command_id": "IronMachineSimulation", "setup_ids": ["2"]}
        )


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
