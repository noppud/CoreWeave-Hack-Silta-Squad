"""Three-minute presenter notebook. Run with make present."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Silta CNC · 3 minute demo")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo

    _repo = (mo.notebook_dir() or Path.cwd()).resolve().parent
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    from silta import ui
    from silta.cad import mesh_arrays
    from silta.demo import prepare_demo
    from silta.fixtures import DEMO_SHOP, DEMO_SPEC
    from silta.loop_diagram import LOOP_DIAGRAM
    from silta.presentation import share_panel
    from silta.viewer import PartViewer, build_scene

    return (
        DEMO_SHOP,
        DEMO_SPEC,
        LOOP_DIAGRAM,
        PartViewer,
        build_scene,
        mesh_arrays,
        mo,
        prepare_demo,
        share_panel,
        ui,
    )


@app.cell
def _(mo, share_panel, ui):
    mo.vstack(
        [
            mo.Html(
                ui.THEME
                + '<h1 style="font-size:32px;margin-bottom:12px">Silta CNC</h1><p class="sx-note">Presenter fixture: scripted candidate plans, real CAD, deterministic checks, fresh simulation and disk-backed memory. The live workbench also supports model inference.</p>'
            ),
            mo.accordion({"Try the live product · QR": mo.Html(share_panel())}),
        ]
    )
    return


@app.cell
async def _(mo, prepare_demo):
    with mo.status.spinner(title="Preparing the real cold and warm runs…"):
        demo = await prepare_demo()
    return (demo,)


@app.cell
def _(mo):
    stage = mo.ui.radio(
        ["1 · The part", "2 · The collision", "3 · The repair", "4 · Memory"],
        value="1 · The part",
        inline=True,
        label="Demo step",
    )
    stage
    return (stage,)


@app.cell
def _(demo, mo, stage, ui):
    _copy = {
        "1 · The part": (
            "The target stays fixed",
            "A drawing describes this part. The shop has a short tool, a longer tool and clamps. The agent can change the process. It cannot change the part.",
        ),
        "2 · The collision": (
            "A failed attempt becomes evidence",
            "The first tool cannot reach the pocket. A longer tool fixes reach, but its traverse hits the clamp. Play shows the actual collision trajectory.",
        ),
        "3 · The repair": (
            "The repaired process passes",
            "The next recipe raises the clearance. The same geometry checks and stock simulation now pass. The target design hash stays unchanged.",
        ),
        "4 · Memory": (
            "The next run remembers",
            "A new controller reads the recipe from disk. It needs one attempt and no planner call, then performs fresh checks and simulation. The stored failure lessons remain proposed until validation passes.",
        ),
    }
    _title, _body = _copy[stage.value]
    mo.Html('<div class="sx-story"><h2>' + _title + "</h2><p>" + _body + "</p></div>")
    return


@app.cell
def _(demo, mo, stage):
    mo.stop(stage.value != "4 · Memory")
    _rows = "".join(
        "<tr>"
        + "".join(f'<td style="font-size:26px;padding:14px">{value}</td>' for value in row.values())
        + "</tr>"
        for row in demo["comparison"]
    )
    mo.Html(
        '<table class="sx-table"><thead><tr>'
        + "".join(
            f'<th style="font-size:18px;padding:14px">{name}</th>' for name in demo["comparison"][0]
        )
        + "</tr></thead><tbody>"
        + _rows
        + "</tbody></table>"
    )
    return


@app.cell
def _(demo, stage):
    shown_run = demo["outcomes"]["warm" if stage.value == "4 · Memory" else "cold"]
    shown_attempt = (
        shown_run.attempts[1] if stage.value == "2 · The collision" else shown_run.best_attempt
    )
    return shown_attempt, shown_run


@app.cell
def _(
    DEMO_SHOP, DEMO_SPEC, PartViewer, build_scene, mesh_arrays, mo, shown_attempt, shown_run, stage
):
    _scene = build_scene(
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        mesh=mesh_arrays(shown_run.cad.mesh_path),
        trajectory=shown_run.trajectories.get(shown_attempt.attempt_id),
        simulation_replay=shown_run.replays.get(shown_attempt.attempt_id),
        simulation_result=shown_attempt.simulation,
    )
    _widget = PartViewer(
        scene=_scene, playhead=1.0 if stage.value in {"3 · The repair", "4 · Memory"} else 0.0
    )
    _widget.view_mode = "target" if stage.value == "1 · The part" else "all"
    _widget.set_camera("isometric")
    mo.ui.anywidget(_widget)
    return


@app.cell
def _(demo, mo, shown_attempt, stage, ui):
    mo.stop(stage.value == "1 · The part")
    _content = [
        mo.accordion({"Inspect the measured checks": mo.Html(ui.check_ledger(shown_attempt))})
    ]
    if stage.value == "4 · Memory":
        _content.append(
            mo.accordion(
                {
                    "Inspect stored memory": mo.json(demo["memory"]),
                    "Recipe and source episode": mo.json(shown_attempt.model_dump(mode="json")),
                }
            )
        )
    mo.vstack(_content)
    return


@app.cell
def _(LOOP_DIAGRAM, mo):
    mo.accordion(
        {
            "Where memory lives": mo.mermaid(LOOP_DIAGRAM, theme="neutral").style(
                {"background": "white", "padding": "16px"}
            )
        }
    )
    return


@app.cell
def _(mo):
    mo.Html(
        '<div class="sx-note"><a href="https://silta-cdswwreljq-uc.a.run.app">Live model workbench</a>'
        ' · <a href="https://wandb.ai/silta/coreweave-hack-silta-squad">W&amp;B project</a>'
        "<p>Geometric prototype only. Sandbox advice validation awaits working W&amp;B "
        "authentication. This presentation does not claim completed ARIA analysis.</p></div>"
    )
    return


if __name__ == "__main__":
    app.run()
