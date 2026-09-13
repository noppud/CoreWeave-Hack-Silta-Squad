# Native evaluation dashboard summary repair

The original six-case evaluations retained correct per-row scores but suppressed the standard aggregate scorer output by calling `EvaluationLogger.log_summary(..., auto_summarize=False)` with application totals. The Evaluation page therefore reported no scorer data. The repaired publisher declares scorer names, retains automatic summarization, and stores custom counts and scope under the SDK's `output` summary field.

This follows the [official EvaluationLogger workflow](https://docs.wandb.ai/weave/guides/evaluation/evaluation_logger). Installed Weave0.53.9 source confirms that automatic summaries exclude null values for each score: invalid-only catch rate uses two cases; valid-only false rejection and acceptance use four. Eight tests exercise those denominators against the installed SDK, reject malformed timing and require native aggregate keys during server readback.

New evaluation pair, published September13 UTC:

- [Baseline: native summary v2](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-b76f-7744-b619-b7a569677668).
- [Learned: native summary v2](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-c591-7d3f-984c-4d661ab3d124).

| Metric | Baseline | Learned | Denominator |
|---|---:|---:|---|
| Invalid cases caught |0 (0%)|2 (100%)|2 invalid cases|
| Valid cases falsely rejected |0 (0%)|0 (0%)|4 valid cases|
| Valid cases accepted |4 (100%)|4 (100%)|4 valid cases|
| Mean recorded check runtime |30.586ms|43.252ms|6 per-case medians|

Each original case/variant median came from five earlier check executions. This publication did not execute checks again and did not run Fusion, inference or promotion. It republishes frozen observations to correct their presentation; it is neither an independent replication nor a new generalization result. Runtime is check execution/artifact preparation, not CNC cycle time. Original evaluation calls, receipts and film references remain unchanged.

The new receipt is `output/evaluation/native-summary-20260913T064011Z/publication.json`. It pins the original replay/receipt hashes, original evaluation references, dataset and result identities, and exact finalized server summaries. Both calls were read back with the expected native scorer keys and values. The presenting agent subsequently verified the learned Evaluation UI in the authenticated browser: caught_invalid 100%, false_rejection 0%, accepted_valid 100%, runtime 43.25 ms average and 6 examples. This is observed dashboard rendering in addition to the server-summary checks.

To publish the same retained observations as another explicitly named evaluation, without changing the original files:

```sh
hsec exec --only COREWEAVE_WANDB_API_KEY -- .venv/bin/python \
  scripts/demo/evaluate_learning.py --publish --republish-retained
```

This needs the retained replay and original source files; a clean source checkout does not include them. Each invocation creates a new output directory and evaluations. Do not use the command as a routine refresh when existing links suffice. The ordinary replay command also uses the corrected native summary format for future evaluations.
