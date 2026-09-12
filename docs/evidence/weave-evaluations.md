# W&B Weave Evaluations — published evidence

**Project:** <https://wandb.ai/silta/coreweave-hack-silta-squad/weave/evaluations>
**Published:** September 12, 2026
**Reproduce:** `make weave-evals` (needs `WANDB_API_KEY`; costs no inference credits)

The same 12 frozen fixtures and the same deterministic scorers that
`uv run python -m silta.evaluation --holdout` reports offline, published as
`weave.Dataset` + `weave.Model` + `weave.Evaluation` so the results are inspectable and
the two policies can be compared side by side.

## What was published

Four named evaluation runs, verified present through the Weave API
(`op_name_contains="Evaluation.evaluate"` returns them as root traces):

| Run | Dataset | Cases | Expectations matched | False accepts | False rejects | Mean simulations |
| --- | --- | --- | --- | --- | --- | --- |
| `silta-development-policy-v0` | `silta-fixtures-development` | 8 | 8/8 | 0 | 0 | 0.500 |
| `silta-development-policy-v1` | `silta-fixtures-development` | 8 | 8/8 | 0 | 0 | **0.375** |
| `silta-holdout-policy-v0` | `silta-fixtures-holdout` | 4 | 4/4 | 0 | 0 | 0.500 |
| `silta-holdout-policy-v1` | `silta-fixtures-holdout` | 4 | 4/4 | 0 | 0 | 0.500 |

The measured improvement is on the development split: policy-v1 reaches the same verdicts
using **one fewer stock simulation across eight cases** (mean 0.375 vs 0.500), because the
promoted `path_fixture_envelope` check rejects the clamp-collision case before the simulator
is called. Correctness is unchanged, in both directions: zero false accepts and zero false
rejects on both splits.

The holdout was evaluated once, after the change was frozen. The promoted check does not fire
on any holdout case, so it saves nothing there — and, importantly, costs nothing either.

## The scorers

Six scorers, all deterministic. None of them asks a model to judge anything.

| Scorer | Reads |
| --- | --- |
| `matches_expectation` | Did the pipeline reach the disposition and blocking checks the frozen oracle specifies? Accepts either allowed outcome where a fixture can legitimately be blocked at more than one stage. |
| `no_false_accept` | Did a known-invalid recipe pass? This is the number that matters most. |
| `no_false_reject` | Did a known-valid recipe get blocked? This is what guards a promoted early check. |
| `simulation_cost` | Simulations run and simulation seconds — the cost the policy paid for its verdict. |
| `machining_quality` | Measured residual, gouge and estimated machining time. |
| `effort` | Candidates tried and wall clock. |

Feasibility is a conjunction: valid schema, unchanged design hash, valid CAD, every blocking
check passed, full feature coverage, and a successful stock/collision simulation. Unknown is
not a pass.

## One number that is easy to misread

`machining_quality.max_residual_mm` shows a mean of **2.5 mm for policy-v0** and **0.0 mm for
policy-v1** on the development split. This is **not** a cut-quality improvement, and should not
be presented as one. It is a measurement artefact: policy-v1 rejects the clamp-collision case
before simulation, so no residual is recorded for that case at all, and the mean is taken over
the remaining cases. The cut quality of a passing plan is identical under both policies.

## Honest limitations

- **12 fixtures.** These are counts with denominators, not a reliability claim. One saved
  simulation out of four on the development split demonstrates the mechanism; it does not
  establish a rate.
- **Deterministic planner by default.** The published runs use the deterministic planner so
  the evaluation is reproducible and free. `make weave-evals` accepts `--live` to plan with
  the configured W&B Inference provider instead; those runs consume credits and are not
  bit-reproducible.
- **Duplicate rows in the tab.** The first publish produced four runs with Weave's
  auto-generated names (`eval-2026-09-12-proud-flower` and similar) before run labelling was
  added. They carry identical metrics to the four named runs and can be ignored or deleted.
- **These evaluations score the pipeline, not the model.** They measure whether deterministic
  geometry reaches the right verdict under a given policy. They are not a benchmark of any
  language model's planning ability.
