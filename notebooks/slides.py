"""SILTA hackathon pitch draft, based on the team's agreed whiteboard loop.

Run `make slides` to present or `make slides-edit` to edit.
Each output cell is one slide. See docs/slides.md for sources and next edits.
"""

import marimo

__generated_with = "0.24.2"
app = marimo.App(
    width="full",
    app_title="SILTA · Hackathon deck",
    layout_file="layouts/slides.slides.json",
    html_head_file="assets/slides-head.html",
)


@app.cell
def _():
    from pathlib import Path

    import marimo as mo

    assets = (mo.notebook_dir() or Path.cwd() / "notebooks") / "assets"

    def frame(number, title, body, *, note="", hero=False):
        return mo.Html(
            f'<article class="silta-slide {"silta-hero" if hero else ""}">'
            "<header><strong>SILTA<span> / CNC</span></strong>"
            "<span>COREWEAVE HACKS 2026</span></header>"
            f"<main><h1>{title}</h1>{body}</main>"
            f"<footer><span>{note}</span><span>{number:02d} / 06</span></footer>"
            "</article>"
        )

    return assets, frame, mo


@app.cell(hide_code=True)
def _(frame):
    frame(
        1,
        "A machining planner<br>that learns from failure",
        '<p class="lead">Drawing to CAD to a verified machining plan.</p>'
        '<p class="sub">Silta Squad</p>',
        note="Drawing to machine instructions / Hackathon prototype",
        hero=True,
    )
    return


@app.cell(hide_code=True)
def _(assets, frame, mo):
    _drawing = mo.image(assets / "sample-fixture-block.png").text
    frame(
        2,
        "The part is only half the problem",
        '<div class="split"><div><p class="lead">A drawing defines what to make.</p>'
        "<p>The machine, tools and fixtures constrain how to make it.</p>"
        '<p class="accent">Keep the target geometry fixed.<br>Improve the machining plan.</p>'
        "</div><figure>"
        + _drawing
        + "<figcaption>Illustrative part drawing</figcaption></figure></div>",
        note="Input: drawing or PDF, machine and available tools",
    )
    return


@app.cell(hide_code=True)
def _(frame, mo):
    _loop = mo.mermaid(
        """
        %%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Helvetica Neue, Arial',
        'fontSize': '20px', 'primaryColor': '#f7f7f4', 'primaryTextColor': '#191919',
        'primaryBorderColor': '#b52e36', 'lineColor': '#62625d',
        'edgeLabelBackground': '#f7f7f4'}, 'flowchart': {'curve': 'linear'}}}%%
        flowchart LR
            D[Drawing] --> P[Machine instructions]
            I[Planning instructions] --> P
            P --> T{Tests}
            T -->|Pass| S{Simulation}
            T -->|Fail| P
            S -->|Fail| P
            S -->|Pass + time| J{Judge}
            J -->|Improve| I
            J -->|Accept| R[Best verified plan]
        """
    )
    frame(
        3,
        "The loop",
        '<div class="loop-diagram">' + _loop.text + "</div>"
        '<p class="loop-caption">Tests catch errors. Simulation checks the plan. '
        "The judge decides whether to improve it.</p>",
        note="The target part stays fixed throughout the loop",
    )
    return


@app.cell(hide_code=True)
def _(frame):
    frame(
        4,
        "The feedback becomes instructions",
        '<div class="split learning"><div class="learning-column"><h2>When a plan fails</h2>'
        "<p>Return the failure to the agent so it can repair the machine instructions.</p>"
        '<p class="accent">A missed failure can also become a new, validated test.</p>'
        '</div><div class="learning-column"><h2>When a plan passes</h2>'
        "<p>The judge reviews the simulation and machining time.</p>"
        '<p class="accent">Update the planning instructions, or accept the best verified plan.</p>'
        "</div></div>",
        note="Learning happens through feedback, validated tests and planning instructions",
    )
    return


@app.cell(hide_code=True)
def _(frame):
    # Replace this walkthrough with the real run once the implementation is ready.
    frame(
        5,
        "One part through the whole loop",
        '<ol class="sequence">'
        "<li><strong>First attempt</strong>"
        "<span>Inspect the drawing and generated machine instructions.</span></li>"
        "<li><strong>Feedback</strong>"
        "<span>See what the tests or simulation reject, and why.</span></li>"
        "<li><strong>Revision</strong>"
        "<span>Inspect the changed instructions and rerun verification.</span></li>"
        "<li><strong>Decision</strong>"
        "<span>Compare machining time. Let the judge improve or accept the plan.</span></li>"
        "</ol>",
        note="Planned demo walkthrough / implementation in progress",
    )
    return


@app.cell(hide_code=True)
def _(frame):
    frame(
        6,
        "The same part.<br>A better machining plan.",
        '<p class="lead">Our goal: a verified plan with less machining time.</p>'
        '<p class="lead">Every revision starts with feedback from the last attempt.</p>'
        '<p class="sub">SILTA / Silta Squad</p>',
        note="Simulation verification / physical machining remains unvalidated",
        hero=True,
    )
    return


if __name__ == "__main__":
    app.run()
