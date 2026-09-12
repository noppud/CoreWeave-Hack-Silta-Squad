# Durable learning memory and W&B Sandbox validation

Implemented September 12, 2026. This extends the active machining controller and the marimo demo; it does not change model weights.

## What improves

Every completed attempt stores its plan, measured checks, simulation verdict, repair differences and provenance. Later attempts read recent measured failures. Later jobs with identical engineering inputs can start from a previously verified recipe, avoiding the same rejected starting point and unnecessary model calls. That recalled recipe still undergoes all current checks, compilation and simulation.

The regression demonstration compares a cold run (short tool failure → clamp collision → passing repair) with a new controller reading the same durable backend. The cold run takes three attempts; the warm run takes one and makes no additional planner calls. This is a measured fixture result, not a claim that every drawing becomes faster.

## Storage and isolation

`LearningMemory` uses the existing `Storage` adapter:

- Cloud Run: Google Cloud Storage selected by `SILTA_ARTIFACT_BUCKET`.
- Development: atomic local files selected by `SILTA_ARTIFACT_DIR`.
- Keys: `memory/<scope>/<context-hash>/episodes/`, `lessons/`, and `validations/`.
- Each attempt/report has a separate object. Workers do not append to a shared mutable JSON array, so simultaneous writers do not erase one another's attempts.
- Context includes the exact design hash, shop hash, policy rules/promoted checks, and a fingerprint of the CAD/check/domain/policy/simulation/toolpath implementation. A change in any of these invalidates recipe and advice retrieval.
- Only the exact team-authored public demo part and shop use `public-demo` scope. Other inputs use a hashed session scope. No visitor can promote arbitrary content to a team-wide policy.
- Retrieval bounds prompt context to recent evidence and at most five validated lessons. The prototype lists stored objects to select them; a paginated indexed store and retention policy are future work for sustained high traffic.

Persisted memory survives controller/server restarts when the same backend and scope are retained. Private session memory requires that session identity; opening a fresh private browser session intentionally creates a separate scope.

## Three kinds of memory

1. **Observed evidence:** failed check IDs, actual/required values and episode IDs. The planner reads these as measurements, not instructions.
2. **Proposed/validated advice:** trusted instruction templates selected by observed failure codes. Proposed advice is inspectable but does not influence planning until a passed validation report exists. Repeated observations retain their separate source episodes and are deduplicated during advice retrieval.
3. **Verified recipes:** complete previously passing plans with source attempt IDs. They are eligible as starting candidates, never as cached approval. Source is labeled `memory_recipe`; a fresh failure prevents a passing result.

Attempt artifacts now record memory episode references, applicable lesson references and the recipe's source episode. Runtime `memory_read`, `memory_written` and `memory_unavailable` events make retrieval and persistence visible. Storage errors do not manufacture memory success.

## W&B Sandbox role

`WandbLessonValidator` creates a short-lived W&B Sandbox, runs a trusted standard-library validation program, captures its exit code and six fixed regression-case results, and closes the sandbox. The host stores the returned report in durable memory. The sandbox filesystem is disposable and is never the memory database.

The first supported lesson template concerns fixture clearance. Its cases cover a collision, safe clearance, the exact boundary, just below the boundary, no fixture, and invalid negative clearance. This gate validates a bounded planning instruction. It does **not** certify a complete machining plan, promote a new mandatory checker, or execute arbitrary model-written Python. Existing full geometry checks and simulation remain authoritative.

The public notebook offers **Validate learned advice in W&B Sandbox**. Failed execution, invalid output, authentication failure and unavailable service remain non-passing reports. Unsupported lesson types remain proposed. There is no silent local fallback labeled as a W&B run.

Official API sources: [create sandboxes](https://docs.wandb.ai/sandboxes/create-sandbox), [run commands](https://docs.wandb.ai/sandboxes/run-commands), [overview and installation](https://docs.wandb.ai/sandboxes). The installed SDK uses `wandb[sandbox]`; the compatibility wrapper currently warns that direct `cwsandbox` usage will replace it in a later release.

**Live probe status:** the configured W&B credentials produced `CWSandboxAuthenticationError` on 2026-09-12. No sandbox pass or lesson activation is claimed. W&B documents organization-enabled preview access; verify the organization's sandbox access and authentication configuration. Do not put credentials inside the sandbox command or public notebook.

## Judge walkthrough

1. Open **How the loop stores and reuses memory** to explain the two feedback paths: immediate repair and durable learning.
2. Complete a cold run with **Use learning memory** enabled. Open **Learning memory · evidence and provenance** to inspect stored attempts and proposed lessons.
3. Run again. The source becomes **Memory recipe** when exact-context passing evidence exists. Inspect the fresh check ledger and simulation and compare candidate/model-call counts.
4. Use the sandbox validation button to validate the supported clearance lesson. A passed report makes its advice available to subsequent planner calls; an unavailable result remains visible as pending.
5. Turn memory off and apply/re-run for an ablation, or change policy to demonstrate context invalidation. Disabling memory bypasses both reads and writes for that job.

## Verification

- Persistent cold → warm behavior across new controller/storage instances.
- Failed fresh simulation of a recalled recipe never returns a verified plan.
- Exact policy/design/validator scoping and private-session isolation.
- Pending/unavailable validation cannot inject advice into planning.
- A stored passing validation enables advice, and planner prompts consume it.
- Trusted sandbox template passes all six fixed cases in a local regression test; this is distinct from a live W&B run.
- UI notebook lint and Python regression suite are run before release.

The canonical diagram is `silta/loop_diagram.py`, rendered directly in the live notebook. Its Mermaid source is also copied into `docs/architecture.md` and `docs/followups/touko-loop-refactor.md`.

Reproduce the measured result with `./.venv/bin/python scripts/demo_memory.py`. It creates a fresh temporary evidence directory and prints the cold/warm counts as JSON. Full regression run: **124 passed**; all six new memory tests passed again after tightening upload/session isolation.

Local browser evidence: job `job-64ca47e0edb6` recalled a recipe and passed fresh checks/simulation; clicking Run again created a distinct job `job-4e48671dd855`, also with one candidate and one fresh simulation. The diagram rendered and the memory inspector exposed source episode IDs, storage backend and pending lesson status.

## Live verification

The memory release was deployed as revision `silta-00008-xbp`. A concurrent deployment subsequently moved traffic to `silta-00009-7b8`; the public app was verified after that change rather than assuming the earlier revision was still serving.

Public job `job-01fa364c6569` completed with one candidate, source `memory_recipe`, seven checks and a fresh passing simulation. The inspector showed `GcsStorage`, six stored attempts and source recipe `job-a3333b7186d8-a0`. Live URL: https://silta-cdswwreljq-uc.a.run.app . The measured wall time for that observed public run was 45 seconds, so the separate preloaded presenter notebook is the recommended timed demonstration surface.
