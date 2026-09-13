# Three-minute live rehearsal

Open the live workspace at http://127.0.0.1:2744/workspace.html. Keep the terminal beside the machining view. Use the example intake for an actual new job; confirm dimensions before execution. Read the real job id from the URL and run:

```sh
cnc_simulator/.venv/bin/python cnc_simulator/competition/live_terminal.py JOB_ID
```

Start the PDF job at the beginning, immediately after reviewing the dimensions. Let it run while showing the measured evidence; return to its actual state during the live-system segment. This gives the model more time without staged progress.

## Spoken sequence

**0:00–0:20 — The job.** “A factory needs the same correct part made faster. We freeze the geometry and let the agent change the manufacturing plan.” Upload the example PDF, review its dimensions, and start the job now. “Checks and stock-removal simulation decide whether a plan passes. Only then does the timing judge ask whether we should try faster.”

**0:20–0:55 — The evidence.** Show the paired chart. “Across three new complex parts, all reference and best plans pass: 75.8 to 20.8 estimated minutes, a 72.5% reduction. We separately retain an earlier failed manifold and its repair.” Times assume constant speeds, not a physical controller.

**0:55–1:20 — The useful memory.** “After a failed manifold plan, the system saves its exact failure condition. We freshly simulated five cases: the check catches both repeated failures, retains both valid controls, and leaves the changed setup for full simulation.” Show the cold/memory Weave evaluations. “This saves repeat verification work. It is not a blanket geometric rule.”

**1:20–1:45 — The outer loop.** “ARIA reviewed these records and proposed an experiment. We ran twelve matched cases. Cleanup repairs the manifold, but cannot rescue the cage at high stepover. We test the advice before retaining it.” Show the ablation evaluation. Hosted checks ran with network disabled and no guest credentials.

**1:45–2:40 — The live system.** Return to the job started at the beginning. Show actual generated CAM, checks and simulation; terminal emits observed stages and decisions. Switch to an earlier completed job only if inference is still pending, and explicitly call it a completed run. Never reset or impersonate live progress. Open the Weave trace after readback succeeds. The verified instrument rehearsal is job a1b399e521ac, memory9->10,125.5s reference to27.3s best.

**2:40–3:00 — What it produces.** Show the staggered drum with 26 features across 17 indexed orientations. “The output is a verified movement plan, machined-stock mesh, and timing estimate. The demo engine supports indexed 3+2, with 3 mm demo tolerance. We are optimizing a manufacturing process, not changing the customer's part.”

## Raw terminal inspection

Use the actual job id from the browser. These commands print saved artifacts with source paths and hashes; they do not run or approve anything:

```sh
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID prompt --attempt 0
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID cam --attempt 0
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID checks --attempt 0
cnc_simulator/.venv/bin/python -m camloop.inspect_job JOB_ID memory
```

`prompt` exposes the application's supplied developer instructions and request context, not an underlying provider system prompt. New runs record the exact instruction text before inference. Older runs honestly report that file as unavailable. `cam` shows Astra's structured strategy and the deterministic compiler's actual tool movements; do not call these model-written G-code. `memory` shows the loaded, feedback, and job-specific saved snapshots, with missing historical snapshots explicit.

## Evidence links

- Live generated job: http://127.0.0.1:2744/workspace.html?job=a1b399e521ac
- Actual live Weave trace: https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0993c-b389-7354-9903-8fb994b6912f
- Hosted checks: https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09937-99b3-7bbe-a02c-ccef3b06f806
- Fresh memory evaluation: https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09935-9d03-70b7-8c0d-53444e7827e6
- ARIA ablation: https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09939-9530-7750-bec0-c4da6fa511a1

## Do not claim

The combined 24-plan transfer study does not prove memory improves speed on unseen parts; the pre-registered new shapes showed no useful transfer benefit. The 116 second film is an edited recording, not live execution. Telemetry outputs are not yet configured Weave UI Signals. Other catalog/Fusion traces in the shared project belong to different execution paths. Do not attribute them to the programmatic engine. No production precision, cutting-force, controller or physical-machine certification.

The terminal observer retries temporary read failures and reports observation as unverified if the connection stays unavailable. It never restarts a job. `--port` selects an independent local server, for example `--port 2745`. A completed-job readback is a readback, not a newly executed run.
