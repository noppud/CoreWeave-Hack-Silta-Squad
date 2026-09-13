"""Transport/state tests only; no synthetic movie is presented as a real recording."""

from pathlib import Path

import pytest

from silta.cnc.simulation_video import SimulationVideo, playback_position


def reply(percent, x=0, document="Part A"):
    return {
        "status": "ok",
        "result": {
            "document": document,
            "active_command": "IronMachineSimulation",
            "fusion_version": "fixture",
            "raw_text": f"time, eDropDownEntry, Time, 0:00:01 ({percent}%)\n"
            f"x, eDropDownEntry, X position, {x} mm\n"
            "y, eDropDownEntry, Y position, 0 mm\n"
            "z, eDropDownEntry, Z position, 0 mm\n",
        },
    }


class Bridge:
    def __init__(self, values):
        self.values = iter(values)

    def request(self, *args, **kwargs):
        return next(self.values)


class Playback:
    def __init__(self, order, fail_start=False):
        self.order, self.fail_start = order, fail_start

    def prepare(self):
        self.order.append("rewind")

    def at_end(self, position):
        return position["percent"] == 100  # transport stub only

    def start(self):
        self.order.append("play")
        if self.fail_start:
            raise RuntimeError("UI read-back unavailable after pressing play")

    def stop(self):
        self.order.append("pause_or_confirm_stopped")


class Recorder:
    def __init__(self, order, directory, fail=False):
        self.order, self.fail = order, fail
        self.path = directory / "window-capture.mp4"

    def start(self):
        self.order.append("recorder_ready")
        if self.fail:
            raise RuntimeError("Screen recording permission unavailable")
        # Opaque transport fixture; no test media is stored in the real runs directory.
        self.path.write_bytes(b"unit-test recorder fixture")

    def status(self):
        return {"status": "recording"}

    def stop(self):
        self.order.append("recorder_finalized")
        return (
            {"status": "failed", "error": "permission denied"}
            if self.fail
            else {"status": "recorded", "duration_seconds": 3, "complete_frames": 180}
        )


def make_video(tmp_path, order, values, fail_recorder=False, fail_start=False):
    return SimulationVideo(
        "Part A",
        tmp_path / "evidence",
        bridge=Bridge(values),
        playback_factory=lambda *args: Playback(order, fail_start),
        recorder_factory=lambda document, directory, *args: Recorder(
            order, directory, fail_recorder
        ),
    )


def test_recording_starts_before_play_and_stops_after_playback(tmp_path):
    order = []
    video = make_video(tmp_path, order, [reply(100, 5), reply(0), reply(100, 5)])
    result = video.record(tmp_path / "movie.mp4")
    assert order == [
        "rewind",
        "recorder_ready",
        "play",
        "pause_or_confirm_stopped",
        "recorder_finalized",
    ]
    assert result["status"] == "recorded"
    assert result["playback_end_observed"]
    assert result["tool_position_changed"]
    assert not result["verification_pass"]
    assert result["visual_review_required"]
    assert Path(result["video"]["path"]).is_file()


def test_no_play_when_screen_recording_access_is_missing(tmp_path):
    order = []
    video = make_video(tmp_path, order, [reply(100), reply(0)], fail_recorder=True)
    result = video.record(tmp_path / "movie.mp4")
    assert "play" not in order
    assert result["status"] == "unavailable"
    assert result["video"] is None
    assert not (tmp_path / "movie.mp4").exists()


def test_uncertain_play_press_still_attempts_guarded_stop(tmp_path):
    order = []
    video = make_video(tmp_path, order, [reply(100), reply(0)], fail_start=True)
    result = video.record(tmp_path / "movie.mp4")
    assert "pause_or_confirm_stopped" in order
    assert result["status"] == "partial"
    assert not result["playback_started"]


def test_wrong_document_cannot_be_recorded(tmp_path):
    order = []
    video = make_video(tmp_path, order, [reply(0, document="Another document")])
    result = video.record(tmp_path / "movie.mp4")
    assert order == []
    assert result["status"] == "unavailable"


def test_missing_motion_never_becomes_successful_machine_video(tmp_path):
    order = []
    video = make_video(tmp_path, order, [reply(100), reply(0), reply(100)])
    result = video.record(tmp_path / "movie.mp4")
    assert result["status"] == "partial"
    assert not result["tool_position_changed"]


def test_no_overwrite(tmp_path):
    output = tmp_path / "movie.mp4"
    output.write_bytes(b"existing")
    video = make_video(tmp_path, [], [])
    with pytest.raises(ValueError, match="new .mp4"):
        video.record(output)
    assert output.read_bytes() == b"existing"


def test_ambiguous_or_absent_progress_is_not_completion():
    data = reply(100)
    data["result"]["raw_text"] *= 2
    with pytest.raises(RuntimeError, match="unambiguous"):
        playback_position(data, "Part A")
    data["result"]["active_command"] = "SelectCommand"
    with pytest.raises(RuntimeError, match="active Fusion"):
        playback_position(data, "Part A")


def test_per_operation_percentage_cannot_finish_whole_movie():
    from silta.cnc.simulation_video import FusionPlayback

    playback = FusionPlayback.__new__(FusionPlayback)
    playback.end_position = {
        "operation": "last side",
        "tool_position": {"x": "0 mm", "y": "0 mm", "z": "50 mm"},
    }
    assert not playback.at_end(
        {
            "percent": 100,
            "operation": "first top",
            "tool_position": {"x": "0 mm", "y": "0 mm", "z": "50 mm"},
        }
    )


def test_matching_end_pose_requires_stopped_playback():
    from silta.cnc.simulation_video import FusionPlayback

    class Native:
        state = {"texts": [{"text": "Pause"}]}

        def menu(self):
            pass

        def ui(self, *args):
            pass

    playback = FusionPlayback.__new__(FusionPlayback)
    playback.native = Native()
    playback.end_position = {"operation": "last", "tool_position": {"x": "1", "y": "2", "z": "3"}}
    position = dict(playback.end_position, percent=0)
    assert not playback.at_end(position)
    playback.native.state = {"texts": [{"text": "Play"}]}
    assert playback.at_end(position)


def test_dim_disabled_pause_is_not_mistaken_for_active_playback(tmp_path):
    from PIL import Image, ImageDraw

    from silta.cnc.simulation_video import menu_play_enabled

    image = Image.new("RGB", (100, 50), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 30, 25), fill=(60, 60, 60))
    draw.rectangle((50, 10, 70, 25), fill=(178, 178, 178))
    path = tmp_path / "menu.png"
    image.save(path)
    state = {
        "screenshot": str(path),
        "window_bounds": [0, 0, 100, 50],
        "texts": [
            {"text": "Play", "bounds": [10, 10, 20, 15]},
            {"text": "Pause", "bounds": [50, 10, 20, 15]},
        ],
    }
    assert menu_play_enabled(state)
    draw.rectangle((50, 10, 70, 25), fill=(60, 60, 60))
    image.save(path)
    assert not menu_play_enabled(state)


def test_recording_waits_for_rewind_controls_without_toggling_play(monkeypatch):
    from types import SimpleNamespace

    import silta.cnc.simulation_video as video
    from silta.cnc.simulation_video import FusionPlayback

    calls = []
    states = iter([False, True])
    monkeypatch.setattr(video, "menu_play_enabled", lambda state: next(states))
    monkeypatch.setattr(video.time, "sleep", lambda seconds: None)
    playback = object.__new__(FusionPlayback)
    playback.native = SimpleNamespace(
        state={},
        menu=lambda: calls.append("menu"),
        ui=lambda action: calls.append(action),
    )
    playback.stopped_menu()
    assert calls == ["menu", "inspect", "menu"]
