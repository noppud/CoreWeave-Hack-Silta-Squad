# /// script
# requires-python = ">=3.12"
# ///
"""Silta CNC workbench — a drawing becomes a checked, simulated machining plan.

Run it as an application:  marimo run notebooks/workbench.py

The demonstration job starts by itself when the page opens, so the loop is
already visible. Every engineering decision lives in `silta/`; this file only
arranges the result on screen.
"""

import marimo

__generated_with = "0.24.2"
# html_head_file carries the cyanotype theme into marimo's shadow-DOM widgets,
# which page CSS cannot reach. See silta/static/head.html.
app = marimo.App(
    width="full",
    app_title="Silta CNC",
    html_head_file="../silta/static/head.html",
)


@app.cell
def _():
    import sys
    import time
    from pathlib import Path

    import marimo as mo

    # marimo puts the notebook's own directory on sys.path, not the repository root,
    # so make `silta` importable whether this runs from a checkout, a container or molab.
    _repo_root = (mo.notebook_dir() or Path.cwd()).resolve().parent
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

    return Path, mo, time


@app.cell
def _():
    from silta import presentation, ui
    from silta.cad import mesh_arrays
    from silta.domain import Budget, JobState
    from silta.fixtures import DEMO_SHOP, naive_plan
    from silta.interpreter import clarification_message
    from silta.policy import POLICIES
    from silta.service import RunRequest, SiltaService, default_service
    from silta.storage import setup_sheet_markdown
    from silta.viewer import PartViewer, build_scene

    service: SiltaService = default_service()
    session_id = service.new_session_id()
    planner_label = (
        f"{service.provider.config.model} on W&B Inference"
        if service.provider is not None
        else "deterministic planner (no inference key configured)"
    )
    return (
        Budget,
        DEMO_SHOP,
        JobState,
        POLICIES,
        PartViewer,
        RunRequest,
        build_scene,
        clarification_message,
        mesh_arrays,
        naive_plan,
        planner_label,
        presentation,
        service,
        session_id,
        setup_sheet_markdown,
        ui,
    )


@app.cell
def _(mo, planner_label, service, session_id, ui):
    mo.Html(ui.masthead(session_id, planner_label, service.commit))
    return


@app.cell
def _(mo, presentation):
    experience_mode = mo.ui.radio(
        ["Inspect", "Story 1: the part", "Story 2: the repair"],
        value="Inspect",
        inline=True,
        label="Explore or present",
    )
    mo.vstack(
        [
            experience_mode,
            mo.accordion({"Open it on your phone": mo.Html(presentation.share_panel())}),
        ]
    )
    return (experience_mode,)


@app.cell
def _(mo):
    # One explicit control drives everything. It carries a counter, so the run cell
    # below fires once on load and once per press — never on an unrelated rerender.
    rerun = mo.ui.run_button(label="Run the loop again", kind="neutral")
    return (rerun,)


@app.cell
def _(mo):
    get_settings, set_settings = mo.state(
        # Learning memory starts OFF for the first automatic run. Once a passing recipe
        # exists for the public demo fixture, recall replays it on attempt 0, and the
        # failure-repair-pass sequence this app exists to show never happens: every
        # visitor after the first would see a single candidate and no loop. Turn it on
        # from the operator controls to demonstrate recall deliberately.
        {
            "policy": "policy-v0",
            "seed": "naive",
            "attempts": 3,
            "deadline": 120,
            "memory": False,
        }
    )
    return get_settings, set_settings


@app.cell
async def _(
    Budget,
    DEMO_SHOP,
    RunRequest,
    get_settings,
    mo,
    naive_plan,
    rerun,
    service,
    session_id,
    time,
):
    _settings = get_settings()
    _ = rerun.value  # explicit trigger; view controls are not dependencies

    # The demonstration drawing is read and its specification confirmed without a
    # click: the operator panel below can still edit and re-freeze it.
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
        policy_version=_settings["policy"],
        seed_plan=naive_plan() if _settings["seed"] == "naive" else None,
        budget=Budget(
            max_attempts=int(_settings["attempts"]),
            job_deadline_s=float(_settings["deadline"]),
        ),
        origin="live",
        idempotency_key=f"auto-{time.time_ns()}",
        memory_enabled=_settings.get("memory", True),
        expected_spec_revision=spec.revision,
    )
    _clock = time.perf_counter()
    _events = []
    with mo.status.spinner(title="Building the solid…") as _spinner:
        async for _event in service.run_job(_request):
            _events.append(_event)
            if _event.type == "state_changed":
                _spinner.update(title=_event.payload["state"].replace("_", " ") + "…")
    run = {
        "job_id": _events[0].job_id,
        "outcome": service.controller.outcomes.get(_events[0].job_id),
        "wall": time.perf_counter() - _clock,
        "events": _events,
        "spec": spec,
        "policy": _settings["policy"],
    }
    return run, spec


@app.cell
def _(experience_mode, mo, run, ui):
    mo.stop(experience_mode.value == "Story 1: the part")
    _outcome = run["outcome"]
    _sims = sum(1 for a in _outcome.attempts if a.simulation is not None)
    mo.Html(
        ui.section(
            "The loop",
            ("Policy", run["policy"]),
            ("Job", run["job_id"]),
        )
        + ui.run_readout(_outcome.state, len(_outcome.attempts), run["wall"], _sims)
        + ui.loop_strip(_outcome.attempts)
    )
    return


@app.cell
def _(mo):
    from silta.loop_diagram import LOOP_DIAGRAM

    mo.accordion(
        {
            "How the loop stores and reuses memory": mo.mermaid(
                LOOP_DIAGRAM, theme="neutral"
            ).style({"background": "#ffffff", "padding": "16px", "overflow": "auto"})
        }
    )
    return


@app.cell
def _(mo, run, service, session_id):
    from silta.fixtures import DEMO_SHOP as _memory_shop
    from silta.policy import get_policy as _memory_policy

    try:
        _snapshot = service.memory.inspect(
            session_id, run["spec"], _memory_shop, _memory_policy(run["policy"])
        )
    except Exception as _memory_error:
        mo.stop(True, mo.md("Memory inspection unavailable: " + type(_memory_error).__name__))
    _reads = [e for e in run["events"] if e.type == "memory_read"]
    _first = _reads[0].payload if _reads else {}
    _recipe = _first.get("recipe_episode_id")
    _message = (
        f"This run reused recipe `{_recipe}` and verified it again."
        if _recipe
        else "This run started without a recalled recipe. Run the loop again to use what it learned."
    )
    mo.accordion(
        {
            "Where the learned advice came from": mo.vstack(
                [
                    mo.md(
                        f"**{_snapshot['episode_count']} stored attempts** · {_snapshot['storage']} · "
                        f"scope: `{_snapshot['scope']}`. " + _message
                    ).style({"color": "var(--white, #13202e)"}),
                    mo.md(
                        "Failed attempts propose advice. W&B Sandbox validation enables supported advice; "
                        "verified recipes are reusable immediately with fresh checks and simulation. "
                        "The exact public demo shares memory. Other designs stay scoped to their session."
                    ).style({"color": "var(--white, #13202e)"}),
                    mo.json(_snapshot).style(
                        {
                            "background": "#f8fafc",
                            "color": "#13202e",
                            "padding": "14px",
                            "max-height": "420px",
                            "overflow": "auto",
                        }
                    ),
                ]
            )
        }
    )
    return


@app.cell
def _(mo):
    validate_memory_button = mo.ui.run_button(label="Validate learned advice in W&B Sandbox")
    validate_memory_button
    return (validate_memory_button,)


@app.cell
async def _(mo, run, service, session_id, validate_memory_button):
    import asyncio as _memory_asyncio

    from silta.fixtures import DEMO_SHOP as _validate_shop
    from silta.learning_sandbox import WandbLessonValidator as _LessonValidator
    from silta.policy import get_policy as _validate_policy

    mo.stop(not validate_memory_button.value)
    with mo.status.spinner(title="Validating the learned clearance advice in W&B Sandbox…"):
        _reports = await _memory_asyncio.to_thread(
            service.memory.validate,
            session_id,
            run["spec"],
            _validate_shop,
            _validate_policy(run["policy"]),
            _LessonValidator(),
        )
    mo.vstack(
        [
            mo.md(
                "Validation evidence is persisted. The next run reads passed advice; "
                "unavailable or failed validation leaves it pending."
            ),
            mo.json(_reports) if _reports else mo.md("No pending supported lesson to validate."),
        ]
    )
    return


@app.cell
def _(experience_mode, mo, presentation, run):
    mo.Html(presentation.story_card(experience_mode.value, run["outcome"], run["spec"]))
    return


@app.cell
def _(mo, run):
    _outcome = run["outcome"]
    _labels = {
        f"Attempt {a.index:02d} — {a.disposition.value.replace('_', ' ')}": a.attempt_id
        for a in _outcome.attempts
    }
    _best = _outcome.best_attempt or (_outcome.attempts[-1] if _outcome.attempts else None)
    attempt_select = mo.ui.dropdown(
        options=_labels or {"No attempts": None},
        value=next(
            (label for label, aid in _labels.items() if _best and aid == _best.attempt_id), None
        ),
        label="Inspect attempt",
    )
    camera_select = mo.ui.dropdown(
        options={"Isometric": "isometric", "Top": "top", "Front": "front", "Side": "side"},
        value="Isometric",
        label="Camera preset (Python)",
    )
    display_select = mo.ui.radio(
        {"Overlay": "all", "Target design": "target", "Machined stock": "stock"},
        value="Overlay",
        inline=True,
        label="Visible geometry",
    )
    mo.vstack(
        [attempt_select, mo.hstack([camera_select, display_select], justify="start", wrap=True)]
    )
    return attempt_select, camera_select, display_select


@app.cell
def _(attempt_select, run):
    selected_attempt = next(
        (a for a in run["outcome"].attempts if a.attempt_id == attempt_select.value), None
    )
    return (selected_attempt,)


@app.cell
def _(DEMO_SHOP, PartViewer, build_scene, mesh_arrays, mo, run, selected_attempt, ui):
    _outcome = run["outcome"]
    _shown = selected_attempt
    _scene = build_scene(
        spec=run["spec"],
        shop=DEMO_SHOP,
        mesh=mesh_arrays(_outcome.cad.mesh_path) if _outcome.cad else None,
        trajectory=_outcome.trajectories.get(_shown.attempt_id) if _shown else None,
        simulation_replay=_outcome.replays.get(_shown.attempt_id) if _shown else None,
        simulation_result=_shown.simulation if _shown else None,
    )
    cad_widget = PartViewer(scene=_scene)
    viewer = mo.ui.anywidget(cad_widget)
    _facts = (
        (
            ("Showing attempt", f"{_shown.index:02d}"),
            ("Outcome", ui.sentence(_shown.disposition.value)),
        )
        if _shown
        else (("Showing attempt", "none"),)
    )
    mo.vstack(
        [
            mo.Html(ui.section("Interactive CAD", *_facts)),
            viewer,
            mo.md(
                "Drag to rotate, scroll to zoom. Focus the model to steer it with the arrow keys, and press R to reset the view. Playback is a geometric replay, not measured machining speed."
            ),
        ]
    )
    return cad_widget, viewer


@app.cell
def _(cad_widget, camera_select):
    cad_widget.set_camera(camera_select.value)
    return


@app.cell
def _(cad_widget, display_select):
    cad_widget.view_mode = display_select.value
    return


@app.cell
def _(experience_mode, mo, run, selected_attempt, ui):
    mo.stop(experience_mode.value == "Story 1: the part")
    _shown = selected_attempt
    mo.output.append(
        mo.Html(
            ui.section(
                "Evidence ledger",
                *(
                    (
                        ("Attempt", f"{_shown.index:02d}"),
                        ("Checks evaluated", str(len(_shown.checks))),
                    )
                    if _shown
                    else ()
                ),
            )
            + (ui.check_ledger(_shown) if _shown else "")
            + "<div style='height:14px'></div>"
            + ui.design_guard(run["spec"], list(run["outcome"].attempts))
        )
    )
    if _shown and _shown.plan:
        mo.output.append(
            mo.accordion(
                {
                    "Inspect this machining recipe (JSON)": mo.json(
                        _shown.plan.model_dump(mode="json")
                    )
                }
            )
        )
    return


@app.cell
def _(DEMO_SHOP, experience_mode, mo, run, ui):
    mo.stop(experience_mode.value == "Story 2: the repair")
    mo.Html(
        ui.section("Confirmed specification", ("Status", "frozen before planning"))
        + ui.spec_panel(run["spec"], DEMO_SHOP)
    )
    return


@app.cell
def _(
    Path, experience_mode, mo, run, selected_attempt, service, session_id, setup_sheet_markdown, ui
):
    mo.stop(experience_mode.value == "Story 1: the part")
    _outcome = run["outcome"]
    _shown = selected_attempt
    _items = [mo.Html(ui.section("Artifacts", ("Integrity", "hash-verified")))]
    try:
        _manifest = service.load_run(session_id, run["job_id"])
        _package = service.export_package(session_id, run["job_id"], _shown.attempt_id)
        _items.append(
            mo.download(
                data=_package,
                filename=f"silta-{run['job_id']}-{_shown.attempt_id}.zip",
                mimetype="application/zip",
                label="Download the artifact package",
            )
        )
        _items.append(mo.accordion({"Setup sheet": mo.md(setup_sheet_markdown(_manifest, _shown))}))
    except Exception as _exc:
        _items.append(
            mo.Html(
                f'<div class="sx-note" style="border-left-color:var(--hold)">'
                f"<b>Export unavailable.</b> {_exc}</div>"
            )
        )
    if _outcome.cad is not None and Path(_outcome.cad.step_path).exists():
        _items.append(
            mo.download(
                data=Path(_outcome.cad.step_path).read_bytes(),
                filename="target.step",
                mimetype="application/step",
                label="Download the target STEP",
            )
        )
    mo.vstack(_items)
    return


@app.cell
def _(POLICIES, experience_mode, get_settings, mo, rerun, ui):
    _s = get_settings()
    policy_select = mo.ui.dropdown(options=list(POLICIES), value=_s["policy"], label="Policy")
    seed_select = mo.ui.dropdown(
        options={
            "Naive shop recipe (short tool, low traverse)": "naive",
            "Plan from scratch": "scratch",
        },
        value="Naive shop recipe (short tool, low traverse)"
        if _s["seed"] == "naive"
        else "Plan from scratch",
        label="Starting point",
    )
    attempts_slider = mo.ui.slider(
        start=1, stop=4, value=int(_s["attempts"]), label="Maximum candidates", show_value=True
    )
    deadline_slider = mo.ui.slider(
        start=30,
        stop=300,
        step=30,
        value=int(_s["deadline"]),
        label="Deadline (s)",
        show_value=True,
    )
    memory_toggle = mo.ui.checkbox(value=_s.get("memory", True), label="Use learning memory")
    apply_button = mo.ui.run_button(label="Apply and re-run", kind="success")
    _panel = mo.vstack(
        [
            mo.Html(ui.section("Operator controls", ("The loop above", "ran on these defaults"))),
            mo.hstack([policy_select, seed_select], justify="start", gap=1.5),
            mo.hstack([attempts_slider, deadline_slider], justify="start", gap=1.5),
            memory_toggle,
            mo.hstack([apply_button, rerun], justify="start", gap=1),
        ]
    )
    _panel if experience_mode.value == "Inspect" else mo.md("")
    return (
        apply_button,
        memory_toggle,
        attempts_slider,
        deadline_slider,
        policy_select,
        seed_select,
    )


@app.cell
def _(
    apply_button,
    attempts_slider,
    deadline_slider,
    mo,
    memory_toggle,
    policy_select,
    seed_select,
    set_settings,
):
    mo.stop(not apply_button.value, mo.md(""))
    set_settings(
        {
            "policy": policy_select.value,
            "seed": seed_select.value,
            "attempts": attempts_slider.value,
            "deadline": deadline_slider.value,
            "memory": memory_toggle.value,
        }
    )
    return


@app.cell
def _(experience_mode, mo, run, ui):
    mo.stop(experience_mode.value != "Inspect")
    _rows = "".join(
        f"<tr><td>{e.sequence}</td><td><span class='sx-mono'>{e.type}</span></td>"
        f"<td>{str(e.payload)[:160]}</td></tr>"
        for e in run["events"]
    )
    mo.accordion(
        {
            f"Persisted event log, {len(run['events'])} events": mo.Html(
                "<table class='sx-table'><thead><tr><th>#</th><th>Type</th>"
                f"<th>Payload</th></tr></thead><tbody>{_rows}</tbody></table>"
            )
        }
    )
    return


@app.cell
def _(mo):
    import inspect

    from silta.cad import build_solid
    from silta.toolpaths import estimated_seconds
    from silta.viewer import PartViewer as _ViewerSource

    mo.accordion(
        {
            "How the controls reach Python": mo.vstack(
                [
                    mo.md(
                        "Python supplies geometry and camera preset commands. Your browser rotates and animates locally, without sending the scene back to Python. Changing a view never calls the planner."
                    ),
                    mo.md("```python\n" + inspect.getsource(_ViewerSource.set_camera) + "\n```"),
                    mo.md("```python\n" + inspect.getsource(build_solid) + "\n```"),
                    mo.md("```python\n" + inspect.getsource(estimated_seconds) + "\n```"),
                    mo.md(
                        "[Inspect the repository](https://github.com/noppud/CoreWeave-Hack-Silta-Squad). The downloadable package contains the actual plan and validation evidence."
                    ),
                ]
            )
        }
    )
    return


@app.cell
def _(mo, ui):
    mo.Html("<div style='height:26px'></div>" + ui.LIMITATIONS)
    return


if __name__ == "__main__":
    app.run()
