# Weave monitoring: smallest useful addition

Reviewed September 12 PDT / September 13 UTC, 2026. **Recommend one deterministic programmatic Weave Scorer applied to finalized Fusion job calls, alongside the existing paired evaluations. Do not add a second service or route Fusion into the current shared native Signal.** The bounded scorer command is now implemented and its actual publication/readback is recorded below; automatic campaign invocation is not wired into the core runtime.

## What is actually required

The current [organizer listing](https://luma.com/coreweavehacks) awards Best Use of Weave and emphasizes observing, evaluating, tracking and improving loops. It does not require Signals, monitors, a particular integration count, or numeric judging weights. The saved handbook summary in docs/hackathon.md requires W&B and meaningful sponsor usage. No reviewed criterion makes a native Signal mandatory.

Our stronger evidence is a traceable failure-to-learning-to-measurement chain. Native monitoring is useful only when its results identify actionable issues; counting integrations is not an evidenced judging strategy.

## Current project state, read directly

Read-only Trace API queries at 2026-09-13 05:37–05:39 UTC found:

| Field | Observed value |
| --- | --- |
| Project | silta/coreweave-hack-silta-squad |
| Native Monitor | silta-verification-evidence-e894 |
| Monitor digest | z3xBzQOvzLDYZczdnvZlA1T5l3VD1A23lR2sIiVwWZQ |
| Active / sample rate | true / 1.0 |
| Eligible operation | weave.genai.turn_ended |
| Additional filter | agent_name equals silta-cnc |
| Referenced scorer | silta-verification-evidence-e894-scorer |
| Actual stored model | coreweave/openai/gpt-oss-20b |

The model ID was read from the referenced LLMStructuredCompletionModel object, not inferred from a label. This shared native monitor is not Astra. It was left untouched. Its presence does not establish Fusion coverage.

Fusion uses ordinary Weave Ops in silta/cnc/tracing.py: cad_target, cam_candidate, candidate_checks, fusion_verification and supervisor_decision. Recorded roots include machining_job and resumed_job. These op calls do not themselves satisfy the native monitor's required agent-turn operation. No eligible Fusion turn or native scorer result was observed in a limited recent-100-call read; that sample is not an exhaustive agent-span audit. A programmatic_verification_signals call was observed, but its name alone does not establish native Signal execution or Fusion evidence.

The hardcoded not_configured fields in scripts/demo/sponsor_review.py and older sponsor documentation are stale. Correct reporting is: **project_has_native_monitor; Fusion_coverage_unverified; model=gpt-oss-20b; no monitor changed**. Keep custom-simulator evidence separate from Fusion machine verification.

Existing local receipts retain a finalized paired evaluation on six historical cases: four valid and two invalid. Baseline caught 0/2 invalid, learned checks caught 2/2, both retained 4/4 valid. These are selected three-axis historical replay cases, not held-out indexed-machine generalization or a live promotion gate. Sources: output/evaluation/learning-evaluation.json and its two finalized Weave call references. ARIA analysis and the bounded readiness change have separate evidence in output/sponsors/aria-review.json; do not merge those claims with native Signals.

## What the current APIs support

| Option | Fit and complexity |
| --- | --- |
| Programmatic Scorer on a completed Call | Deterministic Python in our existing process. Weave stores the scorer result and linked scoring call. No model, new server or UI configuration needed. Recommended. |
| New native agent Signal | Scores agent turns, not arbitrary Fusion stage Ops. A custom definition goes to an LLM judge; filters, tool-call context and sampling are configurable. Need eligible turn instrumentation and an actual Astra runtime selection before using it for this pipeline. |
| RemoteScorer | The installed SDK supports a customer-managed HTTPS scoring endpoint invoked by the Weave worker. This can support custom deterministic logic but adds a deployed endpoint, routing and operational work. Not justified here. |
| Legacy Monitor | Still present in SDK 0.53.9, but current docs direct new implementations to Agents Signals. Constructing/publishing a Monitor alone does not prove hosted execution of arbitrary local Python. |

Official references: [programmatic scorers and apply_scorer](https://docs.wandb.ai/weave/guides/evaluation/scorers), [current agent Signals](https://docs.wandb.ai/weave/guides/tracking/view-agent-signals), [custom Signal configuration](https://docs.wandb.ai/weave/guides/tracking/create-custom-signal), [legacy custom monitors notice](https://docs.wandb.ai/weave/guides/evaluation/custom-monitors). RemoteScorer behavior was inspected directly in installed weave/scorers/remote_scorer.py; Call.apply_scorer in weave/trace/call.py.

## Minimal integration contract

1. Refactor the deterministic review into a versioned FusionOutcomeScorer subclass with an op-decorated score(output) method. Give it a Fusion-specific name; do not reuse a custom-simulator scorer. Apply only to finalized, recognized Fusion job roots.
2. Keep completion and evidence distinct: job_completed, verification_completed, verified_best, false_completion, incomplete_collection. A verified best requires the fixed verifier's passed/completed verdict, retained evidence, no reported issues, required coverage and the matching best candidate. Missing or inconsistent fields produce unavailable/inconsistent evidence, not a pass.
3. Expose machining_seconds and illustrative cost only for that verified best and only when finite, nonnegative values were actually recorded. Never substitute zero for failed or incomplete jobs. Keep historical check replay latency separate from machining time.
4. Call await call.apply_scorer(FusionOutcomeScorer()) after the ordinary job call finishes, then flush and read back the scoring Call and attached score. Skip an already-scored call at the same scorer version. A one-shot backlog command can score existing completed Fusion roots; future calls can be scored at the existing campaign job boundary. No extra supervisor or long-running service.
5. Reuse the same deterministic semantics in offline evaluations. Compare completion rates and valid matched timings; report incomplete jobs in the denominator. A trace score reports verifier evidence, not independent geometry certification.

Call this **programmatic online evaluation with Weave Scorers**, not native Agents Signals. The current custom feedback publisher is a useful predecessor but does not create the same scorer lineage. Once actually published and read back, the new score provides an inspectable completion/reliability view with minimal work.

If a native Signals demo later becomes essential, inspect an Astra-compatible model/custom-runtime option and prove an eligible Fusion turn is scored before claiming it. Do not enable preset weaker-model scoring or reconfigure the shared existing monitor to manufacture coverage.

## Actual native Scorer publication

Implemented scripts/demo/score_fusion_runs.py and tests/test_demo_weave_scorer.py. Run through the existing credential scope:

    hsec exec --only COREWEAVE_WANDB_API_KEY -- .venv/bin/python scripts/demo/score_fusion_runs.py --publish

Without --publish it writes a separate local preview. Only manifests explicitly named by the selected Fusion campaign and their recovery sources are eligible. Each needs its own finalized run receipt; the exact original server root output must match the local result. The scorer rehashes retained candidate, verification and nested stock-comparison artifacts. It never scans generic recent project jobs for publication.

output/sponsors/fusion-native-scores.json records nine finalized scoring calls, original-root native runnable feedback IDs and successful server readback. A second run reused all nine scores at the same scorer version without new scoring calls. At this snapshot, UMC02 recovery4 is completed with a verified best of 371.053684 s; UMC03 recovery3 is not completed but retains a verified best of 438.955225 s. Those states are deliberately separate. Remaining scored recoveries have no verified timing and report null, never zero. UMC08 has no finalized receipt yet and was skipped.

The published scorer version is mHW6QIBH2BenHoJ5RuJcy8QHIzzo1mHkaMiHRRbtIM4. Use its recorded score URLs from the receipt, rather than earlier development scorer versions. Eighteen tests and Ruff passed; the installed Weave SDK emits a Pydantic deprecation warning during one test.

This is native Weave programmatic Scorer usage, not native Agents Signals. No UI, shared monitor settings, model calls, Fusion operations, or core runtime files were changed.
