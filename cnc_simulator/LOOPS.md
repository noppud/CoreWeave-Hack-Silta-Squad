# Updated loop contract

CAM agent builds movements → cheap checks → simulation **pass/fail** → timing judge.
Failure returns to CAM. The judge receives only passing time summaries and decides
accept or try faster. It has no CAD or toolpaths and cannot prescribe them. A request
to try faster returns to CAM, which builds a fresh candidate and repeats both gates.
Judge timing memories pass evaluation before reuse. The target stays fixed.

`passed: false` includes numerical clearance that cannot be verified; that reason is
retained as `verification: unresolved`. The loop never accepts it or exposes a third
simulation decision. Older run artifacts may contain the superseded `unknown` label.

Ten different pocket topologies are available through `camloop benchmark`. Multi-pocket
jobs use `family: pocket_set` and `feature.pockets`, a union of accepted capsule/circular
removals. This is trusted feature input, not arbitrary CAD feature recognition.

MP4 export: `python scripts/render_machining_video.py <playback.json> <output.mp4>`.
Install the `report` extra. Videos reconstruct nominal voxel top surfaces and vertical
walls and the actual XYZ trajectory; they are suitable for the top-access benchmark.
`render_benchmark_videos.py <workspace>` exports each retained passing plan and a reel.

# Silta with the programmatic simulator

This is a runnable local version of the agreed loops. The original Fusion code is
unchanged. `cncsim/` remains deterministic; `camloop/` owns Astra, orchestration,
cheap checks, evaluation and persistence. `viewer/` reads the actual run artifacts.

## Start

Use Python 3.12 for the combined application. From `cnc_simulator/`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test,agent]'
npm --prefix viewer ci
npm --prefix viewer run build
.venv/bin/python -m camloop prepare --workspace workspace
.venv/bin/python -m camloop serve --workspace workspace --port 2731
```

Open **http://127.0.0.1:2731/**. Select Part A and **Run Astra**. After its learning
has been evaluated, run Part B to inspect inheritance. The server binds to loopback;
it does not publish a site or operate a physical machine. The UI uses the existing
ChatGPT subscription login via the local Codex SDK; there is no API-key/model fallback.
The desktop Codex binary defaults to `/Applications/ChatGPT.app/Contents/Resources/codex`;
set `CAMLOOP_CODEX_BINARY` for another installed binary. Model is fixed to `gpt-6-astra`.
`requirements-loop-lock.txt` pins the tested combined environment.
The adapter follows the existing project's subscription pattern and the
[Codex SDK](https://learn.chatgpt.com/docs/codex-sdk).

You can also run without the viewer:

```sh
.venv/bin/python -m camloop run workspace/jobs/part-a/job.json --workspace workspace --mode astra --attempts 8
.venv/bin/python -m camloop run workspace/jobs/part-b/job.json --workspace workspace --mode astra --attempts 8
```

For a reproducible **scripted rehearsal**, explicitly pass `--mode rehearsal`.
Rehearsal calls are labelled and its active learning is isolated from live Astra
learning. No failure silently switches the application to the rehearsal adapter.
`prepare` runs real simulations to establish the evaluation labels. It refuses to
overwrite an existing corpus; choose a fresh workspace when rebuilding labels.

## The loops

1. **Freeze the accepted target and setup.** Copy the mesh inputs, retain their
   hashes, and freeze tools, geometry tolerance, grid resolution, travel limits,
   feed limits, feature description, start position and required final position.
2. **Main Astra agent → cheap checks.** The supplied initial CAM is checked first.
   The planner then returns movements only. Malformed commands, contract changes,
   excessive feeds, overtravel, missing return travel and promoted-check failures
   go back to the planner with concrete feedback.
3. **Checks → simulation → repair.** Only checked candidates reach stock removal.
   Invalid candidates return to the planner. Numerical uncertainty fails the gate;
   immutable tolerance/resolution cannot be relaxed to turn uncertainty green.
4. **Simulation → supervisor → improve/stop.** Only passing time summaries reach the
   Astra timing judge. The controller retains the least-time valid candidate,
   independently of the supervisor's claims. Improvements repeat the entire loop.
   A supervisor stop returns the incumbent. Exhausting the attempt budget or a
   model failure returns `incomplete`, with any verified incumbent retained.
5. **Evaluate reusable learning → save → next part.** A simulator failure can ask
   an Astra check learner for a missing check. A timing judge can propose transferable
   timing observations. Both are evaluated before activation. Promoted
   changes apply to subsequent attempts and are loaded by subsequent jobs.

The model returns structured JSON, never executable CAM or check code. The current
learned-check vocabulary intentionally contains one auditable operator:
`feature_floor`, scoped to accepted capsule-pocket jobs with box stock. It checks
cut endpoints in the feature that reach required stock below the tolerated floor.
It does not reject harmless deep air cuts outside the stock. The simulator remains
responsible for everything this cheap check misses. This is bounded reusable
checking, not arbitrary Python check synthesis.

## Evaluation and durable state

- The check gate replays baseline vs proposed checks on **eight frozen,
  simulator-labelled cases** spanning development Parts A and C: correct pocket,
  overdeep cut, missed material and a valid deep air-cut case for each part.
  Promotion requires at least two valid controls, **zero false rejections**, and
  at least one newly caught invalid case. Runtime is recorded.
- A guidance proposal runs the planner twice per development part with the same
  fixed inputs: current guidance and proposed guidance. Each output goes through
  checks and the real simulator. Promotion requires two proposed valid outcomes,
  no validity/time regression on previously valid cases, and a measurable gain.
  These are small paired development evaluations, not proof of generalization.
- Part B is held out of both gates. Its different pocket length/depth provides a
  concrete next-part inheritance check. It is still the same feature family.
- Evaluation records include proposals, cases/results, role evidence, verifier and
  check versions. Corpus hashes and geometry hashes are checked before reuse.
  Active state must reconstruct from its evaluated promotion history. A lock and
  base-version check prevent concurrent stale promotions. Version history remains
  on disk; no untested proposal becomes active.
- Guidance evaluations default to one per run; attempts default to five (up to 20).
  Each Astra call has a 180-second deadline. A budget limit is not proof of optimality.

State lives under the selected workspace:

```
jobs/                  accepted job inputs
corpus/                frozen labelled evaluation cases (A and C)
knowledge/astra/       evaluated live checks and guidance
knowledge/rehearsal/   separate scripted-rehearsal learning
runs/<id>/manifest.json
runs/<id>/frozen/      immutable inputs
runs/<id>/evidence/    actual Astra requests, replies and turn identifiers
runs/<id>/attempt-*/   proposals, movements, simulation output and playback
runs/<id>/best-plan.json
```

The viewer can follow a running manifest, select earlier attempts, compare times
and verdicts, and show learning promotions and the version inherited by Part B.
Model statements are displayed as text and do not control validity or scoring.

## What the visual means

The 3D view includes a schematic mill/table, cylindrical cutter, shaft and holder,
colored cut/rapid paths, target outline, actual XYZ position, time scrubber,
play/pause and playback speed. Separate Haas VF-2 and Setup views show the actual downloaded machine and prepared setup. Model runs launch
from the same UI; data and model access stay on the local Python process.

Stock removal is animated using the first continuous sweep-entry time of each
nominal voxel. Playback exports are checked against the simulator's final stock;
tests also compare every move boundary. Tool movement is interpolated from the
actual submitted trajectory. No invented chips or fake completion sequence is used.

The Workpiece playback mill and spindle rotation are illustrative. The Haas VF-2
and Setup views use 11 exported machine bodies, 19 vise/parallels bodies, the retained
soft-jaw CAD and two library-derived tool assemblies, all in millimetres. Source
hashes are checked against the existing project configuration. This is a parked
reference setup, not a full-machine collision or machining verification. A one-time
Fusion tessellation produced the local assets; viewer and simulator need no Fusion
runtime. See `assets/machine/README.md` for provenance and regeneration.
The renderer shows nominal voxels, while the simulator decides validity from
conservative lower/upper bounds. A nice animation is not a verification pass.
The optional WebMCP inspection/seek tools are feature-detected; they have not been
verified in a WebMCP-capable browser. Ordinary controls do not require them.

## Scope of this first version

The implemented entry point is an **already accepted mesh plus a trusted capsule
feature description**, not drawing/PDF-to-CAD generation. Parts A/B/C are compact
verification fixtures. Astra can change explicit linear movements, order, feeds,
dwells and allowed tool changes. The new example jobs require a fixed final XYZ
position, so candidates cannot obtain a shorter complete-cycle score by omitting
return travel. There are no extra optimization objectives.

The full soft-jaw machining job and actual setup collision verification, G-code
output, Weave tracing and remote evaluation publication are not implemented.
The downloaded machine and prepared setup are available as reference visuals. The dense grid is not yet suitable for the full soft jaw at its drawing
resolution; it fails verification on its cell budget rather than a fabricated pass.
The same simulator API accepts more general valid meshes and fixtures, but general
feature extraction/CAM strategy generation is not implemented by this first loop.
Existing Fusion results are not reclassified by this version.
