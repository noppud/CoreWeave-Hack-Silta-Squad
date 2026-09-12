# Silta CNC — implementation and recursive agent playbook

Status: ready for implementation handoff; tasks below are not completed. Read [plan](plan.md), [architecture](architecture.md) and [rules](hackathon.md) first. Baseline code is a Python CLI draft/critique/revise example, not a CNC application.

## 1. Execution order and estimates

Estimates assume a lead builder, another coding agent used for bounded implementation/review, and a human handling sponsor access/demo/submission. Workstreams are responsibilities, not invented team members. The same people can fill several roles. Plan roughly 14–18 focused engineering hours including live deployment; actual CAD/visual integration may require cuts. Preserve submission buffer rather than hiding overruns.

| ID | Task / owner role | Depends on | Timebox | Reviewable exit artifact |
| --- | --- | --- | --- | --- |
| T00 | Feasibility + sponsor access / lead + human | — | 45 min | CAD roundtrip, notebook/widget spike, provider capability result, ARIA access status. |
| T01 | Contracts + synthetic fixtures / domain builder | T00 | 45 min | Validated models, frozen coordinates, independent good/bad recipes. |
| T02 | Deterministic CAD + export / geometry builder | T01 | 60 min | STEP roundtrip, mesh, measured oracle report. |
| T03 | Checks + path templates / geometry builder | T01 | 90 min | Short-tool failure, valid reach path, complete operation/trajectory contract. |
| T04 | Repair controller + inference + telemetry / lead | T01–T03 | 75 min | Real CLI repair, bounded calls, local evidence + remote trace. |
| T05 | marimo chat vertical slice / UI builder | T02,T04 | 60 min | Upload/confirm/chat/check/repair/export working in one app. |
| T05D | First live deployment / lead | T05 | 60–90 min | Cloud Run HTTPS URL, remote chat/CAD/check flow, durable artifact download; see deployment.md. |
| T06 | Simulator + viewer / geometry + UI | T03,T05 | 150 min | Actual clamp collision, repaired path, stock removal, synchronized playback. |
| T07 | Cross-task evaluation + ARIA / evaluation builder + human | T04,T06 | 90 min | Baseline batch, actual recommendation, reviewed rule, controlled comparison. |
| T08 | Live release hardening / reviewer | T05D–T07 | 90 min | Remote full flow, cancellation/idempotency, two-session isolation, restart recovery and release URL. |
| T09 | Demo + submission package / human + lead | T06–T08 | 90 min | Recording, rehearsal, evidence links, filled draft, submission readiness. |

T00 must not become an infrastructure project. Prove a block/pocket can be generated, exported and reimported; prove the viewer can display a static trajectory; verify model/ARIA access. If CAD binaries fail, try a compatible locked environment/container in that timebox. Do not substitute an arbitrary mesh and continue claiming STEP works.

Suggested checkpoints in Pacific time, assuming work begins Saturday afternoon:

- Saturday ~3 PM: contracts, real CAD, primitive checks and first CLI repair.
- Saturday ~5 PM: one complete marimo user flow and first live deployment, even with an unpolished viewer.
- Saturday ~7:30 PM: collision/repair/stock-removal replay and saved real sponsor evidence.
- Saturday before 9 PM venue close: known-good checkpoint, local replay and continuation notes.
- Sunday 9–10:30 AM: ARIA comparison, held-out evaluation, final integration.
- Sunday 10:30 AM: feature freeze. Fix blocking failures only.
- Sunday 11:30 AM: recording and clean-start rehearsal complete.
- Sunday 12:15 PM: intended submission target; 45-minute buffer to published 1 PM deadline.

Rebase these checkpoints to actual progress. If T06 is not working Saturday evening, cut P1/P2 immediately. Preserve core chat, STEP, real checks/simulation, sponsor evidence and the recording.

## 2. Task-level acceptance criteria

**T00 — feasibility/access:** exact pinned dependency smoke test; CAD geometry and STEP import both work; notebook displays a local widget asset; model schema/repair/vision capabilities recorded separately; ARIA team project access checked; activated credit balance remains separate from API-key presence. Human confirms submission/roster logistics. No requirement to train a model or allocate a GPU.

**T01 — contracts:** canonical units/transforms, immutable spec revision, stable IDs and schema; independently authored expected geometry; fixtures explicitly identify naive/valid recipes and origin. Invalid units/references/nonfinite values fail. Freeze 8 development/4 holdout IDs before tuning.

**T02 — CAD:** deterministic build for same inputs; positive valid solid; intended feature count/dimensions; STEP reimport; independently calculated volume/bounds within declared numerical tolerances. Image interpretation is not allowed to bypass spec confirmation.

**T03 — checks/paths:** inventory, reach, radius, depth, workspace and coverage checks. Compiler emits stable segment IDs, rapid/feed semantics, tool envelopes and declared coordinate convention. Tool movement between operations cannot silently pass through stock. Unknown operations stop cleanly.

**T04 — runtime:** fake-provider contract suite and a separately recorded real inference trajectory. At most three candidates; schema repair/retries included in global budget. Repeated candidate stops. Corrected plan retains target hash. Cancel/budget exhaustion cannot publish success. Weave trace and W&B metrics are read back, not merely emitted.

**T05 — UI:** example and uploaded image → editable proposal → confirmed spec → plan/check/repair → output. Orbit, filter, playback and reactive rerenders create no duplicate inference. Missing values prompt one coherent clarification. Timeline and artifacts share attempt IDs. Keyboard-accessible controls and readable 1440×900 demo layout.

**T06 — simulation/3D:** independently known collision at an intermediate segment, valid corrected path, correct stock removal and drill-tip convention. Test a collision between sample endpoints. Renderer consumes simulation data; collision position/segment match report. Grid convergence bounds numerical error; unsupported shapes do not pass.

**T07 — improvement:** actual ARIA recommendation referencing development run IDs; one implemented policy/check change with lineage; fixed-candidate validator comparison; false-positive boundary cases; fresh held-out report. Include all failures and actual denominators. No invented uplift.

**T08 — operations:** clean locked install and deployed full-flow test; valid/invalid jobs, cancel, duplicate requests, stale edits, provider timeout/auth/429, telemetry outage, restart/replay and export/hash integrity. Verify two browser sessions remain isolated and artifacts survive revision restart. Record live URL, image digest, release commit and remote smoke-test job. Browser reload must not reinterpret replay as live. See [deployment acceptance](deployment.md).

**T09 — delivery:** all requested sponsor uses evidenced; three-minute rehearsal; <2-minute recording; laptop backup; public repo and correct release commit accessible; every teammate/platform survey complete; final submission fields populated. Only the actual submission confirmation establishes submitted status.

## 3. Two-agent recursive build/review loop

Use a lead implementation agent and a bounded second agent as implementer or reviewer. Do not recursively spawn an unbounded tree. One writer owns a shared module at a time. Parallel work is safe only after contracts are frozen and assignments name separate files. If only one coding session exists, alternate builder/reviewer passes explicitly.

```text
while required_tasks_remain and time_before_feature_freeze:
    select smallest task with dependencies satisfied
    define acceptance evidence and allowed files
    builder implements one working slice
    run targeted checks and save artifacts
    reviewer inspects changed code + independent oracle + real output
    if blocking defect:
        builder fixes it; repeat affected checks; reviewer rechecks
    else:
        integrate; record checkpoint; select next task
    after two failed repair cycles:
        diagnose root cause, simplify approach, or name external blocker
        continue any independent required work
freeze features; run full demo/evidence checklist; fix only blockers
```

“Recursive” means repeated evidence-driven build/review/fix cycles, with bounded decomposition when a task is too large. It does not mean indefinite retries until a score looks good. Stop a task only at its acceptance criteria or a concrete external blocker. Do not declare the whole product ready while ARIA, actual simulation or mandatory submission artifacts are absent.

### Builder task packet

```text
Task: Txx — <concrete behavior>
Baseline: <commit>; current checkpoint: <path>
Read: docs/plan.md, docs/architecture.md, relevant contract/fixture files
Own: <explicit files>; coordinate before changing shared contracts/lockfile
Inputs: <fixture IDs and immutable hashes>
Acceptance: <observable pass/fail cases>
Implement the smallest complete slice and run targeted verification.
Do not change customer dimensions or weaken validators to force success.
Do not fabricate provider/ARIA results or use holdout answers in prompts.
Return: changed files, checks/results, real artifact paths, risks/blockers.
```

### Reviewer task packet

```text
Review Txx against its acceptance criteria and the fixed oracle.
Check unit/coordinate consistency, artifact lineage, state/cancellation,
failure honesty and whether the viewer represents actual simulation.
Inspect test independence; passing tests alone are not proof.
Report blocking defects with file references and reproduction steps.
Separate required fixes from optional polish. Do not edit shared code
unless explicitly assigned a separate fix task.
```

### Checkpoint format

Create `docs/checkpoints/current.md` during implementation, keeping old checkpoints when useful:

```text
Commit / time:
Last accepted task:
Current task and file ownership:
Working user flow:
Checks run and exact outcomes:
Evidence paths / Weave / W&B / ARIA references:
Remaining defects and external gates:
Next smallest task:
Time and inference budget remaining:
```

No secrets in checkpoints. A successful local command, pushed commit, visible trace and submitted project are distinct states. Integrate/checkpoint frequently under the implementation session's authorization; this planning change does not itself commit, push, publish or submit.

## 4. Verification matrix

| Layer | Independent oracle / test | Failure caught |
| --- | --- | --- |
| Specification | Known drawing dimensions; missing-units fixture | Hallucinated or ambiguous geometry. |
| CAD | Analytic dimensions/volume + STEP reimport | Broken export, units, missing features. |
| Recipe | Tool inventory and unchanged spec hashes | Invented tools, geometry changed to satisfy checker. |
| Compiler | Known segment expectations and path invariants | Unsafe traversal, incorrect entry, missing features. |
| Collision | Known intersecting/clear paths including between samples | Tunneling and decorative-only collisions. |
| Stock | Analytic pocket/hole fields; finer-grid comparison | Unremoved material, gouges, inaccurate green status. |
| Controller | Fake provider/clock, failure injection | Unlimited retries, late cancelled success, duplicated jobs. |
| UI | Browser full workflow + record/replay check | Stale attempts, broken download, reactive side effects. |
| Improvement | Frozen saved-candidate set + held-out fixtures | Benchmark leakage, false positives, made-up gains. |
| Sponsors | Remote read-back plus real ARIA reference | Scaffold presented as completed integration. |

Start with existing `make check` (Ruff and offline pytest). Add meaningful oracle/integration tests with implementation. Proposed future commands: `make check-cad`, `make check-simulation`, `make eval-offline`, `make eval-live`, `make app`, `make evals`, `make demo-replay`. They do not exist yet. Keep live network/spend checks outside default offline CI; run them explicitly with recorded limits. After targeted tests pass, run the full demo once at each integration milestone; repeat only for new changes or unresolved failures.

## 5. Cut order and escalation

Cut in order: training/distributed orchestration → gears/assemblies → generic STEP import → multi-face setup optimization → PDF → decorative machine details. Keep actual stock/tool/fixture visualization and the live deployment; hosting is required by the user.

If runtime is over budget, lower replay payload/resolution only after convergence analysis, simplify the fixture family, or reduce concurrent jobs. Do not disable collision checks. If model quality is poor, improve structured context/examples or use a capability-tested provider; keep the same benchmark accounting. If ARIA access fails, the human asks the onsite sponsor to resolve it while geometry/UI work continues.

External gate register: actual credit activation; ARIA Smart features/project permissions; roster/surveys; current submission controls; release/public access; final submission confirmation. Record owner and evidence. No generic “waiting for permission” pause for routine reversible implementation work already requested.
