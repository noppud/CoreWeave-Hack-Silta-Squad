# CNC learning demo — current plan

2026-09-12. The user removed Weave evaluation gates and deferred video recording until learning works. This supersedes earlier promotion/evaluation plans.

## Core loop

Drawing/PDF + machine/tools → Astra creates CAD, then keeps it fixed → creates/revises CAM → learned Python checks → real Fusion simulation and finished-stock comparison → judge improves CAM or returns the best verified plan.

- Check failure: return the issue to the CAD/CAM agent.
- Simulation failure: repair CAM; the check writer can replace the shared checks file.
- Simulation pass: give machining time, tool changes, cost assumptions and simulation feedback to the judge.
- Judge: give next-attempt instructions, stop, and/or replace the shared CAD/CAM prompt directly.
- The next attempt and subsequent parts use the updated files. No evaluation gate or extra agent loop.

## Exactly two active learning files

| File | Initial state | Updates |
|---|---|---|
| `learning/cad_cam.md` | Basic CAD/CAM instructions | Judge returns full replacement Markdown; applied immediately |
| `learning/checks.py` | `check(data)` returns pass; no learned manufacturing checks | Check writer returns full replacement Python after a completed simulation failure |

The judge sees the current Markdown before editing it. Python syntax is checked before saving a check update; this is not a quality evaluation. The supervisor's own instructions are fixed. Existing run logs retain attempts, changes and results; they are not additional learning stores. Old `versions/` and benchmark code are historical and are not consulted by the default runtime.

Fixed target/input integrity and actual simulation completion remain application code. A learned check pass does not replace simulation. Directly learned instructions/checks have not been evaluated for regressions.

## Components

- All agent roles: GPT-6 Astra, low reasoning, fast service tier, subscription-authenticated local Codex SDK. No weaker-model fallback. Fast is normalized to priority by the app-server; live readback and a model call passed.
- Fusion: professional trial on this Mac, linked Haas VF-2, configured vise/stock and two enabled cutter/holder assemblies. Deterministic API code owns setup, toolpath generation and NC export; Astra chooses machining operations.
- Simulation: deterministic native UI runner for Issues and stock export, API timing, stock-to-fixed-STEP comparison. Foreground Fusion is required during UI collection. Native helper compilation is cached; Issues polling skips screenshot/OCR.
- Checks: local Python subprocess. No hosted sandbox dependency.
- Weave: traces only. No benchmark runs or evaluation required to save learning.
- Videos: deferred. No recording in the current job path.

## Evidence and next step

Real Fusion run `runs/soft-jaw-first-loop-v14/manifest.json` completed three verified candidates (216.76 → 211.00 → 205.23 seconds estimated machining time) and a supervisor stop. These were within-part improvements, not persistent learning.

The direct-learning controller integration test now proves immediate checks/prompt refresh and reuse after a process restart, using fake simulation adapters. It creates only the two active learning files. This is software wiring evidence, not proof of learning across real parts.

Next: run a real first part from the basic prompt and empty learned checks, retain its actual learning, then run a second part using those files. Demonstrate the learned behavior before the remaining acceptance parts or videos. Do not claim speed improvement by comparing unrelated part geometries.

## Run

```sh
uv run python -m silta init
hsec exec --only COREWEAVE_WANDB_API_KEY -- uv run python -m silta run config/soft-jaw-job.json
```

`--learning-directory` selects the directory containing the two shared files (default `learning`). Reuse it across parts. `--job-id` selects a new output job, and `--max-attempts` is an operational stop, not the judge's success decision.

Final artifacts: accepted CAD/STEP, editable CAM, posted NC, best verified plan, actual verification evidence and estimated machining time/cost. The simulation verifies its recorded internal CAM scope; this is not a physical machine trial.

### Live test checkpoint — September 12

Fresh PDF-to-CAD acceptance passed in `runs/learning-soft-jaw-a1`. Real simulations found 26, 32 and subsequently 52 errors across repairs; none reached the judge. The check writer initially declined unsupported rules. Its fixed instructions now explicitly require inspecting available posted NC and CAM source, not only the analysis summary.

Testing exposed two integration defects: Fusion can omit the Issues summary from accessibility until the panel is closed/reopened, and completed empty-toolpath generation was interrupting the controller. The native reader now performs one observed Issues-panel refresh; this restored the actual 100%/52-error label live. Completed generation errors now return their source and inspection to the CAM agent; 322 software tests pass.

With Fusion foreground, `runs/learning-soft-jaw-a5` completed two real verified simulations: the saved repair at 384.860379 seconds, followed by a judge-directed ramp-feed change at 211.037438 seconds (45.2% less estimated machining time). Both passed machine Issues collection and bidirectional finished-stock comparison against the fixed CAD. The judge stopped and wrote its first reusable lesson directly into `learning/cad_cam.md`. This proves measured within-part optimization and persistent prompt writing; transfer to another part remains to be tested. Weave receipt: `01a098a9-7350-7b4b-adb4-e5d9c997f8c4`.

Part B is the authored test drawing `output/pdf/learning-part-b.pdf`, with its job in `config/learning-part-b-job.json`. It changes slot size/spacing/recess depth while retaining the fixed blank and fixture; it has not run. The original caliper/engine-case drawings require different setups, so they were not substituted into this fixture. Videos remain deferred. Detailed test status is saved in `.private/fusion-live/learning-test-status.json`.

The corrected check-writer input instructions yielded a real learned check from the completed 52-error run. `learning/checks.py` now checks supported posted-NC cutter endpoints against the exact modeled solid fixture parallels. A diagnostic replay rejected failed candidate-0003 in 0.024 seconds and accepted verified candidate-0006 in 0.040 seconds. This is narrow coverage, not a complete collision detector, and was not an evaluation gate. Both the failure evidence and direct update are traced in Weave call `01a098ad-3518-7fff-a815-21cc0b3585e2`. Part B is now running with both shared learned files.

Part B completed in `runs/learning-part-b2` at 205.344625 seconds after repairing a real stock-conformity failure in `learning-part-b1`. Its first CAM source explicitly used the imported ramp-feed preset from the shared guidance. The failure added a second learned check for outer-side intrusion under the pre-sized-blank/internal-only contract; the same job refreshed its checks before the next candidate. Diagnostic replay rejects the failed B candidate in 0.041 seconds and accepts the verified repair in 0.042 seconds. Fusion omitted a Save Stock checkbox from AX; a single cancel/reopen of the still-unsaved dialog restored it live and is now in the exporter (13 focused tests pass).

The remaining eight authored drawings C-J vary dimensions, feature count and spacing while retaining the same setup. Their configs are `config/learning-part-{c..j}-job.json`. A sequential batch is running; its live status is `runs/learning-ten-part-test/progress.json`, with completed receipts in `results.jsonl`. Each new process/run loads the shared files. No assumption of monotonic machining-time improvement across different geometries is made. Videos remain deferred.
