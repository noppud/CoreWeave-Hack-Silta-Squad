"""Fusion add-in entry point. Only fireCustomEvent is called by the watcher."""

import fcntl
import json
import os
import threading
import traceback
import uuid
from pathlib import Path

import adsk.cam
import adsk.core
import adsk.fusion

from . import operations, recovery

EVENT_ID = "com.silta.fusion.bridge.request"
_handlers = []
_stop = threading.Event()
_thread = None
_app = None
_event = None
_root = None
_owner_file = None
_owner_token = None


def _write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


class RequestHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        # A callback queued before unloading must not operate a new owner's queue.
        if _owner_file is None or _stop.is_set():
            return
        request = json.loads(args.additionalInfo)
        reply = {
            key: request.get(key, "") for key in ("request_id", "candidate_digest", "input_digest")
        }
        reply.update(
            status="ok", completed=True, coverage=[], issues=[], evidence=[], metrics={}, result={}
        )
        try:
            reply.update(operations.dispatch(_app, request["action"], request.get("payload", {})))
        except Exception as exc:
            reply.update(
                status="error",
                completed=False,
                issues=[{"type": "fusion_api_error", "message": str(exc)}],
                result={"traceback": traceback.format_exc()},
            )
        _write(_root / "responses" / (request["request_id"] + ".json"), reply)
        (_root / "processing" / (request["request_id"] + ".json")).unlink(missing_ok=True)
        (_root / "processing" / (request["request_id"] + ".owner")).unlink(missing_ok=True)


def _watch():
    while not _stop.wait(0.2):
        # One in-flight request; do not queue concurrent edits into Fusion.
        if any((_root / "processing").glob("*.json")):
            continue
        for path in sorted((_root / "requests").glob("*.json")):
            claimed = _root / "processing" / path.name
            try:
                _write(claimed.with_suffix(".owner"), {"pid": os.getpid(), "session": _owner_token})
                path.replace(claimed)
                request = json.loads(claimed.read_text(encoding="utf-8"))
                if request.get("request_id") != path.stem:
                    raise ValueError("Request identifier does not match filename")
                if not _app.fireCustomEvent(EVENT_ID, json.dumps(request)):
                    raise RuntimeError("Fusion rejected custom event")
            except Exception:
                _write(
                    _root / "watcher-error.json",
                    {"error": traceback.format_exc(), "request": str(claimed)},
                )
            break


def _acquire_owner(root):
    """flock covers independently loaded modules, including symlink aliases."""
    global _owner_file, _owner_token
    root.mkdir(parents=True, exist_ok=True)
    owner = (root / "bridge-owner.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        owner.close()
        return False
    except Exception:
        owner.close()
        raise
    _owner_file = owner
    _owner_token = uuid.uuid4().hex
    try:
        owner.seek(0)
        owner.truncate()
        json.dump(
            {"pid": os.getpid(), "owner": _owner_token, "source": str(Path(__file__).resolve())},
            owner,
        )
        owner.flush()
    except Exception:
        _release_owner()
        raise
    return True


def _release_owner():
    global _owner_file, _owner_token
    if _owner_file is not None:
        owner, _owner_file = _owner_file, None
        try:
            fcntl.flock(owner.fileno(), fcntl.LOCK_UN)
        finally:
            owner.close()
    _owner_token = None
    # Never unlink the lock: a replacement inode could create two owners.


def run(context):
    global _app, _event, _thread, _root
    if _owner_file is not None:
        if _thread is not None and _thread.is_alive() and not _stop.is_set():
            return True  # Fusion may call Run twice for the same registration.
        raise RuntimeError("Bridge owns its queue but is not running; stop it before restarting")
    root = Path(
        os.environ.get(
            "SILTA_FUSION_BRIDGE_DIR",
            str(Path.home() / "Library/Application Support/Silta/FusionBridge"),
        )
    ).resolve()
    if not _acquire_owner(root):
        return False  # Do not register/unregister events or overwrite another owner's ready.json.
    _root = root
    try:
        _app = adsk.core.Application.get()
        for name in ("requests", "responses", "processing"):
            (_root / name).mkdir(parents=True, exist_ok=True)
        recovered = recovery.recover_dead_requests(_root)
        if recovered:
            _write(_root / "startup-recovery.json", {"recovered": recovered})
        _event = _app.registerCustomEvent(EVENT_ID)
        if _event is None:
            raise RuntimeError("Fusion did not register the bridge event")
        handler = RequestHandler()
        if not _event.add(handler):
            raise RuntimeError("Fusion did not attach the bridge event handler")
        _handlers.append(handler)
        _stop.clear()
        _thread = threading.Thread(target=_watch, daemon=True)
        _thread.start()
        _write(
            _root / "ready.json",
            {
                "version": _app.version,
                "running": True,
                "owner": _owner_token,
                "pid": os.getpid(),
                "source": str(Path(__file__).resolve()),
            },
        )
        return True
    except Exception:
        _stop.set()
        if _thread is not None and _thread.is_alive():
            _thread.join(timeout=2)
            if _thread.is_alive():
                raise RuntimeError(
                    "Bridge startup failed with watcher still alive; ownership retained"
                ) from None
        if _event is not None:
            _app.unregisterCustomEvent(EVENT_ID)
            _event = None
        _handlers.clear()
        _thread = None
        _release_owner()
        raise


def stop(context):
    global _event, _thread
    if _owner_file is None:
        return False  # Stopping a duplicate registration cannot stop the owner.
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=2)
        if _thread.is_alive():
            # Do not let a second watcher acquire this queue until this one exits.
            _write(
                _root / "ready.json", {"running": False, "stopping": True, "owner": _owner_token}
            )
            return False
    if _event is not None:
        _app.unregisterCustomEvent(EVENT_ID)
        _event = None
    _handlers.clear()
    _thread = None
    _write(_root / "ready.json", {"running": False, "owner": _owner_token})
    _release_owner()
    return True
