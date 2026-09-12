# /// script
# requires-python = ">=3.12"
# ///
"""Silta CNC evaluations — policy comparison and improvement evidence.

Run it as an application:  marimo run notebooks/evaluations.py

The baseline-vs-revised comparison starts automatically on load.
"""

import marimo

__generated_with = "0.24.2"
# html_head_file carries the cyanotype theme into marimo's shadow-DOM widgets,
# which page CSS cannot reach. See silta/static/head.html.
app = marimo.App(
    width="full",
    app_title="Silta CNC Evaluations",
    html_head_file="../silta/static/head.html",
)


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo

    # Bootstrap sys.path so silta imports work
    _repo_root = (mo.notebook_dir() or Path.cwd()).resolve().parent
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

    return Path, mo


@app.cell
def _():
    import asyncio

    from silta import ui
    from silta.evaluation import (
        compare,
        convergence_report,
        load_fixtures,
        run_batch,
        run_saved_candidate_corpus,
        score,
    )
    from silta.policy import POLICY_V0, POLICY_V1
    from silta.telemetry import Telemetry

    return (
        Telemetry,
        asyncio,
        compare,
        convergence_report,
        load_fixtures,
        run_batch,
        run_saved_candidate_corpus,
        score,
        ui,
        POLICY_V0,
        POLICY_V1,
    )


@app.cell
def _(mo, ui):
    mo.Html(
        ui.THEME
        + """<div class="sx-mast">
      <h1 class="sx-word">Silta CNC evaluations</h1>
      <p class="sx-tag">
        Policy comparison on frozen fixtures. <b>Development</b> is for tuning;
        <b>former holdout</b> cases now provide regression coverage. Aggregate
        scores show <b>counts and denominators</b>, never bare percentages. False
        accepts and false rejects are surfaced prominently.
      </p>
    </div>"""
    )
    return


@app.cell
async def _(asyncio, load_fixtures, run_batch, POLICY_V0, POLICY_V1):
    # Auto-run the comparison on load (no click required)
    dev_fixtures = load_fixtures("development")
    holdout_fixtures = load_fixtures("holdout")

    # Run both policies on development
    v0_dev_outcomes = await run_batch(dev_fixtures, POLICY_V0, max_attempts=1)
    v1_dev_outcomes = await run_batch(dev_fixtures, POLICY_V1, max_attempts=1)

    # Run both policies on holdout
    v0_holdout_outcomes = await run_batch(holdout_fixtures, POLICY_V0, max_attempts=1)
    v1_holdout_outcomes = await run_batch(holdout_fixtures, POLICY_V1, max_attempts=1)

    return (
        dev_fixtures,
        holdout_fixtures,
        v0_dev_outcomes,
        v0_holdout_outcomes,
        v1_dev_outcomes,
        v1_holdout_outcomes,
    )


@app.cell
def _(compare, mo, score, ui, v0_dev_outcomes, v1_dev_outcomes):
    _v0_score = score(v0_dev_outcomes)
    _v1_score = score(v1_dev_outcomes)
    _comparison = compare(v0_dev_outcomes, v1_dev_outcomes)

    # Per-fixture table
    _per_fixture_rows = "".join(
        f"<tr>"
        f"<td><span class='sx-mono'>{row['fixture_id']}</span></td>"
        f"<td>{row.get('baseline_disposition', '—')}</td>"
        f"<td>{row.get('revised_disposition', '—')}</td>"
        f"<td>{row.get('baseline_simulations', 0)}</td>"
        f"<td>{row.get('revised_simulations', 0)}</td>"
        f"<td><b>{row.get('simulations_saved', 0)}</b></td>"
        f"<td>{'✓' if row.get('baseline_matched') else '✗'}</td>"
        f"<td>{'✓' if row.get('revised_matched') else '✗'}</td>"
        f"</tr>"
        for row in _comparison["per_fixture"]
    )

    # Aggregate scores with counts and denominators
    _agg = _comparison["aggregate"]
    _baseline_summary = _agg["baseline"]
    _revised_summary = _agg["revised"]

    # fmt: off
    # noqa in f-string HTML templates for line length
    mo.Html(
        ui.section("Development set comparison", ("Fixtures", "8, for tuning"))
        + f"""
    <div class="sx-readout">
      <div class="sx-cellr"><span class="sx-k">Baseline matched</span>
        <div class="sx-v">{_baseline_summary["matched_expectation_count"]}/{_baseline_summary["total_cases"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">Revised matched</span>
        <div class="sx-v ok">{_revised_summary["matched_expectation_count"]}/{_revised_summary["total_cases"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">False accepts</span>
        <div class="sx-v {"ok" if _revised_summary["false_accept_count"] == 0 else "bad"}">{_revised_summary["false_accept_count"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">Simulations saved</span>
        <div class="sx-v flag">{_agg["simulations_saved"]}</div></div>
    </div>
    <table class="sx-table">
      <thead><tr>
        <th>Fixture</th>
        <th>v0 Disposition</th>
        <th>v1 Disposition</th>
        <th>v0 Sims</th>
        <th>v1 Sims</th>
        <th>Saved</th>
        <th>v0 Match</th>
        <th>v1 Match</th>
      </tr></thead>
      <tbody>{_per_fixture_rows}</tbody>
    </table>
    <div style="height:14px"></div>
    <div class="sx-readout">
      <div class="sx-cellr"><span class="sx-k">v0 Feasible</span>
        <div class="sx-v">{_baseline_summary["feasible_count"]}/{_baseline_summary["total_cases"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">v1 Feasible</span>
        <div class="sx-v">{_revised_summary["feasible_count"]}/{_revised_summary["total_cases"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">v0 Simulations</span>
        <div class="sx-v">{_baseline_summary["simulations_run"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">v1 Simulations</span>
        <div class="sx-v">{_revised_summary["simulations_run"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">Mean wall (v1)</span>
        <div class="sx-v">{_revised_summary["mean_wall_seconds"]:.2f} s</div></div>
    </div>
    """
    )
    # fmt: on
    return


@app.cell
def _(compare, mo, score, ui, v0_holdout_outcomes, v1_holdout_outcomes):
    _v0_holdout_score = score(v0_holdout_outcomes)
    _v1_holdout_score = score(v1_holdout_outcomes)
    _holdout_comparison = compare(v0_holdout_outcomes, v1_holdout_outcomes)

    _holdout_per_fixture_rows = "".join(
        f"<tr>"
        f"<td><span class='sx-mono'>{row['fixture_id']}</span></td>"
        f"<td>{row.get('baseline_disposition', '—')}</td>"
        f"<td>{row.get('revised_disposition', '—')}</td>"
        f"<td>{row.get('baseline_simulations', 0)}</td>"
        f"<td>{row.get('revised_simulations', 0)}</td>"
        f"<td><b>{row.get('simulations_saved', 0)}</b></td>"
        f"<td>{'✓' if row.get('baseline_matched') else '✗'}</td>"
        f"<td>{'✓' if row.get('revised_matched') else '✗'}</td>"
        f"</tr>"
        for row in _holdout_comparison["per_fixture"]
    )

    _holdout_agg = _holdout_comparison["aggregate"]
    _holdout_baseline = _holdout_agg["baseline"]
    _holdout_revised = _holdout_agg["revised"]

    mo.Html(
        ui.section(
            "Regression set evaluation (former holdout)",
            ("Fixtures", "4"),
            ("Evaluated", "replay of existing cases"),
        )
        + f"""
    <div class="sx-note" style="margin-bottom:14px">
      <b>Regression evidence.</b> The retained check lineage records an earlier fix
      prompted by holdout_03_valid_complex. These four cases are therefore regression
      coverage, not an untouched blind test. A new holdout is needed to measure generalization.
    </div>
    <div class="sx-readout">
      <div class="sx-cellr"><span class="sx-k">Baseline matched</span>
        <div class="sx-v">{_holdout_baseline["matched_expectation_count"]}/{_holdout_baseline["total_cases"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">Revised matched</span>
        <div class="sx-v ok">{_holdout_revised["matched_expectation_count"]}/{_holdout_revised["total_cases"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">False accepts</span>
        <div class="sx-v {"ok" if _holdout_revised["false_accept_count"] == 0 else "bad"}">{_holdout_revised["false_accept_count"]}</div></div>
      <div class="sx-cellr"><span class="sx-k">Simulations saved</span>
        <div class="sx-v">{_holdout_agg["simulations_saved"]}</div></div>
    </div>
    <table class="sx-table">
      <thead><tr>
        <th>Fixture</th>
        <th>v0 Disposition</th>
        <th>v1 Disposition</th>
        <th>v0 Sims</th>
        <th>v1 Sims</th>
        <th>Saved</th>
        <th>v0 Match</th>
        <th>v1 Match</th>
      </tr></thead>
      <tbody>{_holdout_per_fixture_rows}</tbody>
    </table>
    """
    )
    return


@app.cell
def _(Path, mo, ui):
    _aria_file = Path(__file__).parent.parent / "policies" / "aria-recommendation-001.md"
    _aria_content = _aria_file.read_text() if _aria_file.exists() else "File not found"

    mo.Html(
        ui.section(
            "ARIA recommendation and lineage",
            ("Promoted in policy-v1", "path_fixture_envelope"),
        )
        + """
    <div class="sx-readout">
      <div class="sx-cellr"><span class="sx-k">Check ID</span>
        <div class="sx-v flag">path_fixture_envelope</div></div>
      <div class="sx-cellr"><span class="sx-k">Check version</span>
        <div class="sx-v">2</div></div>
      <div class="sx-cellr"><span class="sx-k">Policy</span>
        <div class="sx-v">policy-v1</div></div>
      <div class="sx-cellr"><span class="sx-k">ARIA status</span>
        <div class="sx-v bad">External gate, not yet satisfied</div></div>
    </div>
    <div style="height:14px"></div>
    <div class="sx-readout">
      <div class="sx-cellr"><span class="sx-k">Implemented</span>
        <div class="sx-v ok">✓</div></div>
      <div class="sx-cellr"><span class="sx-k">Dev measured</span>
        <div class="sx-v ok">✓</div></div>
      <div class="sx-cellr"><span class="sx-k">Holdout measured</span>
        <div class="sx-v ok">✓</div></div>
      <div class="sx-cellr"><span class="sx-k">W&B runs uploaded</span>
        <div class="sx-v bad">✗</div></div>
      <div class="sx-cellr"><span class="sx-k">ARIA conversation</span>
        <div class="sx-v bad">✗</div></div>
    </div>
    <div style="height:18px"></div>
    """
        + f'<div class="sx-note">{_aria_content.replace("<", "&lt;").replace(">", "&gt;")}</div>'
    )
    return


@app.cell
def _(convergence_report, dev_fixtures, mo, ui):
    # Pick a valid fixture for convergence testing
    _conv_fixture = next(
        (
            f
            for f in dev_fixtures
            if f.seed_plan is not None and f.fixture_id == "dev_01_valid_baseline"
        ),
        None,
    )

    if _conv_fixture:
        _conv_report = convergence_report(_conv_fixture, grids=(1.0, 0.5, 0.25))
        _conv_rows = ""
        if "results" in _conv_report:
            _conv_rows = "".join(
                f"<tr>"
                f"<td>{r.get('grid_mm', '—')}</td>"
                f"<td>{r.get('status', '—')}</td>"
                f"<td>{r.get('max_residual_mm', '—')}</td>"
                f"<td>{r.get('max_gouge_mm', '—')}</td>"
                f"<td>{r.get('sampling_error_bound_mm', '—')}</td>"
                f"<td>{r.get('elapsed_s', '—'):.3f}</td>"
                f"</tr>"
                for r in _conv_report["results"]
                if "error" not in r
            )

        mo.Html(
            ui.section(
                "Grid convergence report",
                ("Fixture", _conv_fixture.fixture_id),
                ("Resolutions", "multiple"),
            )
            + f"""
        <div class="sx-note" style="margin-bottom:14px">
          <b>Why convergence matters.</b> The residual and gouge thresholds must be
          justified by data, not asserted. This report shows how the measured values
          change with grid resolution, and includes the sampling error bound so the
          chosen thresholds account for discretization.
        </div>
        <table class="sx-table">
          <thead><tr>
            <th>Grid (mm)</th>
            <th>Status</th>
            <th>Max Residual (mm)</th>
            <th>Max Gouge (mm)</th>
            <th>Sampling Error Bound (mm)</th>
            <th>Elapsed (s)</th>
          </tr></thead>
          <tbody>{_conv_rows}</tbody>
        </table>
        """
        )
    else:
        mo.Html(
            ui.section("Grid convergence report", ("Status", "no suitable fixture found"))
            + '<div class="sx-note">No fixture with a seed plan available for convergence testing.</div>'
        )
    return


@app.cell
def _(Telemetry, mo, ui):
    _telemetry = Telemetry.from_env()
    _telem_status = _telemetry.status()

    _weave_status = "✓" if _telem_status.weave == "enabled" else "✗"
    _weave_color = "ok" if _telem_status.weave == "enabled" else "bad"
    _wandb_status = "✓" if _telem_status.wandb == "enabled" else "✗"
    _wandb_color = "ok" if _telem_status.wandb == "enabled" else "bad"

    mo.Html(
        ui.section("Sponsor integrations", ("Covering", "W&B Inference, Weave, ARIA"))
        + f"""
    <div class="sx-readout">
      <div class="sx-cellr"><span class="sx-k">Weave</span>
        <div class="sx-v {_weave_color}">{_weave_status} {_telem_status.weave}</div></div>
      <div class="sx-cellr"><span class="sx-k">W&B</span>
        <div class="sx-v {_wandb_color}">{_wandb_status} {_telem_status.wandb}</div></div>
      <div class="sx-cellr"><span class="sx-k">Detail</span>
        <div class="sx-v">{_telem_status.detail or "—"}</div></div>
      <div class="sx-cellr"><span class="sx-k">Weave URL</span>
        <div class="sx-v">{_telem_status.weave_url or "—"}</div></div>
      <div class="sx-cellr"><span class="sx-k">Run URL</span>
        <div class="sx-v">{_telem_status.run_url or "—"}</div></div>
    </div>
    <div style="height:14px"></div>
    <div class="sx-note">
      <b>Current status.</b> Telemetry is <b>{_telem_status.wandb}</b>. When a W&B
      API key is configured, job runs will be logged to W&B with Weave traces, and
      batches can be uploaded for ARIA analysis. Until then, all evaluation is local
      and offline.
    </div>
    """
    )
    return


@app.cell
def _(mo, ui):
    mo.Html("<div style='height:26px'></div>" + ui.LIMITATIONS)
    return


if __name__ == "__main__":
    app.run()
