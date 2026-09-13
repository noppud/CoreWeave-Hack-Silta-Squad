import json
import runpy
from pathlib import Path

recover = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "fusion/SiltaBridge/recovery.py")
)["recover_dead_requests"]


def test_dead_owner_preserved_without_replay(tmp_path):
    processing = tmp_path / "processing"
    processing.mkdir()
    raw = b'{"request_id":"one","action":"mutation"}'
    (processing / "one.json").write_bytes(raw)
    (processing / "one.owner").write_text(json.dumps({"pid": 123, "session": "old"}))
    rows = recover(tmp_path, dead=lambda pid: pid == 123)
    assert len(rows) == 1 and rows[0]["replayed"] is False
    assert Path(rows[0]["request"]).read_bytes() == raw
    assert not list(processing.glob("*.json"))
    assert not (tmp_path / "requests").exists()


def test_live_and_legacy_owner_remain_blocked(tmp_path):
    processing = tmp_path / "processing"
    processing.mkdir()
    (processing / "legacy.json").write_text("{}")
    (processing / "live.json").write_text("{}")
    (processing / "live.owner").write_text(json.dumps({"pid": 123, "session": "live"}))
    assert recover(tmp_path, dead=lambda pid: False) == []
    assert len(list(processing.glob("*.json"))) == 2


def test_live_pid_reuse_and_probe_errors_are_conservative(monkeypatch):
    import os

    functions = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "fusion/SiltaBridge/recovery.py")
    )
    proven_dead = functions["proven_dead"]
    assert proven_dead(os.getpid()) is False
    assert proven_dead(True) is False
    assert proven_dead(10**100) is False

    def denied(*args):
        raise PermissionError("unknown owner")

    monkeypatch.setattr(os, "kill", denied)
    assert proven_dead(123) is False


def test_orphan_sidecar_and_malformed_metadata_do_not_release_request(tmp_path):
    processing = tmp_path / "processing"
    processing.mkdir()
    (processing / "beforeclaim.owner").write_text('{"pid":123,"session":"old"}')
    (processing / "bad.json").write_text("{}")
    (processing / "bad.owner").write_text("[]")
    assert recover(tmp_path, dead=lambda _: True) == []
    assert (processing / "bad.json").exists()
    assert (processing / "beforeclaim.owner").exists()


def test_completed_response_before_crash_preserved_byte_for_byte(tmp_path):
    processing = tmp_path / "processing"
    processing.mkdir()
    responses = tmp_path / "responses"
    responses.mkdir()
    (processing / "one.json").write_text('{"action":"mutation"}')
    (processing / "one.owner").write_text('{"pid":123,"session":"old"}')
    response = b'{"status":"ok","completed":true,"result":{"saved":true}}'
    (responses / "one.json").write_bytes(response)
    rows = recover(tmp_path, dead=lambda _: True)
    assert rows[0]["existing_response_preserved"] is True
    assert (responses / "one.json").read_bytes() == response
    assert not (tmp_path / "requests").exists()
