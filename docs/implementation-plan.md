# CNC agent implementation plan

2026-09-12 · Current implementation direction; some access and integration checks remain unverified. Earlier research documents contain alternatives, not additional requirements.

**Model requirement:** use GPT-6 Astra for all agentic development and every agent/model-based judge inside the project. No weaker-model fallbacks. ARIA is the explicit exception: use its best available model when added later. Other optional model-based Signals or sponsor inference require verified Astra support. Deterministic checks and scoring do not require a model.

## Goal and loop

Drawing/PDF + machine/tool/setup inputs → accepted CAD target + CAM → cheap checks → Fusion verification → supervisor → improve CAM or return the best verified plan.

- Establish the CAD target against the drawing, then keep it fixed during CAM optimization.
- Check failures return to the main agent for repair.
- Simulation failures return for repair and can trigger proposals for better cheap checks.
- Only a completed verification pass reaches the supervisor, with machining time, cost assumptions and feedback.
- The supervisor proposes a better CAM plan or stops. Keep the best verified candidate throughout.

## What runs where

The deliverable is an autonomous application: one job submission starts the Python controller, which calls Astra through the Codex SDK for every agent role and advances the loop itself. This development chat is not part of the runtime. Fusion remains a desktop dependency on the Mac; its API bridge and the SDK's computer-use tools are application-controlled integrations. Initial account/app consent is setup, and unavailable access is reported as an incomplete job.

| Component | Choice |
|---|---|
| Main agent, supervisor, check writer | GPT-6 Astra through local Codex SDK/app-server using ChatGPT subscription login; separate roles. Managed Agents API is a separately billed alternative, not the default. |
| Controller | One Python application on the Mac |
| CAD, CAM and simulation | Fusion professional trial on the Mac; APIs where supported, computer use for remaining UI workflows |
| Generated check execution | Separate local Python process per check run, with a clean environment and execution limits; no container/service requirement for the controlled demo |
| Traces, datasets, versions and comparisons | Weave |
| Interface | marimo, reading the same job artifacts and metrics |
| Durable state | Versioned files and a JSON job manifest |

Fusion supplies the actual manufacturing simulation and verification. Astra operates it and collects evidence. A moving animation or an empty issues list before verification completes is not a pass. The API for extracting milling-verification results is not yet established; the UI workflow is documented. [Simulation](https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-REF-SIMULATION), [issue inspection](https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-SIMULATE-MACHINE-COLLISION-DETECTION-PREVIEW).

**September 12 setup change:** W&B Sandboxes were unavailable due to the reported service bug. The user authorized replacing them. For the demo, checks run as trusted application code in a local subprocess, with copied job inputs, no inherited API credentials and a timeout. This is process separation, not security isolation: generated code can still access host files. Weave tracing, paired evaluations and promotion rules stay the same. Strong isolation is future work before accepting untrusted code.

## Evaluation before reusable changes

Current-part CAM changes repeat checks and simulation. Reusable prompt, supervisor or check changes go through a Weave evaluation before promotion; no additional always-running outer agent is needed.

- **Prompt/supervisor changes:** run old and proposed versions on the same small part set. Compare verified completion first, then machining time/cost and simulation attempts on matched successful parts.
- **Check changes:** replay frozen simulator-labeled valid/invalid candidates. Measure failures caught, false rejections and runtime; reuse labels only while candidate/setup/verifier inputs remain unchanged.
- Publish versioned results and promote only a demonstrated improvement without unacceptable regressions. Keep old versions for rollback. After an evidenced promotion, the running job adopts that exact check or prompt version for subsequent steps; record each step's versions and preserve earlier evidence. Benchmark runs retain their assigned baseline or proposed versions.
- Include simple and awkward development parts; reserve unseen parts for final assessment. Fixed target, machine constraints and scoring rules cannot be rewritten by the learner.

## First implementation milestone

1. Verify Fusion trial entitlement, subscription-backed Codex execution/computer-use integration, local check execution and one visible Weave trace.
2. Select one three-axis machine profile, cutters/holders, stock/material, fixture, tolerances and supported postprocessor. Define feed limits, tool-change time and cost/batch assumptions.
3. Automatically generate one CAM plan, invoke Fusion verification, capture completion and a deliberately introduced failure, repair it and capture a pass. Establish whether the evidence covers internal CAM motions or the exact exported NC program.
4. Add the repair loop, check learning and supervisor; then demonstrate a reusable change passing the Weave evaluation gate.

Optimize verified machining time/cost under fixed limits; include cutting, rapids and tool changes. Report estimates and assumptions. Do not reward unrestricted feed increases.

## Final result

Accepted CAD/STEP, editable CAM, exported NC/G-code, setup/tool definitions, best verified plan, verification evidence, estimated time/cost and linked Weave history. Claim only the verification coverage actually demonstrated.

If Fusion access or repeatable verification is blocked, resolve it with the team before proceeding. Do not substitute another simulator or change the agreed plan because access is missing.

## Live integration checkpoint

The SDK CAD stage has generated and independently accepted the selected soft-jaw drawing, including actual Aluminum6061 material in Fusion and STEP. The prepared vise and parallels reopened with all19 bodies intact; both enabled cutter/holder assemblies passed actual Fusion library roundtrip. The selected inputs are now ready for CAM generation; completed simulation is still pending.

Autodesk requires the simulation model in a writable Fusion hub. The pinned VF-2 design is saved and fully processed in the helios hub, project **Silta CNC Hackathon**, as **Silta VF2 simulation model**. The user linked that saved design in the local machine definition's Model page. Fusion persisted its version URN, and actual API setup assignment now succeeds. Stock dimensions, G54 and Part Position offsets were applied and read back; the full machine is visible around the setup. The first loop was stopped after setup API errors so that predictable setup could move into deterministic code. No machining simulation verdict is established yet.

### Deterministic CAM preparation

The controller now activates Manufacturing, prepares exactly one owned setup and
fixture, applies the linked machine, stock, G54 (`job_workOffset=1`) and Part
Position, and provides actual approved cutter/holder objects. Astra receives
`cam`, `setup`, `target_bodies` and `tools`; it chooses operations, geometry,
strategies, order, depths, feeds, speeds and paths. Controller code finalizes the
NC program and verifies the actual bound CPS bytes while preserving chosen
cutting parameters. These changes add no agent loop.

Full-machine CAM archives contain external references and cannot be imported
through Fusion's local F3D importer. CAM candidates therefore also carry a
hashed `fusion_document` receipt naming an exact saved cloud version. Improvement
opens that version and completes Save As to an independent working copy before
edits; verification reopens the exact completed candidate version. The F3D export
is retained, and the accepted part-only target still opens locally. Saves are
submitted once and polled, never blindly retried after a timeout.

Live checks confirmed repeatable setup without duplicate fixtures, both approved
tools, exact NC post binding, cloud save/reopen/fork, and retained VF-2 model,
fixture, G54 and unchanged accepted geometry after reopening. The NC wiring
probe has no generated toolpath and is not simulation evidence. The next
integration run must demonstrate actual machining generation and verification.
