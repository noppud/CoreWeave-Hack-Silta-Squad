# Recovering an interrupted Fusion job

There are two queues. The campaign JSON is a progress record; it does not prove a worker is alive. The bridge's `processing/` directory contains individual Fusion requests. A transport timeout establishes neither failure nor success of the underlying CAD/CAM action.

First establish that the old campaign worker and any child model/verification processes have stopped. Do not start another Fusion worker while one still owns the desktop. Keep the old manifest, logs, request and any response. Restarting the campaign command is not a resume: it refuses an existing incomplete job directory.

The new bridge source records PID/session ownership and, at add-in startup under its exclusive owner lock, quarantines requests only when that PID is proven dead. Requests move to `abandoned/<unique-id>/` with an `unknown`, `replayed:false` receipt; existing responses stay unchanged. Live, permission-denied, malformed, reused or missing PID evidence is not proof of death. Legacy requests without an owner sidecar remain blocked. Do not delete `processing/`, remove the owner lock or blindly replay requests. An operator must inspect the original request and document state for those ambiguous cases. This source feature requires loading the updated add-in at a safe pause; copying repository files alone does not activate it.

After the bridge is safely recovered, confirm a response using the normal read-only health request:

```sh
.venv/bin/python -c 'from silta.cnc.fusion import FusionBridge; print(FusionBridge().request("ping"))'
```

To continue a retained job, use a **new, unused job ID** and unchanged input config. Example template (replace the two placeholders before running):

```sh
hsec exec --only COREWEAVE_WANDB_API_KEY -- \
  .venv/bin/python scripts/demo/resume_fusion_job.py \
  runs/SOURCE_JOB/manifest.json config/demo-campaign/umc-06-job.json \
  --job-id NEW_RECOVERY_JOB --api-docs fusion/INDEXED_CAM_API.md
```

This command performs real Fusion work, uses Astra and publishes its trace. It locks the campaign, verifies the input/target/candidate hashes, and freshly verifies the retained CAM before optimization. A changed verifier version requires a fresh baseline; old verdicts remain historical evidence. It creates a new manifest and run receipt, preserving the source job. It does not automatically rewrite the campaign row. Only reconcile that row after checking the new final status and receipt; keep the earlier interrupted runs in the reports. No recovery command was executed to prepare this document.


## Manually nominate a retained CAM trial

Use a completed, current-verifier incumbent as the normal source, then name the exact older candidate to try:

```sh
hsec exec --only COREWEAVE_WANDB_API_KEY -- .venv/bin/python scripts/demo/resume_fusion_job.py \
  runs/demo-umc-umc-11-recovery4/manifest.json config/demo-campaign/umc-11-job.json \
  --job-id demo-umc-umc-11-manual-trial-c2 \
  --trial-source runs/demo-umc-umc-11-recovery1/manifest.json \
  --trial-candidate-id candidate-0002
```

Both trial options are required together. Selection must match exactly one `candidate_created` event, the same manufacturing-input digest and accepted target, and unchanged artifact hashes. The source candidate need not have an old pass; its old verdict is never inherited. The existing current-verifier baseline remains the incumbent, and the selected trial enters normal checks and fresh simulation. Later Astra repair and supervisor decisions remain in the normal loop.

This is a **manual nomination**, not a learned or autonomous supervisor choice. `workspace/manual-trial-nomination.json` records the source-manifest SHA-256, event index, candidate digest and collection warning. `workspace/manual-trial-source.json` preserves the exact source bytes. The nomination is also added to the supervisor's history and subsequent main-agent repair feedback. Historical collection-invalidated failures are not described as machining failures. Do not reuse an existing job ID or run alongside another Fusion worker.
