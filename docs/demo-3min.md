# SILTA CAD: three-minute judge demo

## Start and preload

From the repository root, run:

```sh
make present
```

Open these before the timer starts:

- **Main presentation:** http://localhost:2734/ — seven native marimo slides with interactive CAD, collision playback, memory and evals. Wait for the CAD slides to load, then return to the title.
- **Backup HTML deck:** http://localhost:8010/slides.html — five static slides.
- **Pitch guide:** http://localhost:8010/guide.html — this script rendered as a browser page, rebuilt by `make present`.
- **Joel’s demo notebook:** http://localhost:2732 — his four native slides: part, failure, repair and next-run evidence.
- **Eval evidence:** http://localhost:8010/evals.html — measured policy comparison, every fixture outcome, raw JSON and source hashes.
- **Interactive eval notebook:** http://localhost:2733 — preloads the policy comparison; keep for Q&A.
- **Optional W&B evidence tab:** https://wandb.ai/silta/coreweave-hack-silta-squad/runs/c3cxveft — use Charts for recorded metrics; confirm it opens with the presenter's account before using it on stage.

The launcher returns when all four servers respond and leaves them running. Repeating `make present` safely reuses them. The notebooks need the project's installed `.venv`, but their fixture workflows require no inference key or network. The slideshow uses local drawing and viewer assets and a generated QR code; its fixture runs work offline. The backup HTML deck embeds its drawing and QR code. The QR opens the public product, which needs internet.

The presenter notebook deliberately fixes the candidate proposals for reproducibility. CAD, checks, compilation, simulation and memory storage run for real. It creates fresh isolated memory for each presentation session, so another judge's warm run cannot erase your failure story. It constructs a new controller and storage adapter for the second run to prove disk recall.

## Run of show: one tab, seven slides

Use the bottom-right arrows to advance, or the keyboard arrows when the CAD canvas is not focused. The top-right fullscreen button enlarges the presentation. Stay in the marimo tab for the entire timed pitch.

| Time | Slide and action | Say |
|---|---|---|
| 0:00–0:20 | **1 · Same part. Better plan.** | “Silta turns a part drawing and the shop's available tools into a checked machining plan. This repeatable demo uses scripted proposals with real CAD, checks, simulation and memory. The workbench also supports live inference.” |
| 0:20–0:40 | **2 · Fix the target. Change the process.**, drag the CAD once | “The part stays fixed. The planner repairs how we machine it, using the available tools and fixtures.” |
| 0:40–1:15 | **3 · Reach is fixed. Clearance isn’t.**, press **Play** | “The first tool was too short. The longer tool reaches, but its traverse hits the clamp. Playback stops at the collision, and that measurement becomes repair feedback.” |
| 1:15–1:40 | **4 · A safer traverse. The same part.** | “Raising clearance to fifteen millimeters fixes the traverse. The revised plan passes fresh checks and simulation without changing the part.” |
| 1:40–2:10 | **5 · The next run starts with evidence.**, point to the table | “A new controller recalls the passing recipe from disk. Three attempts become one, but verification still runs. This is recipe reuse, not model training.” |
| 2:10–2:45 | **6 · Catch the collision earlier.** | “We also evaluate our checks on twelve fixed plans. Both policies match every expected outcome, including correct rejections. The revised clamp check catches the collision earlier: four development simulations become three. Regression results stay unchanged. These are validator evals, not a model-quality benchmark.” |
| 2:45–3:00 | **7 · Don’t just watch. Inspect it.**, leave QR visible | “Marimo makes the running notebook the presentation. You can inspect the part, checks and memory. W&B records experiments and evaluations. Scan this to try the product.” |

At **2:45**, move to the QR slide even if a detail remains open. Keep the case-by-case report, W&B and interactive eval notebook for Q&A. The QR opens the public product, not the local presentation.

## Editing and sharing the slideshow

Edit `notebooks/demo_slides.py`. Its native marimo layout is saved in `notebooks/layouts/demo_slides.slides.json`, with presentation styling in `silta/static/demo-slides-head.html`. Keep these files together in the repository. Open a fresh browser session after changing the notebook to load the updated code. `make present` reuses an already running server.

The CAD viewer uses the existing anywidget implementation, with slide-specific controls beside the model. The opening slide now uses a large interactive CAD model; the drawing is shown beside CAD on slide 2. Joel’s shared `silta/static/product.css` provides the off-white, black and red identity. The target starts in an isometric view; collision playback starts at zero; the repaired plan starts at its completed position. Mouse dragging remains interactive. Memory values come from the notebook's freshly executed fixture runs; eval values come from `demo/evals.json`.

## Eval evidence and reproduction

The current presentation snapshot replays the existing corpus under `policy-v0` and `policy-v1`: development matches **8/8 → 8/8**, simulations **4 → 3**; regression matches **4/4 → 4/4**, simulations **2 → 2**. Zero false accepts and false rejects were observed under either policy. Twelve synthetic fixtures do not establish general reliability. The four regression cases remain in the `fixtures/holdout` directory, but retained lineage says an earlier fix used `holdout_03_valid_complex`. Treat them as regression coverage, not a blind holdout.

To refresh the measured report and embed it in the deck:

```sh
.venv/bin/python scripts/build_demo_evals.py
.venv/bin/python scripts/build_demo_slides.py
make present
```

`demo/evals.json` retains every outcome, the measurement timestamp, and hashes of the fixture and Python source files. The native slideshow reads this file when its notebook session starts; the backup deck reads it when built. Neither reruns inference for these scores.

## What to leave out of the timed path

- Do not start an unconstrained model run or provision a sandbox during the three minutes. They are available from the full workbench but have variable latency.
- The presenter fixture does not demonstrate new model training. It demonstrates repair, durable evidence and recipe reuse with fresh verification.
- W&B Charts contains live-run metrics. CNC stage traces are not yet exported to Weave, and the Logs tab does not contain the detailed repair story. Use the notebook to inspect that evidence.
- W&B Sandbox authentication currently fails with the configured credentials. The adapter and regression gate exist, but do not claim a live sandbox pass or active sandbox-validated lesson.
- ARIA analysis has no verified completed conversation in the retained evidence. Do not credit the fixture repair or memory result to ARIA. Keep that discussion for Q&A once its actual analysis is available.

## Recovery lines

- **Animation or WebGL fails:** continue to the memory and eval tables. Use the backup notebook at http://localhost:2732/ or the case-by-case report at http://localhost:8010/evals.html for further evidence.
- **Notebook says “kernel not found” or “Reconnect to app”:** reload the page or open http://localhost:2734/ in a new tab. Wait for the CAD to appear and return to the title. An old tab can retain a disconnected session even while the server is healthy.
- **Notebook was not preloaded:** use the backup HTML deck at http://localhost:8010/slides.html. It includes static eval and memory comparisons while Python prepares.
- **W&B tab asks for login:** skip it immediately. Do not log in on stage.
- **Wi-Fi fails:** the local slides and presenter notebook still work. The public QR becomes useful when connectivity returns.
- **A real live run fails:** say “The system did not find a passing plan within its budget.” Keep that evidence visible. The reproducible presenter notebook remains a separate, explicitly labeled demonstration.

## Files

- `notebooks/demo_slides.py`: main seven-slide interactive presentation.
- `notebooks/layouts/demo_slides.slides.json`: native marimo slides layout.
- `silta/static/demo-slides-head.html`: presentation styling.
- `demo/slides.html`: self-contained backup browser deck.
- `notebooks/demo.py`: Joel’s four-slide native marimo demonstration.
- `silta/demo.py`: preparation of the actual cold and warm fixture runs.
- `scripts/start_presenter.sh` and `scripts/start_presenter.py`: start or reuse all three local presentation servers.
- `scripts/build_demo_evals.py`: refresh the offline eval report and raw evidence.
- `scripts/build_demo_slides.py`: rebuilds the deck from the repository drawing and QR URL.
- `scripts/demo_memory.py`: terminal-only reproduction of the three-attempt versus one-attempt result.

The fixture workflow has been verified: collision playback stopped at `s0005`, the repair opened at playhead 1.0, and the memory comparison displayed Cold `3 / 2 / 2` versus Warm `1 / 0 / 1` for attempts / planner calls / fresh simulations. The native seven-slide presentation was also visually checked at presentation viewport sizes, including CAD interaction, collision playback, completed repair, memory comparison, evals and QR.
