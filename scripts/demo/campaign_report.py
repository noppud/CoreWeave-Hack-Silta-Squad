"""Report distinct Fusion drawings and all retained attempts without causal shortcuts."""

# ruff: noqa: E501
from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def report(root=ROOT):
    campaign = read(root / "runs/demo-campaign.json")
    summary = read(root / "runs/four-part-learning-summary.json")
    paths = set(root / "runs" / p["final_run"] / "manifest.json" for p in summary["parts"])
    # Retain generation/recovery history, not just successful finals.
    paths.update((root / "runs").glob("learning*/manifest.json"))
    paths.update((root / "runs").glob("umc-actuator-v*/manifest.json"))
    for row in campaign["parts"]:
        paths.add(Path(row["manifest_path"]))
        paths.update(Path(p) for p in row.get("recovery_sources", []))
    manifests = []
    for path in paths:
        if path.exists():
            m = read(path)
            drawings = sorted(a["sha256"] for a in m.get("inputs", {}).get("drawings", []))
            if drawings:
                manifests.append(
                    (
                        m.get("created_at", ""),
                        path,
                        m,
                        hashlib.sha256(json.dumps(drawings).encode()).hexdigest(),
                    )
                )
    manifests.sort(key=lambda row: row[0])
    groups = {}
    for _, path, m, identity in manifests:
        group = groups.setdefault(
            identity,
            {
                "drawing_identity": identity,
                "drawing_hashes": sorted(a["sha256"] for a in m["inputs"]["drawings"]),
                "jobs": [],
                "starting_versions": m.get("versions", {}),
                "ending_versions": {},
                "attempts": 0,
                "simulation_passes": 0,
                "simulation_failures": 0,
                "verification_unknown": 0,
                "collection_invalidated": 0,
                "check_rejections": 0,
                "verified_candidates": [],
                "learning_changes": [],
            },
        )
        nomination_path = path.parent / "workspace/manual-trial-nomination.json"
        nomination = read(nomination_path) if nomination_path.is_file() else None
        events = m.get("events", [])
        proposals = {
            e["proposal"]["id"]: e["proposal"]
            for e in events
            if e["event"] == "reusable_change_proposed"
        }
        for e in events:
            if e["event"] == "candidate_created":
                group["attempts"] += 1
            elif e["event"] == "checks_completed" and e["result"].get("passed") is False:
                group["check_rejections"] += 1
            elif e["event"] == "verification_completed":
                v = e["verification"]
                if m.get("collection_warning"):
                    group["verification_unknown"] += 1
                    group["collection_invalidated"] += 1
                elif v.get("completed") is True and v.get("status") in ("passed", "failed"):
                    group[
                        "simulation_passes" if v["status"] == "passed" else "simulation_failures"
                    ] += 1
                    if v["status"] == "passed" and v.get("evidence"):
                        group["verified_candidates"].append(
                            {
                                "job_id": m["job_id"],
                                "attempt": e.get("attempt"),
                                "at": e["at"],
                                "machining_seconds": v.get("machining_seconds"),
                                "candidate_digest": v.get("candidate_digest"),
                                "evidence_count": len(v.get("evidence", [])),
                                "manual_nomination": bool(
                                    nomination
                                    and nomination.get("candidate_digest")
                                    == v.get("candidate_digest")
                                ),
                            }
                        )
                else:
                    group["verification_unknown"] += 1
            elif e["event"] == "learning_change_saved":
                proposal = proposals.get(e.get("proposal_id"), {})
                group["learning_changes"].append(
                    {
                        "job_id": m["job_id"],
                        "at": e["at"],
                        "kind": e.get("change_kind"),
                        "evaluation_performed": e.get("evaluation_performed"),
                        "base_version": proposal.get("base_version"),
                        "proposed_version": proposal.get("proposed_version"),
                    }
                )
        receipt_path = path.parent / "run-receipt.json"
        receipt = read(receipt_path) if receipt_path.exists() else {}
        group["jobs"].append(
            {
                "job_id": m["job_id"],
                "status": m.get("status"),
                "reason": m.get("reason"),
                "collection_warning": m.get("collection_warning"),
                "manual_trial_nomination": nomination,
                "manifest_path": str(path),
                "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "weave_recorded": receipt.get("weave_recorded", False),
                "weave_url": f"https://wandb.ai/{receipt['weave_project']}/r/call/{receipt['weave_call_id']}"
                if receipt.get("weave_call_id") and receipt.get("weave_project")
                else None,
            }
        )
        group["ending_versions"] = m.get("current_versions", m.get("versions", {}))
    parts = []
    for group in groups.values():
        verified = sorted(group["verified_candidates"], key=lambda row: row["at"])
        times = [v for v in verified if isinstance(v["machining_seconds"], (float, int))]
        first = times[0]["machining_seconds"] if times else None
        best = min(v["machining_seconds"] for v in times) if times else None
        group.update(
            first_verified_seconds=first,
            best_verified_seconds=best,
            same_part_improvement_percent=(100 * (first - best) / first)
            if first and best
            else None,
            has_verified_candidate=bool(verified),
            completed=any(j["status"] == "completed" for j in group["jobs"]) and bool(verified),
            job_runs=len(group["jobs"]),
            incomplete_job_runs=sum(j["status"] == "incomplete" for j in group["jobs"]),
        )
        parts.append(group)
    reuse = []
    for previous, current in zip(parts, parts[1:], strict=False):
        for kind in ("main_prompt", "checks"):
            version = previous["ending_versions"].get(kind)
            if version and version == current["starting_versions"].get(kind):
                reuse.append(
                    {
                        "from_drawing": previous["drawing_identity"],
                        "to_drawing": current["drawing_identity"],
                        "kind": kind,
                        "version": version,
                        "meaning": "Recorded next drawing starts with preceding ending version; not causal benefit",
                    }
                )
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "campaign_status": campaign["status"],
        "current_part_id": campaign.get("current_part_id"),
        "counts": {
            "distinct_drawings": len(parts),
            "verified_drawings": sum(p["has_verified_candidate"] for p in parts),
            "completed_drawings": sum(p["completed"] for p in parts),
            "job_runs": sum(p["job_runs"] for p in parts),
            "candidate_attempts": sum(p["attempts"] for p in parts),
            "verification_unknown": sum(p["verification_unknown"] for p in parts),
        },
        "parts": parts,
        "recorded_version_reuse": reuse,
        "limitations": [
            "Different drawings do not establish a causal learning curve.",
            "Repeated verifications/recovery jobs are counted as work, never as additional parts.",
            "First/best comparison uses recorded completed pass verdicts within one drawing; setup/verifier changes can confound optimization claims.",
            "Same version reuse proves configuration continuity, not that a lesson caused improvement.",
            "Manifest hashes snapshot report inputs; this report does not re-run geometry or refresh Weave.",
        ],
    }
    out = root / "output/evaluation"
    out.mkdir(parents=True, exist_ok=True)
    (out / "fusion-campaign.json").write_text(json.dumps(payload, indent=2))
    columns = [
        "drawing_identity",
        "job_runs",
        "attempts",
        "simulation_passes",
        "simulation_failures",
        "verification_unknown",
        "check_rejections",
        "first_verified_seconds",
        "best_verified_seconds",
        "same_part_improvement_percent",
        "has_verified_candidate",
        "completed",
    ]
    with (out / "fusion-campaign.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(parts)
    lines = [
        "# Fusion campaign results",
        "",
        f"Generated {payload['generated_at']}.",
        "",
        f"**{payload['counts']['verified_drawings']} distinct verified drawings**, "
        f"{payload['counts']['completed_drawings']} completed. Campaign: {campaign['status']}.",
        "",
        "| Drawing / first job | Runs | Candidates | Pass / Fail / Unknown | Check rejects | First → best verified seconds |",
        "|---|---:|---:|---|---:|---|",
    ]
    for p in parts:
        lines.append(
            f"| {p['jobs'][0]['job_id']} | {p['job_runs']} | {p['attempts']} | "
            f"{p['simulation_passes']} / {p['simulation_failures']} / {p['verification_unknown']} | "
            f"{p['check_rejections']} | {p['first_verified_seconds']} → {p['best_verified_seconds']} |"
        )
    lines += [
        "",
        "Distinct input drawing hashes define parts. Retries do not increase that count. "
        "Read the JSON for exact versions, learning changes, source manifest hashes and Weave receipt links.",
        "",
        "This is an observational report. Different part times are not a learning curve; "
        "within-drawing comparisons may still include setup/verifier changes. Version continuity is not causal improvement.",
        "",
        "Refresh: `.venv/bin/python scripts/demo/campaign_report.py`.",
    ]
    (root / "docs/campaign-results.md").write_text("\n".join(lines) + "\n")
    return payload


if __name__ == "__main__":
    result = report()
    print(json.dumps(result["counts"]))
