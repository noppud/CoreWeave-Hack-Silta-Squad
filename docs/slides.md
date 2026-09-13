# Hackathon deck

The editable marimo deck lives in `notebooks/slides.py` on `hack-slide-deck`, based on `main`.
It is a six-slide, three-minute pitch around the agreed loop. The implementation is
still being built, so the demo slide describes the planned walkthrough. The timed
speaking script is in [pitch-3min.md](pitch-3min.md).

```sh
make slides          # Present at http://127.0.0.1:2740
make slides-edit     # Edit in marimo (stop the presenter first)
make slides-export   # Export artifacts/slides.html without notebook source
```

Use `SLIDES_PORT=2741 make slides` if the default port is occupied. Use the arrow keys to
navigate. Stop the server with Ctrl-C. The commands install the pinned `slides` dependency
group through uv. The notebook itself needs no API keys, inference calls, CAD service,
or running sample-branch servers. HTML export embeds the drawing, but marimo frontend
assets may require internet access when first opening the export.

## Editing

Each output cell is one slide. Shared composition lives in `frame()`, the palette and
typography in `notebooks/assets/slides-head.html`, and presentation mode in
`notebooks/layouts/slides.slides.json`. Update the page total if adding or removing slides.

1. Project and proposed outcome.
2. Drawing, machine constraints and fixed CAD target.
3. Drawing, machine instructions, tests, simulation and judge, with retry paths.
4. Learning through validated checks and the planning playbook.
5. One-part demo walkthrough, ready to replace with a current run.
6. Intended outcome.

## Sources and boundaries

- Primary architecture reference: the whiteboard supplied by Konsta on September 12,
  saved unchanged at `notebooks/assets/agreed-loop-whiteboard.png`.
- Supporting architecture: [`docs/loop.md`](loop.md) on main at `38136d1`.
  The whiteboard's judge corresponds to the supervisor in that document.
  Its instruction list corresponds to the planning playbook. The deck preserves
  test failure and simulation failure retries, simulation time sent to the judge,
  and the judge's improve/accept decision.
- Presentation structure and cream/charcoal/red identity: `notebooks/demo_slides.py`,
  its layout JSON and `silta/static/demo-slides-head.html` on `konsta-demo-hackathon`
  at `4fbb778`.
- `notebooks/assets/sample-fixture-block.png` is an unchanged copy of that branch's
  `fixtures/demo/fixture-block-01.png`. The slide labels it as illustrative.
- Marimo's [app and slides documentation](https://docs.marimo.io/guides/apps/).

The sample branch's runtime, benchmark numbers, deployment URLs and claims of learning
are not part of this draft. Main currently contains a generic Weave starter and the
agreed CNC loop, rather than the full CNC implementation. The slides describe that
architecture as a concept until the team supplies current execution evidence.

## Next content pass

Replace slide 5 with the real initial failure and revised plan on the same CAD target.
Add measured results with units and a matching Weave trace. Connect an interactive CAD
viewer only after the current implementation is available on this branch. The final presentation duration is three minutes, confirmed by Konsta. Confirm the
project name and roster before the final copy pass.

The rehearsal allocation is 20 / 25 / 40 / 30 / 45 / 20 seconds (180 total).
