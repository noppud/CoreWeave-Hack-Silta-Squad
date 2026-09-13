"""Read-only acceptance snapshot for the retained Fusion demo and active campaign."""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from silta.cnc.benchmarks import decode_candidate, decode_inputs, decode_target, decode_verification
from silta.cnc.models import JobContext


def read_json(path):
    return json.loads(Path(path).read_text())


def check_hashes(value, cache=None):
    """Check only schema-declared path+sha256 references; never invent provenance."""
    cache = {} if cache is None else cache
    errors = []
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            path = Path(value["path"])
            key = (str(path), value["sha256"])
            if key not in cache:
                try:
                    with path.open("rb") as stream:
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    cache[key] = None if actual == value["sha256"] else f"hash mismatch: {path}"
                except OSError:
                    cache[key] = f"missing artifact: {path}"
            if cache[key]:
                errors.append(cache[key])
        for child in value.values():
            errors.extend(check_hashes(child, cache))
    elif isinstance(value, list):
        for child in value:
            errors.extend(check_hashes(child, cache))
    return list(dict.fromkeys(errors))


def assess_manifest(manifest, path="", cache=None):
    errors = check_hashes(manifest, cache)
    verified = False
    target_identity = None
    candidate = manifest.get("best_candidate") or manifest.get("result", {}).get("best_candidate")
    verdict = manifest.get("best_verification") or manifest.get("result", {}).get(
        "best_verification"
    )
    if candidate and verdict:
        try:
            inputs, target = decode_inputs(manifest["inputs"]), decode_target(manifest["target"])
            c, v = decode_candidate(candidate), decode_verification(verdict)
            inputs.verify()
            target.verify()
            c.verify()
            context = JobContext(inputs, target, inputs.digest, manifest["versions"], str(path))
            v.validate(c, context)
            if (
                inputs.digest != manifest["input_digest"]
                or target.digest != manifest["target_digest"]
            ):
                raise ValueError("Manifest identity does not match retained inputs/target")
            if c.target_digest != target.digest:
                raise ValueError("Best candidate targets a different CAD target")
            # Drawing bytes define a part identity across regenerated targets/retries.
            # Target STEP hashes remain exposed separately as artifact provenance.
            target_identity = hashlib.sha256(
                json.dumps(sorted(a.sha256 for a in inputs.drawings)).encode()
            ).hexdigest()
            verified = v.completed is True and v.status == "passed" and bool(v.evidence)
        except (KeyError, ValueError, TypeError, OSError) as exc:
            errors.append(f"Invalid best candidate evidence: {type(exc).__name__}: {exc}")
    status = manifest.get("status", "unknown")
    if status == "completed" and not verified:
        errors.append("Completed status lacks a bound completed passed verification with evidence")
    if errors:
        verified = False
    return {
        "job_id": manifest.get("job_id", Path(path).parent.name),
        "status": status,
        "has_verified_best": verified,
        "completed": status == "completed" and verified,
        "target_identity": target_identity,
        "target_digest": manifest.get("target_digest"),
        "errors": errors,
        "manifest_path": str(path),
        "reason": manifest.get("reason"),
    }


def summarize_targets(jobs, required=10):
    verified = {
        j["target_identity"] for j in jobs if j["has_verified_best"] and j["target_identity"]
    }
    completed = {j["target_identity"] for j in jobs if j["completed"] and j["target_identity"]}
    return {
        "required": required,
        "distinct_verified": len(verified),
        "distinct_completed": len(completed),
        "remaining": max(0, required - len(completed)),
        "counting_basis": "Distinct drawing SHA256 sets; excludes retries and simulation attempts",
    }


def verify(root=ROOT):
    cache, jobs, stages, artifacts = {}, [], [], []

    def stage(name, title, ready, detail):
        stages.append(
            {
                "id": name,
                "title": title,
                "status": "ready" if ready else "not_ready",
                "detail": detail,
            }
        )

    def available(relative):
        p = root / relative
        item = {"path": str(p), "available": p.is_file() and p.stat().st_size > 0}
        artifacts.append(item)
        return item["available"]

    summary = read_json(root / "runs/four-part-learning-summary.json")
    campaign = read_json(root / "runs/demo-campaign.json")
    paths = [root / "runs" / p["final_run"] / "manifest.json" for p in summary["parts"]]
    paths.append(root / "runs/umc-actuator-v5/manifest.json")
    paths.extend(
        Path(p["manifest_path"]) for p in campaign.get("parts", []) if p.get("manifest_path")
    )
    for p in dict.fromkeys(paths):
        try:
            jobs.append(assess_manifest(read_json(p), p, cache))
        except (OSError, ValueError) as exc:
            jobs.append(
                {
                    "job_id": p.parent.name,
                    "status": "unavailable",
                    "completed": False,
                    "has_verified_best": False,
                    "target_identity": None,
                    "manifest_path": str(p),
                    "errors": [f"Manifest unavailable: {type(exc).__name__}"],
                }
            )
    historical = jobs[: len(summary["parts"])]
    stage(
        "four_part_learning",
        "Four-part Fusion evidence",
        len(historical) == 4 and all(j["completed"] for j in historical),
        f"{sum(j['completed'] for j in historical)}/4 completed jobs with validated evidence",
    )
    umc = next(j for j in jobs if j["job_id"] == "umc-actuator-v5")
    stage(
        "indexed_fusion",
        "Indexed Fusion candidate",
        umc["has_verified_best"],
        f"Job status {umc['status']}; verified best {umc['has_verified_best']}; "
        "a passed candidate does not mean the optimization job completed",
    )
    evaluation = read_json(root / "output/evaluation/learning-evaluation.json")
    eval_errors = check_hashes(read_json(root / "output/evaluation/replay-evidence.json"), cache)
    eval_ready = (
        evaluation.get("status") == "published"
        and evaluation.get("publication", {}).get("readback_finalized") is True
        and len(evaluation.get("publication", {}).get("weave_refs", [])) == 2
        and not eval_errors
    )
    stage(
        "weave_evaluation",
        "Published paired Weave evaluation",
        eval_ready,
        "Stored finalized server-readback receipt and retained replay hashes checked; "
        "no fresh network readback performed by this acceptance command",
    )
    latest_capture = root / ".private/five-axis/umc08-machine-playback/result.json"
    wide = read_json(
        latest_capture if latest_capture.exists()
        else root / ".private/five-axis/video-wide-2/result.json"
    )
    video_errors = check_hashes(wide, cache)
    video = available(
        "output/video/umc08-machine-playback.mp4" if latest_capture.exists()
        else "output/video/silta-five-axis-demo.mp4"
    )
    video_ready = (
        video
        and wide.get("status") == "recorded"
        and wide.get("playback_end_observed") is True
        and wide.get("tool_position_changed") is True
        and not video_errors
    )
    stage(
        "video",
        "Actual Fusion playback recording",
        video_ready,
        f"Source: {wide.get('document')}; saved playback receipt checked for completed "
        "recording, observed end, changing tool positions and matching video hash. "
        "Presentation recording is separate from the machining verdict.",
    )
    targets = summarize_targets(jobs)
    stage(
        "ten_targets",
        "Ten completed jobs on distinct targets",
        targets["distinct_completed"] >= 10,
        f"{targets['distinct_verified']}/10 drawing targets have verified candidates; "
        f"{targets['distinct_completed']} completed jobs on distinct targets",
    )
    stage(
        "campaign",
        "Current campaign complete",
        campaign.get("status") == "completed"
        and all(j["completed"] for j in jobs[len(summary["parts"]) + 1 :]),
        f"Recorded campaign status: {campaign.get('status')}; current part: "
        f"{campaign.get('current_part_id')}. Status is from disk, not process liveness.",
    )
    available("output/fusion-workbench.html")
    available("output/evaluation/learning-evaluation.json")
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_ready": all(s["status"] == "ready" for s in stages),
        "stages": stages,
        "targets": targets,
        "campaign": {
            "status": campaign.get("status"),
            "current_part_id": campaign.get("current_part_id"),
            "recorded_parts": len(campaign.get("parts", [])),
            "liveness_scope": "Recorded status only; no process probe",
        },
        "jobs": jobs,
        "artifacts": artifacts,
        "errors": eval_errors + video_errors,
        "links": [v["weave_url"] for v in evaluation.get("variants", []) if v.get("weave_url")],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/demo-readiness.json")
    args = parser.parse_args()
    report = verify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "overall_ready": report["overall_ready"],
                "targets": report["targets"],
                "stages": report["stages"],
                "output": str(args.output),
            }
        )
    )
