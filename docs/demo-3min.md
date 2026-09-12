# Silta CNC: three-minute judge demo

## Start and preload

From the repository root, run:

```sh
make present
```

Open these before the timer starts:

- **Slides:** http://localhost:8010/slides.html — two slides, arrow-key navigation and Fullscreen.
- **Pitch guide:** http://localhost:8010/guide.html — this script rendered as a browser page, rebuilt by `make present`.
- **Presenter notebook:** http://localhost:2732 — wait for CAD and both runs to finish, then leave **1 · The part** selected.
- **Optional W&B evidence tab:** https://wandb.ai/silta/coreweave-hack-silta-squad/runs/c3cxveft — use Charts for recorded metrics; confirm it opens with the presenter's account before using it on stage.

The launcher returns when both servers respond and leaves them running. Repeating `make present` safely reuses them. The notebook needs the project's installed `.venv`, but its fixture workflow requires no inference key or network. The slides embed their drawing and QR code and work offline. The QR opens the public product, which needs internet.

The presenter notebook deliberately fixes the candidate proposals for reproducibility. CAD, checks, compilation, simulation and memory storage run for real. It creates fresh isolated memory for each presentation session, so another judge's warm run cannot erase your failure story. It constructs a new controller and storage adapter for the second run to prove disk recall.

## Run of show

| Time | Screen and action | Say |
|---|---|---|
| 0:00–0:20 | Slide 1 | “Silta turns a part drawing and the shop's available tools into a machining plan. The part stays fixed. When a check finds a problem, we repair the process and keep the evidence for the next job.” |
| 0:20–0:45 | Notebook, **1 · The part**. Drag the CAD model once. | “This is our demonstration part. For a repeatable demo, the candidate proposals are fixed. The CAD, geometry checks, simulation and memory writes execute here. The full workbench also makes live model calls.” |
| 0:45–1:20 | **2 · The collision**. Press **Play**. Wait for the collision stop. Open **Inspect the measured checks** if time permits. | “The first tool was too short. A longer tool fixes reach, but the traverse hits this clamp. The simulator records the segment and the measured collision. That evidence goes back into repair and into memory.” |
| 1:20–1:45 | **3 · The repair**. The final stock view opens automatically. | “The repaired recipe raises clearance. We run the same checks and simulation again. This attempt passes. We changed the process, while the target design stayed fixed.” |
| 1:45–2:25 | **4 · Memory**. Point to the comparison table. Open **Inspect stored memory** briefly. | “Now a new controller reads what the first run stored. Three attempts become one, with no new planner call. It still performs fresh checks and simulation. Each recipe and lesson has source evidence. Advice stays pending until its validation passes.” |
| 2:25–2:40 | Preloaded W&B run, or stay on the notebook if the tab is unavailable. | “W&B records our live agent experiments. Marimo makes the model, checks and stored learning inspectable. Judges can examine the evidence instead of taking our success label on trust.” |
| 2:40–3:00 | Slide 2. Leave the QR visible. | “The result is a process that remembers a verified repair and verifies it again when reused. Scan this to open the live product, rotate the part and inspect a run yourself.” |

Approximate spoken copy: 290 words. The remaining time covers clicks, the collision animation and the tab switch. At **2:40**, move to slide 2 even if a detail remains open.

## What to leave out of the timed path

- Do not start an unconstrained model run or provision a sandbox during the three minutes. They are available from the full workbench but have variable latency.
- The presenter fixture does not demonstrate new model training. It demonstrates repair, durable evidence and recipe reuse with fresh verification.
- W&B Charts contains live-run metrics. CNC stage traces are not yet exported to Weave, and the Logs tab does not contain the detailed repair story. Use the notebook to inspect that evidence.
- W&B Sandbox authentication currently fails with the configured credentials. The adapter and regression gate exist, but do not claim a live sandbox pass or active sandbox-validated lesson.
- ARIA analysis has no verified completed conversation in the retained evidence. Do not credit the fixture repair or memory result to ARIA. Keep that discussion for Q&A once its actual analysis is available.

## Recovery lines

- **Animation or WebGL fails:** open **Inspect the measured checks** and continue from the recorded collision values. All results come from the same executed fixture.
- **Notebook says “kernel not found” or “Reconnect to app”:** reload the page or open http://localhost:2732/ in a new tab. Wait for the CAD to appear and leave **1 · The part** selected. An old tab can retain a disconnected session even while the server is healthy.
- **Notebook was not preloaded:** leave slide 1 up while it prepares. If it takes more than ten seconds, present slide 2's measured comparison and offer the live product.
- **W&B tab asks for login:** skip it immediately. Do not log in on stage.
- **Wi-Fi fails:** the local slides and presenter notebook still work. The public QR becomes useful when connectivity returns.
- **A real live run fails:** say “The system did not find a passing plan within its budget.” Keep that evidence visible. The reproducible presenter notebook remains a separate, explicitly labeled demonstration.

## Files

- `demo/slides.html`: editable, self-contained browser deck.
- `notebooks/demo.py`: focused interactive demonstration.
- `silta/demo.py`: preparation of the actual cold and warm fixture runs.
- `scripts/start_presenter.sh` and `scripts/start_presenter.py`: start or reuse both local presentation servers.
- `scripts/build_demo_slides.py`: rebuilds the deck from the repository drawing and QR URL.
- `scripts/demo_memory.py`: terminal-only reproduction of the three-attempt versus one-attempt result.

Browser rehearsal verified all four notebook steps: collision playback stopped at `s0005`, the repair opened at playhead 1.0, and the memory comparison displayed Cold `3 / 2 / 2` versus Warm `1 / 0 / 1` for attempts / planner calls / fresh simulations. Both browser slides were visually checked. The opening slide and notebook step 1 were left selected.
