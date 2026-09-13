"""Record a camera orbit of the actual finished stock in an open Fusion simulation.

Presentation only. Hide machine/toolpath and set CAD model opacity to zero first;
this never imports replacement geometry or issues a simulation verdict.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from silta.cnc.fusion import FusionBridge  # noqa: E402
from silta.cnc.simulation_video import WindowRecorder, playback_position  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--document", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--seconds", type=float, default=16)
    args = p.parse_args()
    from fusion.SiltaBridge.presentation import orbit_parameters

    payload = {
        "document": args.document,
        "action": "orbit",
        "seconds": args.seconds,
        "target_mm": [0, 0, 195],
        "radius_mm": 380,
        "eye_z_mm": 430,
        "height_mm": 210,
        "sweep_degrees": 360,
    }
    orbit_parameters(payload)
    if args.output.exists():
        raise ValueError("Use a new output and 5..30 seconds")
    args.evidence.mkdir(parents=True, exist_ok=False)
    bridge = FusionBridge()
    before = bridge.request("simulation_dialog")
    playback_position(before, args.document)
    (args.evidence / "simulation-before.json").write_text(json.dumps(before, indent=2))
    recorder = WindowRecorder(args.document, args.evidence, args.seconds + 15, 60)
    orbit_result = {}
    try:
        recorder.start()
        reply = bridge.request("presentation_camera", payload, timeout=args.seconds + 15)
        orbit_result = reply.get("result", {})
        if reply.get("status") != "ok" or orbit_result.get("status") != "completed":
            raise RuntimeError(f"Camera orbit did not complete: {reply}")
    finally:
        recorded = recorder.stop()
        (args.evidence / "camera-trajectory.json").write_text(json.dumps(orbit_result, indent=2))
        (args.evidence / "recorder-result.json").write_text(json.dumps(recorded, indent=2))
    after = bridge.request("simulation_dialog")
    if (
        playback_position(before, args.document)["tool_position"]
        != playback_position(after, args.document)["tool_position"]
    ):
        raise RuntimeError("Tool moved during finished-stock reveal")
    (args.evidence / "simulation-after.json").write_text(json.dumps(after, indent=2))
    if recorded.get("status") != "recorded":
        raise RuntimeError(recorded)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as out, recorder.path.open("rb") as src:
        shutil.copyfileobj(src, out)
    print(
        json.dumps(
            {
                "video": str(args.output),
                "camera_samples": orbit_result.get("actual_update_count", 0),
                "camera_update_hz": orbit_result.get("observed_update_hz"),
                "presentation_only": True,
                "verification_pass": False,
                "recorder": recorded,
            }
        )
    )


if __name__ == "__main__":
    main()
