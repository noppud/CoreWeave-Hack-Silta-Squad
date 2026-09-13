# Silta CNC learning demo

An autonomous drawing-to-CAD/CAM loop using Astra, Fusion and Weave tracing.

Drawing/PDF + machine/tools → fixed CAD target → CAM → cheap learned checks → real Fusion simulation and stock comparison → judge improves or returns the best verified plan.

## Start here

The [project context and agent handoff](docs/project-context.md) consolidates the product goal, both feedback loops, final demo decisions, metric definitions, ARIA's role, and engineering/pitch priorities from Joel's design conversation. Agents should also read [AGENTS.md](AGENTS.md).

**Evidence status:** the [implementation checkpoints](docs/implementation-plan.md) report real within-part optimization, persisted lessons, and later reuse on another authored part. Those reports are chronological and were not rerun for this documentation update. They do not establish broad cross-part generalization; the 54-part animation is scripted presentation data. Verify matching run evidence before using quantitative pitch claims.

## Interactive demo

The [learning-loop presentation](demo/README.md) animates 54 example parts, learned tests, judge feedback, and the improvement charts. Run `python -m http.server 8080 --bind 127.0.0.1` from this directory and open **http://127.0.0.1:8080/demo/**. The standalone page does not require Fusion.

## Learning

Only two active learning files:

- `learning/cad_cam.md`: the CAD/CAM system prompt. Judge-requested edits replace it directly.
- `learning/checks.py`: learned manufacturing checks, initially empty. Simulation failures can produce new checks.

Updates apply to the next attempt and survive for subsequent parts. Weave records traces but does not evaluate or gate updates. Video recording is deferred until learning works. See the [current plan](docs/implementation-plan.md).

The [ARIA loop review](docs/aria-loop-review.md) records the business and learning risks, our questions to ARIA, and a proposed Weave evaluation plan. It is a review, not an implemented change to the runtime.

## Run

```sh
uv sync --locked
uv run python -m silta init
uv run python -m silta doctor --fusion
hsec exec --only COREWEAVE_WANDB_API_KEY -- uv run python -m silta run config/soft-jaw-job.json
uv run marimo run notebooks/cnc_app.py --host 127.0.0.1 --port 2720
```

Reuse the default `learning` directory for sequential parts, or select it with `--learning-directory`. Each job saves its attempts and verification evidence under `runs/`.

All agent roles use **GPT-6 Astra, low reasoning and fast mode**, through the local Codex SDK and ChatGPT subscription login. No weaker-model or API-credit fallback. ARIA has been used for an advisory review; it is not part of the runtime loop.

The [Fusion bridge](fusion/README.md) must be running. The fixed native UI runner needs unlocked foreground Fusion during simulation collection. Setup, CAM generation and postprocessing use Fusion APIs. Routine simulation collection does not require Astra clicking. No physical-machine commands are sent.

Generated checks run in a local Python subprocess with copied inputs, clean environment and execution limits. This is not a security sandbox. No hosted W&B Sandboxes or Docker dependency.

## Development

```sh
uv run pytest
uv run ruff check silta tests checks notebooks/cnc_app.py
```

Tests using adapter doubles are software checks, not manufacturing evidence. Historical evaluation code and `versions/` are retained but inactive in the default application. See [machine configuration](config/README.md), [hackathon evidence](docs/hackathon.md), and the [job viewer](notebooks/cnc_app.py).
