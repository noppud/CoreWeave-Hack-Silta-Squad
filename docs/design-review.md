# SILTA CAD demo design

The workbench uses an off-white page, black SILTA CAD wordmark, restrained red
accent, and a dark CAD viewport. The visual reference supplied by Joel informed
the spacing, typography and contrast.

## Review the notebooks

```sh
uv sync --locked
uv run marimo run notebooks/workbench.py --port 2742
uv run marimo run notebooks/demo.py --port 2743
```

The workbench opens an example automatically, as before. **Run settings** has
one **Run plan** submit action. Editing settings, choosing a plan, changing the
camera, and switching between **Explore** and **Present** do not start a new run.
Present shows four interactive panels for the current run and includes a fullscreen
control. Check details, downloads, learning records and scope remain accessible.

The separate presenter notebook uses Marimo's native slides layout. Use the
arrow controls or keyboard navigation to advance through part, failure, repair
and next-run evidence. It runs scripted candidate plans with actual CAD, checks
and simulation; it does not represent a live model benchmark. Reuse claims and
counts reflect the returned runs. Include `notebooks/layouts/demo.slides.json`
when deploying or sharing this notebook.

The existing Dockerfile copies both notebooks, their layout directory, and
`silta/static/product.css`. Its default command serves the workbench, including
the Present switch. A Git commit alone does not update Cloud Run: rebuild and
deploy the container using the team's configured deployment access.

## Copy and interaction changes

- Technical metadata is in Run details, rather than the header.
- Prototype check status is used consistently; there is no manufacturing approval claim.
- Check counts are labelled as checks, not independent evaluations.
- The failure view uses the actual failing diagnostic, including runs with no failure.
- Camera and playback controls are tucked into options menus. Target-only geometry
  hides playback controls because there is no machining animation to inspect there.
- Settings are submitted as a form so one click starts one requested run.
- Advice validation is in Learning, with pending/unavailable states retained.
- Full evidence and limitations remain available in expandable sections.
