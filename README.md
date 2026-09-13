# Silta CNC learning demo

An autonomous drawing-to-CAD/CAM loop using Astra, Fusion and Weave tracing.

Drawing/PDF + machine/tools → fixed CAD target → CAM → cheap learned checks → real Fusion simulation and stock comparison → judge improves or returns the best verified plan.

**Current evidence:** completed soft-jaw variants and indexed housings, including an octagonal housing with 18 single-tool operations, plus actual machining video. A check learned from Part B rejected Part C’s bad toolpath before simulation in 51 ms. Paired Weave replay evaluations caught 2/2 retained invalid plans with learned checks versus 0/2 with empty checks, while accepting 4/4 valid plans. A fresh five-axis campaign is in progress; consult the generated [readiness report](output/demo-readiness.json) for counts, rather than treating queued jobs as results. See [learning evidence](docs/learning-results.md), [five-axis evidence](docs/five-axis-demo.md), and [evaluation scope](docs/demo-evaluation.md).

The [versioned W&B evidence bundle](https://wandb.ai/silta/coreweave-hack-silta-squad/runs/43m1kgqx) contains drawing/STEP/NC files, verification results, exact learned sources, evaluations and the film. Its first snapshot contains six completed drawings and is explicitly partial. The bundle is for inspection; running Fusion requires the configured local application and machine model.

## Start here

The [project context and agent handoff](docs/project-context.md) consolidates the product goal, both feedback loops, final demo decisions, metric definitions, ARIA's role, and engineering/pitch priorities from Joel's design conversation. Agents should also read [AGENTS.md](AGENTS.md).

## Standalone learning-loop presentation

The [learning-loop presentation](demo/README.md) animates 27 example parts. It uses explicitly scripted presentation data, separate from the real Fusion evidence below. Run `python3 -m http.server 8080 --bind 127.0.0.1` and open **http://127.0.0.1:8080/demo/**. This presentation does not require Fusion. Preserve the separately maintained [pitch notes](docs/demo-3min.md).

## Fusion control center

Run `uv run python -m silta.cnc.control_center` for the local Fusion workbench. See [live Fusion connection](docs/live-fusion-connection.md) for the companion viewer and LAN pairing. Historical runs and full recordings remain local; the [pitch app](demo/pitch-app/README.md) includes curated presentation footage.

## Learning

Only two active learning files:

- `learning/cad_cam.md`: the CAD/CAM system prompt. Judge-requested edits replace it directly.
- `learning/checks.py`: learned manufacturing checks. A fresh learning directory starts empty; the repository file is the learned campaign snapshot. Simulation failures can produce new checks.

Updates apply to the next attempt and survive for subsequent parts. Weave records traces and separate offline replay evaluations; evaluations do not gate live updates. New runs retain exact learning-source snapshots as evidence. The actual five-axis video and evaluation comparisons are available in the marimo workbench.

## Retained Fusion workbench

```sh
uv run marimo run notebooks/cnc_app.py --host 127.0.0.1 --port 8791 --headless
uv run python scripts/demo/verify_demo.py
```

The workbench reads `runs/demo-campaign.json`, refreshes every 15 seconds, and keeps historical runs selectable while the next part runs. It includes the real Fusion video, CAD/CAM/NC downloads, check and prompt changes, and published Weave links. [Campaign drawings](docs/demo-campaign.md) reserve UMC07 as the fresh live example. The independent [`cnc_simulator/`](cnc_simulator/README.md) application is included with its own execution and evidence; the Fusion measurements do not describe that backend.

The workbench displays an empty state in a fresh clone: retained `runs/` and raw media are local artifacts. The published evidence bundle above is for inspection. `verify_demo.py` validates the original recording machine's retained evidence and is not a fresh-clone smoke test.

## Run

```sh
uv sync --locked
uv run python -m silta init
uv run python -m silta doctor --fusion
hsec exec --only COREWEAVE_WANDB_API_KEY -- uv run python -m silta run config/soft-jaw-job.json
uv run marimo run notebooks/cnc_app.py --host 127.0.0.1 --port 2720
```

Before executing a job from another checkout, follow [configuration relocation and Fusion linking](config/README.md#relocating-a-checkout). Relocation verifies local pinned bytes; it does not create Fusion cloud/library access.

Reuse the default `learning` directory for sequential parts, or select it with `--learning-directory`. Each job saves its attempts and verification evidence under `runs/`.

All agent roles use **GPT-6 Astra, low reasoning and fast mode**, through the local Codex SDK and ChatGPT subscription login. No weaker-model or API-credit fallback for project agent roles. A separate ARIA review of actual Weave traces used ARIA's exposed gpt-5.5 and informed a tested Fusion readiness repair; see [sponsor evidence](docs/sponsor-evidence.md).

Joel's separate [ARIA architecture and evaluation review](docs/aria-loop-review.md) remains a development-review record and proposal. The trace-readiness repair described above is a distinct ARIA engagement; neither makes evaluation-gated promotion the default runtime.

The [Fusion bridge](fusion/README.md) must be running. The fixed native UI runner needs unlocked foreground Fusion during simulation collection. Setup, CAM generation and postprocessing use Fusion APIs. Routine simulation collection does not require Astra clicking. No physical-machine commands are sent.

Generated checks run in a local Python subprocess with copied inputs, clean environment and execution limits. This is not a security sandbox. No hosted W&B Sandboxes or Docker dependency.

## Development

```sh
uv run pytest
uv run ruff check silta tests checks notebooks/cnc_app.py
```

Tests using adapter doubles are software checks, not manufacturing evidence. Historical evaluation code and `versions/` are retained but inactive in the default application. See [machine configuration](config/README.md), [hackathon evidence](docs/hackathon.md), and the [job viewer](notebooks/cnc_app.py).
