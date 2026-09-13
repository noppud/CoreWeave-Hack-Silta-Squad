# Five-part indexed machining experiment

Open http://127.0.0.1:2742/study.html for the measured run, videos, CAM attempts, timing decisions and saved memories. The implementation lives entirely in this folder and is independent of the existing Fusion integration.

## Run a fresh sequence

From this folder:

```sh
uv venv --python 3.12
uv pip install -e '.[test,report,agent]'
.venv/bin/python -m camloop.indexed prepare --workspace workspace-new --count 5
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m camloop.indexed sequential --workspace workspace-new --attempts 3
.venv/bin/python scripts/export_indexed_videos.py workspace-new
.venv/bin/python scripts/serve_indexed.py --workspace workspace-new --port 2742
```

The CAM roles require an authenticated Codex subscription session. Every application model call requests `gpt-6-astra`, fast service tier, and low reasoning. There is no model fallback or fabricated model output. The standalone `cncsim` API has no model calls.

Open the study page and click **Record all five videos**. The browser automatically captures available parts sequentially at 1920×1080, 30 fps, 30 seconds each. Run this in another terminal to encode MP4s and assemble the reel:

```sh
.venv/bin/python scripts/encode_indexed_videos.py workspace-new
```

Display assets are namespaced under `assets/study/<workspace-name>`; use distinct workspace names to preserve earlier studies. Video capture requires the study page to remain open. Recordings are accelerated replays, not real-time controller predictions. Intermediate verifier stock is saved as NPZ; final verifier stock as mesh; the display additionally exports smooth Boolean stock derived from actual cutter sweeps. Display meshes never determine a pass.

## What the loop does

1. Freeze the independently built target and stock meshes and hash them.
2. CAM selects cutting parameters and operation ordering. A deterministic compiler creates explicit movements from the catalog's capsule/circular features.
3. Run input, immutable-contract and travel checks, then actual conservative stock-removal simulation.
4. A failed simulation goes back to CAM. Numerical unresolved geometry is `passed: false`; it cannot reach the judge.
5. A passing result reaches a timing-only judge. Its input contains seconds, timing breakdown and budget, with no part geometry or CAM strategy. CAM independently proposes subsequent strategies.
6. Retain the fastest passing plan. Persist the observed episode and an explicitly unvalidated learner note, verify the saved file by reading it back, and reload it before the next part. Save failures too.

The parameter compiler is not a general arbitrary-CAD CAM system. The original run lacked junction cleanup, so parameter-only retries could not repair the manifold. The current compiler adds `junction_cleanup`; see DEMO.md for the new successful repair run. It still cannot infer arbitrary new feature types. A failed reference no longer prevents repair attempts. There is no scripted improvement curve.

## Delivered run and evidence

`workspace-indexed-five/results.json` and `RESULTS.md` contain measured outcomes. Five distinct parts ran in order: actuator housing, hydraulic manifold, bearing block, six-window trunnion cage, flanged sleeve. The first manifold reference exposed an early-abort bug. After fixing the controller, it received three real CAM repair attempts following part five. All three still failed. The original manifest remains in `runs/02-hydraulic-manifold/original-manifest.json`; recovery evidence is under `recovery/`.

Memory versions 0 through 5 preserve the original sequence; version 6 adds recovery. Each `memory/commit-*.json` hashes an immutable source snapshot and the saved memory. These are application memories, not model weight updates. Initial paired proposals on three later parts test memory transfer: cold 2/3 valid, warm 3/3 valid. Among the two jointly valid pairs, warm was 0.108 seconds faster on one and 7.518 seconds slower on the other. This small unseeded comparison does not establish general learning effectiveness. The recovered manifold is not counted as a new independent part or paired trial.

## Supported machine and limits

The viewer uses the downloaded Autodesk Haas UMC-750 Reboot model, including its articulated XYZ/B/C groups. Original files and provenance are in `assets/umc750/`. Fusion was used once to convert the downloaded model; it is not a runtime dependency.

This is **indexed 3+2**, with stationary orientation during each linear cutting move and B/C repositioning at park. It is not simultaneous five-axis milling. The part remains in one canonical stock frame across indexing; rotary motions are checked conservatively. Flat cylindrical end mills, shaft, holder, fixture and configured axis limits are modeled. The machine's enclosure and complete mechanical assembly are visual context, not a full self-collision certificate. Workholding is a simplified pedestal.

The demonstration uses 1 mm cells and 3 mm tolerance, deliberately coarse and unsuitable for certifying precision production parts. Constant vector cutting/rapid speeds, dwell, tool-change duration and index speed/settle are counted. Controller acceleration, physical feed feasibility, forces, chatter, finish and wear are not modeled or scored. The original three-axis API and its pocket tests are documented in README.md. No G-code dialect is supported.
