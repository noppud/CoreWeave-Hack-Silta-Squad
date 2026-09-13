"""Native Weave programmatic scoring of receipt-bound Fusion jobs; no LLM or Signals."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import weave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from silta.cnc.models import Artifact, Candidate, digest_json  # noqa: E402

PROJECT = "silta/coreweave-hack-silta-squad"
SCORER_VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
REQUIRED_COVERAGE = (
    "axis_overtravel",
    "machine_collisions",
    "rapid_stock_collisions",
    "target_stock_comparison",
    "tool_holder_fixture_collisions",
)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def finite(value):
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def artifact_pins(value):
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            yield value
        for item in value.values():
            yield from artifact_pins(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from artifact_pins(item)


def discover(campaign_path):
    """Only explicit campaign manifests/recovery links can nominate a job."""
    campaign = read(campaign_path)
    paths = []
    for part in campaign.get("parts", []):
        for raw in [part.get("manifest_path"), *part.get("recovery_sources", [])]:
            if raw:
                path = Path(raw)
                path = path if path.is_absolute() else Path(campaign_path).parent / path
                if path.resolve() not in paths:
                    paths.append(path.resolve())
    return paths


def evidence_audit(manifest):
    """Recheck retained candidate/evidence bytes, not geometric manufacturing truth."""
    best = manifest.get("best_verification") or {}
    candidate = manifest.get("best_candidate") or {}
    errors, pins = [], {}
    for ref in artifact_pins({"candidate": candidate, "verdict": best}):
        pins[(ref["path"], ref["sha256"])] = ref
    for ref in pins.values():
        try:
            Artifact(ref["path"], ref["sha256"]).verify()
        except (OSError, ValueError) as error:
            errors.append(f"{Path(ref['path']).name}: {type(error).__name__}")
    candidate_digest = None
    if candidate:
        try:
            decoded = Candidate(
                candidate["id"],
                candidate["target_digest"],
                {key: Artifact(**value) for key, value in candidate["artifacts"].items()},
                candidate.get("parameters", {}),
            )
            candidate_digest = decoded.digest
            if decoded.target_digest != manifest.get("target_digest"):
                errors.append("candidate target differs from accepted target")
        except (KeyError, TypeError, ValueError):
            errors.append("candidate structure invalid")
    latest = next(
        (
            event.get("verification", {})
            for event in reversed(manifest.get("events", []))
            if event.get("event") == "verification_completed"
        ),
        {},
    )
    return {
        "input_digest": manifest.get("input_digest"),
        "candidate_digest": candidate_digest,
        "checked_artifact_count": len(pins),
        "artifact_hashes_valid": bool(pins) and not errors,
        "artifact_errors": errors,
        "collection_invalidated": bool(manifest.get("collection_warning")),
        "collection_warning": manifest.get("collection_warning"),
        "recorded_latest_verification_status": latest.get("status"),
        "latest_verification_status": "unknown" if manifest.get("collection_warning")
        else latest.get("status"),
        "latest_verification_completed": not manifest.get("collection_warning")
        and latest.get("completed") is True,
        "manifest_result_digest": digest_json(manifest["result"]),
    }


def score_output(output, audit):
    # Detach Weave boxed scalars so scores store numeric values rather than input refs.
    output = json.loads(json.dumps(output, allow_nan=False))
    audit = json.loads(json.dumps(audit, allow_nan=False))
    best = output.get("best_verification") or {}
    candidate = output.get("best_candidate") or {}
    feedback = best.get("feedback") or {}
    coverage = feedback.get("configured_coverage") or {}
    summary = feedback.get("summary") or {}
    comparison = feedback.get("target_stock_comparison") or {}
    coherent = digest_json(output) == audit.get("manifest_result_digest")
    verified = bool(
        coherent
        and not audit.get("collection_invalidated")
        and candidate
        and best.get("completed") is True
        and best.get("status") == "passed"
        and finite(best.get("machining_seconds"))
        and not best.get("issues")
        and best.get("evidence")
        and best.get("coverage")
        and str(best.get("verifier_version", "")).startswith("fusion-fixed-")
        and best.get("input_digest") == audit.get("input_digest")
        and best.get("candidate_digest") == audit.get("candidate_digest")
        and audit.get("artifact_hashes_valid") is True
        and all(coverage.get(key) is True for key in REQUIRED_COVERAGE)
        and summary.get("percent") == 100
        and summary.get("errors") == 0
        and summary.get("process_errors") == 0
        and comparison.get("status") == "passed"
    )
    completed = output.get("status") == "completed"
    metric = best.get("machining_seconds")
    cost = best.get("estimated_cost")
    return {
        "domain": "autodesk_fusion_internal_cam",
        "job_id": output.get("job_id"),
        "job_completed": completed,
        "record_matches_local_result": coherent,
        "verified_best": verified,
        "collection_invalidated": audit.get("collection_invalidated") is True,
        "collection_warning": audit.get("collection_warning"),
        "recorded_latest_verification_status": audit.get("recorded_latest_verification_status"),
        "false_completion": completed and not verified,
        "latest_verification_completed": audit.get("latest_verification_completed") is True,
        "latest_verification_status": audit.get("latest_verification_status"),
        "incomplete_collection": audit.get("latest_verification_status") == "unknown",
        "artifact_hashes_valid": audit.get("artifact_hashes_valid") is True,
        "artifact_errors": audit.get("artifact_errors", []),
        "machining_seconds": metric if verified and finite(metric) else None,
        "illustrative_estimated_cost": cost if verified and finite(cost) else None,
        "scope": "Recorded fixed Fusion verifier evidence and local artifact integrity; "
        "not independent geometry certification, posted-NC verification or native Agents Signals.",
    }


class FusionOutcomeScorer(weave.Scorer):
    source_sha256: str = SCORER_VERSION

    @weave.op()
    def score(self, output: dict, evidence_audit: dict) -> dict:
        return score_output(output, evidence_audit)


def eligible_record(path):
    manifest = read(path)
    receipt_path = path.parent / "run-receipt.json"
    if not receipt_path.exists():
        raise ValueError("No explicit Fusion run receipt yet")
    receipt = read(receipt_path)
    if receipt.get("weave_project") != PROJECT or receipt.get("job_id") != manifest.get("job_id"):
        raise ValueError("Receipt project/job mismatch")
    if not receipt.get("weave_call_id") or receipt.get("weave_recorded") is not True:
        raise ValueError("Receipt has no finalized recorded call")
    inputs = manifest.get("inputs", {})
    if not inputs.get("machine", {}).get("simulation_geometry") or not inputs.get("setup", {}).get(
        "fixture", {}
    ).get("artifact"):
        raise ValueError("Not a Fusion machine/fixture input")
    if manifest.get("status") not in {
        "completed",
        "incomplete",
        "failed",
        "stopped",
    } or not manifest.get("result"):
        raise ValueError("Manifest has no finalized job result")
    return manifest, receipt


def validate_server_call(call, manifest, receipt):
    if call.id != receipt["weave_call_id"] or call.parent_id is not None or call.ended_at is None:
        raise ValueError("Receipt does not resolve to a finalized root")
    if call.exception:
        raise ValueError("Root call has an exception; no finalized result can be scored")
    if call.output != manifest["result"]:
        raise ValueError("Server result differs from the explicit local Fusion manifest")


def feedback_dict(row):
    return row if isinstance(row, dict) else row.model_dump(mode="json")


async def publish_one(client, scorer, scorer_ref, path):
    manifest, receipt = eligible_record(path)
    call = client.get_call(receipt["weave_call_id"])
    validate_server_call(call, manifest, receipt)
    audit = evidence_audit(manifest)
    expected = score_output(call.output, audit)
    existing = [feedback_dict(row) for row in call.feedback]
    matching = [
        row
        for row in existing
        if row.get("runnable_ref") == scorer_ref
        and row.get("payload", {}).get("output") == expected
    ]
    if matching:
        feedback = matching[-1]
        score_id = feedback["call_ref"].rsplit("/", 1)[-1]
        reused = True
    else:
        applied = await call.apply_scorer(scorer, {"evidence_audit": audit})
        score_id = applied.score_call.id
        client.flush()
        fresh = client.get_call(call.id)
        matching = [
            feedback_dict(row)
            for row in fresh.feedback
            if (feedback_dict(row).get("call_ref") or "").endswith("/" + score_id)
        ]
        if len(matching) != 1:
            raise RuntimeError("Native score feedback readback failed")
        feedback = matching[0]
        reused = False
    score_call = client.get_call(score_id)
    if score_call.ended_at is None or score_call.exception or score_call.output != expected:
        raise RuntimeError("Scoring call not finalized with expected deterministic result")
    return {
        "job_id": manifest["job_id"],
        "manifest": str(path),
        "manifest_sha256": sha(path),
        "root_call_id": call.id,
        "root_url": f"https://wandb.ai/{PROJECT}/r/call/{call.id}",
        "scorer_ref": scorer_ref,
        "score_call_id": score_id,
        "score_url": f"https://wandb.ai/{PROJECT}/r/call/{score_id}",
        "feedback_id": feedback["id"],
        "feedback_type": feedback["feedback_type"],
        "readback_finalized": True,
        "reused_existing": reused,
        "evidence_audit": audit,
        "scores": expected,
    }


async def run(args):
    paths = discover(args.campaign)
    result = {
        "schema_version": 1,
        "project": PROJECT,
        "kind": "native_programmatic_weave_scorer",
        "native_agents_signals": False,
        "model_calls": 0,
        "scorer_source_sha256": SCORER_VERSION,
        "checked_at": datetime.now(UTC).isoformat(),
        "rows": [],
        "skipped": [],
    }
    client = None
    if args.publish:
        if "COREWEAVE_WANDB_API_KEY" not in os.environ:
            raise RuntimeError("Use hsec exec --only COREWEAVE_WANDB_API_KEY")
        os.environ["WANDB_API_KEY"] = os.environ.pop("COREWEAVE_WANDB_API_KEY")
        client = weave.init(PROJECT)
        scorer = FusionOutcomeScorer(name="FusionOutcomeScorer")
        scorer_ref = weave.publish(scorer).uri()
    for path in paths:
        try:
            if client is not None:
                row = await publish_one(client, scorer, scorer_ref, path)
            else:
                manifest, receipt = eligible_record(path)
                audit = evidence_audit(manifest)
                row = {
                    "job_id": manifest["job_id"],
                    "manifest": str(path),
                    "root_call_id": receipt["weave_call_id"],
                    "readback_finalized": False,
                    "scores": score_output(manifest["result"], audit),
                    "evidence_audit": audit,
                }
            result["rows"].append(row)
        except (OSError, ValueError) as error:
            result["skipped"].append({"manifest": str(path), "reason": str(error)})
    if client is not None:
        client.flush()
    result["status"] = (
        "published_and_read_back" if client is not None else "local_preview_not_published"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "scored": len(result["rows"]),
                "skipped": len(result["skipped"]),
                "output": str(args.output),
            }
        )
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=ROOT / "runs/demo-campaign.json")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/sponsors/fusion-native-scores.json"
    )
    args = parser.parse_args()
    if not args.publish and args.output.name == "fusion-native-scores.json":
        args.output = args.output.with_name("fusion-native-scores-preview.json")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
