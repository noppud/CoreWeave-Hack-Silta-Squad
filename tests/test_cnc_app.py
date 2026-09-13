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


@pytest.mark.parametrize("status,errors", [("failed", 54), ("unknown", 0)])
def test_real_fusion_feedback_is_visible_without_overall_approval(reader, status, errors):
    rows = reader["attempt_rows"](
        {
            "events": [
                {
                    "event": "verification_completed",
                    "attempt": 1,
                    "verification": {
                        "status": status,
                        "completed": True,
                        "feedback": {
                            "summary": {
                                "percent": 100.0,
                                "errors": errors,
                                "warnings": 0,
                                "process_errors": 0,
                                "observed_details": [],
                            },
                            "metrics": {"machining_seconds": 223.109368, "tool_change_count": 0},
                        },
                    },
                }
            ]
        }
    )
    row = rows[0]
    assert row["Verification"] == status.capitalize()
    assert row["Fusion verification (%)"] == 100
    assert row["Fusion errors"] == errors
    assert row["Fusion warnings"] == row["Fusion process errors"] == 0
    assert row["API machining estimate (s)"] == 223.109368
    assert row["API tool changes"] == 0
    assert row["Seconds"] is row["Estimated cost"] is None
    assert "No verified" in reader["metric_chart"](rows, "Seconds", "Seconds", "#000")


@pytest.mark.parametrize(
    "feedback",
    [
        None,
        [],
        {},
        {"summary": None, "metrics": []},
        {
            "summary": {"percent": 101, "errors": True, "warnings": -1, "process_errors": 0.5},
            "metrics": {"machining_seconds": float("nan"), "tool_change_count": "2"},
        },
        {
            "summary": {"percent": float("inf"), "errors": "0", "warnings": None},
            "metrics": {"machining_seconds": -4, "tool_change_count": False},
        },
    ],
)
def test_missing_or_invalid_fusion_feedback_stays_missing(reader, feedback):
    rows = reader["attempt_rows"](
        {
            "events": [
                {
                    "event": "verification_completed",
                    "attempt": 1,
                    "verification": {"status": "unknown", "completed": False, "feedback": feedback},
                }
            ]
        }
    )
    for column in (
        "Fusion verification (%)",
        "Fusion errors",
        "Fusion warnings",
        "Fusion process errors",
        "API machining estimate (s)",
        "API tool changes",
    ):
        assert rows[0][column] is None


def test_artifacts_and_weave_links_only_come_from_explicit_records(reader):
    assert reader["artifact_paths"]({"path": "/unverified.mp4"}) == {}
    assert reader["artifact_paths"](
        {"evidence": [{"path": "/recorded.mp4", "sha256": "hash"}]}
    ) == {"/recorded.mp4": "hash"}
    assert reader["weave_link"]("javascript:alert(1)") is None
    assert reader["weave_link"]("weave:///silta/project/call/123") == (
        "https://wandb.ai/silta/project/weave/calls/123"
    )


def test_incomplete_attempt_never_keeps_running_or_passed_label(reader):
    rows = reader["attempt_rows"](
        {
            "status": "incomplete",
            "events": [
                {"event": "verification_started", "attempt": 1},
                {
                    "event": "verification_completed",
                    "attempt": 2,
                    "verification": {
                        "status": "passed",
                        "completed": False,
                        "machining_seconds": 0,
                    },
                },
            ],
        }
    )
    assert rows[0]["Verification"] == "Interrupted"
    assert rows[0]["Checks"] == "Not completed"
    assert rows[1]["Verification"] == "Unknown"
    assert rows[1]["Seconds"] is None


def test_saved_cam_document_displays_exact_pinned_reference_and_rejects_tampering(reader, tmp_path):
    import hashlib
    import json

    reference = {
        "document_name": "Silta CAM 1-unique",
        "version_number": 3,
        "version_id": "urn:adsk.wipprod:fs.file:vf.document?version=3",
        "data_file_id": "urn:adsk.wipprod:dm.lineage:document",
        "project_id": "project-1",
    }
    path = tmp_path / "fusion-document.json"
    path.write_text(json.dumps(reference))
    candidate = {
        "artifacts": {
            "fusion_document": {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        }
    }
    assert reader["saved_cam_document"](candidate) == (reference, None)
    path.write_text(json.dumps({**reference, "version_number": 4}))
    actual, error = reader["saved_cam_document"](candidate)
    assert actual == {} and "hash check" in error
    assert reader["saved_cam_document"]({}) == ({}, None)


def test_refresh_dependent_selector_discovers_a_new_run(tmp_path):
    import ast
    import json
    from pathlib import Path
    from types import SimpleNamespace

    # Marimo uses cell dependencies to decide what refresh actually reruns.
    tree = ast.parse(Path("notebooks/cnc_app.py").read_text())
    selector = next(
        cell
        for cell in tree.body
        if isinstance(cell, ast.FunctionDef)
        and any(
            isinstance(node, ast.Name) and node.id == "manifest_files" for node in ast.walk(cell)
        )
    )
    assert "refresh" in [arg.arg for arg in selector.args.args]
    overrides = {
        "jobs_root": SimpleNamespace(value=str(tmp_path)),
        "campaign_path": SimpleNamespace(value=""),
        "versions_root": SimpleNamespace(value=str(tmp_path / "versions")),
        "refresh": SimpleNamespace(value=0),
    }
    _, empty = app.run(defs=overrides)
    assert empty["job_selector"].value is None
    run = tmp_path / "new-run"
    run.mkdir()
    manifest = run / "manifest.json"
    manifest.write_text(json.dumps({"status": "running", "events": []}))
    overrides["refresh"].value = 1
    _, populated = app.run(defs=overrides)
    assert populated["job_selector"].value == str(manifest)
    assert populated["manifest"]["status"] == "running"


def test_campaign_selects_current_recorded_part_and_retains_pending_parts(tmp_path):
    import json
    from types import SimpleNamespace

    run = tmp_path / "part-one"
    run.mkdir()
    manifest = run / "manifest.json"
    manifest.write_text(json.dumps({"status": "completed", "events": []}))
    campaign = tmp_path / "campaign.json"
    campaign.write_text(
        json.dumps(
            {
                "campaign_id": "sequential",
                "status": "running",
                "current_part_id": "one",
                "parts": [
                    {
                        "part_id": "one",
                        "label": "First",
                        "status": "completed",
                        "manifest_path": str(manifest),
                    },
                    {"part_id": "two", "label": "Second", "status": "pending"},
                ],
            }
        )
    )
    _, definitions = app.run(
        defs={
            "jobs_root": SimpleNamespace(value=str(tmp_path / "no-other-runs")),
            "versions_root": SimpleNamespace(value=str(tmp_path / "versions")),
            "campaign_path": SimpleNamespace(value=str(campaign)),
            "refresh": SimpleNamespace(value=0),
        }
    )
    assert definitions["job_selector"].value == str(manifest)
    assert len(definitions["campaign"]["parts"]) == 2
    assert definitions["campaign_runs"] == [manifest]
