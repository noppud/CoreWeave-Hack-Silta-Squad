"""Fresh Weave trace review and a prepared ARIA outer-loop experiment brief."""

# ruff: noqa: E501
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "silta/coreweave-hack-silta-squad"


def review_finalized_call(call):
    """Score finalized Fusion job semantics, not geometry or cutting safety."""
    output = call.output
    if call.ended_at is None or not isinstance(output, dict):
        return None
    if not str(output.get("job_id", "")).startswith("demo-umc"):
        return None
    best = output.get("best_verification") or {}
    verified = (
        best.get("completed") is True
        and best.get("status") == "passed"
        and bool(best.get("evidence"))
        and bool(output.get("best_candidate"))
    )
    return {
        "job_id": output["job_id"],
        "job_status": output.get("status"),
        "trace_finalized": True,
        "trace_exception": bool(call.exception),
        "has_verified_best": verified,
        "incomplete_verification": "incomplete or unknown" in str(output.get("reason", "")),
        "false_completion": output.get("status") == "completed" and not verified,
        "scope": "Deterministic trace-state review; no independent geometry validation, native Signals or LLM monitor",
    }


def run(publish_feedback=False):
    import weave

    os.environ["WANDB_API_KEY"] = os.environ.pop("COREWEAVE_WANDB_API_KEY")
    client = weave.init(PROJECT)
    calls = list(
        client.get_calls(
            filter={"trace_roots_only": True},
            limit=30,
            sort_by=[{"field": "started_at", "direction": "desc"}],
            include_feedback=True,
            columns=[
                "id",
                "display_name",
                "op_name",
                "parent_id",
                "started_at",
                "ended_at",
                "exception",
                "inputs",
                "output",
                "summary",
            ],
        )
    )
    rows = []
    for call in calls:
        rows.append(
            {
                "id": call.id,
                "name": call.display_name or call.op_name,
                "parent_id": call.parent_id,
                "started_at": str(call.started_at),
                "ended_at": str(call.ended_at) if call.ended_at else None,
                "exception": str(call.exception)[:1000] if call.exception else None,
                "inputs": call.inputs,
                "output": call.output,
                "feedback": call.summary.get("weave", {}).get("feedback", []),
                "url": f"https://wandb.ai/{PROJECT}/r/call/{call.id}",
            }
        )
    evaluation = json.loads((ROOT / "output/evaluation/learning-evaluation.json").read_text())
    eval_readback = []
    for ref in evaluation["publication"]["weave_refs"]:
        call = client.get_call(ref.rsplit("/", 1)[-1])
        eval_readback.append(
            {
                "id": call.id,
                "ended_at": str(call.ended_at),
                "success": call.ended_at is not None and not call.exception,
            }
        )
    monitor_rows = []
    out = ROOT / "output/sponsors"
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = out / "monitor-feedback.json"
    receipts = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    for call in calls:
        findings = review_finalized_call(call)
        if findings is None:
            continue
        if publish_feedback and (
            call.id not in receipts or receipts[call.id]["findings"] != findings
        ):
            feedback_id = call.feedback.add(
                "silta.fusion_verification_review",
                payload=findings,
                creator="Silta deterministic monitor",
            )
            client.flush()
            feedback = client.get_feedback(feedback_id)
            if len(list(feedback)) != 1:
                raise RuntimeError("Monitor feedback readback failed")
            receipts[call.id] = {"feedback_id": feedback_id, "readback": True, "findings": findings}
            receipt_path.write_text(json.dumps(receipts, indent=2))
        monitor_rows.append(
            {
                "call_id": call.id,
                "url": f"https://wandb.ai/{PROJECT}/r/call/{call.id}",
                "findings": findings,
                "receipt": receipts.get(call.id),
            }
        )
    aria_path = out / "aria-review.json"
    aria_record = json.loads(aria_path.read_text()) if aria_path.exists() else None
    result = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "project": PROJECT,
        "weave": {
            "status": "fresh_readback",
            "evaluations": eval_readback,
            "recent_calls": rows,
            "custom_monitor": monitor_rows,
            "native_monitors": "not_configured",
            "native_signals": "not_configured",
        },
        "aria": aria_record
        or {
            "status": "blocked_browser_availability",
            "service": "W&B ARIA",
            "reason": "ARIA is accessed through Ask ARIA in team project UI. The available browser provider rejects hidden-tab visibility and in-app browser is unavailable; Fusion currently owns foreground.",
            "model": "not_selected_no_aria_request_yet",
            "required_next_step": "Open Ask ARIA in the existing team project when Fusion no longer requires foreground; verify available model choices and Smart features.",
        },
    }
    out = ROOT / "output/sponsors"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sponsor-review.json").write_text(json.dumps(result, indent=2, default=str))
    print(
        json.dumps(
            {
                "calls": len(rows),
                "evaluation_readbacks": eval_readback,
                "recent": [{"name": r["name"], "id": r["id"]} for r in rows[:12]],
            }
        )
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-feedback", action="store_true")
    args = parser.parse_args()
    run(args.publish_feedback)
