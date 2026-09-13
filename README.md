# Silta CNC

Drawing/PDF → accepted CAD → CAM → cheap checks → Fusion verification → supervisor → improve or return the best verified plan. Simulation failures also propose better checks; reusable check/prompt changes must pass paired Weave evaluations before promotion.

**Current state:** the controller, Astra role adapters, Fusion add-in, local check runner, evaluation gate and marimo viewer are implemented. Astra subscription execution and Weave trace write/read have passed live smoke tests. The live SDK CAD stage now generates a drawing-matched AL6061 part and passes independent review; actual STEP export retains Aluminum6061 and density2700. The positioned vise/parallels and two cutter/holder assemblies have passed live Fusion export/readback checks. Live Fusion CAM/verification and the complete learning demonstration remain unverified. Unit tests are not manufacturing validation.

## Run

```sh
uv sync --locked
uv run python -m silta doctor
uv run python -m silta doctor --fusion-ui
uv run python -m silta init
uv run marimo run notebooks/cnc_app.py --host 127.0.0.1 --port 2720
```

Load the [Fusion add-in](fusion/README.md), finish the two live setup items in [the selected job configuration](config/README.md), and verify the bridge:

```sh
uv run python -m silta doctor --fusion
hsec exec --only COREWEAVE_WANDB_API_KEY -- uv run python -m silta run config/soft-jaw-job.json
```

The selected configuration blocks execution while setup is unresolved. The fixed
verifier launches Fusion's machine simulation through the bridge and reads its
Issues text through a direct SDK computer-use call, with no model turn for routine
collection. Raw observations are retained. The live reader has extracted a
completed collision report; repeatable job integration and target-stock comparison
are still being validated. Missing access, coverage or completion produces
`unknown`. An animation or generated toolpath is never a verification pass. No
physical-machine commands are sent.

All agent roles use **GPT-6 Astra through the local Codex SDK and ChatGPT subscription login**. There is no weaker-model or API-credit fallback. W&B supplies Weave tracing and evaluation. Credentials are supplied to the process, never checked into this repo. ARIA is deferred.

For the controlled demo, generated checks run in a separate local Python process
with copied inputs, a clean environment and execution limits. This is **not
security isolation**: check code can access host files and network. W&B Sandboxes
and Docker are not required. The historical hosted adapter is inactive; the CLI
explicitly uses the local runner. Reusable changes still require Weave evaluation
before promotion.

Run from an interactive terminal. When Fusion first requests computer-use access,
the launcher asks for explicit `yes` consent for that Silta session. It forwards
consent through the SDK's MCP elicitation protocol; it does not edit global app
permissions. Other app requests and shell/file approval requests remain denied.
The permission handshake and a subsequent native Fusion screen read have passed
live tests through the project launcher. Fusion's welcome setup is complete;
the updated SiltaBridge add-in has started and answered a live ping. CAD generation,
review, CAM toolpath generation and NC export have passed live integration. A
completed simulation has reported collisions; repair to a verified pass and the
learning demonstration still require live validation.

The Python launcher owns the autonomous loop. It calls the Codex SDK directly;
this development conversation is not required to advance a job. Fusion and the
installed Codex runtime remain dependencies on the Mac.

Register real completed simulation cases with `python -m silta.cnc.datasets`;
the [evaluation workflow](docs/evaluation-contract.md) explains how to pin the
verifier, capture cases and pass their dataset references to the promotion gate.

## Files

- [Agreed implementation plan](docs/implementation-plan.md)
- [Core controller](silta/cnc/controller.py), [Astra roles](silta/cnc/agents.py)
- [Fusion bridge and its current verification boundary](fusion/README.md)
- [Machine, tools, stock and setup assumptions](config/README.md)
- [Evaluation and promotion contract](docs/evaluation-contract.md)
- [Real job viewer](notebooks/cnc_app.py)
- [Hackathon evidence](docs/hackathon.md), [sponsor notes](docs/sponsors.md)

Run `uv run pytest` and `uv run ruff check silta tests checks notebooks/cnc_app.py`. Tests use explicitly labeled adapter doubles where external services are unavailable. `runs/`, `versions/` and `.private/` hold local jobs and evidence. The older storyboard and research alternatives are historical planning material, not live results or additional build requirements.
