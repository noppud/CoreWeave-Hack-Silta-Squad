# Tomorrow's demo

[Portable demo kit](release/silta-demo-kit.zip): film, complex machining reel, raw evaluations, ARIA ablation, hosted-check evidence, source archive and an offline guide. All 26 archived files were read back and verified.

Open [the live workspace](http://127.0.0.1:2744/workspace.html). Upload the example PDF, review its dimensions, and start the job immediately. Show the benchmark evidence while it runs, then return to the actual generated CAM and stock-removal playback. Keep the raw terminal alongside the viewer.

- [Three-minute rehearsal](REHEARSAL.md): spoken sequence and completed-run fallback when inference is pending.
- [116-second film](film/silta-demo.mp4): 1080p, silent with selectable embedded English captions; actual machining recordings and observed evidence, with edited waiting time clearly labeled.
- [Film narration](film/NARRATION.md).
- [Recorded Bearing run](http://127.0.0.1:2744/workspace.html?job=3f1703103c1f): 80.745 → 25.852 estimated seconds; memory 12 → 13; exact supplied instructions, responses, CAM, checks, memory snapshots, and completed trace readback retained.
- [New indexed shell playback](http://127.0.0.1:2744/housing.html?part=11-indexed-instrument-shell--attempt-0&study=workspace-transfer-preview&embed=1): preselected first warm trial, not best-of-study selection.

- [Latest updated-server rehearsal](http://127.0.0.1:2744/workspace.html?job=99006bbab905): Instrument, 125.518 → 27.264 estimated seconds, three passing attempts, memory 13 → 14. Trace readback and local preflight passed. The full automated suite passed 75 tests, including four orchestration recovery cases.

[Organizer refresh](ORGANIZER_REFRESH.md) confirms the current public schedule. [Judge Q&A](JUDGE_QA.md) separates demonstrated results from unsupported claims.

## What to demonstrate

1. Frozen geometry → CAM proposal → compiler/checks → stock-removal simulation → timing judge → feedback memory → another CAM proposal. The judge evaluates passing plans; CAM chooses changes.
2. Three new complex parts, all passing reference/best pairs: 4548.57 → 1250.26 estimated seconds, **72.5% reduction**. After judge feedback, carrier 531.04 → 496.79 seconds (6.4% further improvement); manifold ties; drum gets slower and retains its earlier best. The earlier five-part study and failed manifold repair remain separate evidence.
3. A useful, bounded memory behavior: selected five-case failure audit catches two repeated invalid plans, preserves two valid controls, and abstains on a changed-fixture invalid plan. Exact-key checks also ran in a hosted sandbox with network disabled and no guest credentials.
4. ARIA advises experiments. Twelve requested cases were actually simulated; cleanup repaired the manifold but did not rescue the high-stepover cage. Hashes expose only five distinct effective paths among those twelve settings.
5. Transfer is measured separately: **24 fresh plans across four parts**, all pass, but no general memory-driven speed benefit. The two pre-registered new geometries were essentially tied or slightly slower with memory. Show this as an evaluation result, not a learning success.

## Evidence

[Memory persistence audit](memory-chain-audit.md): nine completed jobs across two drawing types, eight consecutive links, saved-byte hashes and actual first-CAM request memory verified. Seven older jobs lack an extra per-job copy; their versioned memory and commit receipts are present. This establishes persistence and use as model input, not a causal timing benefit.


- [Best-plan scored evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09946-a67c-725a-a493-466e6a3905da): 5/5 passing selected plans.
- [Reference evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09946-9f30-7b13-bb9a-97f7a9ab0c93).
- [Failure-memory evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09947-299f-70cd-bf7d-3236720f2c4a).
- [ARIA ablation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09947-aa19-771b-b36f-bac00cd3e5c1).
- [Hosted checks](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09937-99b3-7bbe-a02c-ccef3b06f806).
- [Actual live trace](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09950-08eb-78f2-886c-22c645c1774a).
- [Repeated selected-part transfer report](repeated-memory-study/REPORT.md).
- [Pre-registered new-geometry transfer report](new-geometry-memory-study/REPORT.md).
- [Numerical failure diagnostics](STOCK_DIAGNOSTICS.md).

Weave evaluations score retained files; their publication runtime is not fresh simulator runtime. Actual live traces contain running-stage spans. Other team catalog/Fusion traces are separate execution paths.

## Commands from the repository root

```sh
cnc_simulator/.venv/bin/python cnc_simulator/competition/demo_preflight.py
cnc_simulator/.venv/bin/python cnc_simulator/competition/live_terminal.py JOB_ID
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID prompt --attempt 0
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID cam --attempt 0
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID checks --attempt 0
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID memory
```

After checking that no job is active, restart the traced local service with the scoped vault launcher:

```sh
/Users/touko/.local/bin/hsec status
/Users/touko/.local/bin/hsec exec --only COREWEAVE_WANDB_API_KEY -- cnc_simulator/.venv/bin/python cnc_simulator/competition/serve_traced.py
```

The downloaded UMC-750 machine is present: 58 mesh components with B/C/X/Y/Z/spindle/static groups; provenance hashes and playback-buffer bounds are checked by preflight. The viewer runs separately from Fusion.

## Scope and remaining gaps

Indexed 3+2, flat-end mills, 1 mm cells and 3 mm demo tolerance. PDF intake supports reviewed text-dimensioned vertical circular/obround blind pockets; complex showpieces use structured indexed inputs. No simultaneous five-axis, arbitrary drawing reconstruction, physical cutting-force validation, or controller-accurate timing.

Unresolved numerical cases do not pass. The initial 0.5 mm attempt exceeded its two-million-cell cap. A new, predeclared run with a four-million-cell cap completed: the manifold passes at 0.5 mm, while the high-stepover cage remains unresolved. Plans and machining times were unchanged. See `resolution-refinement/REPORT.md`; this is a numerical refinement result, not a CAM speedup or physical measurement.

Deterministic diagnostic outputs are recorded in Weave. Native Signals remains unconfigured for this engine because its exposed inference runtime does not offer Astra; the user's runtime preference clarification is pending. No claim that native Signals fired.

Submission draft is local. Actual event submission, roster details, and external judge access remain unverified. The main checkout keeps the simulator untracked, but a clean local review branch `codex/programmatic-cnc-demo` now contains commit `a054a16` (87 files, simulator only). It has not been pushed or merged; the public repository alone still does not deliver it. `release/programmatic-cnc.bundle` and `.patch` are verified local handoff artifacts. `release/simulator-source.tar.gz` and its per-file hash manifest provide a prepared handoff with the live viewer and UMC geometry, not a published deployment. Clean-install instructions are in `release/README.md`. Preflight checks local readiness, not those external outcomes.

## Completed: three complex indexed parts

All three frozen targets completed reference simulation and two Astra CAM revisions each; all nine plans passed the configured gates. Carrier: 1984.7 → 496.8 s (26 features, 13 orientations); manifold: 821.1 → 309.4 s (19 features, 5 orientations); staggered drum: 1742.7 → 444.1 s (26 features, 17 orientations). Memory versions progressed 14 → 15 → 16 → 17. This is a complexity stress test, not a controlled memory-benefit result.

Open http://127.0.0.1:2746/study.html for individual videos, raw CAM attempts and interactive stock replay. The fully decoded 89.96-second reel is `../workspace-complex-three/videos/three-complex-parts.mp4`; full results are `../workspace-complex-three/RESULTS.md`. Weave reference/best evaluations were read back complete; receipt: `../workspace-complex-three/weave-publication.json`. Geometry uses indexed 3+2, 1 mm cells and 3 mm demo tolerance; time is a constant-speed estimate.

Latest fresh browser rehearsal: [469436bb78a7](http://127.0.0.1:2744/workspace.html?job=469436bb78a7), Bearing Pocket 80.745 → 25.852 estimated seconds; two tied passing proposals, main memory 14 → 15, completed trace readback. Drawing review, CAM projection, moving-stock replay and final stock inspected. Evidence: `rehearsal-06/receipt.json`. This is separate from complex-study memory 14 → 17.
