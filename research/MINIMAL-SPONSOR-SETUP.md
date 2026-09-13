# Minimal sponsor integration

September 12, 2026. Planning only; no accounts provisioned, code implemented or additional files pushed. This refines SETUP-RECOMMENDATION.md and preserves the approved loop.

## Decision

Keep one Python application. Use Weave for traces, evaluation records, dataset versions and comparison; use the event-enabled W&B hosted Sandboxes service for isolated execution if available. Retain the proposed OpenAI Agents API harness subject to a successful connection test. FreeCAD/CAMotics and the trusted verifier remain the domain-specific work.

There is no need to add another agent orchestration framework, separate evaluation service, task queue, vector database, or model-training stack. Local job manifests and artifact directories are enough for initial durable state; defer SQLite until concurrent writers or queries justify it. Weave is the record of experiments, not the live controller's state store.

## Weave: reuse the loop

Decorate the meaningful controller functions with `@weave.op`: main-agent attempt, cheap checks, simulation, proposed-check validation and supervisor decision. Keep a root trace per part run. Attach candidate and artifact identifiers to each stage so a failure can be followed into the repair and the check it inspired.

Use `EvaluationLogger` to record the same application's outputs and scores. It supports incremental results, per-example scores and aggregate summaries without adopting the more opinionated `Evaluation` runner. Use the built-in evaluation comparison UI rather than building another leaderboard. [EvaluationLogger](https://docs.wandb.ai/weave/guides/evaluation/evaluation_logger), [comparison](https://docs.wandb.ai/weave/guides/evaluation/compare_evals).

Use versioned Weave Datasets for saved examples. Store references to geometry files, not large meshes in every trace. Each row identifies the target, NC candidate, machine, stock, fixture, tool library and verifier versions; each run identifies the checks, playbook and model settings. Keep artifact files durable outside expiring sandboxes. [Datasets](https://docs.wandb.ai/weave/guides/core-types/datasets).

The simulator produces a structured report once. The loop consumes it and the evaluation logger records its metrics. Do not run a second simulator merely to populate Weave. Our deterministic scoring functions supply manufacturing judgments; general language-quality scorers cannot establish geometry correctness. [Scorers](https://docs.wandb.ai/weave/guides/evaluation/scorers).

## Two evaluation workloads

| Workload | Input and execution | Evidence |
|---|---|---|
| Learned-check regression | Run proposed checks against frozen candidates with saved trusted simulator labels | Invalid candidates caught, valid candidates falsely rejected, check runtime and errors |
| Whole-loop comparison | Run baseline and learned configurations on the same held-out parts and machine/setup definitions | Verified completion, simulator calls and runtime, best verified machining time/cost, agent cost when available |

For check regression, reuse a saved label only if candidate, target, setup and verifier inputs are unchanged. This makes the check-learning loop cheap. New or modified candidates still require the normal simulation gate. A changed verifier invalidates labels under the old verifier unless explicitly revalidated.

Known training examples can guide the learner. Hold-out examples must remain unavailable to it; use a development validation set for repeated tuning and reserve an untouched final set to assess generalization. Repeatedly tuning against a holdout turns it into development data. Periodically simulate sampled check rejections to find valid plans that overly strict checks hide.

For end-to-end evaluation, compare three configurations as a small ablation: baseline fixed checks/playbook; learned checks; learned checks plus supervisor/playbook improvement. Keep model, part set, machine and operational budgets fixed. Report completion first, then time/cost on matched successful parts. Failures must not appear as zero-cost successes. Multiple trials expose stochastic variation when feasible; a small benchmark is demonstration evidence, not proof of universal improvement.

Evaluate stopping within that same workload: on a small offline sample, continue after a proposed stop with a bounded number of extra verified trials. Record whether meaningful improvement was missed. This measures the value of the stopping decision without creating another agent framework.

## Sandboxes: buy the isolation, not a cluster project

The current W&B hosted Sandboxes documentation describes public preview with organization enablement. The separate CoreWeave `cwsandbox` getting-started path has infrastructure/runner requirements. Do not treat those as interchangeable accounts or APIs. Prefer the hosted service actually provisioned for the event and confirm its SDK and entitlement. [W&B Sandboxes](https://docs.wandb.ai/sandboxes), [CoreWeave setup](https://docs.coreweave.com/products/sandboxes/get-started).

Use the provider's existing image configuration, command execution, file transfer, resource limits, timeout and cleanup capabilities. Avoid writing our own container scheduler. A pinned image contains public software dependencies, never drawings or keys. Private job inputs arrive through file transfer.

Proposed execution pattern:

- One editing sandbox for a part episode, reused across repairs so dependencies and work files remain available.
- Trusted verification in a clean environment whose code and target cannot be changed by the editing agent. One shared image can support both roles, with different mounts/permissions and entrypoints; they do not need independent software stacks.
- Export final artifacts and the manifest before shutdown. Persist the incumbent outside the sandbox.
- Evaluate parts sequentially first. Add a small concurrency limit only when measured runtime warrants it. Do not share writable candidate directories across evaluation cases.

A provider SDK can simplify lifecycle and isolation; it does not automatically make agent-editable verification trustworthy. Reusing a verifier worker later requires a tested reset procedure.

The OpenAI Agents API harness can connect to a self-hosted executor, but the W&B-hosted integration needs a real test of process lifetime, outbound connection and artifact retrieval. Keep one harness if it works; do not layer the OpenAI Agents SDK and another orchestration framework over it. If the bridge is the blocker, the Python application can expose sandbox commands as model tools without changing the machining loop. [OpenAI self-hosted environments](https://developers.openai.com/api/docs/guides/agents-api/environments/self-hosted).

## Optional sponsor features

**Signals:** once core logging works, optionally sample a signal that asks whether an agent's success claim has matching verification evidence. This is diagnostic, never the machining gate. It should surface contradictions for review, not replace deterministic report checks. Signals have inference cost; no need to enable a broad suite. [Custom signals](https://docs.wandb.ai/weave/guides/tracking/create-custom-signal).

**ARIA:** use it to analyze completed experiment summaries and suggest the next investigation. If its documented W&B run-based workflow requires summaries in W&B Runs, add one summary per benchmark configuration with a Weave link; do not duplicate every event. It is optional until project access is verified. Avoid adding Launch/sweep infrastructure just to use ARIA. [ARIA](https://docs.wandb.ai/aria/overview).

**marimo:** use the same saved results for machine replay and graphs. No second backend or metrics pipeline. Molab hosting can be added when access and runtime support are known.

**W&B Inference / TypeSafe / ART:** defer until a measured need exists. The initial learning is tested check code and planning guidance, not model weights. Sponsor value comes from actual useful work done by the selected services.

## Minimum proof

1. One real controller run is visible in Weave, with stage outputs and session IDs.
2. One sponsor sandbox runs the pinned native software, exports its artifacts, and cleans up correctly.
3. One simulation-discovered failure creates a proposed cheap check that catches related failures without rejecting the saved valid counterexamples.
4. Weave compares baseline and learned versions on unchanged evaluation inputs.

OpenAI managed Agents API internal tracing and token accounting are not automatically established by Weave's separate Agents SDK integration. Record observable controller operations and explicit reported usage; unknown cost stays unknown. [Weave Agents SDK integration](https://docs.wandb.ai/weave/guides/integrations/agents/openai-agents-sdk).
