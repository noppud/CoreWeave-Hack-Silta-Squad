# Silta CNC: three-minute judge demo

## Start and preload

From the repository root, run:

```sh
make present
```

Open these before the timer starts:

- **Slides:** http://localhost:8010/slides.html — five slides, arrow-key navigation and Fullscreen. Reload any previously opened deck tab.
- **Pitch guide:** http://localhost:8010/guide.html — this script rendered as a browser page, rebuilt by `make present`.
- **Presenter notebook:** http://localhost:2732 — wait for CAD and both runs to finish, then leave **1 · The part** selected.
- **Eval evidence:** http://localhost:8010/evals.html — measured policy comparison, every fixture outcome, raw JSON and source hashes.
- **Interactive eval notebook:** http://localhost:2733 — preloads the policy comparison; keep for Q&A.
- **Optional W&B evidence tab:** https://wandb.ai/silta/coreweave-hack-silta-squad/runs/c3cxveft — use Charts for recorded metrics; confirm it opens with the presenter's account before using it on stage.

The launcher returns when all three servers respond and leaves them running. Repeating `make present` safely reuses them. The notebooks need the project's installed `.venv`, but their fixture workflows require no inference key or network. The slides embed their drawing and QR code and work offline. The QR opens the public product, which needs internet.

The presenter notebook deliberately fixes the candidate proposals for reproducibility. CAD, checks, compilation, simulation and memory storage run for real. It creates fresh isolated memory for each presentation session, so another judge's warm run cannot erase your failure story. It constructs a new controller and storage adapter for the second run to prove disk recall.

## Run of show

| Time | Screen and action | Say |
|---|---|---|
| 0:00–0:15 | Slide 1 | “Silta turns a part drawing and the shop's available tools into a machining plan. The target stays fixed while the system repairs the process.” |
| 0:15–0:30 | Slide 2 | “Checks and simulation give the planner concrete failure evidence. Memory retains the attempt and a passing recipe. Every reused recipe must be verified again.” |
| 0:30–0:45 | Notebook, **1 · The part**. Drag once. | “For this repeatable demo, candidate plans are scripted. The CAD, checks, simulation and memory run here. Our full workbench also supports live inference.” |
| 0:45–1:15 | **2 · The collision**, press **Play** | “The first tool was too short. The longer tool reaches, but its traverse hits the clamp. The simulator records where that happened.” |
| 1:15–1:30 | **3 · The repair** | “Raising clearance fixes the process. The repaired plan passes the same checks and a fresh simulation.” |
| 1:30–1:45 | **4 · Memory**, point to comparison | “A new controller recalls the passing recipe from disk: three attempts become one, with fresh verification.” |
| 1:45–2:20 | Slide 3: eval table | “We also test the checks on twelve existing fixtures: eight development and four regression cases. Both policies match every expected outcome, including correct rejections. The revised clamp check catches the collision before simulation: four development simulations become three. Regression results stay unchanged. These are validator evals with fixed plans, not a model-quality benchmark.” |
| 2:20–2:40 | Slide 4: memory | “Memory improves this repeated job by reusing evidence. That is separate from the policy improvement. We are reusing a verified recipe, not training model weights.” |
| 2:40–3:00 | Slide 5: QR | “Marimo lets you inspect the part and checks. W&B records live-run metrics. Scan this to try the product. We also have the case-by-case eval report ready for questions.” |

The schedule includes time for clicks and collision playback. At **2:40**, move to slide 5 even if a detail remains open. Keep the W&B and interactive eval notebooks for Q&A so network latency does not consume the pitch.

## Eval evidence and reproduction

The current presentation snapshot replays the existing corpus under `policy-v0` and `policy-v1`: development matches **8/8 → 8/8**, simulations **4 → 3**; regression matches **4/4 → 4/4**, simulations **2 → 2**. Zero false accepts and false rejects were observed under either policy. Twelve synthetic fixtures do not establish general reliability. The four regression cases remain in the `fixtures/holdout` directory, but retained lineage says an earlier fix used `holdout_03_valid_complex`. Treat them as regression coverage, not a blind holdout.

To refresh the measured report and embed it in the deck:

```sh
.venv/bin/python scripts/build_demo_evals.py
.venv/bin/python scripts/build_demo_slides.py
make present
```

`demo/evals.json` retains every outcome, the measurement timestamp, and hashes of the fixture and Python source files. The deck reads this file when built; it never invents scores or reruns inference on stage.

## What to leave out of the timed path

- Do not start an unconstrained model run or provision a sandbox during the three minutes. They are available from the full workbench but have variable latency.
- The presenter fixture does not demonstrate new model training. It demonstrates repair, durable evidence and recipe reuse with fresh verification.
- W&B Charts contains live-run metrics. CNC stage traces are not yet exported to Weave, and the Logs tab does not contain the detailed repair story. Use the notebook to inspect that evidence.
- W&B Sandbox authentication currently fails with the configured credentials. The adapter and regression gate exist, but do not claim a live sandbox pass or active sandbox-validated lesson.
- ARIA analysis has no verified completed conversation in the retained evidence. Do not credit the fixture repair or memory result to ARIA. Keep that discussion for Q&A once its actual analysis is available.

## Recovery lines

- **Animation or WebGL fails:** open **Inspect the measured checks** and continue from the recorded collision values. All results come from the same executed fixture.
- **Notebook says “kernel not found” or “Reconnect to app”:** reload the page or open http://localhost:2732/ in a new tab. Wait for the CAD to appear and leave **1 · The part** selected. An old tab can retain a disconnected session even while the server is healthy.
- **Notebook was not preloaded:** leave slide 2 up while it prepares. If it takes more than ten seconds, continue with slides 3 and 4's measured comparisons and offer the live product.
- **W&B tab asks for login:** skip it immediately. Do not log in on stage.
- **Wi-Fi fails:** the local slides and presenter notebook still work. The public QR becomes useful when connectivity returns.
- **A real live run fails:** say “The system did not find a passing plan within its budget.” Keep that evidence visible. The reproducible presenter notebook remains a separate, explicitly labeled demonstration.

## Files

- `demo/slides.html`: editable, self-contained browser deck.
- `notebooks/demo.py`: focused interactive demonstration.
- `silta/demo.py`: preparation of the actual cold and warm fixture runs.
- `scripts/start_presenter.sh` and `scripts/start_presenter.py`: start or reuse all three local presentation servers.
- `scripts/build_demo_evals.py`: refresh the offline eval report and raw evidence.
- `scripts/build_demo_slides.py`: rebuilds the deck from the repository drawing and QR URL.
- `scripts/demo_memory.py`: terminal-only reproduction of the three-attempt versus one-attempt result.

Browser rehearsal verified all four notebook steps: collision playback stopped at `s0005`, the repair opened at playhead 1.0, and the memory comparison displayed Cold `3 / 2 / 2` versus Warm `1 / 0 / 1` for attempts / planner calls / fresh simulations. Both browser slides were visually checked. The opening slide and notebook step 1 were left selected.
