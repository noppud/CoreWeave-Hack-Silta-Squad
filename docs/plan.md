# Silta CNC — hackathon implementation plan

Planning baseline: September 12, 2026, repository commit `81c2cc4`. Status: implementation specification; product functionality and sponsor access are not yet verified.

**Build a chat-driven CNC process planner that turns a dimensioned drawing into a STEP model and machining recipe, tests the recipe, repairs failures, and shows machining in 3D.** Across tasks, use W&B results and ARIA to turn recurring simulation failures into earlier checks. Demonstrate the improvement in a marimo notebook application.

Read with:

- [Technical architecture and contracts](architecture.md).
- [Implementation tasks and recursive agent workflow](implementation.md).
- [Required live deployment](deployment.md).
- [Rules verification and submission gates](hackathon.md).
- [Sponsor access and credits](sponsors.md).
- [Submission and three-minute demo](submission.md).

## 1. Product interpretation and decisions

The whiteboard shows drawing → swarm → CAD/STEP → checks → simulation, with failures returning to the swarm. The [team conversation](../meta-ctx/2026-09-12-training-llm-agents-with-openpipe.md) adds the customer context: a CNC shop receives drawings, owns particular machines/tools, and needs a manufacturing recipe. It asks for a failed machining attempt followed by a successful visual simulation, with cheaper checks replacing avoidable simulation work over time.

Keep the customer's intended shape separate from the manufacturing plan. A tool-reach failure should change the tool or setup, not silently make a pocket shallower. STEP describes the target solid; it does not encode the whole machining recipe. Deliver both.

| Decision | Selection | Reason |
| --- | --- | --- |
| Working name | Silta CNC | A bridge from drawing to checked manufacturing plan. |
| User | CNC shop estimator/process planner | One concrete workflow with observable output. |
| First part family | Rectangular pre-cut stock, top-access pockets and blind holes | Feasible geometry, paths, and checks in a weekend. |
| Chat/workbench | marimo Python app | The notebook is the actual product and experiment surface. |
| Hosting | GCP Cloud Run, complete app at a live HTTPS URL | Required delivery; deploy the first slice early and verify remotely. |
| 3D | Three.js through anywidget | One Python application with a focused viewer component. |
| CAD | Deterministic CadQuery builders driven by validated JSON | Real STEP export without executing model-written code. |
| Orchestration | Typed Python state machine | Explicit budgets, reproducible tests, understandable traces. |
| Models | W&B/CoreWeave Inference first if usable; OpenRouter for missing capabilities/access | Reuse starter, select using verified capabilities. |
| Evaluation | Deterministic geometry, tool, path, and stock checks | A model's opinion cannot turn a failure green. |
| Improvement | Per-part repair plus versioned cross-task improvements | Visible correction and evidence of improvement. |
| Sponsor evidence | Weave traces, W&B runs, actual ARIA analysis, two marimo notebooks | Each requested product contributes to the result. |
| Prize strategy | Best Loop Design; provisionally Best Use of Weave if the form allows one track | Select final track based on completed evidence. |

The gears are conceptual input. Involute gears, mating assemblies, five-axis operations, general CAM, arbitrary CAD feature recognition, and industrial certification are beyond the first demo.

## 2. Judge-ready user flow

Layout: conversation left, large 3D part/machine view center, current plan/checks right. A bottom timeline shows attempts, concrete changes, and metrics. Use tabs at laptop widths instead of squeezing the columns.

1. **Start a job.** Choose the supplied dimensioned fixture-block example or upload PNG/JPEG/a short PDF. Show the file and thumbnail. An undimensioned photograph triggers requests for dimensions.
2. **Describe the task.** “Plan this part on our three-axis mill with the tools listed here. Keep the drawing dimensions unchanged.” Machine and tool inventory are visible/editable.
3. **Resolve uncertainty.** Extract proposed features; show missing values and a compact confirmation form for dimensions, units, depths, material, and fixture. Unknowns remain unknown. Confirmation freezes specification revision 1.
4. **Build the model.** Display the target solid with rotation, zoom and feature labels. Offer STEP as a target design artifact with separate machining-check status.
5. **Plan and check.** Show actions such as “Selected EM6-S” and “Reach failed: 12 mm depth exceeds 8 mm cutting length.” Display operation cards, setup count and failing features. Show actions/evidence, not hidden chain-of-thought.
6. **Repair.** Give structured failures to the planner. Show the real diff: EM6-S → EM6-L; later, clearance 5 → 15 mm. Re-run dependent stages and preserve all attempts.
7. **Simulate.** Animate tool, stock removal, fixture and travel. Freeze a collision at the offending segment and highlight it. End successful replay with machined stock beside the target and residual/gouge measurements.
8. **Inspect improvement.** Open the marimo experiment tab to compare baseline/revised policy on fixed inputs. Show the actual ARIA recommendation and results after applying it.
9. **Download.** STEP, mesh, JSON recipe, setup sheet, validation report, trajectory and a manifest tying them to the same attempt. Label completion “Passed prototype checks.”

The first success moment is a blocked plan becoming valid without changing the requested part. The second is catching that failure family before simulation on another part.

Required states: empty, extracting, needs clarification, ready to plan, planning, checking, repairing, simulating, passed prototype checks, needs human review, budget exhausted, cancelled, service unavailable. Keep run/cancel controls and last completed artifacts available after errors.

Distinguish **live run**, **recorded run replay**, and **offline fixture**. A replay does not imply a new model call or increment live evaluation counts. Show provider/model in details.

## 3. Demo part and reproducible failure

Create a synthetic team-authored drawing and independent ground-truth JSON. These are demonstration assumptions, not machining advice:

- Pre-cut block: 80 × 60 × 20 mm; XY lower-left origin; top Z=0, bottom Z=-20.
- Rounded rectangular pocket: X=20…60, Y=20…40, depth 12 mm, internal radius 3 mm.
- Four blind holes: centers (10,10), (70,10), (10,50), (70,50), diameter 6 mm, cylindrical depth 8 mm. Define the drill-tip geometry explicitly and consistently.
- Tools: 6 mm center-cutting end mills with 8 mm and 18 mm cutting lengths; a 6 mm drill with sufficient declared reach. Specify shank/holder separately.
- Simplified clamps: X=34…46; Y=-6…6 and 54…66; top Z=12. Fixtures are computational geometry, not decoration.
- Home tip position: (40,-20,25). A naive 5 mm traverse across the front clamp collides; 15 mm gives the declared 3 mm tip clearance, subject to full path/holder checks.

**Reliable sequence:** load an explicitly labeled naive starting recipe. Attempt 0 selects the short end mill and fails preflight. The model selects the long tool; attempt 1 enters simulation and its low traverse hits the clamp. Structured feedback identifies segment/clamp. The next repair raises clearance; attempt 2 passes. The target CAD hash remains unchanged.

This is an intentional challenge fixture, not evidence that the live model always fails first. Also test fresh drawing-to-plan examples and measure genuine first attempts separately. Never insert a fake failure into a successful live run.

First engineering spike: prove the geometry, holder, pocket path and drill convention yield this trajectory. If the presumed passing plan is invalid, fix it before freezing the fixture. Preserve the final values in the demo and manifests.

## 4. Three feedback loops

### A. Runtime repair within a job

Extract → clarify → freeze spec → CAD → plan → cheap checks → path compilation → simulation → structured feedback → replan. Stop at success, three candidates, deadline/cost cap, repeated candidate, unsupported input, or unsatisfiable requirements. A builder bug is a software error; do not arbitrarily change a valid requested shape.

Interpreter proposes `PartSpec`; planner proposes `ProcessPlan`; repairer revises from check evidence; reporter explains stored results. CAD, verification, compilation and simulation are deterministic tools. The controller owns state and permissions. One model can fill all model roles initially; role labels do not imply concurrent execution or independent models.

### B. Cross-task improvement with W&B and ARIA

1. Run policy v0 on development fixtures and log failures/metrics.
2. Ask ARIA to analyze those W&B runs and propose one bounded improvement.
3. Save its actual response and cited evidence; implement a versioned rule or prompt change.
4. Compare on the same development set, including known-valid boundary recipes.
5. Freeze the candidate and evaluate an untouched holdout. Promote only if hard correctness is preserved and the selected metric improves.
6. Show both policies in marimo, including failures/unsupported cases and simulations avoided.

Example: a low traverse hits a clamp in simulation; a path-envelope check catches this family before stock simulation on later jobs. Model-proposed rules enter the validator only as reviewed code. An uncertain coarse-envelope overlap warns and defers to simulation rather than falsely rejecting a valid path.

This is feedback-driven policy improvement, not model-weight training. OpenPipe ART/RL is follow-up scope after a stable environment, reward, sufficient examples and a reason to train exist.

### C. Implementation with another coding agent

Follow the [task/checkpoint/review loop](implementation.md). Build one complete slice first, then make one measured improvement per iteration. A reviewer checks fixed acceptance criteria; it must not weaken an oracle or edit holdout data simply to make a result green.

## 5. Scope and completion evidence

| Priority | Deliverable | Acceptance evidence |
| --- | --- | --- |
| P0 | Chat + confirmed specification | Typed/uploaded examples reach confirmed spec; unknown units block. |
| P0 | CAD + STEP | Independent reimport matches expected dimensions/volume and renders. |
| P0 | JSON recipe + inventory | Every tool/setup/feature reference exists; design stays unchanged. |
| P0 | Checks + repair | Reach failure gives actual feedback and corrected recipe. |
| P0 | Paths + simplified simulator | Bad clearance collides; corrected path removes expected material. |
| P0 | 3D result playback | Viewer time/selection matches simulator segment IDs. |
| P0 | Sponsor integrations | Live inference; visible Weave/W&B results; actual ARIA analysis; runnable marimo notebooks. |
| P0 | Cross-task improvement | Versioned change, fixed comparison, false-positive tests, holdout result. |
| P0 | Judge package | Reproducible startup, replay, recording, submission evidence. |
| P0 | Live deployment | Public HTTPS app completes real input-to-simulation flow; artifacts persist and two sessions remain isolated. |
| P1 | PDF extraction | Bounded rasterization and dimension confirmation. |
| P1 | STEP input | Restricted supported features; unsupported shapes clearly identified. |
| P1 | Setup/tool-change optimization | Feasible plans compared under identical assumptions. |
| P2 | Gear/assembly/multi-face generation | After all P0 requirements. |
| P2 | Training, distributed swarm, general CAM | Follow-up project. |

PDF is desirable but can be cut before the real checks, simulation, ARIA evidence or demo reliability. PNG/JPEG plus typed dimensions cover the core. If STEP input is cut, call the feature STEP **export** clearly.

## 6. Metrics and experiments

Feasibility is a conjunction: valid schema, unchanged confirmed design, valid CAD, every blocking check passed, complete required-feature coverage, successful simulation. Unknown/timeout is not pass. Low estimated cost never offsets a hard failure.

Among feasible plans compare estimated machining time, setup/tool-change counts, minimum clearance, simulations, actual wall time and inference spend. Animation speed is not manufacturing speed; estimated cycle time is not measured shop performance.

Start with 12 frozen fixtures: 8 development and 4 holdout, split before tuning. Cover valid baseline, reach, clamp collision, missing tool, impossible radius, unknown units, excessive depth, and valid near-boundary cases. Independently author expected geometry and known-valid/invalid recipes; do not derive the oracle from the model or production CAD builder.

Compare A: one attempt; B: bounded repair; C: repair plus promoted early check. Keep input/model/budget constant. Additionally run a fixed saved-candidate corpus through old/new checks to isolate validator effects from model variation. Use three stochastic repeats if credits/time permit. Report counts and denominators, not broad industrial reliability claims. If holdout informs tuning, retire it and create fresh holdout.

Targets to verify, not current results:

- All deterministic oracle cases behave correctly; no known-invalid recipe passes.
- One real recorded repair trajectory preserves design and artifact lineage.
- New check catches the intended failure on another fixture without rejecting known-valid boundary cases.
- Typical completion within 90 seconds, hard deadline 120 seconds, at most three candidates; report measured latency.
- Three-minute demo remains presentable during inference outage using labeled replay.

## 7. Risks and remaining choices

| Risk | Mitigation |
| --- | --- |
| CAD/runtime incompatibility | First 45-minute spike on demo machine and intended container. |
| Ambiguous interpretation | Restricted family, mandatory confirmation, typed/example routes. |
| Simulation consumes weekend | 2.5D stock, explicit tool/fixture geometry, bounded resolution. |
| Viewer diverges from verifier | One trajectory contract with segment IDs and artifact hashes. |
| ARIA unavailable | Check team/Smart features immediately; resolve with sponsor. Generic LLM is not ARIA. |
| Credits unavailable | Verified OpenRouter route with configured cap; retain W&B telemetry. |
| Reactive duplicate execution | Explicit actions, request IDs, idempotency/cancellation tests. |
| GPU distraction | CPU geometry, hosted inference; molab compute optional. |
| Time runs short | Follow implementation cut order; freeze before deadline. |

Live hosted delivery is required; use GCP Cloud Run and retain laptop replay as backup. Confirm final roster/name, preferred part, real machine profile if any, activated provider access and GCP project/budget. The defaults allow implementation to start. Organizer gates are tracked in [hackathon.md](hackathon.md).
