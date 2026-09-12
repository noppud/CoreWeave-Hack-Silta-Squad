"""Four native Marimo slides with fresh, deterministic CAD validation."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(
    width="full",
    app_title="SILTA CAD · Demo",
    layout_file="layouts/demo.slides.json",
    html_head_file="../silta/static/head.html",
)


@app.cell
async def _():
    import sys
    from pathlib import Path

    import marimo as mo

    _root = (mo.notebook_dir() or Path.cwd()).resolve().parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from silta import ui
    from silta.cad import mesh_arrays
    from silta.demo import prepare_demo
    from silta.fixtures import DEMO_SHOP, DEMO_SPEC
    from silta.presentation import public_demo_url
    from silta.viewer import PartViewer, build_scene

    demo = await prepare_demo()
    cold = demo["outcomes"]["cold"]
    warm = demo["outcomes"]["warm"]
    _mesh = mesh_arrays(cold.cad.mesh_path)

    def render_part(attempt, outcome, target=False):
        scene = build_scene(
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            mesh=_mesh,
            trajectory=outcome.trajectories.get(attempt.attempt_id),
            simulation_replay=outcome.replays.get(attempt.attempt_id),
            simulation_result=attempt.simulation,
        )
        widget = PartViewer(scene=scene)
        widget.view_mode = "target" if target else "all"
        return mo.ui.anywidget(widget)

    def title(number, heading, caption):
        return mo.Html(
            ui.THEME
            + ui.brand()
            + f'<div class="sx-story"><span class="sx-k">{number} / 4</span><h2>{heading}</h2><p>{caption}</p></div>'
        )

    scope = mo.Html(
        '<div class="sx-scope">Scripted plans · Fresh geometric checks and simulation · No machine-ready G-code</div>'
    )
    return cold, demo, mo, public_demo_url, render_part, scope, title, ui, warm


@app.cell
def _(cold, mo, render_part, scope, title):
    mo.vstack(
        [
            title(
                1,
                "The part stays fixed.",
                "80 × 60 × 20 mm aluminium block. Five features. Three available tools.",
            ),
            render_part(cold.best_attempt, cold, target=True),
            scope,
        ]
    )
    return


@app.cell
def _(cold, mo, render_part, scope, title):
    _collision = next(a for a in cold.attempts if a.simulation and a.simulation.collisions)
    mo.vstack(
        [
            title(
                2,
                "Catch the failed plan.",
                "The short tool cannot reach. A longer tool reaches, but its low traverse hits the clamp.",
            ),
            render_part(_collision, cold),
            scope,
        ]
    )
    return


@app.cell
def _(cold, mo, render_part, scope, title):
    _best = cold.best_attempt
    mo.vstack(
        [
            title(
                3,
                "Repair the process.",
                f"Clearance: {_best.plan.clearance_mm:g} mm. {len(_best.checks)} checks evaluated. Design unchanged.",
            ),
            render_part(_best, cold),
            scope,
        ]
    )
    return


@app.cell
def _(demo, mo, public_demo_url, scope, title, ui, warm):
    _reused = any(a.plan_source == "memory_recipe" for a in warm.attempts)
    _caption = (
        "The stored plan was reused, then checked and simulated again."
        if _reused
        else "No stored plan was reused in this run. The planner produced a freshly checked plan."
    )
    _rows = "".join(
        "<tr>" + "".join(f"<td>{v}</td>" for v in row.values()) + "</tr>"
        for row in demo["comparison"]
    )
    _table = (
        '<table class="sx-table"><thead><tr><th>Run</th><th>Attempts</th><th>Planner calls</th><th>Simulations</th></tr></thead><tbody>'
        + _rows
        + "</tbody></table>"
    )
    mo.vstack(
        [
            title(4, "The next run.", _caption),
            mo.Html(_table + ui.check_summary(warm.best_attempt)),
            mo.md(
                "Stored advice remains pending until validation passes. These counts come from this scripted demonstration."
            ),
            mo.md(
                f"[Explore SILTA CAD]({public_demo_url()}) · [W&B project](https://wandb.ai/silta/coreweave-hack-silta-squad)"
            ),
            scope,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
