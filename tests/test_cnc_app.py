"""Reader tests: incomplete evidence never becomes a successful chart point."""

import pytest

from notebooks.cnc_app import app


@pytest.fixture(scope="module")
def reader():
    _, definitions = app.run()
    return definitions


def test_unknown_verification_does_not_get_fast_zero_score(reader):
    event = {
        "event": "verification_completed",
        "attempt": 1,
        "verification": {
            "status": "unknown",
            "completed": False,
            "machining_seconds": 0,
            "estimated_cost": 0,
        },
    }
    rows = reader["attempt_rows"]({"events": [event]})
    assert rows[0]["Seconds"] is None
    assert rows[0]["Estimated cost"] is None
    assert rows[0]["Verification"] == "Unknown"


def test_only_recorded_completed_pass_is_charted(reader):
    event = {
        "event": "verification_completed",
        "attempt": 2,
        "verification": {
            "status": "passed",
            "completed": True,
            "machining_seconds": 83.5,
            "estimated_cost": None,
        },
    }
    rows = reader["attempt_rows"]({"events": [event]})
    assert rows[0]["Seconds"] == 83.5
    assert rows[0]["Estimated cost"] is None
    assert "83.50" in reader["metric_chart"](rows, "Seconds", "Seconds", "#000")
    assert "No verified" in reader["metric_chart"](rows, "Estimated cost", "Cost", "#000")


def test_artifacts_and_weave_links_only_come_from_explicit_records(reader):
    assert reader["artifact_paths"]({"path": "/unverified.mp4"}) == {}
    assert reader["artifact_paths"](
        {"evidence": [{"path": "/recorded.mp4", "sha256": "hash"}]}
    ) == {"/recorded.mp4": "hash"}
    assert reader["weave_link"]("javascript:alert(1)") is None
    assert reader["weave_link"]("weave:///silta/project/call/123") == (
        "https://wandb.ai/silta/project/weave/calls/123"
    )
