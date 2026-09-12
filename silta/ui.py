"""Presentation helpers for the workbench.

Rendering only. Nothing here decides anything: every status, number and message
comes from an `Attempt`, `CheckResult` or `SimulationResult` produced by the
deterministic pipeline.

Visual identity: the cyanotype. A blueprint is a negative — Prussian-blue paper
where the light struck, white line work where the drawing was. Everything here
is drawn in that white line work, and the drawing's own devices carry meaning
rather than decoration: a rubber stamp gives the verdict, a revision triangle
marks a value the planner changed, and a failed measurement is written as a
dimension callout between what was measured and what was required.
"""

from __future__ import annotations

from silta.domain import (
    Attempt,
    CheckResult,
    CheckStatus,
    Disposition,
    JobState,
    PartSpec,
    Severity,
    ShopProfile,
)

THEME = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {
  /* Cyanotype ground: Prussian blue paper, not a tinted near-black. */
  --field:   #0E3550;
  --field-2: #0A2B41;
  --field-3: #134462;

  /* Line work. White is where the drawing is; pale blue is the faint rule. */
  --white:   #EFF6FA;
  --line:    #6FA3C2;
  --line-2:  #2F5F80;
  --dim:     #9CC0D6;

  /* Stamps. These are ink on top of the print, so they are the only hues. */
  --stamp:   #F2634B;
  --approve: #5CC894;
  --hold:    #E8B24A;

  --text: "Jost", system-ui, -apple-system, sans-serif;
  --disp: "Jost", system-ui, sans-serif;
  --mono: "DM Mono", ui-monospace, "SF Mono", Menlo, monospace;
}

html, body, #App, #root {
  background: var(--field) !important;
  color: var(--white);
  accent-color: var(--line);
}
body { font-family: var(--text); font-size: 14px; line-height: 1.55; }

/* marimo centres app content in a narrow reading column. This is a drawing
   sheet, not an essay, so give it the bench. Targets marimo's own Tailwind
   wrapper classes by substring, since the escaped names are not selectable. */
div[class*="xl:px-24"] { padding-left: 26px !important; padding-right: 26px !important; }
/* The sheet border: the double rule every drawing is trimmed to. */
div.m-auto[class*="max-w-full"] {
  max-width: 1560px !important; width: 100% !important;
  border: 1px solid var(--line-2);
  box-shadow: inset 0 0 0 4px var(--field), inset 0 0 0 5px var(--line-2);
  padding: 20px !important;
}

.marimo-cell { background: transparent !important; border: none !important; }
.markdown, .markdown p, .markdown li, .markdown td, .markdown th { color: var(--white); }
.markdown p, .markdown li { max-width: 72ch; color: var(--dim); }
.markdown a { color: var(--line); text-underline-offset: 3px; }
.markdown code {
  font-family: var(--mono); font-size: .9em; color: var(--white);
  background: var(--field-2); padding: 1px 5px; border: 1px solid var(--line-2);
}
.markdown h1, .markdown h2, .markdown h3 {
  font-family: var(--disp); font-weight: 500; color: var(--white);
}
pre, .marimo-cell pre {
  background: var(--field-2) !important; color: var(--white) !important;
  border: 1px solid var(--line-2);
}

/* ---- marimo's own widgets ---------------------------------------------
   marimo renders sliders, dropdowns, radios and buttons inside shadow roots
   that page CSS cannot reach. Custom properties do cross that boundary, so its
   theme variables are restated here in cyanotype; `pyproject.toml` puts marimo
   in its dark theme first, and these repaint that theme. --radius squares the
   corners off, because a drawing has no rounded ones. */
:root, .dark, [data-theme="dark"] {
  --background: var(--field);
  --foreground: var(--white);
  --card: var(--field-3);
  --card-foreground: var(--white);
  --popover: var(--field-2);
  --popover-foreground: var(--white);
  --primary: var(--line);
  --primary-foreground: var(--field-2);
  --secondary: var(--field-3);
  --secondary-foreground: var(--white);
  --muted: var(--field-2);
  --muted-foreground: var(--dim);
  --accent: #1B5478;
  --accent-foreground: var(--white);
  --border: var(--line-2);
  --input: var(--line-2);
  --ring: var(--line);
  --link: #8FC4DE;
  --link-visited: #B9CBD8;
  --destructive: var(--stamp);
  --destructive-hover: #D9533D;
  --destructive-border: #94402F;
  --destructive-foreground: var(--field-2);
  --error: var(--stamp);
  --error-foreground: var(--field-2);
  --success: var(--approve);
  --success-hover: #4BB683;
  --success-border: #3B7C5E;
  --success-foreground: var(--field-2);
  --action: var(--hold);
  --action-hover: #D9A33C;
  --action-border: #A67C2E;
  --action-foreground: var(--field-2);
  --radius: 2px;
  --text-font: "Jost", system-ui, sans-serif;
  --heading-font: "Jost", system-ui, sans-serif;
  --monospace-font: "DM Mono", ui-monospace, monospace;
  --markdown-max-width: 72ch;
}

input[type="range"], input[type="radio"], input[type="checkbox"], progress {
  accent-color: var(--line);
}
.marimo-cell button,
.marimo-cell select,
.marimo-cell input[type="text"],
.marimo-cell input[type="number"] {
  font-family: var(--text); font-size: 13.5px; color: var(--white);
  background: var(--field-3); border: 1px solid var(--line-2); border-radius: 2px;
  padding: 6px 12px; box-shadow: none;
}
.marimo-cell button { font-weight: 500; cursor: pointer; }
.marimo-cell button:hover { background: var(--line-2); border-color: var(--line); }
.marimo-cell button:focus-visible,
.marimo-cell select:focus-visible { outline: 2px solid var(--line); outline-offset: 2px; }
/* The primary action is struck in the paper white the drawing is made of. */
.marimo-cell button[data-kind="success"],
.marimo-cell .mo-success button,
.marimo-cell button.success {
  background: var(--white); border-color: var(--white); color: var(--field);
  font-weight: 600;
}
.marimo-cell button[data-kind="success"]:hover,
.marimo-cell .mo-success button:hover,
.marimo-cell button.success:hover { background: var(--line); border-color: var(--line); }
.marimo-cell label { font-family: var(--text); color: var(--dim); font-size: 13px; }
.marimo-cell svg circle[stroke], .marimo-cell .spinner { stroke: var(--line) !important; }

/* ---- title block ------------------------------------------------------
   A drawing's title block: the sheet name, what it is for, and the facts that
   identify this print, in ruled cells. */
.sx-mast {
  border: 1px solid var(--line); border-bottom: none; background: var(--field-2);
  padding: 26px 26px 22px; margin: 2px 0 0;
}
.sx-word {
  font-family: var(--disp); font-weight: 500; font-size: 54px; line-height: .95;
  letter-spacing: .11em; margin: 0; color: var(--white); text-transform: uppercase;
}
.sx-tag {
  margin: 16px 0 0; font-size: 14.5px; color: var(--dim);
  max-width: 66ch; line-height: 1.65; font-weight: 300;
}
.sx-tag b { color: var(--white); font-weight: 500; }
.sx-stake {
  margin: 9px 0 0; font-size: 14.5px; color: var(--white); font-weight: 500;
  max-width: 66ch;
}

/* ---- ruled fact strip -------------------------------------------------- */
.sx-readout {
  display: flex; flex-wrap: wrap; gap: 0; border: 1px solid var(--line);
  background: var(--field-2); margin-bottom: 20px;
}
.sx-cellr {
  flex: 1 1 150px; padding: 10px 14px 11px; border-right: 1px solid var(--line-2);
  min-width: 0;
}
.sx-cellr:last-child { border-right: none; }
.sx-k { font-size: 12px; color: var(--dim); display: block; margin-bottom: 2px; font-weight: 300; }
.sx-v {
  font-size: 14px; color: var(--white); font-weight: 500; line-height: 1.4;
  overflow-wrap: anywhere;
}
.sx-v.flag { color: var(--hold); }
.sx-v.ok   { color: var(--approve); }
.sx-v.bad  { color: var(--stamp); }

/* ---- section headers --------------------------------------------------
   A view marker, not an 01/02/03 counter: these sections are a page outline,
   and only the attempts below are a real sequence. */
.sx-h {
  display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap;
  margin: 38px 0 14px; border-bottom: 1px solid var(--line); padding-bottom: 8px;
}
.sx-h span.t {
  position: relative; padding-left: 15px; font-family: var(--disp);
  font-size: 25px; font-weight: 400; letter-spacing: .015em; color: var(--white);
  line-height: 1.1;
}
.sx-h span.t::before {
  content: ""; position: absolute; left: 0; top: .12em; bottom: .12em;
  width: 2px; background: var(--white);
}
.sx-h .facts { margin-left: auto; display: flex; gap: 18px; flex-wrap: wrap; }
.sx-h .facts span { font-size: 13px; color: var(--dim); font-weight: 300; }
.sx-h .facts span b {
  color: var(--white); font-weight: 400; font-family: var(--mono);
  font-size: 12.5px; margin-left: 6px;
}

/* ---- the loop ---------------------------------------------------------- */
.sx-loop { display: flex; width: 100%; gap: 16px; align-items: stretch; flex-wrap: wrap; }
.sx-att {
  flex: 1 1 250px; min-width: 240px; border: 1px solid var(--line-2);
  background: var(--field-3); padding: 15px 17px 16px;
}
.sx-att-h {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 12px; margin-bottom: 13px;
}
.sx-att-n {
  font-family: var(--disp); font-size: 17px; font-weight: 400; color: var(--dim);
  letter-spacing: .05em; text-transform: uppercase; padding-top: 3px;
}
.sx-att-n b { font-family: var(--mono); font-size: 17px; font-weight: 500; color: var(--white); }

/* The verdict, stamped on the print. Caps and tracking here are the artifact
   itself, not a label style borrowed for decoration. */
.sx-stamp {
  font-family: var(--disp); font-weight: 600; font-size: 12.5px;
  letter-spacing: .2em; text-transform: uppercase; white-space: nowrap;
  border: 2px solid currentColor; padding: 4px 9px 3px 11px;
  outline: 1px solid currentColor; outline-offset: 2px;
  transform: rotate(-3.5deg); opacity: .95; flex: 0 0 auto; margin-right: 3px;
}
.sx-stamp.reject  { color: var(--stamp); }
.sx-stamp.approve { color: var(--approve); }
.sx-stamp.hold    { color: var(--hold); }

/* What the planner changed, marked the way a drawing marks a revised
   dimension. This is the link between one attempt and the next. */
.sx-diff { margin-bottom: 12px; }
.sx-rev-row { display: flex; align-items: flex-start; gap: 9px; font-size: 13px; }
.sx-rev-row + .sx-rev-row { margin-top: 6px; }
.sx-rev { flex: 0 0 auto; color: var(--hold); }
.sx-rev-text {
  color: var(--white); font-family: var(--mono); font-size: 12.5px; line-height: 1.45;
}

.sx-why { font-size: 13.5px; line-height: 1.55; color: var(--dim); font-weight: 300; }
.sx-why .id { font-family: var(--mono); font-size: 12.5px; color: var(--stamp); }
.sx-why b { color: var(--white); font-weight: 400; }

/* A failed measurement, written as the drawing would write it: the value that
   was measured, an extension line, and the limit it had to meet. */
.sx-dim {
  display: flex; align-items: center; margin: 12px 0 4px;
  font-family: var(--mono); font-size: 12.5px;
}
.sx-dim .a { color: var(--stamp); }
.sx-dim .r { color: var(--white); }
.sx-dim .bar {
  flex: 1 1 auto; min-width: 26px; height: 1px; background: var(--line);
  margin: 0 10px; position: relative;
}
.sx-dim .bar::before, .sx-dim .bar::after {
  content: ""; position: absolute; top: -4px; width: 1px; height: 9px;
  background: var(--line);
}
.sx-dim .bar::before { left: 0; }
.sx-dim .bar::after { right: 0; }
.sx-dim-note { font-size: 12px; color: var(--dim); font-weight: 300; margin-top: 2px; }

/* ---- measurement grid -------------------------------------------------
   Measured values share a left edge so rows can be read against each other,
   which a run of dot-separated prose does not allow. */
.sx-meas {
  margin-top: 13px; padding-top: 11px; border-top: 1px solid var(--line-2);
  display: grid; grid-template-columns: max-content 1fr; gap: 4px 18px;
  font-size: 12.5px;
}
.sx-meas dt { color: var(--dim); font-weight: 300; }
.sx-meas dd {
  margin: 0; font-family: var(--mono); font-size: 12px; color: var(--white);
  font-variant-numeric: tabular-nums; overflow-wrap: anywhere;
}
.sx-meas dd.bad { color: var(--stamp); }
.sx-meas dd.ok { color: var(--approve); }
.sx-halt {
  margin-top: 13px; padding-top: 11px; border-top: 1px solid var(--line-2);
  font-size: 12.5px; color: var(--dim); font-weight: 300;
}

/* ---- ledger ------------------------------------------------------------ */
.sx-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sx-table th {
  text-align: left; font-size: 12.5px; color: var(--dim); font-weight: 300;
  border-bottom: 1px solid var(--line); padding: 7px 10px;
}
.sx-table td {
  padding: 7px 10px; border-bottom: 1px solid rgba(111, 163, 194, .16);
  color: var(--white); vertical-align: top; font-weight: 300;
}
.sx-table tbody tr:hover td { background: rgba(111, 163, 194, .09); }
.sx-table td.num {
  font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums;
}
.sx-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  margin-right: 9px; vertical-align: middle;
}
.sx-dot.pass { background: var(--approve); }
.sx-dot.fail { background: var(--stamp); }
.sx-dot.warn { background: var(--hold); }
.sx-dot.na   { background: var(--line-2); }
.sx-mono { font-family: var(--mono); font-size: 12px; color: var(--white); }

/* ---- notes ------------------------------------------------------------- */
.sx-note {
  border: 1px solid var(--line-2); border-left: 2px solid var(--line);
  background: var(--field-2); padding: 13px 16px; font-size: 13.5px;
  color: var(--dim); line-height: 1.65; max-width: 88ch; font-weight: 300;
}
.sx-note b { color: var(--white); font-weight: 500; }

/* ---- story views and phone sharing ------------------------------------ */
.sx-story {
  padding: 24px 26px; border: 1px solid var(--line-2);
  border-left: 3px solid var(--line); background: var(--field-2);
}
.sx-story h2, .sx-share h2 {
  font-family: var(--disp); font-weight: 400; color: var(--white);
  font-size: clamp(24px, 3.4vw, 36px); letter-spacing: .01em; margin: 0 0 14px;
}
.sx-story p, .sx-share p { line-height: 1.65; max-width: 70ch; color: var(--dim); }
.sx-story p b, .sx-share p b { color: var(--white); font-weight: 500; }
.sx-share {
  display: flex; flex-wrap: wrap; align-items: center; gap: 24px; padding: 20px;
  border: 1px solid var(--line-2); background: var(--field-2);
}
.sx-share > div:first-child { flex: 1 1 240px; min-width: 0; }
.sx-share-url { overflow-wrap: anywhere; font-family: var(--mono); font-size: 12px; }
.sx-share a { color: var(--line); display: inline-block; padding: 12px 0; }
.sx-qr { background: #FFF; padding: 10px; border: 1px solid var(--line); flex: 0 0 auto; }
.sx-qr svg { display: block; }

@media (max-width: 700px) {
  div[class*="xl:px-24"] { padding-left: 12px !important; padding-right: 12px !important; }
  div.m-auto[class*="max-w-full"] { padding: 12px !important; }
  .sx-mast { padding: 20px 16px; }
  .sx-word { font-size: 34px; letter-spacing: .08em; }
  .sx-h { gap: 8px; }
  .sx-h .facts { margin-left: 0; width: 100%; gap: 14px; }
  .sx-loop { gap: 12px; }
  .sx-att { flex: 1 1 100%; }
  .sx-table { display: block; max-width: 100%; overflow-x: auto; }
  .sx-story { padding: 16px; }
  pre { max-width: 100%; overflow-x: auto; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: .01ms !important;
    animation-duration: .01ms !important;
  }
}
</style>
"""

_DISPOSITION_TONE = {
    Disposition.PASSED: "pass",
    Disposition.FAILED_CHECKS: "fail",
    Disposition.FAILED_SIMULATION: "fail",
    Disposition.SCHEMA_INVALID: "fail",
    Disposition.CANCELLED: "warn",
    Disposition.BUDGET_EXHAUSTED: "warn",
    Disposition.ERROR: "fail",
}

# The stamp carries the verdict; the precise disposition stays in the grid below.
_STAMP = {"pass": ("approve", "Approved"), "fail": ("reject", "Rejected"), "warn": ("hold", "Held")}

_STATE_TONE = {
    JobState.PASSED: "ok",
    JobState.NEEDS_HUMAN_REVIEW: "flag",
    JobState.BUDGET_EXHAUSTED: "flag",
    JobState.CANCELLED: "flag",
}


def sentence(value: str) -> str:
    """`failed_simulation` -> `Failed simulation`."""
    words = value.replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else words


def _revision_triangle(number: int) -> str:
    """The mark a drawing puts beside a dimension that changed in a revision."""
    return (
        f'<svg class="sx-rev" width="19" height="17" viewBox="0 0 19 17" aria-hidden="true">'
        f'<polygon points="9.5,1.4 18,15.6 1,15.6" fill="none" stroke="currentColor" '
        f'stroke-width="1.3"/>'
        f'<text x="9.5" y="14" text-anchor="middle" font-size="8.5" font-family="DM Mono, '
        f'monospace" fill="currentColor">{number}</text></svg>'
    )


def masthead(session_id: str, planner: str, commit: str | None) -> str:
    short = (commit or "uncommitted")[:8]
    # Amber means "running degraded", so it appears only without an inference key.
    planner_tone = "flag" if "deterministic" in planner.lower() else ""
    return f"""{THEME}
<div class="sx-mast">
  <h1 class="sx-word">Silta CNC</h1>
  <p class="sx-tag">
    A dimensioned drawing becomes a solid model, a machining recipe, a compiled
    toolpath and a simulated cut. When a <b>real geometric check</b> fails, the
    measurement that failed goes back to the planner, and the next attempt is
    measured the same way.
  </p>
  <p class="sx-stake">Nothing here passes because a model said it would.</p>
</div>
<div class="sx-readout">
  <div class="sx-cellr"><span class="sx-k">Session</span>
    <div class="sx-v">{session_id}</div></div>
  <div class="sx-cellr"><span class="sx-k">Planner</span>
    <div class="sx-v {planner_tone}">{planner}</div></div>
  <div class="sx-cellr"><span class="sx-k">Build</span>
    <div class="sx-v">{short}</div></div>
  <div class="sx-cellr"><span class="sx-k">Simulator</span>
    <div class="sx-v">2.5D heightfield, 0.5 mm grid</div></div>
</div>"""


def section(title: str, *facts: tuple[str, str]) -> str:
    """A ruled section head. `facts` are label/value pairs, set to the right.

    Structured pairs rather than one dot-joined string: the labels say what the
    values are, and each value stays selectable on its own.
    """
    rendered = "".join(f"<span>{label}<b>{value}</b></span>" for label, value in facts if value)
    block = f'<div class="facts">{rendered}</div>' if rendered else ""
    return f'<div class="sx-h"><span class="t">{title}</span>{block}</div>'


def run_readout(state: JobState, attempts: int, wall: float, simulations: int) -> str:
    tone = _STATE_TONE.get(state, "bad")
    label = "Passed prototype checks" if state is JobState.PASSED else sentence(state.value)
    return f"""<div class="sx-readout">
  <div class="sx-cellr"><span class="sx-k">Outcome</span>
    <div class="sx-v {tone}">{label}</div></div>
  <div class="sx-cellr"><span class="sx-k">Candidates</span>
    <div class="sx-v">{attempts}</div></div>
  <div class="sx-cellr"><span class="sx-k">Simulations</span>
    <div class="sx-v">{simulations}</div></div>
  <div class="sx-cellr"><span class="sx-k">Wall clock</span>
    <div class="sx-v">{wall:.1f} s</div></div>
</div>"""


def _headline_failure(attempt: Attempt) -> CheckResult | None:
    failures = attempt.blocking_failures
    if not failures:
        return None
    order = {"simulation": 0, "path": 1, "preflight": 2, "schema": 3}
    return sorted(failures, key=lambda c: order.get(c.stage.value, 9))[0]


def _dimension_callout(failure: CheckResult) -> str:
    """Measured against required, drawn the way a drawing dimensions a feature."""
    if failure.actual is None or failure.required is None:
        return ""
    units = f" {failure.units}" if failure.units else ""
    return (
        f'<div class="sx-dim"><span class="a">{failure.actual}{units}</span>'
        f'<span class="bar"></span>'
        f'<span class="r">{failure.required}{units}</span></div>'
        f'<div class="sx-dim-note">measured &rarr; required</div>'
    )


def attempt_card(attempt: Attempt, is_last: bool) -> str:
    tone = _DISPOSITION_TONE.get(attempt.disposition, "warn")
    stamp_class, stamp_word = _STAMP[tone]
    plan = attempt.plan
    tools = ", ".join(sorted({op.tool_id for op in plan.operations})) if plan else "—"
    clearance = f"{plan.clearance_mm:g} mm" if plan else "—"

    diff = ""
    if attempt.repair_diff:
        rows = "".join(
            f'<div class="sx-rev-row">{_revision_triangle(n)}'
            f'<span class="sx-rev-text">{d}</span></div>'
            for n, d in enumerate(attempt.repair_diff, start=1)
        )
        diff = f'<div class="sx-diff">{rows}</div>'

    failure = _headline_failure(attempt)
    if failure is not None:
        why = (
            f'<div class="sx-why"><span class="id">{failure.check_id}</span> '
            f"{failure.message}</div>{_dimension_callout(failure)}"
        )
    else:
        why = (
            f'<div class="sx-why">Every blocking check cleared across '
            f"{len(attempt.checks)} evaluations, and the simulated cut matched the "
            f"target surface.</div>"
        )

    rows = [
        ("Disposition", sentence(attempt.disposition.value), ""),
        ("Source", sentence(attempt.plan_source), ""),
        ("Tools", tools, ""),
        ("Clearance", clearance, ""),
    ]
    sim = attempt.simulation
    if sim is not None:
        rows += [
            (
                "Simulation",
                sentence(sim.status.value),
                "ok" if sim.status.value == "pass" else "bad",
            ),
            ("Residual", f"{sim.max_residual_mm} mm", ""),
            ("Gouge", f"{sim.max_gouge_mm} mm", ""),
            ("Simulated in", f"{sim.elapsed_s:g} s", ""),
        ]
        halt = ""
    else:
        halt = (
            '<div class="sx-halt">Stopped before simulation. No machine time was spent on it.</div>'
        )
    grid = (
        '<dl class="sx-meas">'
        + "".join(f'<dt>{k}</dt><dd class="{c}">{v}</dd>' for k, v, c in rows)
        + "</dl>"
    )

    return f"""<div class="sx-att {tone}">
  <div class="sx-att-h">
    <span class="sx-att-n">Attempt <b>{attempt.index:02d}</b></span>
    <span class="sx-stamp {stamp_class}">{stamp_word}</span>
  </div>
  {diff}
  {why}
  {grid}
  {halt}
</div>"""


def loop_strip(attempts: list[Attempt]) -> str:
    if not attempts:
        return '<div class="sx-note">No attempts were made.</div>'
    cards = "".join(attempt_card(a, index == len(attempts) - 1) for index, a in enumerate(attempts))
    return f'<div class="sx-loop">{cards}</div>'


_STATUS_CLASS = {
    CheckStatus.PASS: "pass",
    CheckStatus.FAIL: "fail",
    CheckStatus.UNKNOWN: "na",
    CheckStatus.NOT_APPLICABLE: "na",
}


def check_ledger(attempt: Attempt) -> str:
    rows = []
    for check in attempt.checks:
        css = _STATUS_CLASS[check.status]
        if check.status is CheckStatus.FAIL and check.severity is not Severity.BLOCKING:
            css = "warn"
        actual = "" if check.actual is None else check.actual
        required = "" if check.required is None else check.required
        rows.append(
            f"<tr><td><span class='sx-dot {css}'></span>"
            f"<span class='sx-mono'>{check.check_id}</span></td>"
            f"<td>{check.stage.value}</td>"
            f"<td>{check.severity.value}</td>"
            f"<td class='num'>{actual}</td><td class='num'>{required}</td>"
            f"<td>{check.units or ''}</td>"
            f"<td>{check.message}</td></tr>"
        )
    return (
        "<table class='sx-table'><thead><tr>"
        "<th>Check</th><th>Stage</th><th>Severity</th><th>Actual</th>"
        "<th>Required</th><th>Units</th><th>Finding</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def spec_panel(spec: PartSpec, shop: ShopProfile) -> str:
    features = "".join(
        f"<tr><td><span class='sx-mono'>{f.feature_id}</span></td>"
        f"<td>{f.kind.value.replace('_', ' ')}</td>"
        f"<td class='num'>{f.depth_mm:g} mm</td>"
        f"<td>{', '.join(f.drawing_refs) or '—'}</td></tr>"
        for f in spec.features
    )
    tools = "".join(
        f"<tr><td><span class='sx-mono'>{t.tool_id}</span></td>"
        f"<td>{t.kind.value.replace('_', ' ')}</td>"
        f"<td class='num'>&#8960;{t.diameter_mm:g}</td>"
        f"<td class='num'>{t.cutting_length_mm:g} mm</td>"
        f"<td class='num'>{t.stickout_mm:g} mm</td></tr>"
        for t in shop.tools
    )
    return f"""<div class="sx-readout">
  <div class="sx-cellr"><span class="sx-k">Stock</span><div class="sx-v">
    {spec.stock_x_mm:g} &times; {spec.stock_y_mm:g} &times; {spec.stock_z_mm:g} mm</div></div>
  <div class="sx-cellr"><span class="sx-k">Material</span>
    <div class="sx-v">{spec.material}</div></div>
  <div class="sx-cellr"><span class="sx-k">Revision</span>
    <div class="sx-v">r{spec.revision}, frozen</div></div>
  <div class="sx-cellr"><span class="sx-k">Design hash</span>
    <div class="sx-v"><span class="sx-mono">{spec.design_hash[:16]}</span></div></div>
</div>
<div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:14px">
  <div style="flex:1 1 320px">
    <table class="sx-table"><thead><tr><th>Feature</th><th>Kind</th>
    <th>Depth</th><th>Drawing</th></tr></thead><tbody>{features}</tbody></table>
  </div>
  <div style="flex:1 1 320px">
    <table class="sx-table"><thead><tr><th>Tool</th><th>Type</th><th>&#8960;</th>
    <th>Cutting length</th><th>Stickout</th></tr></thead>
    <tbody>{tools}</tbody></table>
  </div>
</div>"""


def design_guard(spec: PartSpec, attempts: list[Attempt]) -> str:
    """Evidence that repair never moved the customer's requested shape."""
    hashes = {a.plan.spec_design_hash for a in attempts if a.plan}
    unchanged = hashes == {spec.design_hash}
    tone = "ok" if unchanged else "bad"
    word = "unchanged across every attempt" if unchanged else "changed, and needs investigating"
    return (
        f'<div class="sx-note">The confirmed design hash '
        f'<span class="sx-mono">{spec.design_hash[:16]}</span> is '
        f'<span class="sx-v {tone}" style="display:inline">{word}</span>. '
        "Repair may change tooling, ordering, step parameters and clearances. It "
        "cannot change a dimension, invent a tool, move a fixture or edit a "
        "threshold — those need a visible operator edit and a new revision.</div>"
    )


LIMITATIONS = (
    '<div class="sx-note"><b>What this is and is not.</b> Geometric 2.5D '
    "stock-removal and collision simulation only: no cutting forces, deflection, "
    "chatter or machine dynamics. Estimated machining time is arithmetic from "
    "feeds and declared constants, not measured shop performance. No G-code, "
    "postprocessor or controller execution is produced — the trajectory is a "
    "replay and verification format. The part, the drawing and the shop profile "
    "are a synthetic demonstration fixture. These are prototype checks, not a "
    "manufacturing certification.</div>"
)
