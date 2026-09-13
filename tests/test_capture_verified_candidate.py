"""Capture orchestration tests; all playback/bridge/recorder dependencies are doubles."""

import importlib.util
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from silta.cnc.models import Artifact, Candidate

SPEC = importlib.util.spec_from_file_location(
    "capture", Path(__file__).resolve().parents[1] / "scripts/demo/capture_verified_candidate.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def source(tmp_path):
    def artifact(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return Artifact.from_path(path)

    cloud = artifact("reference.json", {"document_name": "exact"})
    geometry = artifact("geometry.json", {})
    machine = artifact("machine.json", {})
    evidence = artifact("verification.json", {"recorded": True})
    candidate = Candidate("c2", "fixed-target", {"fusion_document": cloud})
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "job_id": "example",
                "status": "completed",
                "best_candidate": asdict(candidate),
                "best_verification": {
                    "status": "passed",
                    "completed": True,
                    "candidate_digest": candidate.digest,
                    "machining_seconds": 200,
                    "evidence": [asdict(evidence)],
                    "coverage": ["test-evidence"],
                    "issues": [],
                },
                "target": {"artifacts": {"geometry": asdict(geometry)}},
                "inputs": {"machine": {"definition": asdict(machine)}, "setup": {}},
            }
        )
    )
    return path


def test_reject_changed_candidate_before_any_capture(tmp_path):
    path = source(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["best_verification"]["candidate_digest"] = "wrong"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="digest"):
        module.load_source(path)


def test_reject_incomplete_job_even_with_verified_best(tmp_path):
    path = source(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["status"] = "incomplete"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="completed job"):
        module.load_source(path)


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "binding",
        "partial_video",
        "stock_pending",
        "stock_unready",
        "tool_moved",
        "restore",
        "interrupt",
    ],
)
@pytest.mark.parametrize("framing", ["wide", "close"])
def test_capture_cleanup_and_source_receipt(tmp_path, failure, framing):
    from silta.cnc.agents import _GEOMETRY_SCRIPT
    from silta.cnc.ui_verifier import _BINDING_SCRIPT

    path = source(tmp_path)
    calls = []

    class Bridge:
        def __init__(self):
            self.observations = 0

        def request(self, action, payload=None, **kwargs):
            if action == "run_script":
                arguments = payload.get("arguments", {})
                display = arguments.get("display_action")
                if display:
                    calls.append(display)
                    if display == "restore" and failure == "restore":
                        return {"status": "error", "error": "restore failed"}
                    return {
                        "status": "ok",
                        "result": {
                            "states_before": {"target": True},
                            "states_after": {"target": display != "hide"},
                        },
                    }
                if payload["source"] == _GEOMETRY_SCRIPT:
                    return {"status": "ok", "result": {}}
                if payload["source"] == _BINDING_SCRIPT:
                    return {
                        "status": "ok",
                        "result": {
                            "setups": [
                                {
                                    "machine_matches": True,
                                    "machine_simulation_model": True,
                                    "models": ["target"],
                                }
                            ],
                            "operations": [{"has_toolpath": True, "has_error": False}],
                        },
                    }
                if failure == "binding":
                    return {"status": "error", "error": "wrong cloud version"}
                return {"status": "ok", "result": {"document": "exact", "setup_ids": ["2"]}}
            if action == "simulation_command":
                calls.append(payload["command_id"])
                return {"status": "ok", "result": {}}
            if action == "presentation_camera":
                calls.append(payload["action"])
                if payload["action"] == "frame":
                    assert payload["height_mm"] == (850 if framing == "wide" else 300)
                return {"status": "ok", "result": {"status": "completed"}}
            if action == "simulation_dialog":
                self.observations += 1
                moved = failure == "tool_moved" and self.observations > 1
                return {"status": "ok", "result": {"tool_position": [int(moved), 0, 0]}}
            raise AssertionError(action)

    class Video:
        def __init__(self, *args, **kwargs):
            pass

        def record(self, output, **kwargs):
            calls.append("record_machine")
            if failure == "interrupt":
                raise KeyboardInterrupt("presenter interrupted")
            Path(output).write_bytes(b"test-only-video-double")
            return {
                "status": "partial" if failure == "partial_video" else "recorded",
                "playback_end_observed": failure != "partial_video",
                "tool_position_changed": True,
                "errors": [],
            }

    class StockExporter:
        def __init__(self, document, evidence, **kwargs):
            self.directory = evidence

        def export(self, output):
            calls.append("export_ready_stock")
            if failure == "stock_pending":
                raise TimeoutError("Stock regeneration completion was not observed")
            self.directory.mkdir()
            Path(output).write_bytes(b"test-only-stock-double")
            result = {
                "status": "exported",
                "stock_readiness": {"status": "waiting" if failure == "stock_unready" else "ready"},
            }
            (self.directory / "result.json").write_text(json.dumps(result))
            return result

    class Recorder:
        def __init__(self, document, evidence, *args):
            self.path = evidence / "window-capture.mp4"

        def start(self):
            calls.append("record_orbit")
            self.path.write_bytes(b"test-only-orbit-double")

        def stop(self):
            calls.append("stop_recorder")
            return {"status": "recorded"}

    row = module.capture(
        path,
        tmp_path / "capture",
        Bridge(),
        video_factory=Video,
        recorder_factory=Recorder,
        stock_exporter_factory=StockExporter,
        open_candidate=lambda *_: {"opened": "exact"},
        position=lambda reply, _: reply["result"],
        framing=framing,
    )
    if failure == "binding":
        assert "IronMachineSimulation" not in calls
    else:
        assert calls[-2:] == ["SimulationStop", "restore"]
    if failure in {"partial_video", "stock_pending", "stock_unready"}:
        assert "record_orbit" not in calls
    if failure:
        assert row["status"] == "capture_failed" and row["errors"]
    else:
        assert row["status"] == "recorded_requires_visual_review"
        assert len(row["media"]) == 2 and row["source_manifest_unchanged"]
        assert row["target_display_restored"]["states_after"] == {"target": True}
        assert row["orbit"]["tool_position_unchanged"]
        assert calls.index("record_machine") < calls.index("export_ready_stock")
        assert calls.index("export_ready_stock") < calls.index("record_orbit")
        Artifact(**row["finished_stock_artifact"]).verify()
        assert "not a new verdict" in row["scope"]
        for record in row["media"] + row["evidence"]:
            Artifact(**record).verify()
