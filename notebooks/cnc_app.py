"""Read-only CNC run viewer. Run: marimo run notebooks/cnc_app.py.

Set SILTA_JOBS_DIR and SILTA_VERSIONS_DIR to change the artifact directories.
All metrics/media come from recorded manifests; no demo scores or motion are synthesized.
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Silta · CNC loop")


@app.cell
def _():
    import html
    import json
    import math
    import os
    from pathlib import Path

    import marimo as mo

    return Path, html, json, math, mo, os


@app.cell
def _(Path, html, json, math):
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
                    "Seconds": None,
                    "Estimated cost": None,
                    "Issues": "",
                },
            )
            if event.get("event") == "candidate_created":
                row["Candidate"] = event.get("candidate", {}).get("id", "—")
            elif event.get("event") == "checks_completed":
                result = event.get("result", {})
                row["Checks"] = "Passed" if result.get("passed") is True else "Failed"
                row["Issues"] = "; ".join(result.get("issues", []))
            elif event.get("event") == "verification_started":
                row["Verification"] = "Running"
            elif event.get("event") == "verification_completed":
                result = event.get("verification", {})
                passed = result.get("status") == "passed" and result.get("completed") is True
                row["Verification"] = (
                    "Passed" if passed else str(result.get("status", "unknown")).capitalize()
                )
                row["Issues"] = "; ".join(result.get("issues", []))
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
        return [attempts[key] for key in sorted(attempts)]

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

    return artifact_paths, attempt_rows, metric_chart, read_json, weave_link


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
    refresh = mo.ui.refresh(options=["5s", "15s", "1m"], default_interval="15s")
    mo.vstack(
        [
            mo.md("# Silta · From drawing to verified machining"),
            mo.md("Recorded runs, machine evidence and measured improvements."),
            mo.hstack([jobs_root, versions_root, refresh], align="end"),
        ]
    )
    return jobs_root, refresh, versions_root


@app.cell
def _(Path, jobs_root, mo):
    manifest_files = sorted(
        Path(jobs_root.value).expanduser().glob("*/manifest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    job_selector = mo.ui.dropdown(
        options={path.parent.name: str(path) for path in manifest_files},
        value=manifest_files[0].parent.name if manifest_files else None,
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
def _(attempt_rows, job_selector, mo, read_json, refresh):
    _refresh_tick = refresh.value
    manifest, load_error = read_json(job_selector.value) if job_selector.value else ({}, None)
    rows = attempt_rows(manifest)
    events = manifest.get("events", [])
    current_event = events[-1].get("event", "Waiting for a run") if events else "Waiting for a run"
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
    best = manifest.get("best_candidate") or {}
    best_verification = manifest.get("best_verification") or {}
    mo.vstack(
        [
            mo.callout(mo.md(f"Could not read this run: {load_error}"), kind="danger")
            if load_error
            else mo.md(""),
            mo.hstack(
                [
                    mo.stat(label="Run status", value=manifest.get("status", "Not started")),
                    mo.stat(label="Latest event", value=current_event.replace("_", " ")),
                    mo.stat(label="Current candidate", value=latest_candidate.get("id", "—")),
                    mo.stat(label="Best verified candidate", value=best.get("id", "None yet")),
                ]
            ),
            mo.md(str(manifest.get("reason", ""))),
        ]
    )
    return best, best_verification, events, latest_verification, manifest, rows


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
            mo.ui.table(rows, selection=None) if rows else mo.md("No machining attempts recorded."),
        ]
    )
    return


@app.cell
def _(Path, artifact_paths, html, latest_verification, mo):
    _media = [
        Path(path)
        for path in artifact_paths(latest_verification)
        if Path(path).suffix.lower() in {".mp4", ".webm", ".mov"} and Path(path).is_file()
    ]
    _screens = [
        Path(path)
        for path in artifact_paths(latest_verification)
        if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg"} and Path(path).is_file()
    ]
    mo.vstack(
        [
            mo.md("## Machine verification evidence"),
            mo.Html(
                "<p>Status: <strong>"
                + html.escape(str(latest_verification.get("status", "not run")))
                + f"</strong> · Completed: {latest_verification.get('completed') is True}</p>"
            ),
            mo.video(str(_media[-1]), controls=True, width="100%")
            if _media
            else mo.callout(
                mo.md(
                    "No machine recording is attached to this verification. "
                    "The application will display the actual Fusion recording when available."
                )
            ),
            mo.image(str(_screens[-1]), width="100%") if _screens else mo.md(""),
            mo.md(
                "\n".join(
                    f"- {html.escape(str(issue))}"
                    for issue in latest_verification.get("issues", [])
                )
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
                "Reusable changes are promoted only after the paired evaluation gate. "
                "This run retains its pinned versions."
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
