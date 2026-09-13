# Fastest path to the SILTA showcase

## Correction after the user identified the drawing

The original review below targeted the wrong showcase. The reference recovered from the pushed `hack-slide-deck` branch is `notebooks/assets/agreed-loop-whiteboard.png`: an A4 drawing, a machine-code box, a numbered planning-instruction list, Tests → Simulation → Judge, and feedback arrows. The goal is execution of that learning architecture, not primarily reproducing the hosted slide presentation. The following recommendation supersedes the presentation-first recommendation below; its measured timings remain useful.

The runtime must preserve these behaviors: establish and freeze the part; generate/revise CAM; reject with cheap checks; simulate checked candidates; return failures for repair and missing-check learning; send only passing results and machining time to the judge; let the judge improve the shared instructions or finish; carry instructions and checks to the next part. The visible numbered list should reflect real saved guidance edits. A growing list or descending graph alone is not proof of useful learning.

The Fusion path is currently closer to that full behavior: its controller updates `learning/cad_cam.md` and `learning/checks.py` directly, and retained runs show transfer. The custom indexed path is faster and already compiles small parameter proposals deterministically, but `camloop/indexed/runner.py` does not contain the Fusion path's missing-check writer, and `sequential.py` saves episodic strategy memory rather than the same direct two-file learning contract. Therefore, switching branches wholesale would change the product, not simply speed it up.

Recommended direction: retain the existing learning semantics and adapt the bounded recipe compiler/custom verifier to them. Keep the same drawing, tests, simulation, judge, instruction-update and next-part arrows. Reuse role implementations where their input contracts fit, but do not describe the adapters as already implemented or compatible. One shared planning Markdown file and one learned-check file remain sufficient; do not reintroduce the removed Weave evaluation gate. Keep tracing separate from acceptance.

The user's active Fusion task explicitly requests one tool, indexed five-axis motion, impressive parts and video, and no more three-axis development. Preserve that scope: one fixed end mill, a known indexed multi-face part family, a prepared target and machine, and bounded CAM choices. The earlier suggestion below to return to a three-axis fixture block is not the recommended next work under that preference.

Priorities: (1) replace model-written Fusion API code/raw movement lists with small CAM proposals; (2) keep fixed geometry and simulator workers warm; (3) preserve both actual learning paths and their next-part loading; (4) demonstrate a real failure, saved lesson, and subsequent part using it; (5) generate polished machine playback from the retained candidate. Do not weaken verification thresholds to improve the graph. The existing custom geometric verdict and Fusion stock/machine checks remain different verification scopes.

Use two graphs with distinct meanings: attempts/full simulations or planning wall time per verified job for learning efficiency; and same-part before/after machining time for process improvement. Different parts' raw cycle times do not form a valid learning curve. The longer instruction list should be inspectable as an actual file diff with its source failure or judge decision, rather than merely accumulating bullets.

The revised conclusion is: **the learning architecture is appropriate; the expensive and overly general implementation of its CAM-generation box is the main redesign opportunity. Preserve the learning loop while narrowing the generator and using the faster simulator where its stated scope is sufficient.**

## Original review and timing evidence

Assessment of the repository, live GitHub refs, working tree, retained runs and presentation on September 12, 2026. This is a recommendation, not an implemented architecture change. Existing implementation work was preserved. The indexed campaign was still incomplete at inspection.

The fastest credible path is a bounded, headless machining loop: fixed target and shop → Astra proposes a small recipe → deterministic toolpath compiler → cheap checks → custom geometric simulation → timing judge → repair or retain. Present the resulting artifacts in the existing showcase. Keep Fusion as a separately identified final verification/export capability when required. Do not put Fusion document generation and native UI collection inside every interactive proposal.

## What was reviewed

| Version | Actual role | Best use now | Important gap |
| --- | --- | --- | --- |
| `main` at `38136d1` | Starter, agreed loop and team context | Shared requirements | Not the integrated application |
| `hack-slide-deck` at `8e14f54`, PR #1 | Earlier architecture slides | Narrative reference | Planned walkthrough, not execution evidence |
| `konsta-demo-hackathon` at `4fbb778` | Hosted workbench, deterministic CAD/path compiler, 2.5D simulator, memory and interactive marimo slides | Fastest route to the uploaded presentation's visible story | Presenter proposals are scripted; same-job recipe recall is not new-part learning; its documented live provider differs from the Astra path |
| `toukoversion` remote at `9aa8275`, local HEAD `0afc2ec` plus extensive current edits | Astra drawing-to-CAD/CAM, Fusion machine verification, stock comparison, learned checks and prompt updates | Stronger external verification and editable manufacturing artifacts | Expensive generation/recovery, document lifecycle, native UI and multiple model calls |
| `custom-simulation-touko` at `6a7c7cb`, plus current local `cnc_simulator/` work and retained runs | Headless conservative voxel simulator, Astra CAM loops, viewer, housing video and indexed 3+2 extension | Fast agent iteration and moving-machine visual story | Narrow geometric scope, coarse demo tolerance, incomplete indexed campaign, no current Fusion-plan interchange or Weave instrumentation in `camloop/` |

The directory contains several implementations and historical documents. The latest local indexed artifacts are more current than parts of `INDEXED-MACHINING.md`; the README does not alone describe the whole project. Avoid merging all branches wholesale: the `silta` module layouts, plan schemas, model adapters and learning contracts differ.

## What the showcase actually demonstrates

I opened the [seven-slide presentation](https://silta-cdswwreljq-uc.a.run.app/slides/), observed the drawing/fixed-target slide, played the failed path until it stopped at `s0005` against `clamp_front`, and inspected the repaired pass at 15 mm clearance. Its visible opening label says scripted proposals with real CAD, checks, simulation and memory. The source runbook explicitly fixes proposals for reproducibility and reruns verification after disk recall. This is a useful, honest demo of those mechanics, but is not evidence of fresh autonomous Astra repair during that presentation.

I also inspected sampled frames from the local 59.97-second, 1920×1080 housing video, `cnc_simulator/workspace-housing/housing-machining.mp4`. It shows the spindle, indexed workpiece, material removal and machine context. Its supporting code uses deterministic seed CAM and swept-tool display meshes. That clip does not itself establish learned housing CAM optimization. It already demonstrates that Fusion need not run to produce the desired machine visuals.

The visual story needs an understandable failure, an unchanged part, a repaired process, measured timing and subsequent reuse. An entire Fusion setup lifecycle is not necessary to show those events. The housing clip has visual impact, but the learning story needs to be added explicitly; beautiful machining alone does not show an improving agent.

## Measured latency

These are wall-clock planning/verification times, distinct from estimated machining time.

- Fresh Fusion Part D (`runs/learning-part-d1/manifest.json`): 345.7 seconds total. Target acceptance took 124.6 s; failed CAM generation 86.0 s; repaired candidate creation 73.2 s; verification 40.4 s; judge 21.4 s. Event intervals aggregate several activities and are not isolated kernel profiles.
- Final Fusion A/B/C/D manifests contain verification intervals of 40.4–143.0 s. Several are recovery/reuse runs; their near-zero candidate creation must not be described as fresh generation speed.
- The ten-part custom pocket campaign contains 75 recorded simulation intervals: median 6.73 s, range 5.19–9.71 s. Its 68 adjacent planner-to-simulation intervals have median 14.80 s. Whole runs still took roughly 2.3–15.9 minutes, including repeated attempts and, in some cases, later final-judge review. Removing Fusion does not automatically make the whole workflow instantaneous.
- The retained indexed bearing-block run finished in 92.4 s, including a reference simulation, cold/warm proposal comparison, multiple attempts and judges. Its candidate evaluations were approximately 2.9–3.2 s in those records.
- A fresh local replay of its 331-move passing plan measured **20.545 s cold**, **3.123 s with cached geometry and no exports**, and **3.803 s warm with exports**. All passed under the same 1 mm voxel resolution / 3 mm tolerance; 368,640 cells. This is one sequential profiling sample under current machine load, not a percentile or an accuracy-matched Fusion comparison. No model calls or Fusion UI operations were made for this profile.

Raw extracted Fusion event intervals: [fusion-timings.json](2026-09-12-fusion-timings.json). Fresh simulator measurements: [simulator-profile.json](2026-09-12-simulator-profile.json).

## Highest-value design changes

1. **Make the agent produce a recipe.** Choose tools, operation order, clearance, stepover and stepdown within a fixed schema. Deterministic code produces motions. The indexed compiler already does this in `camloop/indexed/cam.py`; reuse it. The older pocket loop emits every movement, and the Fusion loop emits Python source. Both spend model effort on low-level representation and repair. Keep Astra; speed does not require a different model.
2. **Freeze CAD and shop once per job.** Cache immutable geometry queries and reuse the accepted target. Keep the simulator worker alive between attempts; `_GEOMETRY_CACHE` is currently process-local. Scope persistence by source content, grid settings and verifier version. Do not run the reference and cold/warm learning audit on every ordinary UI request; those belong to experiment mode. Final candidate verification remains mandatory.
3. **Budget the interactive search.** One candidate plus one repair/improvement is a practical starting point, retaining a verified incumbent. Target a warm proposal-to-verdict around 15–25 s and a short job around 30–60 s, then measure it. These are proposed targets, not achieved service guarantees. Keep a timing-only judge at meaningful decision points, and perform learning analysis after the visible candidate result. Report budget exhaustion honestly.
4. **Reuse the existing presentation.** Adapt one run record into target, trajectory, failure location, stock states, before/after time and memory evidence. Do not rebuild another viewer or host a second product to prove the same interaction. Keep replay and live-run labels visible. A cached real run can be instant to inspect while a fresh run computes separately.
5. **Render expensive polished assets once.** Ordinary candidates need a verdict and lightweight playback. Produce Boolean surface checkpoints and MP4 for the selected presentation runs. The profiler suggests ordinary simulation exports are a modest cost here (~0.7 s); optimizing them is secondary to cold geometry setup, model calls and excessive attempts.
6. **Integrate Weave into the chosen custom execution path.** Reuse the project's known tracing pattern around propose/check/simulate/judge/learn. The Fusion branch's traces do not establish that the standalone `camloop` path is traced.

## Where Fusion fits

For the immediate showcase, preserve the existing Fusion results as separate evidence rather than require a new hybrid integration. If the deliverable must be editable Fusion CAM plus stronger machine/stock checks, implement a recipe-to-Fusion adapter and validate the resulting Fusion toolpath independently. A custom simulator pass cannot automatically certify a newly generated Fusion path.

If Fusion must remain in every iteration, the least disruptive route is validated operation templates plus parameter edits, generation only for invalid/changed operations, and deferred NC posting/export until an accepted checkpoint. Current `silta/cnc/agents.py` requests `generate_toolpaths` with `skip_valid=False`, posts NC and saves/exports the candidate before controller cheap checks. Moving simple recipe checks ahead of that stage avoids paying for obviously rejected proposals. Preserve exact candidate/evidence identity and a recoverable document; do not simply remove the saved-document mechanism that keeps the linked machine intact.

Autodesk supports [generation for individual operations or collections and skipping valid paths](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAMIntroduction_UM.htm), and [CAM templates created from existing operations](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/cam_CAMTemplate.htm). These reduce orchestration work; they do not remove native simulation collection or prove an end-to-end speedup until profiled.

## Scope and evidence choices

For the fastest learning demonstration, use the existing three-axis fixture block: one pocket, a few holes, two tools and a visible clamp. For an indexed visual demonstration, use one existing passing housing/bearing-block family and a few faces; finish that loop before adding more parts or simultaneous five-axis machining. General PDF interpretation and arbitrary geometry should not be the critical path of the demo.

The custom indexed campaign was incomplete: one reference failed, two runs were completed, and the fourth manifest still said running when inspected. There were no completed MP4s in its `videos/` directory. It is promising, not a finished five-part product.

Do not compare the custom 3 mm demonstration tolerance directly with Fusion's 0.127 mm stock-comparison result. Raising voxel resolution for finer detail grows a dense three-dimensional grid cubically; this is not an immediate route to general precision verification. A 2.5D heightfield is cheaper for top-access pockets, but cannot represent arbitrary multi-face geometry and undercuts. Keep each verifier's scope explicit.

Finally, the large custom machining-time gains combine higher allowed feeds, deeper/wider passes, reduced travel and fewer tool changes. For the bearing block, the reference used 350 mm/min cutting feed versus 900 mm/min for the retained best. Without force/deflection/controller physics, this is not evidence of production-safe 79% improvement. For a persuasive learning experiment, fix feed presets and show a concrete structural repair or ordering improvement, then test one unseen part with and without the saved lesson. Same-part recipe recall, fixed-check improvements and autonomous cross-part learning should have distinct labels.

## Recommended next work order

Choose one accepted part and one visible failure; wire the existing parameter compiler and custom verifier to the showcase artifact contract; run one fresh Astra repair with timing; retain its replay and a matching trace; demonstrate one subsequent-part check or planning lesson. Use existing Fusion evidence as an optional deeper verification view. Add recipe-to-Fusion export only if that deliverable is essential. This consolidates the strongest parts already built without starting another simulator, viewer or broad CAM rewrite.
