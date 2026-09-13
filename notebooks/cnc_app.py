"""Read-only CNC run viewer. Run: marimo run notebooks/cnc_app.py.

Set SILTA_JOBS_DIR and SILTA_VERSIONS_DIR to change the artifact directories.
All metrics/media come from recorded manifests; no demo scores or motion are synthesized.
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Silta · CNC loop")


@app.cell
def _():
    import hashlib
    import html
    import json
    import math
    import os
    import sys
    from pathlib import Path

    import marimo as mo

    # Marimo launches with the notebook directory on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from silta.cnc.presentation import current_stage, run_summary, stage_rows

    return Path, current_stage, hashlib, html, json, math, mo, os, run_summary, stage_rows


@app.cell
def _(Path, hashlib, html, json, math):
    def read_json(path):
        try:
            data = json.loads(Path(path).read_text())
            if not isinstance(data, dict):
                return {}, "Expected a JSON object"
            return data, None
        except (OSError, ValueError) as error:
            return {}, str(error)

    def attempt_rows(manifest):
        attempts = {}
        for event in manifest.get("events", []):
            number = event.get("attempt")
            if not isinstance(number, int):
                continue
            row = attempts.setdefault(
                number,
                {
                    "Attempt": number,
                    "Candidate": "—",
                    "Checks": "Pending",
                    "Verification": "Pending",
                    "Fusion verification (%)": None,
                    "Fusion errors": None,
                    "Fusion warnings": None,
                    "Fusion process errors": None,
                    "API machining estimate (s)": None,
                    "API tool changes": None,
                    "Seconds": None,
                    "Estimated cost": None,
                    "Issues": "",
                },
            )
            if event.get("event") == "candidate_created":
                row["Candidate"] = event.get("candidate", {}).get("id", "—")
            elif event.get("event") == "checks_completed":
                result = event.get("result", {})
                row["Checks"] = (
                    "Passed"
                    if result.get("passed") is True
                    else "Failed"
                    if result.get("passed") is False
                    else "Unknown"
                )
                row["Issues"] = "; ".join(result.get("issues", []))
            elif event.get("event") == "verification_started":
                row["Verification"] = "Running"
            elif event.get("event") == "verification_completed":
                result = event.get("verification", {})
                passed = result.get("status") == "passed" and result.get("completed") is True
                row["Verification"] = (
                    "Passed"
                    if passed
                    else "Unknown"
                    if result.get("status") == "passed"
                    else str(result.get("status", "unknown")).capitalize()
                )
                row["Issues"] = "; ".join(result.get("issues", []))
                # Observations remain useful on rejected/unapproved plans, but
                # never populate the verified-only chart fields below.
                feedback = result.get("feedback")
                feedback = feedback if isinstance(feedback, dict) else {}
                summary = feedback.get("summary")
                summary = summary if isinstance(summary, dict) else {}
                metrics = feedback.get("metrics")
                metrics = metrics if isinstance(metrics, dict) else {}
                for column, value, count, maximum in (
                    ("Fusion verification (%)", summary.get("percent"), False, 100),
                    ("Fusion errors", summary.get("errors"), True, None),
                    ("Fusion warnings", summary.get("warnings"), True, None),
                    ("Fusion process errors", summary.get("process_errors"), True, None),
                    ("API machining estimate (s)", metrics.get("machining_seconds"), False, None),
                    ("API tool changes", metrics.get("tool_change_count"), True, None),
                ):
                    if (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                        and value >= 0
                        and (maximum is None or value <= maximum)
                        and (not count or isinstance(value, int))
                    ):
                        row[column] = value
                # Failed/unknown plans never appear as cheap or fast successes.
                if passed:
                    for column, key in (
                        ("Seconds", "machining_seconds"),
                        ("Estimated cost", "estimated_cost"),
                    ):
                        value = result.get(key)
                        if (
                            isinstance(value, (int, float))
                            and not isinstance(value, bool)
                            and math.isfinite(value)
                            and value >= 0
                        ):
                            row[column] = value
        if manifest.get("status") == "incomplete":
            for row in attempts.values():
                if row["Checks"] == "Pending":
                    row["Checks"] = "Not completed"
                if row["Verification"] in {"Pending", "Running"}:
                    row["Verification"] = (
                        "Interrupted" if row["Verification"] == "Running" else "Not reached"
                    )
        return [attempts[key] for key in sorted(attempts)]

    def saved_cam_document(candidate):
        artifact = candidate.get("artifacts", {}).get("fusion_document")
        if not artifact:
            return {}, None
        try:
            raw = Path(artifact["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != artifact.get("sha256"):
                return {}, "Saved Fusion document reference failed its artifact hash check"
            reference = json.loads(raw)
            if (
                not isinstance(reference, dict)
                or not all(
                    isinstance(reference.get(key), str) and reference[key]
                    for key in ("document_name", "version_id", "data_file_id", "project_id")
                )
                or type(reference.get("version_number")) is not int
            ):
                return {}, "Saved Fusion document reference is incomplete"
            return reference, None
        except (OSError, ValueError, KeyError, TypeError) as error:
            return {}, str(error)

    def metric_chart(rows, metric, label, color):
        points = [(row["Attempt"], row[metric]) for row in rows if row[metric] is not None]
        if not points:
            return f'<p style="color:#64748b">No verified {html.escape(label.lower())} yet.</p>'
        ceiling = max(value for _, value in points) or 1
        xmax = max(row["Attempt"] for row in rows) or 1
        circles = []
        for attempt, value in points:
            x, y = 54 + (attempt - 1) / max(xmax - 1, 1) * 480, 182 - value / ceiling * 142
            circles.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}">'
                f"<title>Attempt {attempt}: {value:,.2f}</title></circle>"
                f'<text x="{x:.2f}" y="{y - 12:.2f}" text-anchor="middle" '
                f'font-size="12" fill="#334155">{value:,.2f}</text>'
            )
        return (
            f'<svg viewBox="0 0 590 225" role="img" '
            f'aria-label="{html.escape(label)} by verified attempt" '
            'style="width:100%;max-height:240px;font-family:system-ui">'
            '<path d="M54 30 V182 H550" fill="none" stroke="#cbd5e1"/>'
            f'<text x="12" y="45" font-size="11" fill="#64748b">{ceiling:,.0f}</text>'
            '<text x="30" y="185" font-size="11" fill="#64748b">0</text>'
            f"{''.join(circles)}"
            '<text x="54" y="207" font-size="11" fill="#64748b">Attempt 1</text>'
            f'<text x="505" y="207" font-size="11" fill="#64748b">{xmax}</text>'
            "</svg>"
        )

    def artifact_paths(value):
        """Only explicitly recorded artifact objects, never an arbitrary directory scan."""
        found = {}

        def visit(item):
            if isinstance(item, dict):
                if isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str):
                    found[item["path"]] = item["sha256"]
                for child in item.values():
                    visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)

        visit(value)
        return found

    def weave_link(reference):
        if reference.startswith("weave:///"):
            parts = reference.removeprefix("weave:///").split("/")
            if len(parts) == 4 and parts[2] == "call":
                return f"https://wandb.ai/{parts[0]}/{parts[1]}/weave/calls/{parts[3]}"
        return reference if reference.startswith("https://wandb.ai/") else None

    return artifact_paths, attempt_rows, metric_chart, read_json, saved_cam_document, weave_link


@app.cell
def _(Path, mo, os):
    jobs_root = mo.ui.text(
        value=os.environ.get("SILTA_JOBS_DIR", str(Path.cwd() / "runs")),
        label="Jobs directory",
        full_width=True,
    )
    versions_root = mo.ui.text(
        value=os.environ.get("SILTA_VERSIONS_DIR", str(Path.cwd() / "versions")),
        label="Evaluation versions directory",
        full_width=True,
    )
    campaign_path = mo.ui.text(
        value=os.environ.get(
            "SILTA_CAMPAIGN_MANIFEST",
            str(Path.cwd() / "runs/demo-campaign.json"),
        ),
        label="Sequential campaign manifest (optional)",
        full_width=True,
    )
    refresh = mo.ui.refresh(options=["5s", "15s", "1m"], default_interval="15s")
    mo.vstack(
        [
            mo.md("# SILTA / Machining that learns"),
            mo.md("Drawing → fixed CAD → CAM → checks → Fusion simulation → judge → better plan."),
            mo.accordion(
                {
                    "Run sources and refresh": mo.vstack(
                        [mo.hstack([jobs_root, versions_root, refresh], align="end"), campaign_path]
                    )
                }
            ),
        ]
    )
    return campaign_path, jobs_root, refresh, versions_root


@app.cell
def _(Path, campaign, hashlib, jobs_root, mo, read_json, refresh, run_summary):
    _tick = refresh.value
    _repo = Path(jobs_root.value).expanduser().parent
    history, _history_error = read_json(Path(jobs_root.value) / "four-part-learning-summary.json")
    _parts = []
    _seen_targets = set()
    for _part in history.get("parts", []):
        _path = Path(jobs_root.value) / _part["final_run"] / "manifest.json"
        _run, _error = read_json(_path)
        _result = _run.get("best_verification") or {}
        if _run.get("target_digest"):
            _seen_targets.add(_run["target_digest"])
        _parts.append(
            {
                "Part": _part.get("part"),
                "Run": _part["final_run"],
                "Plan": _result.get("status", "unavailable"),
                "Job": _run.get("status", "unavailable"),
                "Machining estimate (s)": run_summary(_run)["best_seconds"],
                "Learning carried forward": ", ".join(
                    key
                    for key, value in _part.get("final_versions", {}).items()
                    if value != _part.get("initial_learning_versions", {}).get(key)
                )
                or "Existing guidance reused",
            }
        )
    video_evidence, _ = read_json(_repo / "output/video/demo-evidence.json")
    _video_manifest, _ = (
        read_json(video_evidence["run_manifest"])
        if video_evidence.get("run_manifest")
        else ({}, None)
    )
    _verified_video = _video_manifest.get("best_verification") or {}
    if _video_manifest and _video_manifest.get("job_id") not in {row["Run"] for row in _parts}:
        _parts.append(
            {
                "Part": "Indexed 3+2",
                "Run": _video_manifest.get("job_id"),
                "Plan": _verified_video.get("status", "unavailable"),
                "Job": _video_manifest.get("status", "unavailable"),
                "Machining estimate (s)": run_summary(_video_manifest)["best_seconds"],
                "Learning carried forward": "See this run's recorded versions",
            }
        )
    if _video_manifest.get("target_digest"):
        _seen_targets.add(_video_manifest["target_digest"])
    for _part in campaign.get("parts", []):
        _run, _ = read_json(_part["manifest_path"]) if _part.get("manifest_path") else ({}, None)
        _target = _run.get("target_digest")
        if not _target or _target in _seen_targets:
            continue
        _seen_targets.add(_target)
        _result = _run.get("best_verification") or {}
        _parts.append(
            {
                "Part": _part.get("label") or _part.get("part_id"),
                "Run": _run.get("job_id"),
                "Plan": _result.get("status", "pending"),
                "Job": _run.get("status", "pending"),
                "Machining estimate (s)": run_summary(_run)["best_seconds"],
                "Learning carried forward": "See campaign versions and this run's changes",
            }
        )
    _verified_count = sum(
        row["Plan"] == "passed" and row["Machining estimate (s)"] is not None for row in _parts
    )
    _video = Path(video_evidence["video"]) if video_evidence.get("video") else None
    _video_ok = (
        _video
        and _video.is_file()
        and hashlib.sha256(_video.read_bytes()).hexdigest() == video_evidence.get("sha256")
        and _verified_video.get("status") == "passed"
        and _verified_video.get("completed") is True
        and _video_manifest.get("best_candidate", {}).get("id")
        == video_evidence.get("verified_candidate")
    )
    mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(
                        label="Distinct showcased parts with verified plans", value=_verified_count
                    ),
                    mo.stat(label="Historical target", value="10 parts"),
                    mo.stat(label="Next live demonstration", value="Run 11 · when ready"),
                ]
            ),
            mo.md(
                f"**{_verified_count} verified parts are available in this showcase.** "
                "The ten-part history and eleventh live run are not yet complete."
            )
            if _verified_count < 10
            else mo.md("Open the campaign below for live progress."),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            mo.md("### The machine, actually machining"),
                            mo.video(str(_video), controls=True, width="100%")
                            if _video_ok
                            else mo.md("No validated machine recording available."),
                            mo.md(
                                "Actual Fusion recording · Haas UMC-750 · indexed 3+2. "
                                "Edited playback ends with a still of finished stock. "
                                "Candidate passed; job stopped at the attempt limit."
                            ),
                            mo.accordion({"Recording provenance": mo.json(video_evidence)}),
                        ]
                    ),
                    mo.vstack(
                        [
                            mo.md("### Learning that transferred"),
                            mo.vstack(
                                [
                                    mo.callout(
                                        mo.md(
                                            f"**{item.get('source', '')}**  "
                                            f"\n{item.get('effect', '')}"
                                        )
                                    )
                                    for item in history.get("observed_learning", [])
                                ]
                            ),
                            mo.md(
                                "Historical changes were saved directly. "
                                "Weave traces and later replay evaluations are separate."
                            ),
                        ]
                    ),
                ]
            ),
            mo.ui.table(_parts, selection=None)
            if _parts
            else mo.md("No showcase history recorded."),
            mo.md(
                "Different parts contain different machining work; "
                "their times are not a controlled learning curve."
            ),
        ]
    ) if history or video_evidence else mo.md("")
    return history, video_evidence


@app.cell
def _(Path, jobs_root, mo, read_json, refresh):
    import difflib

    _tick = refresh.value
    _path = Path(jobs_root.value).expanduser().parent / "output/evaluation/learning-evaluation.json"
    evaluation, _ = read_json(_path) if _path.is_file() else ({}, None)
    _variant_rows = [
        {
            key: variant.get(key)
            for key in ("name", "caught_invalid", "false_rejections", "median_runtime_ms")
        }
        for variant in evaluation.get("variants", [])
    ]
    _links = [
        mo.md(f"[{variant.get('name', 'Evaluation')} in Weave]({variant['weave_url']})")
        for variant in evaluation.get("variants", [])
        if str(variant.get("weave_url", "")).startswith("https://wandb.ai/")
    ]
    _source = evaluation.get("check_source", {})
    _diff = "\n".join(
        difflib.unified_diff(
            str(_source.get("baseline", "")).splitlines(),
            str(_source.get("learned", "")).splitlines(),
            fromfile="Initial checks",
            tofile="Learned checks",
            lineterm="",
        )
    )
    mo.vstack(
        [
            mo.md("## Does the learning hold up?"),
            mo.md(str(evaluation.get("scope", "No replay evaluation recorded yet."))),
            mo.md(
                f"**{evaluation.get('dataset', {}).get('case_count', 0)} retained cases** · "
                f"{evaluation.get('dataset', {}).get('invalid_count', 0)} invalid · "
                f"{evaluation.get('dataset', {}).get('valid_count', 0)} valid · "
                f"Publication: {evaluation.get('status', 'not recorded')}"
            ),
            mo.ui.table(_variant_rows, selection=None)
            if _variant_rows
            else mo.md("Evaluation results pending."),
            mo.hstack(_links) if _links else mo.md("No published evaluation links yet."),
            mo.accordion(
                {
                    "Learned check diff": mo.md("```diff\n" + _diff + "\n```"),
                    "Planning guidance": mo.md(
                        "```markdown\n"
                        + str(evaluation.get("prompt_source", "Not supplied"))
                        + "\n```"
                    ),
                    "Per-case replay": mo.ui.table(evaluation.get("rows", []), selection=None)
                    if evaluation.get("rows")
                    else mo.md("No cases"),
                    "Prompt improvement evidence": mo.json(evaluation.get("prompt_evidence", [])),
                    "Scope and limitations": mo.json(evaluation.get("limitations", [])),
                }
            ),
        ]
    ) if evaluation else mo.md("")
    return (evaluation,)


@app.cell
def _(Path, campaign_path, mo, read_json, refresh, run_summary):
    _tick = refresh.value
    campaign, _error = (
        read_json(campaign_path.value)
        if campaign_path.value and Path(campaign_path.value).is_file()
        else ({}, None)
    )
    campaign_runs = []
    _rows = []
    for _part in campaign.get("parts", []):
        _manifest_path = _part.get("manifest_path")
        _run, _run_error = read_json(_manifest_path) if _manifest_path else ({}, None)
        if _manifest_path and Path(_manifest_path).is_file():
            campaign_runs.append(Path(_manifest_path))
        _summary = run_summary(_run)
        _rows.append(
            {
                "Part": _part.get("label") or _part.get("part_id"),
                "Campaign status": _part.get("status", "pending"),
                "Run status": _run.get("status", "Not started"),
                "Verified time (s)": _summary["best_seconds"],
                "Within-part improvement (%)": _summary["improvement_percent"],
                "Evaluations": _summary["evaluations"],
                "Promotions": _summary["promotions"],
                "Evidence": _run_error or ("Recorded run" if _run else "No run yet"),
            }
        )
    mo.vstack(
        [
            mo.md("## Sequential learning campaign"),
            mo.md(
                f"**{campaign.get('campaign_id', 'Campaign')}** · "
                f"{campaign.get('status', 'unknown')} "
                f"· Current part: {campaign.get('current_part_id') or 'none'}"
            ),
            mo.md(
                "Parts run in order. Each part keeps its own fixed target. "
                "Learning status comes from recorded events; "
                "saved changes and evaluated promotions are distinct."
            ),
            mo.ui.table(_rows, selection=None) if _rows else mo.md("No campaign parts recorded."),
            mo.accordion(
                {
                    "Initial versions and campaign history": mo.json(
                        {
                            "initial_versions": campaign.get("initial_versions"),
                            "version_store": campaign.get("version_store"),
                            "events": campaign.get("events", []),
                            "part_versions": [
                                {
                                    "part": part.get("part_id"),
                                    "starting": part.get("starting_versions"),
                                    "ending": part.get("ending_versions"),
                                }
                                for part in campaign.get("parts", [])
                            ],
                        }
                    )
                }
            ),
        ]
    ) if campaign else (mo.callout(mo.md(_error), kind="danger") if _error else mo.md(""))
    return campaign, campaign_runs


@app.cell
def _(mo):
    selected_run, remember_selected_run = mo.state(None)
    return remember_selected_run, selected_run


@app.cell
def _(Path, campaign, campaign_runs, jobs_root, mo, refresh, remember_selected_run, selected_run):
    _refresh_tick = refresh.value
    manifest_files = sorted(
        set(Path(jobs_root.value).expanduser().glob("*/manifest.json")) | set(campaign_runs),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    _current_path = next(
        (
            part.get("manifest_path")
            for part in campaign.get("parts", [])
            if part.get("part_id") == campaign.get("current_part_id")
        ),
        None,
    )
    _preferred = selected_run() or _current_path
    _selected = next(
        (path.parent.name for path in manifest_files if str(path) == _preferred),
        manifest_files[0].parent.name if manifest_files else None,
    )
    job_selector = mo.ui.dropdown(
        options={path.parent.name: str(path) for path in manifest_files},
        value=_selected,
        on_change=remember_selected_run,
        label="Run",
        full_width=True,
    )
    mo.vstack(
        [
            job_selector,
            mo.md("No recorded runs yet. Start a machining job to populate this view.")
            if not manifest_files
            else mo.md(""),
        ]
    )
    return (job_selector,)


@app.cell
def _(attempt_rows, current_stage, job_selector, mo, read_json, refresh):
    _refresh_tick = refresh.value
    manifest, load_error = read_json(job_selector.value) if job_selector.value else ({}, None)
    rows = attempt_rows(manifest)
    events = manifest.get("events", [])
    latest_candidate = next(
        (
            event.get("candidate", {})
            for event in reversed(events)
            if event.get("event") == "candidate_created"
        ),
        {},
    )
    latest_verification = next(
        (
            event.get("verification", {})
            for event in reversed(events)
            if event.get("event") == "verification_completed"
        ),
        {},
    )
    latest_verification_candidate = next(
        (
            event.get("candidate", {}).get("id", "Unknown")
            for event in reversed(events)
            if event.get("event") == "candidate_created"
            and event.get("candidate_digest")
            and event["candidate_digest"] == latest_verification.get("candidate_digest")
        ),
        "No bound candidate recorded",
    )
    best = manifest.get("best_candidate") or {}
    best_verification = manifest.get("best_verification") or {}
    mo.vstack(
        [
            mo.callout(mo.md(f"Could not read this run: {load_error}"), kind="danger")
            if load_error
            else mo.md(""),
            mo.hstack(
                [
                    mo.stat(
                        label="Recorded run status", value=manifest.get("status", "Not started")
                    ),
                    mo.stat(label="Current stage", value=current_stage(manifest)),
                    mo.stat(label="Current candidate", value=latest_candidate.get("id", "—")),
                    mo.stat(label="Best verified candidate", value=best.get("id", "None yet")),
                ]
            ),
            mo.md(str(manifest.get("reason", ""))),
            mo.md(
                "Last recorded event: "
                + str(events[-1].get("at", "Timestamp unavailable"))
                + (
                    " · Activity is not independently monitored."
                    if manifest.get("status") == "running"
                    else ""
                )
            )
            if events
            else mo.md(""),
        ]
    )
    return (
        best,
        best_verification,
        events,
        latest_candidate,
        latest_verification,
        latest_verification_candidate,
        manifest,
        rows,
    )


@app.cell
def _(manifest, mo, run_summary, stage_rows):
    summary = run_summary(manifest)
    _best = summary["best_seconds"]
    _baseline = summary["baseline_seconds"]
    _gain = summary["improvement_percent"]
    mo.vstack(
        [
            mo.md("## The loop in this run"),
            mo.md(
                "**Fixed CAD → CAM → cheap checks → "
                "Fusion + finished-part comparison → supervisor.** "
                "Failures return to CAM repair; missing checks can become evaluated improvements."
            ),
            mo.hstack(
                [
                    mo.stat(
                        label="First verified plan in this run",
                        value=f"{_baseline:.2f} s" if _baseline is not None else "—",
                    ),
                    mo.stat(
                        label="Best verified machining estimate",
                        value=f"{_best:.2f} s" if _best is not None else "—",
                    ),
                    mo.stat(
                        label="Improvement within this run",
                        value=f"{_gain:.1f}%" if _gain is not None else "—",
                    ),
                    mo.stat(label="Completed verification passes", value=summary["passes"]),
                ]
            ),
            mo.ui.table(stage_rows(manifest), selection=None),
            mo.accordion(
                {
                    f"Supervisor decision {index + 1} · {decision.get('action', 'unknown')}": mo.md(
                        str(decision.get("instructions", "No instructions recorded"))
                    )
                    for index, decision in enumerate(summary["supervisor_decisions"])
                }
            )
            if summary["supervisor_decisions"]
            else mo.md("Supervisor has not been reached."),
        ]
    )
    return (summary,)


@app.cell
def _(best, html, latest_candidate, mo, saved_cam_document):
    _selected_candidate = best or latest_candidate
    _document, _document_error = saved_cam_document(_selected_candidate)
    mo.vstack(
        [
            mo.md(
                "## Best verified Fusion CAM document" if best else "## Latest Fusion CAM document"
            ),
            mo.callout(mo.md(_document_error), kind="danger") if _document_error else mo.md(""),
            mo.Html(
                "<p>Candidate <strong>"
                + html.escape(str(_selected_candidate.get("id", "—")))
                + "</strong>: "
                + html.escape(_document["document_name"])
                + " · Version "
                + str(_document["version_number"])
                + "</p>"
            )
            if _document
            else mo.md("No saved CAM reference recorded for this candidate."),
            mo.accordion({"Exact Fusion document reference": mo.json(_document)})
            if _document
            else mo.md(""),
            mo.md("Verification results below identify the candidate they apply to.")
            if _document
            else mo.md(""),
        ]
    )
    return


@app.cell
def _(best_verification, metric_chart, mo, rows):
    mo.vstack(
        [
            mo.md("## Machining estimates"),
            mo.md(
                "Only completed verification passes are plotted. Missing costs stay missing. "
                "Estimates use the recorded machine and costing assumptions."
            ),
            mo.hstack(
                [
                    mo.vstack(
                        [
                            mo.md("**Machining time · seconds**"),
                            mo.Html(metric_chart(rows, "Seconds", "Machining seconds", "#0d9488")),
                        ]
                    ),
                    mo.vstack(
                        [
                            mo.md("**Estimated cost · configured currency**"),
                            mo.Html(
                                metric_chart(rows, "Estimated cost", "Estimated cost", "#6366f1")
                            ),
                        ]
                    ),
                ]
            ),
            mo.md(
                "**Best plan verification coverage:** "
                + str(best_verification.get("coverage", "Not available"))
            ),
            mo.md(
                "The attempt table also shows Fusion's observed progress/issues and API time "
                "estimates for failed or unknown plans. These do not imply overall verification "
                "approval; 100% means Fusion finished its verification."
            ),
            mo.ui.table(rows, selection=None) if rows else mo.md("No machining attempts recorded."),
        ]
    )
    return


@app.cell
def _(
    Path,
    artifact_paths,
    best,
    best_verification,
    html,
    latest_verification,
    latest_verification_candidate,
    mo,
    manifest,
    video_evidence,
):
    _showcase_matches = video_evidence.get("verified_candidate") == best.get("id") and Path(
        video_evidence.get("run_manifest", "missing")
    ).parent.name == manifest.get("job_id")
    _shown_verification = best_verification or latest_verification
    _shown_candidate = best.get("id") if best_verification else latest_verification_candidate
    _media = [
        Path(path)
        for path in artifact_paths(_shown_verification)
        if Path(path).suffix.lower() in {".mp4", ".webm", ".mov"} and Path(path).is_file()
    ]
    _screens = [
        Path(path)
        for path in artifact_paths(_shown_verification)
        if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg"} and Path(path).is_file()
    ]
    mo.vstack(
        [
            mo.md("## Machine verification evidence"),
            mo.Html(
                "<p>Best verified result (or latest if none passed) · Candidate: <strong>"
                + html.escape(str(_shown_candidate))
                + "</strong></p>"
            ),
            mo.Html(
                "<p>Status: <strong>"
                + html.escape(str(_shown_verification.get("status", "not run")))
                + f"</strong> · Completed: {_shown_verification.get('completed') is True}</p>"
            ),
            mo.video(str(_media[-1]), controls=True, width="100%")
            if _media
            else mo.callout(
                mo.md(
                    "This candidate’s recording is shown in the showcase above."
                    if _showcase_matches
                    else "No machine recording is attached to this verification."
                )
            ),
            mo.accordion(
                {
                    f"Recorded Fusion screenshot {index + 1}": mo.image(str(path), width="100%")
                    for index, path in enumerate(_screens)
                }
            )
            if _screens
            else mo.md(""),
            mo.md(
                "\n".join(
                    f"- {html.escape(str(issue))}"
                    for issue in _shown_verification.get("issues", [])
                )
            ),
        ]
    )
    return


@app.cell
def _(Path, best, best_verification, hashlib, manifest, mo):
    _target = manifest.get("target", {}).get("artifacts", {})
    _cam = best.get("artifacts", {})
    _downloads = []
    _missing = []
    _preview = None
    _records = [
        ("Target CAD · STEP", _target.get("step")),
        ("CAM project · Fusion", _cam.get("f3d")),
    ]
    _records.extend(
        (f"Posted NC · {key}", value) for key, value in _cam.items() if key.startswith("nc-")
    )
    for _label, _record in _records:
        if not _record:
            continue
        _path = Path(_record["path"])
        if _path.is_file() and hashlib.sha256(_path.read_bytes()).hexdigest() == _record.get(
            "sha256"
        ):
            _downloads.append(mo.download(data=_path.read_bytes, filename=_path.name, label=_label))
        else:
            _missing.append(f"{_label}: recorded file missing or changed")
    _image_record = _target.get("preview", {})
    if _image_record.get("path"):
        _image_path = Path(_image_record["path"])
        if _image_path.is_file() and hashlib.sha256(
            _image_path.read_bytes()
        ).hexdigest() == _image_record.get("sha256"):
            _preview = mo.image(str(_image_path), width="100%")
    _comparison = best_verification.get("feedback", {}).get("target_stock_comparison", {})
    mo.vstack(
        [
            mo.md("## The part and returned files"),
            mo.hstack(
                [
                    _preview or mo.md("No recorded target preview."),
                    mo.vstack(
                        [
                            mo.md(
                                "**Machine:** "
                                + str(
                                    manifest.get("inputs", {})
                                    .get("machine", {})
                                    .get("name", "Not recorded")
                                )
                            ),
                            mo.md(
                                "**Finished-part comparison:** "
                                + str(_comparison.get("status", "Not recorded"))
                                + (
                                    f" · tolerance {_comparison['tolerance_mm']} mm"
                                    if "tolerance_mm" in _comparison
                                    else ""
                                )
                            ),
                            mo.vstack(_downloads)
                            if _downloads
                            else mo.md("No returned manufacturing files yet."),
                            mo.md(
                                "Internal CAM was simulated. "
                                "The posted NC is a separate exported deliverable."
                            ),
                            mo.md("\n".join(_missing)) if _missing else mo.md(""),
                        ]
                    ),
                ]
            ),
        ]
    )
    return


@app.cell
def _(Path, artifact_paths, best, html, manifest, mo):
    _artifacts = artifact_paths(manifest)
    _downloads = []
    for _path in _artifacts:
        _file = Path(_path)
        if _file.is_file():
            _downloads.append(
                mo.download(
                    data=_file.read_bytes,
                    filename=_file.name,
                    label=f"Download {_file.parent.name}/{_file.name}",
                )
            )
        else:
            _downloads.append(mo.Html(f"<p>Missing artifact: {html.escape(_path)}</p>"))
    mo.vstack(
        [
            mo.md("## Inputs and deliverables"),
            mo.accordion(
                {
                    "Drawing, machine, tools and setup": mo.json(manifest.get("inputs", {})),
                    "Accepted fixed target": mo.json(manifest.get("target", {})),
                    "Best verified plan": mo.json(best),
                    "Pinned versions": mo.json(manifest.get("versions", {})),
                    "Artifact downloads": mo.vstack(_downloads)
                    if _downloads
                    else mo.md("No artifacts yet."),
                }
            ),
        ]
    )
    return


@app.cell
def _(Path, hashlib, manifest, mo):
    import difflib as learning_difflib

    _sources = manifest.get("learning_sources", {})
    _changes = []
    for _event in manifest.get("events", []):
        if _event.get("event") != "promoted_change_applied":
            continue
        _texts = []
        for _version in (_event.get("previous_version"), _event.get("version")):
            _record = _sources.get(_version, {})
            _file = Path(_record["path"]) if _record.get("path") else None
            _texts.append(
                _file.read_text()
                if _file
                and _file.is_file()
                and hashlib.sha256(_file.read_bytes()).hexdigest() == _record.get("sha256")
                else None
            )
        _diff = (
            "\n".join(
                learning_difflib.unified_diff(
                    _texts[0].splitlines(),
                    _texts[1].splitlines(),
                    fromfile="Before",
                    tofile="After",
                    lineterm="",
                )
            )
            if all(text is not None for text in _texts)
            else "Source snapshots unavailable for this historical change."
        )
        _changes.append(
            mo.vstack(
                [
                    mo.md(
                        f"**{_event.get('change_kind', 'Learning')}** · "
                        f"after attempt {_event.get('after_attempt', '—')}"
                    ),
                    mo.md("```diff\n" + _diff + "\n```"),
                ]
            )
        )
    mo.accordion(
        {"Learning changes applied in this run": mo.vstack(_changes)}
    ) if _changes else mo.md("")
    return


@app.cell
def _(Path, job_selector, manifest, mo, read_json, weave_link):
    _receipt_path = (
        Path(job_selector.value).parent / "run-receipt.json" if job_selector.value else None
    )
    _receipt, _ = (
        read_json(_receipt_path) if _receipt_path and _receipt_path.is_file() else ({}, None)
    )
    _project = _receipt.get("weave_project", "")
    _call = _receipt.get("weave_call_id", "")
    _recorded = _receipt.get("weave_recorded") is True
    _same_job = not _receipt.get("job_id") or _receipt.get("job_id") == manifest.get("job_id")
    _link = weave_link(f"weave:///{_project}/call/{_call}") if _project and _call else None
    mo.md(f"[Open this run in Weave]({_link})") if _recorded and _same_job and _link else mo.md("")
    return


@app.cell
def _(Path, events, html, mo, read_json, refresh, versions_root, weave_link):
    _refresh_tick = refresh.value
    _decisions = [
        event.get("result", {}) for event in events if event.get("event") == "promotion_evaluated"
    ]
    _evaluations = []
    _links = {}
    for _decision in _decisions:
        for _reference in _decision.get("evidence", []):
            _url = weave_link(_reference)
            if _url:
                _links[_url] = "Open recorded Weave evaluation"
            elif Path(_reference).is_file():
                _object, _error = read_json(_reference)
                if _object.get("kind") == "evaluation":
                    _evaluations.append(_object.get("content", {}))
    _production, _ = read_json(Path(versions_root.value).expanduser() / "production.json")
    mo.vstack(
        [
            mo.md("## Learning and evaluation"),
            mo.md(
                "Saved learning, later reuse and evaluation results are separate evidence. "
                "The historical four-part experiment saved changes directly; it did not use "
                "a Weave promotion gate. Replay evaluations below do not change that history."
            ),
            mo.ui.table(
                [
                    {
                        "Proposal": item.get("proposal_id"),
                        "Promoted": item.get("promoted"),
                        "Reason": item.get("reason"),
                    }
                    for item in _decisions
                ],
                selection=None,
            )
            if _decisions
            else mo.md("No reusable-change evaluation recorded in this run."),
            mo.vstack(
                [
                    mo.Html(
                        f'<a href="{html.escape(url, quote=True)}" target="_blank" '
                        f'rel="noopener noreferrer">{label}</a>'
                    )
                    for url, label in _links.items()
                ]
            ),
            mo.accordion(
                {
                    "Evaluation scores": mo.json(_evaluations),
                    "Production version history": mo.json(_production),
                    "Full event history": mo.json(events),
                }
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
