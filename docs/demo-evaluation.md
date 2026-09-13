# Demo evaluation

The demo has a published, paired Weave evaluation of empty versus learned checks on six retained Fusion cases. This is an offline replay against historical verdict evidence. It does not change either active learning file or add a promotion gate.

Results: empty checks caught **0 of 2** known invalid plans; learned checks caught **2 of 2**. Both variants allowed all **4** known valid plans. Five isolated runs per case/variant produced identical verdicts. The median across per-case median runtimes was **24.0 ms** for empty checks and **43.3 ms** for learned checks. These timings include artifact preparation; they are not CNC cycle times.

- [Empty checks evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-b76f-7744-b619-b7a569677668)
- [Learned checks evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-c591-7d3f-984c-4d661ab3d124)

These corrected native-summary calls republish the existing frozen replay; there were no additional check, model or Fusion executions. The original calls and receipts remain preserved. Both new calls were read back with the correct native score aggregates, and the learned Evaluation UI was visually confirmed with 6 examples. Its runtime is the mean of six original per-case medians: 30.586 ms baseline and 43.252 ms learned. The median-of-medians figures above describe the original local report. Dataset and evaluated source code are linked. See [summary repair and denominators](weave-evaluation-dashboard.md).

## Run

From the repository root:

```sh
.venv/bin/python scripts/demo/evaluate_learning.py
hsec exec --only COREWEAVE_WANDB_API_KEY -- .venv/bin/python scripts/demo/evaluate_learning.py --publish
```

The first command produces local replay results. The second also publishes paired Weave evaluations. A fresh local-only run replaces the UI artifact with a local-only status; run with `--publish` for a fresh published demo result. Missing credentials or publication errors cannot be reported as published.

UI data is `output/evaluation/learning-evaluation.json`. Full raw samples, retained cases and scoring details are in `output/evaluation/replay-evidence.json`. Exact executed check snapshots are adjacent hash-named Python files. `variants[].median_runtime_ms` is the median of the six per-case medians, each calculated from five repetitions.

The six selected cases are A's fixture collision, B's stock-conformity failure, and the final verified A/B/C/D plans. Every referenced input, target, candidate and verdict-evidence artifact is hash-validated before replay. Execution errors are rejected rather than counted as caught manufacturing failures.

## What this proves

The current learned checks reject the two selected historical invalid plans while retaining four historical valid plans. It makes the learned-check benefit visible and auditable in Weave.

The historical verifier source bytes were not retained. The dataset's `verifier_hash` is explicitly an identity of the recorded verdict and evidence, not a claimed implementation hash. Accordingly, this is **historical-label replay**, not the stronger frozen-verifier benchmark described by the deferred evaluation gate. It is not a held-out test or a production speedup claim.

The prompt panel separately displays the current guidance and historical verified within-part candidate improvements: A 384.860→211.037 seconds and C 228.182→211.850 seconds. These are estimated machining times of specific verified candidates, not controlled measurements of changing the prompt alone. Historical learning was applied directly, before this retrospective evaluation.

The three-axis learned checks do not cover the indexed simulation machine. The custom machine visualization and the retained Fusion evaluation evidence must retain their distinct labels.
