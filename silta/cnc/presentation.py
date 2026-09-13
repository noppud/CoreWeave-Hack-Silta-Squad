"""Read-only presentation of recorded CNC events; never drives manufacturing."""

import math


def complete_pass(result):
    return result.get("status") == "passed" and result.get("completed") is True


def finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def run_summary(manifest):
    """Compare only passes in this run, with explicit denominator and provenance."""
    events = manifest.get("events", [])
    passes = [
        event["verification"]
        for event in events
        if event.get("event") == "verification_completed"
        and complete_pass(event.get("verification", {}))
    ]
    timed = [item for item in passes if finite_number(item.get("machining_seconds"))]
    best = manifest.get("best_verification") or {}
    best_seconds = best.get("machining_seconds") if complete_pass(best) else None
    if not finite_number(best_seconds):
        best_seconds = None
    baseline = timed[0]["machining_seconds"] if timed else None
    # An incumbent may have a different input or verifier. Do not call that an improvement.
    comparable = bool(
        timed
        and complete_pass(best)
        and best.get("input_digest")
        and best.get("verifier_version")
        and best.get("coverage")
        and timed[0].get("input_digest") == best.get("input_digest")
        and timed[0].get("verifier_version") == best.get("verifier_version")
        and timed[0].get("coverage") == best.get("coverage")
    )
    saved = baseline - best_seconds if comparable and best_seconds is not None else None
    percent = 100 * saved / baseline if saved is not None and baseline else None
    decisions = [
        event.get("result", {}) for event in events if event.get("event") == "supervisor_decision"
    ]
    promotions = [
        event.get("result", {}) for event in events if event.get("event") == "promotion_evaluated"
    ]
    return {
        "passes": len(passes),
        "baseline_seconds": baseline,
        "best_seconds": best_seconds,
        "saved_seconds": saved,
        "improvement_percent": percent,
        "supervisor_decisions": decisions,
        "evaluations": len(promotions),
        "promotions": sum(item.get("promoted") is True for item in promotions),
        "last_action": decisions[-1].get("action") if decisions else None,
    }


def stage_rows(manifest):
    """Every stage reports recorded evidence, including pending learning."""
    events = manifest.get("events", [])

    def count(name):
        return sum(event.get("event") == name for event in events)

    checks = [
        event.get("result", {}) for event in events if event.get("event") == "checks_completed"
    ]
    results = [
        event.get("verification", {})
        for event in events
        if event.get("event") == "verification_completed"
    ]
    summary = run_summary(manifest)
    check_passed = sum(item.get("passed") is True for item in checks)
    check_failed = sum(item.get("passed") is False for item in checks)
    failed = sum(item.get("status") == "failed" for item in results)
    unknown = sum(not complete_pass(item) and item.get("status") != "failed" for item in results)
    decisions = len(summary["supervisor_decisions"])
    action = summary["last_action"] or "not reached"
    return [
        {
            "Stage": "1 · Fixed CAD",
            "Recorded evidence": "Accepted" if count("target_accepted") else "Not accepted yet",
        },
        {
            "Stage": "2 · Main agent → CAM",
            "Recorded evidence": f"{count('candidate_created')} candidates",
        },
        {
            "Stage": "3 · Cheap checks",
            "Recorded evidence": f"{check_passed} passed · {check_failed} failed",
        },
        {
            "Stage": "4 · Fusion + target comparison",
            "Recorded evidence": (
                f"{summary['passes']} passed · {failed} failed · {unknown} unknown"
            ),
        },
        {
            "Stage": "5 · Supervisor",
            "Recorded evidence": f"{decisions} decisions · latest: {action}",
        },
        {
            "Stage": "Learning → evaluated changes",
            "Recorded evidence": (
                f"{summary['evaluations']} evaluated · {summary['promotions']} promoted"
            ),
        },
    ]
