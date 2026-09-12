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

## Deploy it

The live service is a container running `marimo run notebooks/workbench.py --headless` on Google
Cloud Run. There is no continuous delivery: GitHub Actions runs lint and tests on every push, but
nothing deploys on merge. A release is one deliberate command.

```sh
gcloud auth login
gcloud config set project silta-hack
bash scripts/deploy.sh
```

`scripts/deploy.sh` is idempotent and safe to re-run. It creates what is missing and reuses what
exists: the `silta` Artifact Registry repository, the `silta-hack-silta-artifacts` bucket, the
`silta-run` runtime service account, and the `wandb-api-key` secret. It then builds the image
through Cloud Build (`cloudbuild.yaml`, ~10 minutes on the first run because of cadquery/OCP),
tags it with the current git commit, and deploys it.

Deployed settings that matter: `--min-instances=1 --max-instances=1` so a job's in-memory state
survives the demo, `--session-affinity` and `--timeout=3600` for the workbench WebSocket, and
`--allow-unauthenticated` so judges need no Google account.

### Live inference is optional

The W&B key is read from Secret Manager. If the secret has no enabled version, the script deploys
**without** it rather than blocking — the app falls back to its deterministic planner and says so in
its header. To enable live inference:

```sh
echo -n 'YOUR_WANDB_API_KEY' | gcloud secrets versions add wandb-api-key --data-file=-
export WANDB_INFERENCE_MODEL=...   # a model id `make models` actually returned
bash scripts/deploy.sh
```

Use `echo -n`; a trailing newline in the secret breaks authentication.

### Verify the deployment

```sh
uv run python scripts/smoke_remote.py https://silta-1020247549062.us-central1.run.app
uv run python scripts/acceptance_remote.py https://silta-1020247549062.us-central1.run.app
```

The smoke test checks the page serves unauthenticated HTML; the acceptance harness drives a full
job over the WebSocket and checks the run reaches a passing attempt. Both exit non-zero on failure.

Overrides, if you are deploying somewhere other than the team project: `GCP_PROJECT`, `GCP_REGION`,
`SERVICE_NAME`, `WANDB_ENTITY`, `WANDB_PROJECT`.

Rollback, key rotation and artifact cleanup are in [the runbook](docs/runbook.md). Do not deploy
during the three-minute presentation — a new revision drops the running job.

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
| Live W&B inference | **working** — the deployed service plans with `deepseek-ai/DeepSeek-V4-Pro` on W&B Inference |
| W&B Weave Evaluations | **published** — 4 runs over the frozen corpus, both policies, [evidence](docs/evidence/weave-evaluations.md) |
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


### Judge presentation

[Interactive slideshow](https://silta-cdswwreljq-uc.a.run.app/slides/) ·
[Three-minute pitch guide](https://silta-cdswwreljq-uc.a.run.app/presentation/guide.html) ·
[Eval evidence](https://silta-cdswwreljq-uc.a.run.app/presentation/evals.html)

For local rehearsal, run `make present` and open http://localhost:2734/.
