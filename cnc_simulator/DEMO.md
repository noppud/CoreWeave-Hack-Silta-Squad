# Measured two-loop demo

Open **http://127.0.0.1:2743/loop.html**. Select the hydraulic manifold and step through its measured reference failure, saved check, CAM repair, passing simulation and timing-judge feedback. The machine panel uses the actual candidate's cutter-sweep stock when that candidate has a playback asset; otherwise it explicitly identifies the best-plan replay. The machine's playback clock is accelerated and separate from the event stepping.

The agreed Mermaid diagram was verified on `origin/main` at `38136d1:docs/loop.md`; the original is preserved in `references/agreed-loop.md`. Joel's latest reviewed GitHub work on `origin/toukoversion` is `1b1980d23bcdefdf3986363d6055b84327f4dbac`, “Add standalone interactive learning-loop demo.” It adds a standalone HTML storyboard with 54 scripted examples and two return routes. Its original source and README are preserved under `references/joel-demo/`. The measured demo adapts those routes; it does not import the scripted outcomes or claim Joel's presentation was connected to simulation.

## Why the earlier manifold kept failing

The previous compiler offset intersecting pockets independently. Conservative swept stock remained possible at the junction, so the numerical check returned false. The model was only allowed to change parameters such as feed and stepover; it had no junction-cleanup operation. A separate controller bug initially aborted a part on a failed reference. Parameter-only retries were therefore ineffective. Original failures are preserved in `workspace-indexed-five/`.

The compiler now supports `junction_cleanup: true`: it unions compatible same-orientation pockets at common depths, erodes the union by the smaller cutter radius plus clearance, and emits explicit plunge/retract cuts in the junction regions. These are full modeled cuts with timing and collision checks. The target, stock, machine and tolerance remain unchanged. The new manifold passes.

## What follows the diagram

See [the Mermaid contract](LOOP-CONTRACT.md). CAM compiles before the test gate. Test failure returns to CAM. Simulation failure saves an exact failed-configuration check plus repair observation, then returns through the gate to CAM. Only passing simulation reaches the judge. A request to improve saves timing-only guidance before the next CAM request. The judge has no geometry or toolpath inputs and cannot design an operation.

Failure checks use exact fixed-input/geometry-strategy/compiler/verifier fingerprints. They can block feed-only repeats, not generalize a rejection to a different part. Other diagnostic memories are advisory. New paths always need full simulation. This is a bounded implemented learning mechanism, not unrestricted agent-written test-code evolution or model training.

## Run / inspect

From this folder, with the dependencies in INDEXED.md installed:

```sh
.venv/bin/python scripts/serve_indexed.py --workspace workspace-loop-demo --port 2743
.venv/bin/python scripts/audit_indexed_run.py workspace-loop-demo
```

For a fresh five-part sequence, use `camloop.indexed prepare --count 5` then `sequential --attempts 3` as documented in INDEXED.md. Every application model role requests Astra fast tier and low reasoning. The simulation itself has no model calls. Run `scripts/export_indexed_videos.py WORKSPACE`, open its served study page and click Record all five videos, then run `scripts/encode_indexed_videos.py WORKSPACE` to obtain MP4s and a combined reel. Stock playback assets are namespaced by workspace name, preserving prior studies.

`workspace-loop-demo/` contains the new measured run. `learning-check-audit/receipt.json` records the 24.8 ms preflight rejection of the earlier failed geometry when only feed changed. `tests.log` records 60 passing tests. `memory/versions/` and immutable commit snapshots prove persistence. `runs/*/feedback-memory.json` records immediate within-part feedback. `results.json` contains timing and paired memory comparisons. No geometry failure is scored as a success.

## Demo limits

Indexed 3+2, flat-end tools and explicit capsule/circular catalog features. The machine really tilts and indexes; it is not simultaneous five-axis cutting or arbitrary-CAD CAM. The display uses the downloaded Haas UMC-750 model. One-millimetre stock cells and 3 mm demonstration tolerance do not certify production precision. Workholding is simplified, full-machine self-collision and cutting physics are not modeled, and timing assumes constant commanded speeds.
