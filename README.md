# CoreWeave Hack — Silta Squad

Team workspace for the CoreWeave Hacks hackathon.

**Status:** implemented and running. **Silta CNC** is a marimo application that turns a dimensioned
drawing into a STEP solid, a machining recipe, a compiled toolpath and a simulated cut — and when a
real geometric check fails, hands that failure back to the planner and measures the next attempt.

The demonstration job runs by itself when the page opens:

| Attempt | Plan | Outcome |
| --- | --- | --- |
| 00 | naive shop recipe: EM6-S, 5 mm clearance | `tool_cutting_reach` — the 12.0 mm pocket depth exceeds the 8.0 mm cutting length |
| 01 | repaired: `EM6-S -> EM6-L` | simulation collision — the cutter strikes `clamp_front` on segment `s0005` |
| 02 | repaired: `clearance 5.0 -> 15.0 mm` | passed prototype checks; residual 0.0 mm, gouge 0.0 mm, full coverage |

The confirmed design hash is unchanged across all three: repair may change tooling, ordering and
clearances, never the customer's requested shape.

**Live application: https://silta-1020247549062.us-central1.run.app** — public, no Google account needed.

Repository: https://github.com/noppud/CoreWeave-Hack-Silta-Squad

## Run it

```sh
make setup            # creates local configuration once, installs locked dependencies
make app              # the workbench at http://localhost:2718
make evals            # the experiment notebook
make check            # ruff + offline pytest
```

`make app` needs no credentials. Without a W&B key the planner is deterministic and the page says so
in its header; it never presents a deterministic plan as live inference.

## Start here

- [**Verification evidence**](docs/evidence/): geometry oracles, learning subsystem,
  deployment acceptance and the measured policy improvement.
- [**The agentic loop**](docs/agentic-loop.md): what the agent does, what feedback it
  receives, what it may and may not change, and how the next attempt is measured. Start here
  if you want to understand the product rather than run it.
- [Hackathon brief](docs/hackathon.md): handbook requirements, judging, resources, and schedule caveats.
- [Sponsor setup and credits](docs/sponsors.md): W&B, TypeSafe credit activation, ARIA, MCP, and molab GPU access.
- [Build plan](docs/plan.md): product scope, user flow, demo fixture and measured improvement loops.
- [Technical architecture](docs/architecture.md): schemas, CAD, toolpaths, simulation, providers, UI and sponsor integrations.
- [Implementation playbook](docs/implementation.md): tasks, acceptance criteria, schedule and recursive coding-agent review loop.
- [Live deployment](docs/deployment.md): required GCP Cloud Run hosting, durable artifacts and remote acceptance checks.
- [Submission draft](docs/submission.md): fill this in as we build.

The supplied handbook requires W&B usage and emphasizes agents that improve through feedback. Keep the first demo focused on one useful task, a measurable failure, and a visible correction.

## What is real, and what is not

| Claim | State |
| --- | --- |
| CAD and STEP export, reimported and checked against an independent analytic oracle | working — 85 519.97 mm³ against 85 519.97 mm³ |
| Deterministic preflight, path and simulation checks | working — 12 frozen fixtures, 0 false accepts, 0 false rejects |
| 2.5D stock-removal and collision simulation | working — a real clamp collision, and a clean cut at 0.0 mm residual |
| Three.js replay driven by the simulator's own results | working |
| Cross-task improvement (`path_fixture_envelope` promoted into the path stage) | working — measured on development, confirmed on untouched holdout |
| Live W&B inference | **not verified** — no API key configured, no credit grant confirmed |
| Weave traces and W&B run metrics read back | **not verified** — telemetry is wired and degrades cleanly to disabled |
| ARIA analysis | **outstanding external gate** — see `policies/aria-recommendation-001.md` |

The improvement recorded in `policies/` was authored and verified by hand, not by ARIA. It is
labelled that way everywhere, and it stays labelled that way unless a real ARIA conversation happens.

## Run the starter

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
make setup
# Add your W&B API key to .env; team is preset to konstav-control-dev.
make models
# Set WANDB_INFERENCE_MODEL in .env to one of the returned model IDs.
make doctor
make trace
uv run python -m silta "Draft a practical plan for our hackathon demo"
```

The starter makes one initial draft, asks the model for a critique, and revises the answer. Each model request and the enclosing loop are traced in Weave using the [documented tracing API](https://docs.wandb.ai/weave/quickstart); inference uses the [W&B API](https://docs.wandb.ai/inference/api-reference). It defaults to three inference calls. `--rounds 2` or `--rounds 3` adds revision rounds (five or seven total calls). Each request has a timeout and an output token limit; failed requests stop the run.

This is a wiring example. Model critique does **not** establish measured improvement. Replace it with a task-specific evaluator and real examples once we choose the product. No UI, deployment, or live W&B verification is included yet.

`--check` validates that settings are present without calling any service. A real run uses inference credits and sends the task, draft, and feedback to W&B for inference and tracing. Choose a model currently available to the team's account at [W&B Inference](https://wandb.ai/inference). Open the printed Weave link to verify traces and add it to the submission draft.

## Development checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests use a fake provider and require no credentials or network. GitHub Actions runs these checks when the files are pushed.

## Team workflow

Use short branches and small commits. Integrate a working path early, then improve it. Keep credentials in a local `.env` file; commit only placeholder configuration. Record the distinction between hackathon work and anything that already existed.

Current official event pages confirm **September 12–13, 2026** and Sunday **1 PM** submissions. Plan for **September 13 at 1 PM Pacific**, targeting 12:15 PM. The live handbook still has stale June date headings; [the rules ledger](docs/hackathon.md) records the discrepancy and remaining authenticated submission gates.
