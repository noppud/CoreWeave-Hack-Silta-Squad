# Silta CNC learning demo

An autonomous drawing-to-CAD/CAM loop using Astra, Fusion and Weave tracing.

Drawing/PDF + machine/tools → fixed CAD target → CAM → cheap learned checks → real Fusion simulation and stock comparison → judge improves or returns the best verified plan.

**Current state:** a real soft-jaw run completed three verified CAM candidates and stopped at an estimated 205.23 seconds. Direct learning is wired and tested with adapter doubles; learning transfer across real parts remains to be demonstrated.

## Learning

Only two active learning files:

- `learning/cad_cam.md`: the CAD/CAM system prompt. Judge-requested edits replace it directly.
- `learning/checks.py`: learned manufacturing checks, initially empty. Simulation failures can produce new checks.

Updates apply to the next attempt and survive for subsequent parts. Weave records traces but does not evaluate or gate updates. Video recording is deferred until learning works. See the [current plan](docs/implementation-plan.md).

## Run

```sh
uv sync --locked
uv run python -m silta init
uv run python -m silta doctor --fusion
hsec exec --only COREWEAVE_WANDB_API_KEY -- uv run python -m silta run config/soft-jaw-job.json
uv run marimo run notebooks/cnc_app.py --host 127.0.0.1 --port 2720
```

Reuse the default `learning` directory for sequential parts, or select it with `--learning-directory`. Each job saves its attempts and verification evidence under `runs/`.

All agent roles use **GPT-6 Astra, low reasoning and fast mode**, through the local Codex SDK and ChatGPT subscription login. No weaker-model or API-credit fallback. ARIA is deferred.

The [Fusion bridge](fusion/README.md) must be running. The fixed native UI runner needs unlocked foreground Fusion during simulation collection. Setup, CAM generation and postprocessing use Fusion APIs. Routine simulation collection does not require Astra clicking. No physical-machine commands are sent.

Generated checks run in a local Python subprocess with copied inputs, clean environment and execution limits. This is not a security sandbox. No hosted W&B Sandboxes or Docker dependency.

## Development

```sh
uv run pytest
uv run ruff check silta tests checks notebooks/cnc_app.py
```

Tests using adapter doubles are software checks, not manufacturing evidence. Historical evaluation code and `versions/` are retained but inactive in the default application. See [machine configuration](config/README.md), [hackathon evidence](docs/hackathon.md), and the [job viewer](notebooks/cnc_app.py).
