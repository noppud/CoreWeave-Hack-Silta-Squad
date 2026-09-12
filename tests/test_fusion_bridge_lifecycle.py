"""Two independently imported add-ins share one real filesystem ownership lock."""

import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import pytest

ENTRY = Path(__file__).resolve().parents[1] / "fusion/SiltaBridge/SiltaBridge.py"


class FakeEvent:
    def __init__(self, app):
        self.app, self.handlers = app, []

    def add(self, handler):
        if self.app.reject_handler:
            return False
        self.handlers.append(handler)
        return True


class FakeFusion:
    version = "lifecycle-test-double"

    def __init__(self):
        self.registered, self.unregistered, self.dispatched = [], [], []
        self.events = {}
        self.reject_handler = False
        self.registration_error = False

    def registerCustomEvent(self, event_id):
        if self.registration_error:
            raise RuntimeError("test registration failure")
        if event_id in self.events:
            raise RuntimeError("duplicate Fusion event")
        self.registered.append(event_id)
        event = FakeEvent(self)
        self.events[event_id] = event
        return event

    def unregisterCustomEvent(self, event_id):
        self.unregistered.append(event_id)
        self.events.pop(event_id)
        return True

    def fireCustomEvent(self, event_id, additional_info):
        for handler in list(self.events[event_id].handlers):
            handler.notify(types.SimpleNamespace(additionalInfo=additional_info))
        return True


@pytest.fixture
def instances(tmp_path, monkeypatch):
    app = FakeFusion()
    core = types.SimpleNamespace(
        Application=types.SimpleNamespace(get=lambda: app), CustomEventHandler=object
    )
    adsk = types.SimpleNamespace(
        core=core, fusion=types.SimpleNamespace(), cam=types.SimpleNamespace()
    )
    for key, value in {
        "adsk": adsk,
        "adsk.core": core,
        "adsk.fusion": adsk.fusion,
        "adsk.cam": adsk.cam,
    }.items():
        monkeypatch.setitem(sys.modules, key, value)
    monkeypatch.setenv("SILTA_FUSION_BRIDGE_DIR", str(tmp_path / "queue"))
    modules = []
    for name in ("test_bridge_original", "test_bridge_alias"):
        package = types.ModuleType(name)
        package.__path__ = [str(ENTRY.parent)]
        operations = types.ModuleType(name + ".operations")

        def dispatch(app, action, payload):
            app.dispatched.append(action)
            return {"result": {"handled": action}}

        operations.dispatch = dispatch
        monkeypatch.setitem(sys.modules, name, package)
        monkeypatch.setitem(sys.modules, name + ".operations", operations)
        spec = importlib.util.spec_from_file_location(name + ".SiltaBridge", ENTRY)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        modules.append(module)
    yield modules[0], modules[1], app, tmp_path / "queue"
    for module in modules:
        module.stop(None)


def test_duplicate_registration_never_owns_event_or_overwrites_ready(instances):
    owner, duplicate, app, queue = instances
    assert owner.run(None) is True
    before = (queue / "ready.json").read_bytes()
    thread = owner._thread
    assert duplicate.run(None) is False
    assert duplicate._thread is None and duplicate._owner_file is None
    assert duplicate.stop(None) is False
    assert (queue / "ready.json").read_bytes() == before
    assert not app.unregistered and thread.is_alive()
    assert app.registered == [owner.EVENT_ID]


def test_repeated_run_is_idempotent_and_queue_request_executes_once(instances):
    owner, duplicate, app, queue = instances
    owner.run(None)
    thread = owner._thread
    assert owner.run(None) is True and owner._thread is thread
    assert duplicate.run(None) is False
    request = {"request_id": "one", "action": "ping", "payload": {}}
    (queue / "requests/one.json").write_text(json.dumps(request))
    deadline = time.monotonic() + 2
    while not (queue / "responses/one.json").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert json.loads((queue / "responses/one.json").read_text())["result"] == {"handled": "ping"}
    assert app.dispatched == ["ping"]
    assert len(app.registered) == 1


def test_owner_release_allows_duplicate_to_start_without_deleting_lock_inode(instances):
    owner, duplicate, app, queue = instances
    owner.run(None)
    inode = (queue / "bridge-owner.lock").stat().st_ino
    assert owner.stop(None) is True
    assert not json.loads((queue / "ready.json").read_text())["running"]
    assert duplicate.run(None) is True
    assert len(app.registered) == 2 and len(app.unregistered) == 1
    assert (queue / "bridge-owner.lock").stat().st_ino == inode
    assert owner.stop(None) is False
    assert len(app.unregistered) == 1
    assert json.loads((queue / "ready.json").read_text())["owner"] == duplicate._owner_token


@pytest.mark.parametrize("failure", ["register", "handler"])
def test_startup_failure_releases_only_its_own_registration_and_lock(instances, failure):
    owner, duplicate, app, _ = instances
    if failure == "register":
        app.registration_error = True
    else:
        app.reject_handler = True
    with pytest.raises(RuntimeError):
        owner.run(None)
    assert owner._owner_file is None and owner._thread is None and owner._event is None
    app.registration_error = app.reject_handler = False
    assert duplicate.run(None) is True
    count = len(app.unregistered)
    owner.stop(None)
    assert len(app.unregistered) == count


def test_nonowner_or_stopped_handler_cannot_dispatch_queued_event(instances):
    owner, duplicate, app, _ = instances
    owner.run(None)
    args = types.SimpleNamespace(additionalInfo=json.dumps({"request_id": "old", "action": "edit"}))
    duplicate.RequestHandler().notify(args)
    owner.stop(None)
    owner.RequestHandler().notify(args)
    assert not app.dispatched


def test_lock_retained_until_watcher_has_actually_stopped(instances):
    owner, duplicate, app, queue = instances
    owner.run(None)
    owner._stop.set()
    owner._thread.join(timeout=2)
    # Explicit thread-status double exercises the join timeout branch without a
    # real leaked background worker or holding the test suite for two seconds.
    busy = types.SimpleNamespace(alive=True)
    owner._thread = types.SimpleNamespace(join=lambda timeout: None, is_alive=lambda: busy.alive)
    assert owner.stop(None) is False
    assert json.loads((queue / "ready.json").read_text())["stopping"] is True
    assert duplicate.run(None) is False and not app.unregistered
    busy.alive = False
    assert owner.stop(None) is True
    assert duplicate.run(None) is True


def test_alias_queue_path_resolves_to_same_owner(instances, tmp_path, monkeypatch):
    owner, duplicate, app, queue = instances
    owner.run(None)
    alias = tmp_path / "alias"
    alias.symlink_to(queue, target_is_directory=True)
    monkeypatch.setenv("SILTA_FUSION_BRIDGE_DIR", str(alias))
    assert duplicate.run(None) is False
    assert len(app.registered) == 1
