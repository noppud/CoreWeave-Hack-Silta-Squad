"""SILTA CAD workbench. Run with marimo run notebooks/workbench.py."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="SILTA CAD", html_head_file="../silta/static/head.html")


@app.cell
def _():
    import sys
    import time
    from pathlib import Path

    import marimo as mo

    _root = (mo.notebook_dir() or Path.cwd()).resolve().parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from silta import presentation, ui
    from silta.cad import mesh_arrays
    from silta.domain import Budget
    from silta.fixtures import DEMO_SHOP, naive_plan
    from silta.policy import POLICIES, get_policy
    from silta.service import RunRequest, default_service
    from silta.storage import setup_sheet_markdown
    from silta.viewer import PartViewer, build_scene

    service = default_service()
    session_id = service.new_session_id()
    planner_label = (
        service.provider.config.model
        if service.provider
        else "Deterministic example · no live inference"
    )
    return (
        Budget,
        DEMO_SHOP,
        POLICIES,
        PartViewer,
        Path,
        RunRequest,
        build_scene,
        get_policy,
        mesh_arrays,
        mo,
        naive_plan,
        planner_label,
        presentation,
        service,
        session_id,
        setup_sheet_markdown,
        time,
        ui,
    )


@app.cell
def _(mo, planner_label, service, session_id, ui):
    mo.Html(ui.masthead(session_id, planner_label, service.commit))
    return


@app.cell
def _(mo):
    experience = mo.ui.radio(["Explore", "Present"], value="Explore", inline=True, label="View")
    experience
    return (experience,)


@app.cell
def _(POLICIES, mo):
    # Only submitting this form starts a run; editing a field does not.
    settings = (
        mo.md("{seed}\n\n{memory}\n\n{policy}\n\n{attempts}\n\n{deadline}")
        .batch(
            **{
                "policy": mo.ui.dropdown(list(POLICIES), value="policy-v0", label="Check policy"),
                "seed": mo.ui.dropdown(
                    {"Example with a short tool": "naive", "Plan from scratch": "scratch"},
                    value="Example with a short tool",
                    label="Starting plan",
                ),
                "attempts": mo.ui.slider(1, 4, value=3, label="Attempt limit", show_value=True),
                "deadline": mo.ui.slider(
                    30, 300, step=30, value=120, label="Time limit (seconds)", show_value=True
                ),
                "memory": mo.ui.checkbox(value=False, label="Reuse a previously checked plan"),
            }
        )
        .form(submit_button_label="Run plan", show_clear_button=False)
    )
    return (settings,)


@app.cell
def _(experience, mo, settings):
    mo.stop(experience.value != "Explore")
    mo.accordion({"Run settings": settings})
    return


@app.cell
async def _(Budget, DEMO_SHOP, RunRequest, mo, naive_plan, service, session_id, settings, time):
    _s = settings.value or {
        "policy": "policy-v0",
        "seed": "naive",
        "attempts": 3,
        "deadline": 120,
        "memory": False,
    }
    _proposal = await service.propose_spec(
        session_id=session_id, message="Demonstration fixture block.", use_example=True
    )
    spec = service.confirm_spec(
        session_id=session_id,
        proposal_id=_proposal.proposal_id,
        edits={},
        expected_revision=_proposal.revision,
    )
    _request = RunRequest(
        session_id=session_id,
        spec=spec,
        shop=DEMO_SHOP,
        policy_version=_s["policy"],
        seed_plan=naive_plan() if _s["seed"] == "naive" else None,
        budget=Budget(max_attempts=int(_s["attempts"]), job_deadline_s=float(_s["deadline"])),
        origin="live",
        idempotency_key=f"demo-{time.time_ns()}",
        memory_enabled=_s["memory"],
        expected_spec_revision=spec.revision,
    )
    _clock = time.perf_counter()
    _events = []
    with mo.status.spinner(title="Preparing the example plan…") as _spinner:
        async for _event in service.run_job(_request):
            _events.append(_event)
            if _event.type == "state_changed":
                _spinner.update(title=_event.payload["state"].replace("_", " ").capitalize() + "…")
    _job_id = _events[0].job_id if _events else None
    outcome = service.controller.outcomes.get(_job_id)
    run = {
        "job_id": _job_id,
        "outcome": outcome,
        "wall": time.perf_counter() - _clock,
        "events": _events,
        "spec": spec,
        "policy": _s["policy"],
    }
    return outcome, run, spec


@app.cell
def _(mo, outcome, run, ui):
    mo.stop(
        outcome is None, mo.md("The run did not return a result. Open Run settings to try again.")
    )
    mo.Html(
        ui.run_readout(
            outcome.state,
            len(outcome.attempts),
            run["wall"],
            sum(a.simulation is not None for a in outcome.attempts),
        )
    )
    return


@app.cell
def _(mo, outcome):
    _attempts = outcome.attempts if outcome else []
    _labels = {
        f"{'Initial plan' if a.index == 0 else 'Revision ' + str(a.index)} · {a.disposition.value.replace('_', ' ')}": a.attempt_id
        for a in _attempts
    }
    _best = outcome.best_attempt if outcome else None
    attempt_select = mo.ui.dropdown(
        _labels or {"No plan": None},
        value=next(
            (k for k, v in _labels.items() if _best and v == _best.attempt_id),
            next(iter(_labels), None),
        ),
        label="Plan",
    )
    camera_select = mo.ui.dropdown(
        {"Isometric": "isometric", "Top": "top", "Front": "front", "Side": "side"},
        value="Isometric",
        label="Camera",
    )
    display_select = mo.ui.radio(
        {"Compare": "all", "Target": "target", "Machined stock": "stock"},
        value="Compare",
        inline=True,
        label="Geometry",
    )
    return attempt_select, camera_select, display_select


@app.cell
def _(attempt_select, camera_select, display_select, experience, mo):
    mo.stop(experience.value != "Explore")
    mo.hstack(
        [
            attempt_select,
            mo.accordion({"View options": mo.vstack([camera_select, display_select])}),
        ],
        justify="space-between",
        wrap=True,
    )
    return


@app.cell
def _(DEMO_SHOP, PartViewer, attempt_select, build_scene, mesh_arrays, mo, outcome, spec):
    selected = (
        next((a for a in outcome.attempts if a.attempt_id == attempt_select.value), None)
        if outcome
        else None
    )
    _scene = build_scene(
        spec=spec,
        shop=DEMO_SHOP,
        mesh=mesh_arrays(outcome.cad.mesh_path) if outcome and outcome.cad else None,
        trajectory=outcome.trajectories.get(selected.attempt_id) if selected else None,
        simulation_replay=outcome.replays.get(selected.attempt_id) if selected else None,
        simulation_result=selected.simulation if selected else None,
    )
    cad_widget = PartViewer(scene=_scene)
    viewer = mo.ui.anywidget(cad_widget)
    return cad_widget, selected, viewer


@app.cell
def _(cad_widget, camera_select, display_select):
    cad_widget.set_camera(camera_select.value)
    cad_widget.view_mode = display_select.value
    return


@app.cell
def _(experience, mo, outcome, ui, viewer):
    mo.stop(experience.value != "Explore" or outcome is None)
    mo.vstack(
        [
            viewer,
            mo.Html(
                '<div class="sx-scope">Drag to rotate · Scroll to zoom · Geometric replay</div>'
            ),
            mo.Html(ui.section("Plan history") + ui.loop_strip(outcome.attempts)),
        ]
    )
    return


@app.cell
def _(DEMO_SHOP, PartViewer, build_scene, experience, mesh_arrays, mo, outcome, spec, ui):
    mo.stop(experience.value != "Present" or outcome is None)
    _mesh = mesh_arrays(outcome.cad.mesh_path) if outcome.cad else None

    def _view(attempt, target=False):
        scene = build_scene(
            spec=spec,
            shop=DEMO_SHOP,
            mesh=_mesh,
            trajectory=outcome.trajectories.get(attempt.attempt_id) if attempt else None,
            simulation_replay=outcome.replays.get(attempt.attempt_id) if attempt else None,
            simulation_result=attempt.simulation if attempt else None,
        )
        widget = PartViewer(scene=scene)
        widget.view_mode = "target" if target else "all"
        return mo.ui.anywidget(widget)

    _failed = next((a for a in outcome.attempts if a.blocking_failures), None)
    _best = outcome.best_attempt
    _reason = _failed.blocking_failures[0].message if _failed else "This run had no rejected plan."
    _slides = [
        mo.vstack(
            [
                mo.md("## The part\nThe target stays fixed while the machining plan changes."),
                _view(_best, True),
            ]
        ),
        mo.vstack([mo.md("## The problem"), mo.plain_text(_reason), _view(_failed)]),
        mo.vstack(
            [
                mo.md("## The repair"),
                mo.Html(ui.attempt_card(_best, True))
                if _best
                else mo.md("No plan passed the prototype checks."),
                _view(_best),
            ]
        ),
        mo.vstack(
            [
                mo.md("## The result"),
                mo.Html(ui.design_guard(spec, list(outcome.attempts))),
                mo.Html(ui.check_summary(_best))
                if _best
                else mo.md("Review required. No passing plan to export."),
                mo.md(
                    "Open Check details below for measurements and downloads. Learning evidence is available under Learning."
                ),
            ]
        ),
    ]
    mo.carousel(_slides)
    return


@app.cell
def _(
    DEMO_SHOP, Path, mo, outcome, run, selected, service, session_id, setup_sheet_markdown, spec, ui
):
    mo.stop(outcome is None)
    _details = {}
    if selected:
        _details["Check details"] = mo.Html(
            ui.check_summary(selected)
            + '<div class="sx-table-wrap">'
            + ui.check_ledger(selected)
            + "</div>"
            + ui.design_guard(spec, list(outcome.attempts))
        )
        if selected.plan:
            _details["Plan JSON"] = mo.json(selected.plan.model_dump(mode="json"))
    _details["Part and tools"] = mo.Html(ui.spec_panel(spec, DEMO_SHOP))
    _downloads = []
    if selected:
        try:
            _manifest = service.load_run(session_id, run["job_id"])
            _package = service.export_package(session_id, run["job_id"], selected.attempt_id)
            _downloads.append(
                mo.download(
                    data=_package,
                    filename=f"silta-{run['job_id']}-{selected.attempt_id}.zip",
                    mimetype="application/zip",
                    label="Download plan package",
                )
            )
            _details["Setup sheet"] = mo.md(setup_sheet_markdown(_manifest, selected))
        except Exception as _exc:
            _downloads.append(mo.md("Plan export unavailable: " + type(_exc).__name__))
    if outcome.cad and Path(outcome.cad.step_path).exists():
        _downloads.append(
            mo.download(
                data=Path(outcome.cad.step_path).read_bytes(),
                filename="target.step",
                mimetype="application/step",
                label="Download CAD (.step)",
            )
        )
    mo.vstack([mo.hstack(_downloads, justify="start", wrap=True), mo.accordion(_details)])
    return


@app.cell
def _(mo):
    validate_advice = mo.ui.run_button(label="Validate pending advice")
    return (validate_advice,)


@app.cell
def _(DEMO_SHOP, get_policy, mo, run, service, session_id, validate_advice):
    try:
        _snapshot = service.memory.inspect(
            session_id, run["spec"], DEMO_SHOP, get_policy(run["policy"])
        )
    except Exception as _exc:
        mo.stop(True, mo.md("Learning history unavailable: " + type(_exc).__name__))
    _reads = [e.payload for e in run["events"] if e.type == "memory_read"]
    _used = bool(_reads and _reads[0].get("recipe_episode_id"))
    _items = [
        mo.md(
            "**Used in this run:** "
            + (
                "A stored plan was reused and checked again."
                if _used
                else "No stored plan was reused. Enable reuse in Run settings for the next run."
            )
        )
    ]
    for _lesson in _snapshot.get("lessons", []):
        _items.append(
            mo.plain_text(_lesson.get("instruction", "") + " · " + _lesson.get("status", "pending"))
        )
    _reports = _snapshot.get("validations", [])
    if _reports:
        _items.append(
            mo.plain_text("Latest advice validation: " + _reports[-1].get("status", "unknown"))
        )
    _items.extend(
        [
            mo.md(
                "Advice needs validation before use. Reused plans always receive fresh checks and simulation."
            ),
            validate_advice,
            mo.accordion({"Learning records": mo.json(_snapshot)}),
        ]
    )
    mo.accordion({"Learning": mo.vstack(_items)})
    return


@app.cell
async def _(DEMO_SHOP, get_policy, mo, run, service, session_id, validate_advice):
    import asyncio

    from silta.learning_sandbox import WandbLessonValidator

    mo.stop(not validate_advice.value)
    try:
        with mo.status.spinner(title="Validating advice…"):
            _reports = await asyncio.to_thread(
                service.memory.validate,
                session_id,
                run["spec"],
                DEMO_SHOP,
                get_policy(run["policy"]),
                WandbLessonValidator(),
            )
        mo.output.append(
            mo.accordion(
                {
                    "Advice validation result": mo.json(_reports)
                    if _reports
                    else mo.md("No pending supported advice.")
                }
            )
        )
    except Exception as _exc:
        mo.output.append(
            mo.md("Advice validation unavailable. Advice remains pending. " + type(_exc).__name__)
        )
    return


@app.cell
def _(mo, planner_label, presentation, run, service, session_id, ui):
    mo.vstack(
        [
            mo.accordion(
                {
                    "Run details": mo.json(
                        {
                            "session": session_id,
                            "job": run["job_id"],
                            "planner": planner_label,
                            "build": service.commit,
                            "policy": run["policy"],
                            "simulator": "2.5D heightfield · 0.5 mm grid",
                        }
                    ),
                    "Event log": mo.json([e.model_dump(mode="json") for e in run["events"]]),
                    "Share demo": mo.Html(presentation.share_panel()),
                    "Scope and limitations": mo.Html(ui.LIMITATIONS),
                }
            ),
            mo.Html(
                '<div class="sx-scope">Synthetic example · Geometric simulation · No machine-ready G-code</div>'
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
