"""Record actual Fusion machine-simulation playback, never reconstructed motion.

Requires an already open machine simulation and an explicitly authorized foreground
interval. Construction does not touch Fusion. `record()` rewinds, starts and stops
playback. The resulting video is presentation evidence, not a machining verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from .fusion import FusionBridge
from .models import Artifact
from .stock_export import StockExporter, find_text

ROOT = Path(__file__).resolve().parents[2]
VIDEO_SOURCE = ROOT / "scripts/fusion/window_video.swift"
PLAY_IDENTIFIER = "QTApplication.IronUI::QtPlayButton"


def playback_position(reply: dict, document: str) -> dict:
    result = reply.get("result", {})
    if reply.get("status") != "ok" or result.get("document") != document:
        raise RuntimeError("Recording lost its exact Fusion document")
    if result.get("active_command") != "IronMachineSimulation":
        raise RuntimeError("Expected an active Fusion machine simulation")
    raw = result.get("raw_text", "")
    matches = re.findall(r"^\s*time, eDropDownEntry, Time, [^\n]*\(([\d.]+)%\)", raw, re.M)
    if len(matches) != 1:
        raise RuntimeError("Fusion did not expose one unambiguous playback position")
    percent = float(matches[0])
    if not 0 <= percent <= 100:
        raise RuntimeError("Invalid Fusion playback percentage")
    pose = {}
    for axis in ("x", "y", "z"):
        values = re.findall(rf"^\s*{axis}, eDropDownEntry, [XYZ] position, ([^\n]+)", raw, re.M)
        if len(values) == 1:
            pose[axis] = values[0]
    return {
        "percent": percent,
        "tool_position": pose,
        "document": document,
        "fusion_version": result.get("fusion_version"),
    }


class FusionPlayback:
    """Small adapter over the already tested guarded native UI transport."""

    def __init__(self, document: str, evidence: Path, bridge):
        self.document, self.bridge = document, bridge
        self.native = StockExporter(document, evidence, bridge=bridge)

    def prepare(self) -> None:
        self.native.ui("focus")
        self.native.menu()
        # A visible Play command establishes that playback is currently stopped.
        # Do not blindly toggle a Play/Pause control when its state is unknown.
        find_text(self.native.state, "Play")
        self.native.click_text("Start of Toolpath")
        self.native.menu()
        find_text(self.native.state, "Play")
        self.native.ui("key", "escape")

    def start(self) -> None:
        buttons = [
            item
            for item in self.native.state["elements"]
            if item.get("AXIdentifier") == PLAY_IDENTIFIER and item.get("AXEnabled") is True
        ]
        if len(buttons) != 1:
            raise RuntimeError("Expected one observed Fusion play control")
        self.native.ui("press", buttons[0]["window"], PLAY_IDENTIFIER)

    def stop(self) -> None:
        self.native.ui("inspect")
        self.native.menu()
        labels = {
            item["text"].strip()
            for item in self.native.state["texts"]
            if item.get("confidence", 0) >= 0.8
        }
        if "Pause" in labels:
            self.native.click_text("Pause")
        elif "Play" in labels:
            self.native.ui("key", "escape")  # Already stopped at the end.
        else:
            self.native.ui("key", "escape")
            raise RuntimeError("Could not establish whether Fusion playback has stopped")


class WindowRecorder:
    def __init__(self, document: str, evidence: Path, max_seconds: float, fps: int):
        self.document, self.directory = document, evidence
        self.maximum, self.fps = max_seconds, fps
        self.binary = evidence / "window-video"
        self.path, self.stop_file = evidence / "window-capture.mp4", evidence / "stop-recording"
        self.status_path = evidence / "recorder-status.json"
        self.process = None
        self.log = None

    def status(self) -> dict:
        return json.loads(self.status_path.read_text()) if self.status_path.exists() else {}

    def start(self) -> None:
        subprocess.run(
            ["swiftc", "-parse-as-library", str(VIDEO_SOURCE), "-o", str(self.binary)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.log = (self.directory / "recorder.log").open("w")
        self.process = subprocess.Popen(
            [
                str(self.binary),
                self.document,
                str(self.path),
                str(self.stop_file),
                str(self.status_path),
                str(self.maximum),
                str(self.fps),
            ],
            stdout=self.log,
            stderr=self.log,
        )
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            state = self.status()
            if state.get("status") == "recording":
                return
            if self.process.poll() is not None:
                raise RuntimeError(state.get("error", "Window recorder exited before ready"))
            time.sleep(0.1)
        raise TimeoutError("Window recording did not become ready; playback was not started")

    def stop(self) -> dict:
        if self.process is None:
            return {"status": "not_started"}
        self.stop_file.touch(exist_ok=True)
        try:
            self.process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        finally:
            if self.log:
                self.log.close()
        return self.status()


class SimulationVideo:
    def __init__(
        self,
        document: str,
        evidence: str | Path,
        *,
        bridge=None,
        playback_factory=FusionPlayback,
        recorder_factory=WindowRecorder,
    ):
        self.document, self.directory = document, Path(evidence).resolve()
        self.bridge = bridge or FusionBridge()
        self.playback_factory, self.recorder_factory = playback_factory, recorder_factory

    def record(self, output: str | Path, *, max_seconds: float = 300, fps: int = 60) -> dict:
        if not self.document.strip() or not 5 <= max_seconds <= 840 or fps not in (30, 60):
            raise ValueError("Require document, 5..840 second limit and 30/60 fps")
        output = Path(output).resolve()
        if output.suffix.lower() != ".mp4" or output.exists():
            raise ValueError("Output must be a new .mp4 file")
        self.directory.mkdir(parents=True, exist_ok=False)
        samples, errors = [], []
        complete, started, start_attempted = False, False, False
        playback, recorder = None, None
        recorded = {"status": "not_started"}

        def observe():
            reply = self.bridge.request("simulation_dialog", timeout=15)
            position = playback_position(reply, self.document)
            (self.directory / f"position-{len(samples):04d}.json").write_text(
                json.dumps(reply, indent=2)
            )
            position["wall_time"] = time.time()
            samples.append(position)
            return position

        try:
            observe()  # Bind the document before any foreground action.
            playback = self.playback_factory(self.document, self.directory / "ui", self.bridge)
            playback.prepare()
            initial = observe()
            if initial["percent"] > 0.1:
                raise RuntimeError("Start of Toolpath did not read back at the beginning")
            recorder = self.recorder_factory(self.document, self.directory, max_seconds + 30, fps)
            recorder.start()  # Explicit recorder-ready handshake precedes Play.
            start_attempted = True
            playback.start()
            started = True
            deadline = time.monotonic() + max_seconds
            while time.monotonic() < deadline:
                position = observe()
                if recorder.status().get("status") != "recording":
                    raise RuntimeError("Native window recording failed during playback")
                if position["percent"] >= 99.9:
                    complete = True
                    break
                time.sleep(0.5)
            if not complete:
                errors.append("Playback end was not observed before the recording limit")
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            if start_attempted and playback:
                try:
                    playback.stop()
                except Exception as error:
                    errors.append(f"Playback stop not confirmed: {error}")
            if recorder:
                recorded = recorder.stop()

        artifact = None
        if recorded.get("status") == "recorded" and recorder and recorder.path.is_file():
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as destination, recorder.path.open("rb") as source:
                shutil.copyfileobj(source, destination)
            artifact = Artifact.from_path(output)
        else:
            errors.append(recorded.get("error", "No finalized multi-frame MP4"))
        # Dialog time/position is auxiliary playback evidence, not stock verification.
        moving_poses = {
            json.dumps(sample["tool_position"], sort_keys=True)
            for sample in samples[1:]
            if sample["tool_position"]
        }
        motion = len(moving_poses) > 1
        if artifact and not motion:
            errors.append("Tool motion was not confirmed by changing Fusion position readings")
        result = {
            "status": "recorded"
            if artifact and complete and not errors
            else "partial"
            if artifact
            else "unavailable",
            "document": self.document,
            "video": {"path": artifact.path, "sha256": artifact.sha256} if artifact else None,
            "playback_started": started,
            "playback_end_observed": complete,
            "tool_position_changed": motion,
            "recorder": recorded,
            "errors": errors,
            "samples": samples,
            "evidence_directory": str(self.directory),
            "verification_pass": False,
            "meaning": "Actual Fusion window playback; separate from machining verification",
            "visual_review_required": True,
        }
        (self.directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False))
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--max-seconds", type=float, default=300)
    parser.add_argument("--fps", type=int, choices=(30, 60), default=60)
    args = parser.parse_args()
    result = SimulationVideo(args.document, args.evidence).record(
        args.output, max_seconds=args.max_seconds, fps=args.fps
    )
    print(json.dumps(result, indent=2))
    if result["status"] != "recorded":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
