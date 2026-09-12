# Reusable-change evaluation contract

`silta.cnc.evaluation.WeaveEvaluationGate` implements the controller's promotion interface. It does not run a separate agent loop. The application supplies a benchmark runner that really executes the current and proposed versions on the same frozen cases.

After the gate confirms promotion with matching evidence, the running controller adopts only the proposal's exact kind and version. A promoted check is rebuilt through the runtime's check runner factory before the next attempt; promoted main and supervisor prompts are read from the updated context on subsequent calls. The initial versions and each earlier candidate/decision remain recorded unchanged, while `current_versions` and `promoted_change_applied` events record adoption. CAD, manufacturing inputs, objective and verifier stay fixed. Benchmark controllers disable learning and promotion, so their assigned baseline/proposed versions remain fixed.

## Inputs

- `VersionStore.put(kind, content)` freezes `checks`, `main_prompt`, `supervisor_prompt`, or `dataset` by SHA-256. Register the trusted baseline once with `initialize`; jobs copy the active pointers at creation.
- Dataset rows include `case_id`, `input_hash`, `verifier_hash` and the input artifact references required by the runner. `input_hash` covers the drawing, accepted CAD target, machine, tools/holders, fixtures, tolerances, and costing assumptions. The verifier hash covers its implementation and coverage/configuration.
- The runner receives `(kind, version_ref, frozen_cases, job_context)` and returns one record per case. Every record carries the same case/input/verifier references and the executed `version_ref`.
- Loop results: explicit `verified` bool, evidence references, `machining_seconds`, `cost`, and `simulation_attempts`. Failed runs may omit metrics; they are never converted into zero-cost successes.
- Check datasets additionally contain simulator `label` (`valid` or `invalid`) and `verification_evidence`. Check results have explicit `passed` and `runtime_ms`. A changed candidate/setup/verifier invalidates the cached label.

## Gate

Loop changes cannot lose an existing verified completion. Compare machining time, cost and attempts only on cases where both versions succeeded. Require a completion or metric improvement without regression in those matched aggregate metrics. Check changes require both valid and invalid examples, no false rejection, no newly escaped known failure, and no runtime regression. These intentionally strict deterministic rules are controller code, never mutable agent instructions.

Local scoring is not a Weave evaluation success. The gate publishes a versioned dataset and paired `weave.EvaluationLogger` runs, including the actual evaluated prompt/check artifacts, then reads both finalized server calls. Missing credentials or failed publication leave the production pointer unchanged. Each decision and publication receipt is saved locally. Promotion uses a locked compare-and-swap; rollback can select a previously active version. Running jobs retain their original versions.

No real benchmark results are included in this implementation. The tests use explicit fixtures and are unit/integration verification of the gate, not evidence that generated CAM improves. The live application must configure the production runner factories and cloud credentials.

Implementation follows the installed Weave SDK's `EvaluationLogger` signatures and explicit prediction finalization. The SDK currently exposes its evaluation call through `_evaluate_call`; the code fails closed if that interface changes. See [EvaluationLogger documentation](https://docs.wandb.ai/weave/guides/evaluation/evaluation_logger).

## Capture real benchmark datasets

The local command module `python -m silta.cnc.datasets` handles dataset preparation. It never starts a model, executes generated checks or runs a simulation. Capture only completed verification attempts; unknown/incomplete results are rejected. All commands emit JSON and return nonzero on failure. Output files cannot overwrite an existing identity or case.

1. **Before collecting examples**, pin the verifier implementation and configuration. Use its exact declared version and coverage, and repeat `--artifact` for every relevant verifier dependency. This records the files in use; it does not certify that the verifier's claimed coverage is correct.

   ```sh
   python -m silta.cnc.datasets identity --version '<pinned verifier version>' --coverage '<exact verification coverage>' --artifact silta/cnc/fusion.py --configuration verifier-config.json --output cases/verifier-identity.json
   ```

2. After a real job has recorded verification, capture specific attempts using that unchanged identity. These are example paths and attempt numbers; select attempts that actually exist in the job manifest.

   ```sh
   python -m silta.cnc.datasets capture --manifest runs/part-a/manifest.json --attempt 1 --identity cases/verifier-identity.json --kind checks --output cases/part-a-invalid.json
   python -m silta.cnc.datasets capture --manifest runs/part-a/manifest.json --attempt 2 --identity cases/verifier-identity.json --kind checks --output cases/part-a-valid.json
   ```

3. Register the cases. The output's `dataset_ref` is the content-addressed reference accepted by the main CLI's `--check-dataset` flag.

   ```sh
   python -m silta.cnc.datasets register --store versions --case cases/part-a-invalid.json --case cases/part-a-valid.json
   ```

For prompt/supervisor evaluation, capture with `--kind loop` and select one accepted target per part/setup. Register those case files separately and pass their returned `dataset_ref` as `--loop-dataset`. Include varied parts and reserve unseen cases for final assessment; do not let duplicate attempts overweight a single part. Check datasets require both simulator-valid and simulator-invalid examples.

Revalidate retained evidence before reuse:

```sh
python -m silta.cnc.datasets inspect --store versions --dataset '<dataset_ref>'
```

Keep the recorded job artifacts and verifier files: datasets reference their exact hashed bytes, including failed-verdict evidence. Moving, deleting or changing a referenced file makes reuse fail rather than silently relabeling it. Registration is local; the actual Weave dataset and paired results are published when a reusable-change evaluation runs.

The production `BenchmarkRunner` executes full controller runs sequentially with the accepted CAD target frozen, and disables recursive evaluation. Check replays use the configured isolated runner and reuse unchanged simulator labels. The CLI supplies these production factories; neither dataset preparation nor benchmark execution substitutes synthetic metrics when access is missing.
