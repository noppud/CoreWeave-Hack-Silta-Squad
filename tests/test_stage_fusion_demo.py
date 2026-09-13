import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "stage", Path(__file__).resolve().parents[1] / "scripts/demo/stage_fusion_demo.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Candidate:
    id = "candidate-1"
    digest = "frozen-digest"

    def verify(self):
        pass


def test_first_verification_pauses_only_once(tmp_path):
    calls = []
    pause = module.PresentationPause(
        tmp_path / "receipt.json", wait=lambda: calls.append("release")
    )
    context = SimpleNamespace(input_digest="inputs", versions={"checks": "v1"})
    pause.before_verify(Candidate(), context)
    pause.before_verify(Candidate(), context)
    assert calls == ["release"]
    assert pause.data["status"] == "live_verification"
    assert "prepared_at" in pause.data and "released_at" in pause.data


def test_wrong_candidate_release_never_starts_verifier(tmp_path):
    release = tmp_path / "release"
    release.write_text("different-candidate")
    pause = module.PresentationPause(tmp_path / "receipt.json", release)
    with pytest.raises(ValueError, match="candidate digest"):
        pause.before_verify(Candidate(), SimpleNamespace(input_digest="i", versions={}))
    assert not pause.released


def test_shadow_learning_does_not_modify_main(tmp_path):
    source = tmp_path / "main"
    source.mkdir()
    for name in ("cad_cam.md", "checks.py"):
        (source / name).write_text("original")
    target = tmp_path / "shadow"
    module.copy_learning(source, target)
    (target / "checks.py").write_text("learned during assessment")
    assert (source / "checks.py").read_text() == "original"
    with pytest.raises(FileExistsError):
        module.copy_learning(source, target)


def test_presentation_binding_failure_never_starts_simulation(tmp_path):
    import json
    import runpy

    show = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/stage_playback.py")
    )["show"]
    path = tmp_path / "reference.json"
    path.write_text(json.dumps({"version_id": "exact"}))
    candidate = SimpleNamespace(
        id="c1", verify=lambda: None, artifacts={"fusion_document": SimpleNamespace(path=path)}
    )

    class Bridge:
        def __init__(self):
            self.calls = []

        def request(self, action, payload=None):
            self.calls.append(action)
            return {"status": "error", "error": "wrong document"}

    bridge = Bridge()
    result = show(candidate, bridge, tmp_path / "evidence", wait=lambda _: None)
    assert result["status"] == "presentation_failed"
    assert bridge.calls == ["run_script"]
    assert "not a new verdict" in result["meaning"]


@pytest.mark.parametrize("read_fails", [False, True])
@pytest.mark.parametrize("stop_fails", [False, True])
def test_playback_observes_motion_and_stops_on_read_failure(
    tmp_path, monkeypatch, read_fails, stop_fails
):
    import json
    import runpy

    import silta.cnc.simulation_video as video

    observations = iter(
        [
            {"tool_position": [0, 0, 0]},
            {"tool_position": [0, 0, 0]},
            RuntimeError("evidence unavailable") if read_fails else {"tool_position": [1, 0, 0]},
        ]
    )

    def observe(*args):
        value = next(observations)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(video, "playback_position", observe)
    show = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/stage_playback.py")
    )["show"]
    path = tmp_path / "ref.json"
    path.write_text(json.dumps({}))
    candidate = SimpleNamespace(
        id="c1", verify=lambda: None, artifacts={"fusion_document": SimpleNamespace(path=path)}
    )
    commands = []

    class Bridge:
        def request(self, action, payload=None):
            if action == "run_script" and "display_action" in payload["arguments"]:
                display = payload["arguments"]["display_action"]
                commands.append(display)
                return {
                    "status": "ok",
                    "result": {
                        "states_before": {"target": True},
                        "states_after": {"target": display != "hide"},
                    },
                }
            if action == "simulation_command":
                commands.append(payload["command_id"])
            return {"status": "ok", "result": {"document": "exact", "setup_ids": [1]}}

    class Playback:
        def __init__(self, *args):
            pass

        def prepare(self):
            pass

        def start(self):
            commands.append("play")

        def stop(self):
            commands.append("stop")
            if stop_fails:
                raise RuntimeError("stop failed")

    result = show(
        candidate, Bridge(), tmp_path / "evidence", playback_factory=Playback, wait=lambda _: None
    )
    assert result["playback_requested"] is True
    assert result["tool_motion_observed"] is (not read_fails)
    assert commands[:3] == ["inspect", "hide", "IronMachineSimulation"]
    assert commands[-3:] == ["stop", "SimulationStop", "restore"]
    assert result["target_display_restore"]["result"]["states_after"] == {"target": True}
    if read_fails or stop_fails:
        assert result["status"] == "presentation_failed"


def test_stage_binding_serializes_setup_id(monkeypatch):
    import runpy
    import sys
    import types

    source = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/stage_playback.py")
    )["_BIND"]
    setup = SimpleNamespace(operationId=2)
    cam = SimpleNamespace(setups=SimpleNamespace(count=1, item=lambda _: setup))
    adsk = types.ModuleType("adsk")
    adsk.cam = types.ModuleType("adsk.cam")
    adsk.cam.CAM = SimpleNamespace(cast=lambda _: cam)
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.cam", adsk.cam)
    reference = dict(data_file_id="f", version_id="v1", version_number=1, project_id="p")
    data = SimpleNamespace(
        id="f", versionId="v1", versionNumber=1, parentProject=SimpleNamespace(id="p")
    )
    doc = SimpleNamespace(
        dataFile=data, name="exact", products=SimpleNamespace(itemByProductType=lambda _: cam)
    )
    scope = {
        "app": SimpleNamespace(activeDocument=doc, hasActiveJobs=False),
        "payload": {"reference": reference},
    }
    exec(source, scope)
    assert scope["result"]["setup_ids"] == ["2"]


def display_scope(monkeypatch, *, changed_document=False):
    """Minimal Fusion API double exercises the actual embedded display script."""
    import runpy
    import sys
    import types

    source = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/stage_playback.py")
    )["_DISPLAY"]

    class Body:
        def __init__(self, identity, visible):
            self.nativeObject = None
            self.isLightBulbOn = visible
            self.attributes = SimpleNamespace(
                itemByName=lambda group, key: SimpleNamespace(value=identity) if identity else None
            )

    target, hidden_target, fixture = (
        Body("target", True),
        Body("hidden-target", False),
        Body(None, True),
    )
    bodies = [target, hidden_target, fixture]
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(
            bRepBodies=SimpleNamespace(count=3, item=bodies.__getitem__), allOccurrences=[]
        )
    )
    cam = SimpleNamespace(
        setups=SimpleNamespace(count=1, item=lambda _: SimpleNamespace(operationId=2))
    )
    adsk = types.ModuleType("adsk")
    adsk.cam = types.ModuleType("adsk.cam")
    adsk.cam.CAM = SimpleNamespace(cast=lambda value: value)
    adsk.fusion = types.ModuleType("adsk.fusion")
    adsk.fusion.Design = SimpleNamespace(cast=lambda value: value)
    for name, value in (("adsk", adsk), ("adsk.cam", adsk.cam), ("adsk.fusion", adsk.fusion)):
        monkeypatch.setitem(sys.modules, name, value)
    reference = dict(data_file_id="f", version_id="v1", version_number=1, project_id="p")
    data = SimpleNamespace(
        id="other" if changed_document else "f",
        versionId="v1",
        versionNumber=1,
        parentProject=SimpleNamespace(id="p"),
    )
    doc = SimpleNamespace(
        dataFile=data,
        name="exact",
        products=SimpleNamespace(
            itemByProductType=lambda kind: cam if kind == "CAMProductType" else design
        ),
    )
    app = SimpleNamespace(activeDocument=doc, hasActiveJobs=False)

    def execute(action, states=None):
        scope = {
            "app": app,
            "payload": {
                "reference": reference,
                "display_action": action,
                "states": states,
            },
        }
        exec(source, scope)
        return scope["result"]

    return execute, bodies


def test_target_display_hides_only_tagged_bodies_and_restores_exact_states(monkeypatch):
    execute, bodies = display_scope(monkeypatch)
    saved = execute("inspect")["states_before"]
    assert saved == {"target": True, "hidden-target": False}
    result = execute("hide", saved)
    assert result["states_after"] == {"target": False, "hidden-target": False}
    assert bodies[2].isLightBulbOn is True
    execute("restore", saved)
    assert [b.isLightBulbOn for b in bodies] == [True, False, True]


def test_target_display_wrong_document_fails_before_visibility_changes(monkeypatch):
    execute, bodies = display_scope(monkeypatch, changed_document=True)
    with pytest.raises(RuntimeError, match="document/version changed"):
        execute("hide", {"target": True, "hidden-target": False})
    assert [b.isLightBulbOn for b in bodies] == [True, False, True]


def test_target_display_rejects_stale_snapshot_without_hiding_fixture(monkeypatch):
    execute, bodies = display_scope(monkeypatch)
    with pytest.raises(RuntimeError, match="snapshot does not match"):
        execute("hide", {"fixture": True})
    assert [b.isLightBulbOn for b in bodies] == [True, False, True]


@pytest.mark.parametrize("failure", ["hide", "launch", "restore"])
def test_display_restoration_attempted_when_presentation_fails(tmp_path, failure):
    import json
    import runpy

    show = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/stage_playback.py")
    )["show"]
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({}))
    candidate = SimpleNamespace(
        id="c1",
        verify=lambda: None,
        artifacts={"fusion_document": SimpleNamespace(path=reference)},
    )
    calls = []

    class Bridge:
        def request(self, action, payload=None):
            if action == "run_script":
                display = payload["arguments"].get("display_action")
                if display is None:
                    return {"status": "ok", "result": {"document": "doc", "setup_ids": ["2"]}}
                calls.append(display)
                if display == "hide" and failure == "hide":
                    # Transport failure after mutation still requires restoring the prior snapshot.
                    raise RuntimeError("hide reply lost")
                if display == "restore" and failure == "restore":
                    return {"status": "error", "error": "restore unavailable"}
                return {
                    "status": "ok",
                    "result": {
                        "states_before": {"target": True},
                        "states_after": {"target": display != "hide"},
                    },
                }
            if action == "simulation_command":
                command = payload["command_id"]
                calls.append(command)
                if command == "IronMachineSimulation":
                    return {"status": "error", "error": "launch failed"}
                return {"status": "ok"}
            raise AssertionError("No camera or playback after launch failure")

    row = show(candidate, Bridge(), tmp_path / "receipt", wait=lambda _: None)
    assert row["status"] == "presentation_failed"
    assert calls[-1] == "restore"
    if failure != "hide":
        assert calls[-2] == "SimulationStop"
    if failure == "restore":
        assert "target_display_restore_error" in row
    else:
        assert row["target_display_restore"]["result"]["states_after"] == {"target": True}


@pytest.mark.parametrize("has_menu", [True, False])
def test_stop_cleanup_escape_only_for_observed_menu(has_menu):
    import runpy

    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/demo/stage_playback.py")
    )["dismiss_observed_marking_menu"]
    calls = []

    class Native:
        def ui(self, *args):
            calls.append(args)
            return {"windows": [{"title": "Marking Menu"}] if has_menu and len(calls) == 1 else []}

    receipt = helper(Native())
    assert receipt["escape_sent"] is has_menu
    assert (("key", "escape") in calls) is has_menu
    if has_menu:
        assert receipt["menu_still_open"] is False
