"""Summary evidence must not conflate cheap, incomplete, or incompatible runs."""

from silta.cnc.presentation import run_summary, stage_rows


def verification(seconds, **updates):
    return dict(
        status="passed",
        completed=True,
        machining_seconds=seconds,
        input_digest="inputs",
        verifier_version="verifier",
        coverage="coverage",
        **updates,
    )


def test_summary_uses_first_verified_baseline_and_pinned_best():
    first, best = verification(120), verification(90)
    manifest = {
        "events": [
            {
                "event": "verification_completed",
                "verification": {"status": "failed", "machining_seconds": 30},
            },
            {"event": "verification_completed", "verification": first},
            {"event": "verification_completed", "verification": best},
            {
                "event": "supervisor_decision",
                "result": {"action": "stop", "instructions": "Retain best"},
            },
        ],
        "best_verification": best,
    }
    summary = run_summary(manifest)
    assert summary["baseline_seconds"] == 120
    assert summary["best_seconds"] == 90
    assert summary["improvement_percent"] == 25
    assert summary["passes"] == 2
    assert summary["last_action"] == "stop"
    assert summary["promotions"] == summary["evaluations"] == 0


def test_incompatible_incumbent_does_not_claim_improvement():
    first, best = verification(120), verification(90)
    best["input_digest"] = "different-input"
    summary = run_summary(
        {
            "events": [{"event": "verification_completed", "verification": first}],
            "best_verification": best,
        }
    )
    assert summary["improvement_percent"] is None


def test_unknown_and_unpromoted_learning_are_distinct():
    manifest = {
        "events": [
            {
                "event": "verification_completed",
                "verification": {"status": "passed", "completed": False},
            },
            {"event": "promotion_evaluated", "result": {"promoted": False}},
        ]
    }
    summary = run_summary(manifest)
    assert summary["passes"] == 0
    assert summary["evaluations"] == 1
    assert summary["promotions"] == 0
    assert "1 unknown" in stage_rows(manifest)[3]["Recorded evidence"]
    assert stage_rows(manifest)[-1]["Recorded evidence"] == "1 evaluated · 0 promoted"
