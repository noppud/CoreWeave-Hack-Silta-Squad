# Main-agent CAM measurement and repair

Implemented in the main workbench loop. The confirmed part is built once; the
main planner proposes a complete `PlanDraft`, then receives trusted measurements
from executed checks, compilation and simulation before its next revision.

## Planner input

- Full previous CAM plan, including setups, tools, feeds, stepdown and stepover.
- Latest five measured attempts, with IDs, target and trajectory hashes,
  check evidence, collision locations, simulation grid and duration,
  residual/gouge thresholds, feature coverage and estimated machining seconds.
- Applicable persistent memory and, when supervision is enabled, the supervisor's
  improvement instruction. Optimization starts from the verified incumbent;
  a failed optimization is the next repair target.

Unmeasured results are null. A simulation that stops on collision does not report
its placeholder material-removal values as measurements. Runtime estimates come
from the compiled toolpath and declared shop constants, not from the model.

## Repair and verification

The model cannot change the CAD target, shop inventory or validation thresholds.
Output is a bounded JSON plan, never executable code. Invalid tool/feature/setup
references and schema errors can get one correction call within the remaining
planner-call budget. The configured output token limit is respected.

Every candidate runs through the same checks, compilation and simulation. Repeated
candidates stop the loop. Repair diffs report changed operation parameters.
Without inference, the fallback can repair tool reach and fixture clearance from
measured evidence; unsupported diagnoses request review instead of blindly
increasing clearance.

The `attempt_completed` event includes `measurements`, persisted in the existing
event store. The workbench Evidence ledger exposes the same measurements beside
the selected recipe. This does not add W&B trace export or change the scripted
three-minute presenter into a live model run.

## Verification

`tests/test_cam_repair.py` runs the real check/compiler/simulator pipeline with an
evidence-reading test provider: short-tool rejection, clamp collision, repaired
pass. It also covers deterministic repair, invalid tool correction with a one-call
budget, supervisor instruction forwarding and a freshly verified faster candidate,
unsupported repair, and incomplete simulation classification.

```sh
.venv/bin/pytest tests/test_cam_repair.py -q
.venv/bin/python scripts/verify_cam_repair.py --live
```

Live inference verification on September 12, 2026: job `job-8355746bfd31` used
`deepseek-ai/DeepSeek-V4-Pro` for two repair calls with no fallback. Attempt 0
failed tool reach, attempt 1 failed on the measured clamp collision, and attempt 2
passed fresh checks and simulation. Evidence is retained in
`artifacts/job-8355746bfd31/repair-events.json` and `repair-summary.json`.
This verifies the local implementation against live inference, not a deployment.

The supervisor remains opt-in through `Budget(supervised_loop_enabled=True)`.
No model training, real-machine execution, or general CAM capability is claimed.
