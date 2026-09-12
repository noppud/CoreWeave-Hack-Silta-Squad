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


def test_incomplete_attempt_never_keeps_running_or_passed_label(reader):
    rows = reader["attempt_rows"]({
        "status": "incomplete",
        "events": [
            {"event": "verification_started", "attempt": 1},
            {"event": "verification_completed", "attempt": 2,
             "verification": {"status": "passed", "completed": False, "machining_seconds": 0}},
        ],
    })
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
    candidate = {"artifacts": {"fusion_document": {
        "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }}}
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
    selector = next(cell for cell in tree.body if isinstance(cell, ast.FunctionDef)
                    and any(isinstance(node, ast.Name) and node.id == "manifest_files"
                            for node in ast.walk(cell)))
    assert "refresh" in [arg.arg for arg in selector.args.args]
    overrides = {
        "jobs_root": SimpleNamespace(value=str(tmp_path)),
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
