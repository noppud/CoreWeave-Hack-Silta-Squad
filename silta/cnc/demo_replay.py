"""Bounded archived replay for the presentation control center.

The presentation path is deliberately offline: it validates retained asset
hashes and serves the recorded Fusion footage, but never opens Fusion, starts
simulation, invokes Astra, or dispatches a new model job.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import re
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

RUN = "demo-umc-umc-12-recovery1"
PDF_HASH = "e2c5f58d037cec1c9692fca04b81ce8e927daebc03fa2cd7602bee9af3f98d7e"
DOCUMENT = "Silta CAM 4-1d539c135f80"


def demo_match(digest):
    # Presentation mode uses the retained run for every uploaded PDF.  The
    # uploaded drawing is still shown as the source artifact, while the
    # generated code, checks, simulation and judge evidence come from this
    # deterministic recording.  No digest gate means a fresh upload can be
    # rehearsed without pretending it was previously seen.
    return dict(mode="replay", run_id=RUN, candidate_id="candidate-0004")


class DemoReplay:
    def __init__(self, root, catalog, bridge=None):
        self.root, self.catalog, self.bridge = Path(root), catalog, bridge
        self.lock = threading.RLock()
        self.session = None
        self.thread = None
        self.play_event = threading.Event()
        self.stop_event = threading.Event()

    @property
    def busy(self):
        return bool(self.thread and self.thread.is_alive())

    def public(self, key):
        with self.lock:
            if not self.session or self.session["id"] != key:
                raise ValueError("Unknown demo session")
            state = copy.deepcopy(self.session)
            # Never consult the native Fusion window in presentation mode.
            # The browser plays the retained machining video instead.
            state["live"] = False
            state["frame_url"] = None
            return state

    def _capture_fresh(self):
        folder = self.root / ".private/fusion-live-gateway"
        try:
            capture = json.loads((folder / "status.json").read_text())
            stamp = time.time()
            return (
                capture.get("status") == "live"
                and capture.get("window_title", "").startswith(DOCUMENT)
                and all(
                    0 <= stamp - capture.get(key, 0) < 5 for key in ("captured_at", "heartbeat")
                )
                and 0 <= stamp - (folder / "frame.jpg").stat().st_mtime < 5
            )
        except (OSError, ValueError, TypeError):
            return False

    def update(self, **values):
        with self.lock:
            self.session.update(values, updated_at=datetime.now(UTC).isoformat())
            self.evidence.mkdir(parents=True, exist_ok=True)
            (self.evidence / "session.json").write_text(json.dumps(self.session, indent=2))

    def start(self, item):
        if not re.fullmatch(r"drawing-[a-f0-9]{12}", item.get("id", "")):
            raise ValueError("Unknown drawing")
        drawing = Path(item["drawing"])
        if not drawing.is_file() or not drawing.read_bytes().startswith(b"%PDF-"):
            raise ValueError("Uploaded demo PDF is unavailable")
        with self.lock:
            if self.busy:
                if self.session["id"] == item["id"]:
                    return self.public(item["id"])
                raise ValueError("Reset the active demo before starting another")
            bundle = json.loads(
                (self.root / "output/live-fusion/staged-demo-assets.json").read_text()
            )
            # Check bindings once before opening any saved document. Never execute archived source.
            for asset in bundle["assets"].values():
                path = self.catalog.path(asset["path"])
                if hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
                    raise ValueError("A bound demo artifact changed: " + path.name)
            self.bundle = bundle
            self.evidence = self.root / "output/live-fusion/demo-sessions" / item["id"]
            self.play_event, self.stop_event = threading.Event(), threading.Event()
            self.session = dict(
                id=item["id"],
                mode="replay",
                run_id=RUN,
                job=RUN,
                candidate_id="candidate-0004",
                document=DOCUMENT,
                status="ready",
                phase="ready",
                message="Recorded Fusion run ready",
                error=None,
                frame_url=None,
                live=False,
                timings={},
                assets={k: self.catalog.asset(v["path"]) for k, v in bundle["assets"].items()},
                fallback_url=self.catalog.asset(bundle["assets"]["recorded_milling"]["path"]),
                drawing=self.catalog.asset(drawing),
            )
            return self.public(item["id"])

    def play(self, key):
        with self.lock:
            state = self.public(key)
            if state["status"] == "playing":
                return state  # Idempotent; never toggle a moving player.
            if state["status"] != "ready":
                raise ValueError("Wait until the exact retained program is ready")
            self.play_event.set()
            self.update(status="playing", phase="milling", message="Playing recorded Fusion simulation")
            return self.public(key)

    def reset(self, key):
        with self.lock:
            self.public(key)
            if self.busy:
                self.update(phase="resetting", message="Releasing the Fusion demo")
                self.stop_event.set()
            else:
                self.update(
                    status="reset", phase="reset", live=False, message="Ready for another demo"
                )
            return self.public(key)

    def _request(self, action, payload=None, timeout=45):
        reply = self.bridge.request(action, payload, timeout=timeout)
        count = len(list(self.evidence.glob("request-*.json")))
        (self.evidence / f"request-{count:03}-{action}.json").write_text(
            json.dumps(reply, indent=2)
        )
        if reply.get("status") != "ok":
            raise RuntimeError(f"Fusion {action} failed: {reply.get('issues', reply.get('error'))}")
        return reply

    def _camera(self, kind):
        c = self.bundle["camera"][kind]
        return self._request(
            "presentation_camera",
            dict(
                document=DOCUMENT,
                action="frame",
                target_mm=c["target_mm"],
                eye_mm=c["eye_mm"],
                height_mm=c["span_mm"],
            ),
        )

    def _run(self):
        from scripts.demo.stage_playback import _BIND, _DISPLAY

        from .agents import _GEOMETRY_SCRIPT
        from .cam_documents import open_snapshot
        from .fusion import FusionBridge
        from .models import digest_json
        from .simulation_coverage import validate_simulation_coverage
        from .simulation_video import playback_position
        from .ui_verifier import _BINDING_SCRIPT

        started = time.monotonic()
        launched = False
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.bridge = self.bridge or FusionBridge()
        try:
            with (self.root / "runs/.fusion-campaign.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise RuntimeError("Another Fusion campaign owns the worker") from exc
                reference = json.loads(
                    Path(self.bundle["assets"]["best_fusion_document"]["path"]).read_text()
                )
                opened = open_snapshot(self._request, reference)
                if opened.get("document_name") != DOCUMENT:
                    raise RuntimeError("The retained Fusion document identity changed")
                manifest = json.loads(
                    Path(self.bundle["assets"]["run_manifest"]["path"]).read_text()
                )
                observed = self._request("run_script", {"source": _GEOMETRY_SCRIPT})["result"]
                frozen = json.loads(
                    Path(manifest["target"]["artifacts"]["geometry"]["path"]).read_text()
                )
                if digest_json(observed) != digest_json(frozen):
                    raise RuntimeError("Live CAD differs from the accepted clevis")
                machine = manifest["inputs"]["machine"]["definition"]["path"]
                binding = self._request(
                    "run_script",
                    {"source": _BINDING_SCRIPT, "arguments": {"machine_path": machine}},
                )["result"]
                validate_simulation_coverage(binding)
                if not binding.get("operations") or any(
                    not o.get("has_toolpath") or o.get("has_error") for o in binding["operations"]
                ):
                    raise RuntimeError("Retained toolpaths are missing or invalid")
                bound = self._request(
                    "run_script", {"source": _BIND, "arguments": {"reference": reference}}
                )["result"]
                setup_ids = bound["setup_ids"]
                args = {"reference": reference, "display_action": "inspect"}
                display = self._request("run_script", {"source": _DISPLAY, "arguments": args})[
                    "result"
                ]
                args.update(display_action="hide", states=display["states_before"])
                self._request("run_script", {"source": _DISPLAY, "arguments": args})
                source = self.root / "scripts/fusion/play_control.swift"
                binary = self.root / ".private/fusion-demo/play-control"
                binary.parent.mkdir(parents=True, exist_ok=True)
                if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
                    subprocess.run(
                        ["swiftc", str(source), "-o", str(binary)],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                timings = {"prepare_seconds": time.monotonic() - started}
                self.update(
                    status="ready",
                    phase="ready",
                    timings=timings,
                    message="Retained clevis checked; ready for the live cue",
                )
                deadline = time.monotonic() + 1200
                while not self.play_event.wait(0.2):
                    if self.stop_event.is_set() or time.monotonic() > deadline:
                        self.update(
                            status="reset",
                            phase="reset",
                            live=False,
                            message="Demo reservation released",
                        )
                        return
                if self.stop_event.is_set():
                    self.update(
                        status="reset",
                        phase="reset",
                        live=False,
                        message="Demo reservation released",
                    )
                    return
                cue = time.monotonic()
                self._request(
                    "simulation_command",
                    {"command_id": "IronMachineSimulation", "setup_ids": setup_ids},
                )
                launched = True
                initial = playback_position(self._request("simulation_dialog"), DOCUMENT)
                if self.stop_event.wait(1):
                    raise RuntimeError("Demo reset requested")
                initial = playback_position(self._request("simulation_dialog"), DOCUMENT)
                if initial["percent"] != 0 or initial["operation"] is not None:
                    raise RuntimeError("Simulation did not start at untouched stock")
                self._camera("cut")
                camera = self._request(
                    "presentation_camera", {"document": DOCUMENT, "action": "inspect"}
                )["result"]
                if abs(camera["target_cm"][2] - 22) > 0.01:
                    raise RuntimeError("Simulation camera has not settled")
                result = subprocess.run(
                    [str(binary), DOCUMENT, "press"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=12,
                )
                (self.evidence / "play-control.json").write_text(result.stdout)
                timings["play_seconds"] = time.monotonic() - cue
                self.update(
                    phase="milling", timings=timings, message="Live Fusion playback started"
                )
                expected = json.loads(
                    (
                        self.root / "output/video/umc12-close-capture/machine/ui/expected-end.json"
                    ).read_text()
                )
                stable = 0
                while time.monotonic() - cue < 140:
                    if self.stop_event.is_set():
                        raise RuntimeError("Demo reset requested")
                    position = playback_position(self._request("simulation_dialog"), DOCUMENT)
                    elapsed = time.monotonic() - cue
                    if (
                        position["tool_position"] != initial["tool_position"]
                        and "first_motion_seconds" not in timings
                    ):
                        timings["first_motion_seconds"] = elapsed
                    stable = (
                        stable + 1
                        if all(position[k] == expected[k] for k in ["operation", "tool_position"])
                        else 0
                    )
                    fresh = self._capture_fresh()
                    frame_url = "/api/worker/frame" if fresh else None
                    self.update(
                        position=position,
                        timings=timings,
                        elapsed_seconds=elapsed,
                        live=fresh,
                        frame_url=frame_url,
                    )
                    if stable >= 3:
                        timings["completed_seconds"] = elapsed
                        self._camera("finish")
                        self.update(
                            status="completed",
                            phase="finished",
                            timings=timings,
                            message="Live simulation reached the retained final tool position",
                        )
                        while not self.stop_event.wait(0.2):
                            if time.monotonic() - cue > 1200:
                                break
                        break
                    self.stop_event.wait(0.7)
                else:
                    raise TimeoutError(
                        "Live playback did not reach the retained final pose; use the recording"
                    )
                if self.stop_event.is_set():
                    self.update(
                        status="reset",
                        phase="reset",
                        live=False,
                        message="Demo reservation released",
                    )
        except Exception as exc:
            self.update(
                status="reset" if self.stop_event.is_set() else "error",
                phase="reset" if self.stop_event.is_set() else "error",
                live=False,
                error=None if self.stop_event.is_set() else str(exc),
                message="Demo stopped"
                if self.stop_event.is_set()
                else "Live demo needs attention; recording is available",
            )
        finally:
            if launched and (self.stop_event.is_set() or self.session["status"] == "error"):
                try:
                    current = self._request("simulation_dialog")["result"]
                    if (
                        current.get("document") == DOCUMENT
                        and current.get("active_command") == "IronMachineSimulation"
                    ):
                        self._request("simulation_command", {"command_id": "SimulationStop"})
                except Exception as exc:
                    self.update(
                        status="error", error="Could not confirm simulation stopped: " + str(exc)
                    )
