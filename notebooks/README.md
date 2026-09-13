# CNC loop storyboard

A runnable marimo presentation prototype for the [final plan](../docs/plan.md). Includes a Three.js machine view, six loop stages, an illustrative collision and completed drilling replay, tool availability toggle, orbit/scrub/play controls, and analytically calculated example time/cost charts.

This is a storyboard, not the finished CNC agent or geometry verifier. It does not call models or consume inference credits. Learning charts intentionally contain no invented benchmark data. Example times use synthetic motion rates; they are not measured cutting results. Stock holes are revealed at the end of each illustrative cut, not computed with material-removal physics.

```sh
uv run --no-project --with marimo==0.24.2 --with anywidget==0.11.0 marimo run notebooks/loop_storyboard.py --host 127.0.0.1 --port 2718
```

For editing, replace `run` with `edit`. The widget imports pinned Three.js 0.180.0 modules from esm.sh, so its first load requires network access. Vendor these dependencies before relying on an offline stage demo.

The production app should replace sample queues with the motion events and stock snapshots from the same verifier that approves the plan. Existing starter code and project dependencies were left intact; notebook dependencies are declared inline.
