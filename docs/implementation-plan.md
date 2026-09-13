# CNC learning demo — current plan

For the consolidated product/design conversation and agent handoff, start with [project-context.md](project-context.md). This file contains chronological implementation checkpoints; later reports supersede earlier next steps. ARIA's evaluation proposals are documented separately and do not change the current direct-learning runtime.

## Core loop

Drawing/PDF + machine/tools → Astra creates CAD and fixes the target → creates/revises CAM → learned Python checks → real Fusion simulation and finished-stock comparison → judge improves the plan or returns the best verified result.

- Check failure returns to CAM repair.
- Simulation failure returns to CAM repair and can generate a learned check.
- Only a completed simulation pass reaches the judge, with estimated machining time, tool changes, cost assumptions and feedback.
- The judge can edit shared CAD/CAM guidance. Updates apply immediately and persist across parts.

Exactly two active learning files: `learning/cad_cam.md` and `learning/checks.py`. Changes are applied directly; Python syntax is checked. No Weave evaluation gate or additional learning loop. Fixed input/target integrity and simulation-completion requirements remain application code.

## Runtime

- All model roles: GPT-6 Astra, low reasoning, fast tier, subscription-authenticated Codex SDK.
- Fusion on this Mac: four-part learning evidence uses the Haas VF-2. The active presentation build uses a Haas UMC-750, indexed five-axis (3+2), pedestal fixture and one enabled T1 cutter/holder assembly. Deterministic code handles setup, generation, export and result collection.
- Verification: completed internal CAM machine checks plus bounded bidirectional finished-stock comparison against fixed STEP, 0.127 mm tolerance. Not physical cutting or posted-NC certification.
- Local Python checks; no hosted sandbox dependency. Weave traces and local evidence retained.
- Native UI collection needs visible, unlocked Fusion. `caffeinate -di` prevents idle system/display sleep for batch execution; it ends with the process.
- Recoveries retain the previously verified incumbent with matching target/setup/evidence. Unknown results cannot replace it.

## Historical learning checkpoint

Four parts A-D completed the initial learning test. E-J from that original three-axis set were not run. Prompt guidance transferred between parts. A check learned after B failed then rejected C’s bad plan in 51 ms before simulation. A improved 384.860 → 211.037 seconds; C improved 228.182 → 211.850 seconds. These within-part comparisons do not make the different parts’ final times a learning curve.

See `docs/learning-results.md` and `runs/four-part-learning-summary.json` for exact evidence and limitations. Several integration recoveries were necessary, and empty narrow-pocket generation remains a recurring repair case.

## Current demo campaign

The current target is at least ten completed distinct drawings across the historical test and the single-tool indexed five-axis campaign. Real UMC machine playback and a finished-stock camera orbit have been recorded. New drawings include an octagonal instrument housing and an open forked bracket. The latter is a drawing input, not a prewritten CAM solution.

`runs/demo-campaign.json` records the queue; `scripts/demo/verify_demo.py` checks completed jobs, drawing identity, artifact hashes and retained passes. Its generated `output/demo-readiness.json` is the current count, rather than a static progress claim here. See `docs/learning-transfer.md` for exact within-part comparisons and what the source does or does not establish about transfer. No further three-axis batch or tool-switch optimization is planned.

For the stage, show the loop and measured transfer, then the actual generated source, checks and Fusion verification. `scripts/demo/stage_fusion_demo.py` can prepare CAD/CAM in advance, pause before simulation, and release the live verification explicitly. Preparation and verification time remain separate. The stage helper uses a copy of the two learning files, so rehearsal does not silently change the campaign's learned state.

## Run

```sh
uv run python -m silta init
hsec exec --only COREWEAVE_WANDB_API_KEY -- caffeinate -di uv run python -m silta run config/soft-jaw-job.json
```

Reuse `learning/` across parts. `--max-attempts` is an operational stop, not a judge success decision. Outputs include accepted CAD/STEP, editable CAM, posted NC, best verified plan, verification evidence and estimated timing/cost.
