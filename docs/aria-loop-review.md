# Loop review and Weave integration plan

Review date: 2026-09-12 (America/Los_Angeles). Reviewed code: `1b1980d23bcdefdf3986363d6055b84327f4dbac` on `toukoversion`.

This is a review and implementation proposal. It does not enable evaluation gates, change the learning loop, or report newly executed manufacturing experiments.

## Product and business logic

Silta helps evaluate a new part and develop a machining plan: drawing/PDF input, accepted fixed CAD, generated CAM, learned checks, Fusion verification, and an LLM optimization judge. The demo also illustrates text-prompt input. A new part does not need an existing production history: two CAM plans can be compared for the same fixed part and manufacturing setup.

The two feedback loops make sense:

1. A completed simulation failure provides evidence for a proposed early check and a CAM repair.
2. A verified plan gives the judge a starting point for a specific speed or cost improvement. The modified CAM must pass verification again.

The business outcome should be a useful, verified plan and an estimate under explicit assumptions. Shorter predicted machining time alone does not establish that a part is economical. The existing cost helper includes machine time, setup amortized over a batch, material, and tool wear. An economics decision additionally needs a customer cost ceiling or price/margin target, the cost of planning/optimization, and an appropriate treatment of uncertainty and unmodeled production costs.

The code already preserves the best verified candidate, bounds attempts, keeps the accepted target fixed, and stops on incomplete verification. Keep those properties.

## Main loopholes

| Issue | Why it matters | Recommended response |
| --- | --- | --- |
| A proposed lesson becomes shared policy immediately | `SharedLearning.apply()` validates structure and Python syntax, but not whether the change helps other parts. | Keep a hypothesis local to its job; evaluate a reusable proposal before global activation. |
| A failure is treated as a universal rule | A fixture-specific test can reject valid CAM for another setup. | Record applicability and test valid counterexamples, failure cases, and boundary cases. |
| The judge's opinion stands in for an experiment | “Use shorter toolpaths” is a hypothesis, not evidence that the revised CAM is faster. | Compare the revised and best valid plan in the same simulator under fixed constraints. Keep improvements backed by results. |
| A shared full-file replacement can forget earlier lessons | New checks or instructions can remove, contradict, or overgeneralize older ones. | Save immutable versions, diffs, provenance, and rollback references; evaluate old versus proposed versions. |
| A falling average can reflect easier parts | Raw machining time over the latest 20 different parts confounds part complexity with learning. | Compare frozen and learned systems on the same unseen parts. Report correctness and failure rates alongside paired time/cost differences. |
| Generated check code runs on the host | `local_checks.py` explicitly describes a process with limits, not a security sandbox. | Before use with untrusted inputs, isolate generated execution from host files, credentials, and network access. |
| Simulation approval is mistaken for production qualification | Geometric agreement does not establish posted-NC correctness, cutting forces, chatter, tool life, finish, or real setup accuracy. | State the achieved verification scope; add posted-NC checks and physical inspection evidence as the product matures. |

Adding prompt instructions does not update model weights. It improves the surrounding agent system through persistent instructions and checks. A judge can still be nondeterministic while following an explicit rubric; an empty prompt is not what makes it nondeterministic.

## Judge behavior

Ask for a concrete hypothesis, the evidence that motivated it, the proposed CAM change, and the conditions where it applies. For example: “These non-cutting moves account for much of this plan's time; reorder these operations to reduce travel while retaining clearance.”

Measure the actual revised plan. Require unchanged geometry, manufacturing constraints, and verification coverage. Never reward lower reported time if the part is incomplete or verification is unknown. Use a bounded optimization budget and retain the best verified result even if the last attempt is worse. For a batch, compare the expected batch savings with the additional planning and simulation cost.

## Minimum useful Weave evaluation

Use Weave for versioned traces, datasets, and paired evaluations. Keep manufacturing truth in the fixed verifier. Weave records and compares evidence; an LLM text score does not replace Fusion verification.

Start with two distinct evaluations:

| Evaluation | Inputs | Scorers |
| --- | --- | --- |
| Learned Python checks | Frozen CAM examples with independently established valid/invalid labels, failure reasons, setup and evidence hashes | False rejection of valid CAM, missed known failures, correct failure reason, unsupported coverage, execution errors, check wall time |
| Learned CAM instructions | The same held-out parts run under old and proposed instructions, with learning disabled during comparison | Verified completion, first-candidate success, unknown/failure rate, CAM attempts, simulation calls, planning wall time/cost, paired machining time/cost for mutually verified results |

Choose a small initial suite that includes valid cases, known failures, and cases near each learned rule's boundary, with more than one geometry/setup where supported. Split by part or geometry family rather than scattering attempts from the same part across development and holdout. A tiny suite is a regression starting point, not proof of broad generalization. Repeat stochastic agent runs; do not infer a reliable gain from one lucky sample.

For the judge's text output, deterministic checks can validate required fields, referenced operations, and allowed changes. A calibrated LLM scorer can assess whether the explanation is grounded in the supplied evidence and makes a specific, applicable proposal. The final score for speed advice must come from the resulting verified CAM, including regressions and extra compute.

Promotion should require demonstrated benefit without new protected-case false rejections or escaped known failures. Keep failure outcomes in the denominator; do not record their machining time as zero. Separate predicted physical machining time from the wall time spent running simulation.

## Proposed repository changes

These are proposed follow-up changes, not implemented by this review.

| File | Work |
| --- | --- |
| `silta/cnc/tracing.py` | Extend existing stage traces with stable job/attempt IDs, policy hashes, proposal provenance, and measured costs. Preserve current client/SDK redaction. |
| `silta/cnc/learning.py` | Retain immutable proposal contents and parent references; distinguish proposed, evaluated, and active versions. Keep activation atomic. |
| `silta/cnc/controller.py` | Separate job-local feedback from shared activation; emit proposal/evaluation/activation events and unambiguous attempt outcomes. |
| `silta/cnc/evaluation.py` | Reuse the existing paired evaluation and `EvaluationLogger` publishing code. Add the missing outcome metrics and frozen independent labels instead of building a second evaluator. |
| CLI wiring | Add an explicit offline/shadow evaluation command first. Change the default runtime's activation behavior only as a separately reviewed implementation decision. |
| `tests/test_cnc_evaluation.py`, `tests/test_cnc_controller.py`, `tests/test_cnc_tracing.py` | Cover a deliberately harmful proposal, false rejection, unknown verification, recovered success versus first-candidate success, and exact version attribution. |

For the hackathon, prioritize trustworthy traces, one versioned check replay, and one paired prompt comparison. Later, expand holdouts, calibrate judge scores with manufacturing reviewers, isolate generated execution, and add staged activation with rollback.

The existing default deliberately bypasses evaluation gates; see `docs/implementation-plan.md`. This note recommends an evaluation path but does not silently reverse that decision.

## ARIA collaboration log

ARIA was consulted in the `silta/coreweave-hack-silta-squad` W&B project. We shared the exact demo link and corrected the earlier chat's stale code assumptions. ARIA confirmed after reviewing the supplied commit that stock comparison is now present and that direct shared updates remain the main risk. Its earlier claims about an incomplete positive verifier path referred to older captured code and must not be applied to this commit.

Artifact supplied: [demo at reviewed commit](https://github.com/noppud/CoreWeave-Hack-Silta-Squad/blob/1b1980d23bcdefdf3986363d6055b84327f4dbac/demo/index.html). The 54-part animation is illustrative, not measured learning evidence.

Questions sent, in order:

1. “Does this make sense for judging whether a new part is economical to manufacture? What are the three biggest holes? Review only; don't launch runs.” Context included both loops, persistent lessons, the fixed CAD target, and the current direct-update behavior.
2. “Then give us the smallest useful Weave eval plan: how do we test new Python checks and learned text instructions against the old version on unseen parts? Which scorers catch false rejections and bad speed advice? Keep it short and practical.”
3. “Make that a concrete integration plan for this repo: which files should change, what should we trace, and how should we version and evaluate prompt/check updates in Weave? Separate a hackathon minimum from later work. We'll save this review in GitHub. Advice only for now.”

ARIA was authorized to read the linked GitHub source. We did not ask it to launch experiments or alter the manufacturing system. Its analysis is advisory, not an independent manufacturing validation.

ARIA's completed review identified three main issues: unevaluated shared learning, confusing geometric verification with production readiness, and an economic objective without a numerical rule for whether another optimization attempt is worthwhile. Its project-run analysis also recommended separating LLM spend from manufacturing cost and recording commit/policy hashes consistently. The older aggregate runs are not evidence of this exact commit's performance.

For a minimal evaluation, ARIA suggested eight unseen parts with verified valid candidates and verified invalid candidates where available. It proposed replaying old/new checks on these frozen examples, and comparing old/new prompts end-to-end on four to eight unseen parts. Its check scorers were false rejections, newly caught failures, newly escaped known failures, and runtime; its prompt scorers covered lost verified completions, verification regressions, paired objective changes, additional simulation attempts, and net economic value. These small sample counts are a hackathon starting point, not a sufficient production validation size.

ARIA recommended activating the existing paired gate. Our staged recommendation is to run that evaluator explicitly in shadow/offline mode first, establish useful frozen cases, and then review global activation separately. This respects the current deliberate direct-learning configuration while making its limitations visible. Repeatedly using the same holdout for policy selection can also overfit it; reserve an untouched final evaluation set before making a generalization claim.

### ARIA's repository-specific integration proposal

ARIA completed the third question and proposed the following migration:

- In `silta/cnc/cli.py`, replace direct `SharedLearning` wiring with the existing `VersionStore`, `BenchmarkRunner`, and `WeaveEvaluationGate` path. Missing evaluation data should defer reusable promotion rather than apply a proposal.
- In `silta/cnc/controller.py`, preserve immediate job-local repair instructions, but require paired evaluation and a successful publication receipt before changing globally active checks or prompts. Preserve stale-version protection.
- In `silta/cnc/evaluation.py`, route check and prompt proposals to separate frozen datasets. Retain the current paired `EvaluationLogger` publisher and add explicit compatibility coverage for its private `_evaluate_call` access; consider public `weave.Evaluation` APIs later.
- In `silta/cnc/datasets.py` and `silta/cnc/benchmarks.py`, record part/source-job identities and manufacturing context; reject proposal-source leakage and keep learning disabled during comparisons.
- Publish immutable policy objects and datasets to Weave, recording their URIs alongside local hashes. ARIA recommends retaining the existing local production pointer during the hackathon rather than migrating activation to cloud aliases simultaneously.
- Add proposal, benchmark, scoring, publication, activation-decision, and active-version-change traces. Store references to large code/evidence objects instead of repeating their contents in every span.
- Test that a harmful proposal, missing publication, or stale proposal cannot change active policy. Demonstrate one check proposal and one prompt proposal through the complete evaluation path.

This is more than adding logging: it changes the runtime's learning policy and storage design. It should be implemented as a separate reviewed change, not presented as already deployed by this documentation update. ARIA's strict “no regression in any metric” suggestion also needs an explicit product decision: preserve hard verification constraints, but choose an economic objective and allowable efficiency tradeoffs rather than treating every diagnostic metric as an independent business objective.

## References

- Current direct-update behavior: `silta/cnc/learning.py`, `silta/cnc/controller.py`, `docs/implementation-plan.md`.
- Current stage tracing and paired publishing: `silta/cnc/tracing.py`, `silta/cnc/evaluation.py`.
- Cost assumptions: `silta/cnc/ui_verifier.py`, `FusionUIVerifier._cost`.
- [Weave evaluations](https://docs.wandb.ai/weave/guides/core-types/evaluations).
- [Weave scorers](https://docs.wandb.ai/weave/guides/evaluation/scorers).
- [EvaluationLogger](https://docs.wandb.ai/weave/guides/evaluation/evaluation_logger).
- [ARIA overview](https://docs.wandb.ai/aria/overview).
