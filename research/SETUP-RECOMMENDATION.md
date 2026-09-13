# Proposed implementation setup

Research date: September 12, 2026. This is a recommendation, not a record of installed or working integrations. The team has no Fusion or Siemens NX access. The approved flow remains `docs/loop.md` on origin/main; this document supplies proposed implementation choices without changing that flow.

Follow-up: [MINIMAL-SPONSOR-SETUP.md](MINIMAL-SPONSOR-SETUP.md) refines the sponsor integration to reduce complexity. Prefer the event-enabled W&B hosted Sandboxes service over provisioning CoreWeave infrastructure; use Weave EvaluationLogger around the existing loop; defer SQLite and separate experiment infrastructure until needed. Account access remains unverified.

## Recommendation

**Trial-route correction:** lack of existing Fusion/NX access does not eliminate them. Assess the Fusion professional trial before committing to a custom verifier. Fusion documents CAM automation and manufacturing collision verification, but automated extraction of completed milling-verification results remains unverified. Its desktop application requires macOS/Windows, so it cannot simply replace FreeCAD inside the proposed Linux sandbox. NX also offers a trial; scripted workflow access in its trial remains unverified. The open-source stack below is the fallback pending that assessment. Sources: [Fusion CAM API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMIntroduction_UM.htm), [manufacturing simulation](https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-REF-SIMULATION), [NX trial](https://blogs.sw.siemens.com/nx-manufacturing/Start-your-free-NX-CAM-cloud-trial-in-just-minutes/).

Use GPT-6 Astra through the new OpenAI Agents API, with a custom Linux execution image on CoreWeave Sandboxes if event access is available. Use FreeCAD for CAD and CAM, CAMotics for interpreting supported G-code and simulating material removal, and a separate trusted geometry verifier for the capabilities CAMotics lacks. Use Python to enforce the loop, Weave to record and evaluate it, and marimo for the eventual interactive interface.

The two main unproven integrations are the account-enabled Agents API to CoreWeave connection and a reproducible automated FreeCAD/CAMotics image. Prove these early. No paid infrastructure was provisioned for this research.

## What runs where

| Responsibility | Proposed component | Contract |
|---|---|---|
| Agent execution | OpenAI Agents API, GPT-6 Astra | Main agent creates artifacts; separate check writer proposes rules; supervisor issues structured continue/finish decisions. These are roles, not different trained models. |
| Execution environment | CoreWeave Sandbox, pinned custom Linux image | Native geometry dependencies, bounded processes and candidate files. Start with an estimated 4–8 CPU and 8–16 GB RAM; measure actual requirements. No GPU requirement established. |
| Loop controller | Python, typed records/Pydantic | Owns state transitions, versions, retries, artifact hashes, and best verified candidate. Only successful verification calls the supervisor. |
| CAD/CAM | FreeCAD Python interfaces and CAM workbench | Editable native project plus STEP target, CAM operations and tool definitions, then postprocessed NC/G-code. Pin the working FreeCAD version. |
| NC execution semantics and cutting | CAMotics Python extension | Interpret the exact emitted supported NC program, export its motion path and remaining-stock mesh. Reject unsupported commands before simulation. |
| Independent verification | Custom wrapper; mesh comparison plus FCL collision queries | Detect target damage, unremoved stock, holder/fixture interference and other modeled failures. CAMotics alone is insufficient. |
| Cheap checks | Python functions, tested with pytest and counterexamples | Fast structural, machine-limit and geometry checks. Learned additions must pass validation before promotion. |
| Learned strategy | Versioned Markdown playbook and structured outcome records | Supervisor can propose additions/removals. Controller preserves fixed constraints and logs each change. |
| Experiment evidence | Weave traces/evals and W&B experiment metrics | Compare versions on the same parts and constraints; preserve real failures and improvements. |
| Durable state | SQLite and versioned files initially; W&B artifact references for experiments | Survives worker expiration. Export self-hosted files explicitly. Do not rely on sandbox lifetime for storage. |
| Interface | marimo, anywidget/Three.js, Plotly | Display verified motion, stock and recorded metrics; interface does not own the verification verdict. Molab is optional hosting after dependency/access checks. |

FreeCAD keeps modeling and CAM in one geometry environment. Adding CadQuery is possible later, but it would introduce another geometry handoff before we have proved the first path.

## OpenAI and CoreWeave fit together

The screenshot announces the Agents API, which supplies the managed Codex harness. Its documentation offers both OpenAI-hosted and self-hosted environments. “Self-hosted” includes a remote provider sandbox. A `codex exec-server` process connects the environment to OpenAI; the main application retains the broader API credentials, while the executor uses restricted credentials. [OpenAI overview](https://developers.openai.com/api/docs/guides/agents-api/overview), [self-hosted environments](https://developers.openai.com/api/docs/guides/agents-api/environments/self-hosted).

CoreWeave documents custom container images, CPU/RAM resources, networking and lifecycle controls. This makes it a plausible host for our executor and native geometry tools. The exact Agents API plus CoreWeave connection is a proposed generic integration, not a verified turnkey adapter. Confirm outbound HTTPS/WSS, image pull, file transfer, concurrency, lifetime and price against the team's actual account. [CoreWeave configuration](https://docs.coreweave.com/products/sandboxes/client/guides/sandbox-configuration).

Fallback order: run the same image in a local isolated container if cloud access is delayed; alternatively test OpenAI-hosted package installation for the native stack. Hosted environments support package/setup configuration, but we have not established that FreeCAD and the CAMotics Python extension install and fit their available resources. If Agents API access itself is missing, retain the Python controller and tools with an explicit Responses API tool loop. None of these fallbacks changes the product loop. [OpenAI-hosted environments](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted).

## CAD and simulation boundary

The model reads the drawing/PDF. It creates a CAD candidate, whose dimensions must match the drawing before it becomes the fixed target. An ambiguous drawing can admit multiple interpretations; “frozen” must not mean an initial modeling error is silently accepted. CAM optimization cannot modify the accepted target. A deliberate target correction starts a new target version and invalidates comparisons to the old one.

FreeCAD supplies CAM jobs and machining operations rather than requiring us to invent a CAM engine. Its headless documentation establishes console operation, but does not guarantee every CAM operation works without GUI dependencies. The integration test must exercise the operations we choose; a virtual display is an acceptable automation fallback. [FreeCAD CAM](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/CAM_Workbench.md), [headless FreeCAD](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Headless_FreeCAD.md).

The machine consumes a controller-specific NC program, commonly called G-code. Proposed initial dialect: a documented LinuxCNC-compatible subset accepted by both the selected FreeCAD postprocessor and CAMotics. Establish a whitelist and test units, coordinate modes, tool changes, offsets and arcs. Expand cycles into supported primitives where necessary. A parser warning or unmodeled command cannot count as a pass.

CAMotics' official Python example exposes `compute_path`, `get_path`, simulation and remaining-stock export. These are suitable integration points for replay and verification, but the extension still needs a reproducible build/install in our image. [Python example](https://github.com/CauldronDevelopmentLLC/CAMotics/blob/master/examples/python/camotics_python_example.py).

Its published limitations explicitly omit automatic over/undercut detection, shaft/fixture collisions and rapid moves through material. Therefore, our “simulation” stage must compose:

1. Supported NC interpretation and material removal.
2. Comparison of remaining stock to the fixed CAD: gouging and missing cuts, evaluated at a declared numerical resolution and tolerance.
3. Tool/holder/fixture/machine collision checks using the interpreted motion. FCL supplies collision and distance primitives; we must implement the scene and motion integration. Continuous checks where supported, otherwise conservative swept geometry or bounded subdivision—not sparse animation-frame sampling.
4. Rapid-motion checks against the stock at that point in execution. This needs stock checkpoints or another incremental representation; a final-stock-only comparison will miss some crashes.
5. Machine limits, tool reach and supported machining parameters.

Use the same interpreted NC motions for collision analysis, timing and visualization. CAMotics stock discretization is not tolerance certification; resolution sensitivity must be measured. Generic geometric simulation does not establish real cutting-force, chatter, wear or surface-finish accuracy. Those remain modeled limits or later calibrated physics extensions. [CAMotics limitations](https://camotics.org/), [FCL](https://github.com/flexible-collision-library/fcl).

## Preserve the learning loops

Main-agent workspaces may modify candidate CAD/CAM files. Learned-check workspaces may modify proposed checks. The trusted verifier, accepted target, fixed constraints and evaluation labels are outside both agents' write access. Run proposed checks in isolated processes; a prompt alone is not the integrity boundary.

A simulation failure returns a localized counterexample: NC line/motion, tool, positions, geometric witnesses and failure category. The main agent repairs the plan. The check writer proposes a cheap rule that would catch this class of failure. Validate it against the failing example, nearby variants and valid examples before enabling it. Record runtime and false rejections. Audit some rejected candidates with the trusted simulator so learning cannot hide valid solutions behind increasingly restrictive rules.

Only a simulation pass reaches the supervisor. The supervisor receives the current verified candidate, best candidate, score breakdown, past trials and uncertainty. It returns either a concrete next experiment or finish with the best verified candidate. Every proposed improvement repeats checks and full verification; an unsuccessful later trial never destroys the incumbent.

Learn stopping decisions from outcomes of proposed experiments. Sometimes continue offline after a proposed stop to measure missed improvements; otherwise the supervisor never learns whether stopping was premature. Validate new playbook versions on held-out parts. Budget and retry caps remain operational backstops; reaching one is “stopped with best verified result,” not proof of optimality. No model-weight training is required for this mechanism.

## Optimize a defined objective

Feasibility and target tolerance are gates. Among passing candidates, default to minimum estimated cost per good part at the specified batch size, while showing machining time separately.

`cycle time = cutting motion + rapid/repositioning motion + tool changes + dwell + modeled machine overhead`

`cost per part = material + machine rate × cycle time + setup cost / batch size + calibrated tooling cost`

Track agent and simulation compute cost separately. Tool wear costs are unknown until a model/data source is chosen; do not fabricate savings. Include acceleration/rapid assumptions in timing. Tool-change time and setup labor are explicit machine parameters.

Optimize operation ordering, grouping by tool where dependencies permit, tool selection, roughing/finishing strategies, stepdown/stepover, retracts, linking paths, feeds and speeds within approved material/tool limits. “Avoid tool changes” is a heuristic, not a hard rule: a specialized tool can save more cutting time than its change costs. Never let arbitrary feed increases win against a geometric-only simulator.

Keep the machine, target, material, stock, fixture and cost assumptions identical when comparing plans. Each experiment records its expected benefit and actual verified result. The supervisor learns which interventions pay off for which part features, rather than simply repeating generic advice.

## Natural sponsor use

| Sponsor component | Use | Status / caveat |
|---|---|---|
| CoreWeave Sandboxes | Actual isolated CAD/CAM execution and verification workers | Account access, grant and exact SDK need confirmation; W&B and CoreWeave documentation expose different wrappers. Do not mix their configuration schemas. |
| Weave | Every candidate, repair, learned check, verification and supervisor decision; evaluations across parts | Mandatory W&B usage in the participant handbook. Instrument our controller explicitly. OpenAI's managed internal traces are not automatically guaranteed to appear through ordinary client patching. |
| ARIA | Analyze real W&B experiments and propose better checks/strategies from aggregate outcomes | Useful experiment analyst; do not assume an available API that makes it the live supervisor. Verify team Smart features and project access. |
| marimo / molab | Interactive machine replay and experiment analysis | Use marimo locally first; verify molab's packages, quotas and hosting before making it a dependency. |
| W&B Inference | Optional cheaper decision/check-generation model tested against Astra | Inference credits do not imply OpenAI or sandbox credits. Use only if measured quality/cost warrants another model. |
| TypeSafe | Optional structured decision component after endpoint and model access are provided | No verified working API for this team. Keep outside the critical path. |

Sources: [participant handbook](https://wandbai.notion.site/CoreWeave-Hacks-Participant-Handbook-3c9e2f5c7ef380eab21ecdde12620caf), [Weave OpenTelemetry](https://docs.wandb.ai/weave/guides/tracking/otel), [ARIA](https://docs.wandb.ai/aria/overview), [marimo widgets](https://docs.marimo.io/api/inputs/anywidget), [OpenAI tracing](https://developers.openai.com/api/docs/guides/agents-api/tracing). Current repo uses W&B entity `silta`; use origin/main's sponsor configuration rather than older local notes.

## Decisions and proof before the full build

1. **Machine profile:** one explicit three-axis virtual machine or a specified real machine's published limits; controller dialect, workspace, feed/rapid/acceleration limits, spindle range and tool-change behavior.
2. **Tool/stock/setup data:** actual catalog of cutter and holder dimensions, material and machining limits, stock, fixture geometry and allowed setups. Start with one fixed setup; additional setups require explicit transforms and re-clamping/clearance modeling.
3. **Acceptance:** drawing tolerances, supported NC semantics, simulation resolution and what a pass proves. Choose representative parts including difficult reach and fixture cases.
4. **Objective:** batch size, machine/setup rates, minimum meaningful improvement and treatment of uncertainty. Defaults can be declared synthetic until real shop values exist.
5. **Access and reproducibility:** one working Agents API session, one sandbox with the pinned native image, successful artifact retrieval and one visible Weave trace. Check separate OpenAI/sandbox billing; the event's inference offer is not a blanket compute grant.
6. **End-to-end feasibility test:** automatically generate a part and toolpath, postprocess NC, simulate it, export stock and detect an intentionally wrong cut. Then detect a holder/fixture collision and a rapid move through stock. These tests prove the hardest interfaces before investing in the complete agent loop.

Build order after those choices: deterministic artifact-to-verdict path; main-agent repair loop; validated learned checks; supervisor optimization and stopping; held-out evaluation; interactive replay. The scope stays ambitious, but the verifier has to earn its authority before we use its outputs as learning signals.

## Deliverable

For each completed job: accepted STEP/native CAD, editable CAM project, supported NC program, machine/tool/setup description, best verified candidate, versioned verification report, stock/motion artifacts, time/cost assumptions and trace links. This is a simulation-verified manufacturing plan for the modeled environment, not a claim of physical-machine validation.
