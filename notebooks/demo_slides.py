"""Seven interactive SILTA CAD slides using Joel's product identity."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(
    width="full",
    app_title="Silta CNC · Interactive slides",
    layout_file="layouts/demo_slides.slides.json",
    html_head_file="../silta/static/demo-slides-head.html",
)


@app.cell
def _():
    import json
    import os
    import sys
    from pathlib import Path

    import marimo as mo

    repo = (mo.notebook_dir() or Path.cwd()).resolve().parent
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from silta import ui
    from silta.cad import mesh_arrays
    from silta.demo import prepare_demo
    from silta.fixtures import DEMO_SHOP, DEMO_SPEC
    from silta.presentation import public_demo_url, qr_svg
    from silta.viewer import PartViewer, build_scene

    class SlideViewer(PartViewer):
        _css = (
            (repo / "silta/static/viewer.css").read_text()
            + """
        .silta-viewer{height:350px;border:0}
        .silta-viewer .silta-viewer-controls{
          width:200px;left:auto;right:14px;top:14px;bottom:auto;padding:12px;gap:6px}
        .silta-viewer .silta-viewer-top-controls{flex-wrap:wrap;gap:6px}
        .silta-viewer .silta-viewer-readout{flex-direction:column;gap:4px}
        .silta-viewer .silta-viewer-playback{flex-wrap:wrap}
        .silta-viewer .silta-viewer-collision-banner{position:static;padding:8px}
        """
        )

    class TargetViewer(SlideViewer):
        _css = SlideViewer._css + ".silta-viewer .silta-viewer-controls{display:none}"

    class HeroViewer(TargetViewer):
        _css = TargetViewer._css + ".silta-viewer{height:440px}"

    links = {
        "evals": "/presentation/evals.html"
        if os.getenv("SILTA_HOSTED")
        else "http://localhost:8010/evals.html",
        "guide": "/presentation/guide.html"
        if os.getenv("SILTA_HOSTED")
        else "http://localhost:8010/guide.html",
        "demo": "/demo/" if os.getenv("SILTA_HOSTED") else "http://localhost:2732/",
    }

    def cad_slide(outcome, attempt, *, target=False, finished=False, hero=False):
        viewer_class = HeroViewer if hero else TargetViewer if target else SlideViewer
        widget = viewer_class(
            scene=build_scene(
                spec=DEMO_SPEC,
                shop=DEMO_SHOP,
                mesh=mesh_arrays(outcome.cad.mesh_path),
                trajectory=None if target else outcome.trajectories.get(attempt.attempt_id),
                simulation_replay=None if target else outcome.replays.get(attempt.attempt_id),
                simulation_result=None if target else attempt.simulation,
            ),
            playhead=1.0 if finished else 0.0,
        )
        widget.view_mode = "target" if target else "all"
        widget.set_camera("isometric")
        return mo.ui.anywidget(widget)

    def title(kicker, headline, description=""):
        return mo.Html(
            f'<div class="deck-title"><div class="deck-eyebrow">{kicker}</div>'
            f"<h2>{headline}</h2><p>{description}</p></div>"
        )

    def frame(number, content, note):
        return mo.vstack(
            [
                mo.Html(
                    "<style>" + (repo / "silta/static/product.css").read_text() + "</style>"
                    '<div class="deck-header">'
                    + ui.brand()
                    + '<span class="deck-edition">COREWEAVE HACKS / 2026</span></div>'
                ),
                content,
                mo.Html(
                    f'<div class="deck-footer"><span>{note}</span>'
                    f'<span class="deck-page">{number:02d} / 07</span></div>'
                ),
            ],
            gap=0,
        ).style({"height": "620px", "justify-content": "space-between"})

    return cad_slide, frame, json, links, mo, prepare_demo, public_demo_url, qr_svg, repo, title


@app.cell
async def _(prepare_demo):
    demo = await prepare_demo()
    return (demo,)


@app.cell
def _(json, repo):
    eval_snapshot = json.loads((repo / "demo/evals.json").read_text())
    return (eval_snapshot,)


@app.cell(hide_code=True)
def _(cad_slide, demo, frame, mo):
    _cold = demo["outcomes"]["cold"]
    frame(
        1,
        mo.hstack(
            [
                mo.Html(
                    '<div class="deck-hero-copy"><div class="deck-eyebrow">DRAWING → MACHINING PLAN</div>'
                    "<h2>Same part.<br>Better plan.</h2>"
                    "<p>A machining planner that checks its work.<br>And remembers the repair.</p>"
                    '<div class="deck-red-rule"></div>'
                    '<span class="deck-small">Inspect. Simulate. Repair. Remember.</span></div>'
                ),
                mo.vstack(
                    [
                        cad_slide(_cold, _cold.best_attempt, target=True, hero=True),
                        mo.Html(
                            '<div class="deck-caption"><span>01 / FIXTURE BLOCK</span><span>LIVE CAD · DRAG TO ROTATE</span></div>'
                        ),
                    ],
                    gap=0,
                ),
            ],
            widths=[2, 3],
            align="center",
            gap=2,
        ),
        "Scripted proposals · Real CAD, checks, simulation and memory",
    )
    return


@app.cell(hide_code=True)
def _(cad_slide, demo, frame, mo, repo, title):
    _cold = demo["outcomes"]["cold"]
    frame(
        2,
        mo.vstack(
            [
                title("01 / THE INPUT", "Fix the target. Change the process."),
                mo.hstack(
                    [
                        mo.vstack(
                            [
                                mo.Html('<div class="deck-eyebrow">DIMENSIONED DRAWING</div>'),
                                mo.image(
                                    repo / "fixtures/demo/fixture-block-01.png",
                                    width=390,
                                    height=280,
                                ),
                                mo.Html(
                                    '<div class="deck-spec"><strong>80 × 60 × 20</strong><span>mm · aluminium stock</span></div>'
                                ),
                            ],
                            gap=1,
                        ),
                        mo.vstack(
                            [
                                cad_slide(_cold, _cold.best_attempt, target=True),
                                mo.Html(
                                    '<div class="deck-caption"><span>FIXED CAD TARGET</span><span>5 FEATURES / 3 TOOLS</span></div>'
                                ),
                            ],
                            gap=0,
                        ),
                    ],
                    widths=[2, 3],
                    gap=2,
                ),
            ],
            gap=1,
        ),
        "The drawing defines the part. Available tools and fixtures constrain the plan.",
    )
    return


@app.cell(hide_code=True)
def _(cad_slide, demo, frame, mo, title):
    _cold = demo["outcomes"]["cold"]
    _collision = next(a for a in _cold.attempts if a.simulation and a.simulation.collisions)
    frame(
        3,
        mo.vstack(
            [
                title("02 / MEASURE THE FAILURE", "Reach is fixed. Clearance isn't."),
                cad_slide(_cold, _collision),
                mo.Html(
                    '<div class="deck-caption"><span class="deck-alert">COLLISION / FRONT CLAMP</span><span>PRESS PLAY → REPLAY STOPS AT CONTACT</span></div>'
                ),
            ],
            gap=1,
        ),
        "Attempt 1: tool too short. Attempt 2: longer tool reaches, but its traverse hits a clamp.",
    )
    return


@app.cell(hide_code=True)
def _(cad_slide, demo, frame, mo, title):
    _cold = demo["outcomes"]["cold"]
    _best = _cold.best_attempt
    frame(
        4,
        mo.vstack(
            [
                title("03 / REPAIR & RECHECK", "A safer traverse. The same part."),
                cad_slide(_cold, _best, finished=True),
                mo.Html(
                    f'<div class="deck-caption"><span class="deck-pass">PROTOTYPE CHECKS PASSED</span><span>CLEARANCE → {_best.plan.clearance_mm:g} MM / DESIGN UNCHANGED</span></div>'
                ),
            ],
            gap=1,
        ),
        "The revised CAM plan passes fresh checks and a new geometric simulation.",
    )
    return


@app.cell(hide_code=True)
def _(demo, frame, mo, title):
    _rows = demo["comparison"]
    _cold, _warm = _rows
    _reused = any(a.plan_source == "memory_recipe" for a in demo["outcomes"]["warm"].attempts)
    _stats = "".join(
        f'<tr><td>{key}</td><td>{_cold[key]}</td><td class="deck-pass">{_warm[key]}</td></tr>'
        for key in ("Attempts", "Planner calls", "Fresh simulations")
    )
    frame(
        5,
        mo.vstack(
            [
                title("04 / DURABLE MEMORY", "The next run starts with evidence."),
                mo.hstack(
                    [
                        mo.Html(
                            f'<div class="deck-big-number">{_cold["Attempts"]}<span>→</span>{_warm["Attempts"]}</div>'
                            '<p class="deck-number-label">attempts on the repeated job</p>'
                            '<div class="deck-memory-path">STORE RECIPE<br>↓<br>RECALL FROM DISK<br>↓<br>VERIFY AGAIN</div>'
                        ),
                        mo.Html(
                            '<table class="deck-table"><thead><tr><th>Measured work</th><th>Cold</th><th>Warm</th></tr></thead><tbody>'
                            + _stats
                            + "</tbody></table>"
                            + '<p class="deck-body-note">A new controller reads the stored plan.<br>Checks and simulation still run.</p>'
                            + f'<span class="deck-tag">RECIPE {"REUSED" if _reused else "NOT REUSED"}</span>'
                        ),
                    ],
                    widths=[1, 1],
                    align="center",
                    gap=3,
                ),
            ],
            gap=2,
        ),
        "Freshly executed demo results · Scripted planner invocations · No model weight training",
    )
    return


@app.cell(hide_code=True)
def _(eval_snapshot, frame, links, mo, title):
    _batches = eval_snapshot["batches"]
    _rows = "".join(
        f"<tr><td>{b['display_split']}</td><td>{b['policy']}</td><td>{b['matched']}/{b['cases']}</td><td>{b['simulations']}</td></tr>"
        for b in _batches
    )
    _dev = [b for b in _batches if b["display_split"] == "Development"]
    frame(
        6,
        mo.vstack(
            [
                title("05 / EVALUATE THE CHECKS", "Catch the collision earlier."),
                mo.hstack(
                    [
                        mo.Html(
                            f'<div class="deck-big-number">{_dev[0]["simulations"]}<span>→</span>{_dev[1]["simulations"]}</div>'
                            '<p class="deck-number-label">development simulations</p>'
                            '<p class="deck-body-note">The revised clamp check rejects<br>the collision before simulation.</p>'
                            '<span class="deck-tag">FIXED-PLAN VALIDATOR EVALS</span>'
                        ),
                        mo.Html(
                            '<table class="deck-table"><thead><tr><th>Fixtures</th><th>Policy</th><th>Matches</th><th>Sims</th></tr></thead><tbody>'
                            + _rows
                            + "</tbody></table>"
                            f'<div class="deck-links"><a href="{links["evals"]}" target="_blank">Case-by-case evidence ↗</a>'
                            '<a href="https://wandb.ai/silta/coreweave-hack-silta-squad/weave/evaluations" target="_blank">W&B Weave ↗</a></div>'
                        ),
                    ],
                    widths=[2, 3],
                    align="center",
                    gap=3,
                ),
                mo.Html(
                    '<p class="deck-body-note">Expected rejections count as correct. The former holdout informed earlier fixes;<br>we report those four cases as regression coverage.</p>'
                ),
            ],
            gap=2,
        ),
        "12 existing fixtures · Frozen plans · Validator coverage, not a model-quality benchmark",
    )
    return


@app.cell(hide_code=True)
def _(frame, links, mo, public_demo_url, qr_svg):
    _url = public_demo_url()
    frame(
        7,
        mo.hstack(
            [
                mo.Html(
                    '<div class="deck-hero-copy"><div class="deck-eyebrow">OPEN THE WORKBENCH</div>'
                    '<h2>Don’t just<br>watch.<br><span class="deck-alert">Inspect it.</span></h2>'
                    "<p>Rotate the part. Read the checks.<br>See what the system remembers.</p>"
                    f'<div class="deck-links"><a href="{links["demo"]}" target="_blank">Joel’s four-slide demo ↗</a>'
                    f'<a href="{links["guide"]}" target="_blank">Pitch notes ↗</a></div></div>'
                ),
                mo.Html(
                    '<div class="deck-qr">' + qr_svg(_url) + "</div>"
                    f'<a class="deck-qr-link" href="{_url}" target="_blank">TRY SILTA CAD ↗</a>'
                    '<p class="deck-body-note">Scan to open the public product.</p>'
                ),
            ],
            widths=[3, 2],
            align="center",
            gap=3,
        ),
        "Interactive notebooks with marimo · Experiments and evaluations with Weights & Biases",
    )
    return


if __name__ == "__main__":
    app.run()
