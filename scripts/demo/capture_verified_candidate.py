"""Capture one retained verified candidate. Default is read-only source inspection.

--capture requires the campaign to have released Fusion and its Display controls
already configured for visible machine/tool/stock. No speed or display UI guesses.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import runpy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from silta.cnc.models import Artifact, Candidate, digest_json  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text())


def pin(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def load_source(path):
    path = Path(path).resolve()
    manifest = read(path)
    verdict = manifest.get("best_verification") or {}
    if not (
        manifest.get("status") == "completed"
        and verdict.get("status") == "passed"
        and verdict.get("completed") is True
        and verdict.get("evidence")
        and verdict.get("coverage")
        and not verdict.get("issues")
    ):
        raise ValueError("Capture requires a completed job with an evidenced verified best")
    data = manifest["best_candidate"]
    candidate = Candidate(
        data["id"],
        data["target_digest"],
        {k: Artifact(**v) for k, v in data["artifacts"].items()},
        data.get("parameters", {}),
    )
    candidate.verify()
    if candidate.digest != verdict["candidate_digest"]:
        raise ValueError("Best candidate digest does not match verification")
    cloud = candidate.artifacts.get("fusion_document")
    if cloud is None:
        raise ValueError("Capture requires a saved cloud candidate")
    geometry = Artifact(**manifest["target"]["artifacts"]["geometry"])
    machine = Artifact(**manifest["inputs"]["machine"]["definition"])
    geometry.verify()
    machine.verify()
    for evidence in verdict["evidence"]:
        Artifact(**evidence).verify()
    return manifest, candidate, read(cloud.path), geometry, machine


def capture(
    manifest_path,
    directory,
    bridge,
    *,
    max_seconds=840,
    orbit_seconds=16,
    framing="wide",
    video_factory=None,
    recorder_factory=None,
    stock_exporter_factory=None,
    open_candidate=None,
    position=None,
):
    """Caller holds the shared Fusion lock. Factories permit tests without desktop activity."""
    from fusion.SiltaBridge.presentation import orbit_parameters
    from silta.cnc.agents import _GEOMETRY_SCRIPT
    from silta.cnc.cam_documents import open_snapshot
    from silta.cnc.simulation_video import SimulationVideo, WindowRecorder, playback_position
    from silta.cnc.stock_export import StockExporter
    from silta.cnc.ui_verifier import _BINDING_SCRIPT

    if not math.isfinite(max_seconds) or not 5 <= max_seconds <= 840:
        raise ValueError("Capture limit must be finite and within5..840seconds")
    if framing not in {"wide", "close"}:
        raise ValueError("Framing must be wide or close")
    manifest, candidate, reference, geometry, machine = load_source(manifest_path)
    document = reference["document_name"]
    orbit_payload = {
        "document": document,
        "action": "orbit",
        "seconds": orbit_seconds,
        "target_mm": [0, 0, 195],
        "radius_mm": 380,
        "eye_z_mm": 430,
        "height_mm": 210,
        "sweep_degrees": 360,
    }
    orbit_parameters(orbit_payload)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    stage = runpy.run_path(str(ROOT / "scripts/demo/stage_playback.py"))
    position = position or playback_position
    row = {
        "schema_version": 1,
        "status": "not_started",
        "source_job": manifest["job_id"],
        "candidate_id": candidate.id,
        "candidate_digest": candidate.digest,
        "verified_seconds": manifest["best_verification"]["machining_seconds"],
        "reference": reference,
        "source_manifest": pin(manifest_path),
        "scope": "Presentation recording of retained verified candidate; not a new verdict",
        "speed": "Unchanged; no supported speed setter in existing adapter",
        "simulator_display": "Existing machine/tool/stock display; visual review required",
        "target_display_scope": "Only accepted target bodies hidden; fixtures untouched",
        "visual_review_required": True,
        "machining_framing": framing,
        "errors": [],
        "media": [],
        "implementation_sources": [
            pin(ROOT / p)
            for p in (
                "scripts/demo/capture_verified_candidate.py",
                "scripts/demo/stage_playback.py",
                "silta/cnc/simulation_video.py",
                "silta/cnc/stock_export.py",
                "scripts/fusion/record_part_reveal.py",
                "fusion/SiltaBridge/presentation.py",
            )
        ],
    }
    sequence = 0
    saved_visibility = None
    launched = False

    def request(action, payload=None, **kwargs):
        nonlocal sequence
        reply = bridge.request(action, payload, candidate_hash=candidate.digest, **kwargs)
        sequence += 1
        (directory / f"request-{sequence:03d}-{action}.json").write_text(
            json.dumps(reply, indent=2)
        )
        if reply.get("status") != "ok":
            raise RuntimeError(f"Capture {action} failed: {reply.get('error')}")
        return reply

    def display(action, states=None):
        return request(
            "run_script",
            {
                "source": stage["_DISPLAY"],
                "arguments": {
                    "reference": reference,
                    "display_action": action,
                    "states": states,
                },
            },
        )["result"]

    try:
        row["opened"] = (open_candidate or open_snapshot)(request, reference)
        row["binding"] = request(
            "run_script",
            {
                "source": stage["_BIND"],
                "arguments": {"reference": reference},
            },
        )["result"]
        actual_geometry = request("run_script", {"source": _GEOMETRY_SCRIPT})["result"]
        if digest_json(actual_geometry) != digest_json(read(geometry.path)):
            raise ValueError("Opened candidate geometry differs from accepted target")
        row["geometry_matches"] = True
        binding = request(
            "run_script", {"source": _BINDING_SCRIPT, "arguments": {"machine_path": machine.path}}
        )["result"]
        setups, operations = binding.get("setups", []), binding.get("operations", [])
        if not setups or not all(
            s.get("machine_matches") and s.get("machine_simulation_model") and s.get("models")
            for s in setups
        ):
            raise ValueError("Configured machine or setup model is missing")
        if manifest["inputs"]["setup"].get("fixture") and not all(
            s.get("fixture_enabled") and s.get("fixtures") for s in setups
        ):
            raise ValueError("Configured fixture is missing")
        if not operations or any(
            not op.get("has_toolpath") or op.get("has_error") for op in operations
        ):
            raise ValueError("Retained toolpaths missing or invalid")
        row["cam_binding"] = binding
        row["target_display_before"] = display("inspect")
        saved_visibility = row["target_display_before"]["states_before"]
        row["target_display_hidden"] = display("hide", saved_visibility)
        launched = True
        request(
            "simulation_command",
            {"command_id": "IronMachineSimulation", "setup_ids": row["binding"]["setup_ids"]},
        )
        request(
            "presentation_camera",
            {
                "document": document,
                "action": "frame",
                "target_mm": [0, 0, 230] if framing == "wide" else [0, 0, 195],
                "eye_mm": [900, -1300, 1000] if framing == "wide" else [380, -380, 430],
                "height_mm": 850 if framing == "wide" else 300,
            },
        )
        video = (video_factory or SimulationVideo)(document, directory / "machine", bridge=bridge)
        row["machine_playback"] = video.record(
            directory / "machine-playback.mp4", max_seconds=max_seconds, fps=60
        )
        result = row["machine_playback"]
        if not (
            result.get("status") == "recorded"
            and result.get("playback_end_observed")
            and result.get("tool_position_changed")
            and not result.get("errors")
        ):
            raise RuntimeError(
                "Full machine playback was not confirmed; finished-stock orbit skipped"
            )
        row["media"].append(pin(directory / "machine-playback.mp4"))
        # Playback completion is independent of stock regeneration. Reuse the
        # v6 exporter gate before any camera footage is labeled finished stock.
        stock_path = directory / "finished-stock.stl"
        exporter = (stock_exporter_factory or StockExporter)(
            document, directory / "stock-export", bridge=bridge
        )
        row["stock_export"] = exporter.export(stock_path)
        exported = row["stock_export"]
        if (exported.get("status") != "exported"
                or exported.get("stock_readiness", {}).get("status") != "ready"):
            raise RuntimeError("Completed stock regeneration was not confirmed; orbit skipped")
        row["finished_stock_artifact"] = pin(stock_path)
        row["stock_export_scope"] = "Observed completed stock for presentation; not a new verdict"
        orbit_dir = directory / "orbit"
        orbit_dir.mkdir()
        before = request("simulation_dialog")
        before_position = position(before, document)
        if len(before_position.get("tool_position", {})) != 3:
            raise RuntimeError("Orbit requires three observed tool position axes")
        recorder = (recorder_factory or WindowRecorder)(document, orbit_dir, orbit_seconds + 15, 60)
        recorded, trajectory = {}, {}
        try:
            recorder.start()
            trajectory = request(
                "presentation_camera", orbit_payload, timeout=orbit_seconds + 15
            ).get("result", {})
            if trajectory.get("status") != "completed":
                raise RuntimeError("Camera orbit did not complete")
        finally:
            recorded = recorder.stop()
            (orbit_dir / "camera-trajectory.json").write_text(json.dumps(trajectory, indent=2))
            (orbit_dir / "recorder-result.json").write_text(json.dumps(recorded, indent=2))
        after = request("simulation_dialog")
        if before_position["tool_position"] != position(after, document)["tool_position"]:
            raise RuntimeError("Tool moved during finished-stock orbit")
        if recorded.get("status") != "recorded":
            raise RuntimeError("Orbit recorder did not finalize")
        with (
            (directory / "finished-stock-orbit.mp4").open("xb") as out,
            recorder.path.open("rb") as src,
        ):
            shutil.copyfileobj(src, out)
        row["orbit"] = {
            "recorder": recorded,
            "camera": trajectory,
            "tool_position_unchanged": True,
            "before": before_position,
            "after": position(after, document),
        }
        row["media"].append(pin(directory / "finished-stock-orbit.mp4"))
        row["status"] = "recorded_requires_visual_review"
    except BaseException as error:
        row["status"] = "capture_failed"
        row["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if launched:
            try:
                row["simulation_stop"] = request(
                    "simulation_command", {"command_id": "SimulationStop"}
                )
            except Exception as error:
                row["errors"].append(f"SimulationStop: {error}")
        if saved_visibility is not None:
            try:
                row["target_display_restored"] = display("restore", saved_visibility)
                if row["target_display_restored"]["states_after"] != saved_visibility:
                    raise RuntimeError("Target visibility restoration mismatch")
            except Exception as error:
                row["errors"].append(f"Target visibility restoration: {error}")
        if row["errors"]:
            row["status"] = "capture_failed"
        row["source_manifest_unchanged"] = pin(manifest_path) == row["source_manifest"]
        if not row["source_manifest_unchanged"]:
            row["status"] = "capture_failed"
            row["errors"].append("Source manifest changed during capture")
        row["evidence"] = [pin(p) for p in sorted(directory.rglob("*.json"))]
        (directory / "capture-receipt.json").write_text(json.dumps(row, indent=2))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--max-seconds", type=float, default=840)
    parser.add_argument("--orbit-seconds", type=float, default=16)
    parser.add_argument("--framing", choices=("wide", "close"), default="wide")
    args = parser.parse_args()
    manifest, candidate, reference, _, _ = load_source(args.manifest)
    if not args.capture:
        print(
            json.dumps(
                {
                    "mode": "read_only",
                    "job_id": manifest["job_id"],
                    "candidate_id": candidate.id,
                    "candidate_digest": candidate.digest,
                    "reference": reference,
                },
                indent=2,
            )
        )
        return
    if args.output is None:
        parser.error("--capture requires a new --output directory")
    from silta.cnc.fusion import FusionBridge

    with (ROOT / "runs/.fusion-campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = capture(
            args.manifest,
            args.output,
            FusionBridge(),
            max_seconds=args.max_seconds,
            orbit_seconds=args.orbit_seconds,
            framing=args.framing,
        )
    print(json.dumps(result, indent=2))
    if result["status"] != "recorded_requires_visual_review":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
