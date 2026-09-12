# CoreWeave Hack — Silta Squad

Team workspace for the CoreWeave Hacks hackathon.

**Status:** repository bootstrap. The product idea, team roster, and prize track are still to be chosen.

Repository: https://github.com/noppud/CoreWeave-Hack-Silta-Squad

## Start here

- [Hackathon brief](docs/hackathon.md): handbook requirements, judging, resources, and schedule caveats.
- [Sponsor setup and credits](docs/sponsors.md): W&B, TypeSafe credit activation, ARIA, MCP, and molab GPU access.
- [Build plan](docs/plan.md): choose the problem and ship the first complete agent loop.
- [Submission draft](docs/submission.md): fill this in as we build.

The supplied handbook requires W&B usage and emphasizes agents that improve through feedback. Keep the first demo focused on one useful task, a measurable failure, and a visible correction.

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

The saved handbook lists **June 6–7**, while this repository is being initialized on **September 12, 2026**. Confirm the current event schedule and submission link with the organizers before relying on the stated Sunday 1 PM deadline.
