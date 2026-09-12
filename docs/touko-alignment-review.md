# Alignment review — Touko's loop diagram

Reviewed September 12, 2026 against the user-supplied diagram and a snapshot of the active working tree. Claude is implementing concurrently; findings describe the files inspected, not a finished release. This handoff supplements the plan without editing Claude's implementation files.

## Verdict

The CAD/CAM separation and verification architecture are aligned. Two behaviors need to become explicit requirements to deliver Touko's full loop: optimization supervised after a successful simulation, and observable generation/validation/promotion of missing checks. The existing plan's first-pass stop and developer-operated improvement cycle are a smaller version of that design.

## What exists in the inspected code

- `silta/domain.py`: validated part, shop, recipe, trajectory, simulation, attempt and manifest contracts; design hashes and a best-attempt reference.
- `silta/cad.py`: trusted CAD primitives, STEP/STL export and roundtrip measurement.
- `silta/toolpaths.py`: deterministic pocket/drilling paths and machining-time estimates.
- `silta/fixtures.py`: explicitly labeled naive, reach-repaired and reference recipes.

These are suitable foundations. At initial inspection there was no runtime controller, supervisor, checker-generation implementation, simulator, chat notebook or deployment code. Their absence is unfinished work, not proof that Claude chose a different direction. CAD/simulation success and live hosting were not verified in this review.

During the review Claude also added `silta/checks.py` and `silta/policy.py`. The latter has versioned planner rules and a promoted-check set, which is useful progress toward the playbook. However, its v0/v1 policies are presently predefined; they do not yet establish the diagram's generation/validation loop. Its v1 provenance claims an ARIA recommendation at `policies/aria-recommendation-001.md`, which was absent when checked. Treat that attribution as pending until the actual conversation/evidence exists; use truthful provisional provenance in the meantime.

## Changes to give Claude now

### 1. Success goes through a supervisor

Change `simulation pass -> finish` to `simulation pass -> retain best verified candidate -> supervisor -> improve or finish`. The supervisor receives all relevant attempt metrics and constraints, proposes a bounded planning instruction, and records why it continues/stops. Show this decision in the UI and Weave.

Implement one optional optimization attempt after the first valid plan, only while the existing time/call budget allows it. Recheck and resimulate every changed recipe. Keep the original verified plan if optimization fails, regresses, repeats or times out. If no plan has passed, return a clearly failed/incomplete result. Never select the last candidate merely because it is last.

Use deterministic comparison among feasible candidates: declared estimated machining time and tool/setup-change costs, with safety/geometry constraints as hard gates. Model-written scores cannot override check results. Do not increase feed beyond the declared tool/material/machine constraints simply to lower the arithmetic estimate.

### 2. Persist a real planning playbook

Add a versioned `PlanningPlaybook` with scoped instructions, source attempt/evidence IDs, applicability, validation results and status. Feed the accepted version into subsequent main-agent calls. Show a concrete lesson being reused on another case. Keep customer dimensions and tool inventory outside the writable playbook.

The runtime supervisor and W&B ARIA are separate roles in the current technical plan. Keep ARIA's actual experiment-analysis contribution; do not claim a generic model supervisor is ARIA or assume an unverified ARIA embedding API.

### 3. Make the missing-check loop observable

Simulation failure -> missing-check proposal -> validation on the failure plus independent valid/invalid boundary fixtures -> versioned activation -> next candidate checked earlier. Record candidate, test outcomes, activated version and failure evidence. A failed candidate check must not enter the active checker set or weaken existing checks.

For the weekend, constrain proposals to a small typed rule/template family executed by trusted checker code. State clearly if this is rule generation rather than arbitrary Python generation. If actual generated Python is essential to the demo, isolate execution and require independent validation before promotion; do not execute unrestricted generated code inside the app process. Agree that expanded scope before implementing it.

This loop should actually run in the demonstrated product/evaluation workflow. A checker manually added between development sessions demonstrates engineering iteration but does not by itself demonstrate autonomous check generation.

### 4. Prove the whole diagram with two cases

Case A: cheap failure -> repair -> simulation failure -> repaired valid plan -> supervisor improvement attempt -> return best verified result. Preserve target hash across attempts and retain the valid fallback when improvement fails.

Case B: load a different applicable fixture; show the accepted check catches the same failure family before simulation and the playbook instruction reaches the planner. Show actual simulation-call counts and a valid boundary case that is not falsely rejected. Add a regression where generated-check validation fails and activation is refused.

Keep live deployment required. These changes do not justify expanding the part family or building a general agent framework.

## Confirmed code issue relevant to optimization

`ProcessPlan.fingerprint` in `silta/domain.py` omits feed, spindle speed, peck depth and setup assignment. Consequently a materially different candidate can be rejected as a repeat. Include all manufacturing/verification-relevant inputs while excluding cosmetic IDs/notes, and keep design/shop context in comparison scope.

Reproduced locally using the existing reference plan and compiler: halve the first pocket operation's feed; estimated total duration changes from **287.438 s to 411.896 s**, but the fingerprint is unchanged. These are computed estimates, not measured machining times. Add a regression proving feed/peck/setup changes differ while purely cosmetic changes do not.

## Acceptance before claiming full diagram alignment

- [ ] Supervisor can request one bounded improvement after simulation passes.
- [ ] Best verified plan survives a failed/worse optimization.
- [ ] Planning playbook is versioned, persisted and demonstrably used later.
- [ ] A proposed missing check is validated and activated; rejected proposals stay inactive.
- [ ] Second-case evidence demonstrates earlier detection without a false positive.
- [ ] Candidate fingerprints distinguish manufacturing-relevant changes.
- [ ] Live app displays these events and evidence; actual ARIA use remains separately verified.
