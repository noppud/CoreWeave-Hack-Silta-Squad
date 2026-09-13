# Three-hour demo finish plan

Decision proposal, September 12, 2026. Three hours from execution start; feature freeze at 90 minutes. Preserve one tool, Astra fast/low, fixed CAD, existing failure-learning and supervisor routes. This document changes no runtime behavior.

## What wins the presentation

**A machining agent that turns an expensive mistake into a cheap check—and carries the lesson into the next job.** Open with the five-axis machine and finished part, then prove the learning. The visuals attract attention; the before/after evidence explains the contribution.

Prioritize Best Loop Design and meaningful Weave usage. Use the existing marimo workbench as the presentation shell if it can display the selected evidence cleanly; do not redesign the application framework to chase another prize. No new sandbox, model provider, model training, or permanent outer agent.

## Event evidence

- [Current organizer listing](https://luma.com/coreweavehacks), refreshed this turn: self-improving agent loops are the theme; Best Loop Design, Weave, marimo and social-demo awards are listed. Sunday September 13 submission is 13:00 PDT; judging starts 13:30.
- [W&B event listing](https://wandb.ai/site/resources/events/coreweave-hacks-agent-loops-hackathon-with-weights-biases-and-agi-house/) confirms September 12–13.
- [Saved handbook assessment](hackathon.md): loop improvement, creativity, utility, execution and meaningful sponsor usage; three-minute demo, at most two slides, prepare an under-two-minute video, readable GitHub source and W&B link. No numerical scoring weights were found. The Notion page could not be refreshed through web retrieval this turn; its old June schedule headings conflict with current organizer dates. Reconfirm any changed presentation instructions onsite.
- [Joel's latest handoff](https://github.com/noppud/CoreWeave-Hack-Silta-Squad/blob/6571f360be74cd2ac9c628fd13cb6dd21fb99fcd/docs/project-context.md) agrees on cross-part learning and shadow/offline evaluation before changing live promotion semantics. The separate six-slide pitch should be condensed.

## Choose one evidence trail

Use the real Fusion loop as the main evidence source: four prior verified parts, two learning files, measured transfer, plus the new verified UMC-750 candidate and actual footage. Use prior learning results without running more three-axis work. The new five-axis part is a capability demonstration; do not imply it independently proves cross-part learning.

`cnc_simulator/` is a separate implementation with its own measured runs, a narrower CAM compiler and coarser verification. Its visual layout may inform presentation, but do not attach its movement, tolerance or learning outcomes to Fusion records. Do not merge both execution backends in this window. Main on GitHub currently ends at the diagram; the latest work lives in branches and this dirty checkout. Packaging a single reviewed runnable revision is a delivery task, not already done.

## Parallel work, 15–90 minutes

| Workstream | Deliverable | Acceptance |
| --- | --- | --- |
| Learning / Weave | One command replays empty/current checks on 4–6 frozen, simulator-labeled valid and invalid cases; publish paired evaluations. Display exact check and prompt diffs with source traces. | Finalized Weave links read back; caught failures, false rejections, denominator and check runtime visible. Historical cases labeled as replay, not held-out generalization. |
| Demo / visuals | One workbench view: part + machine/tool → real candidate timeline → new check/prompt diff → verified output. Embed the current Fusion film and provide direct trace/artifact links. | Every visible number belongs to a selected run. Recorded, live and illustrative states are clearly distinguished. No placeholder curves or fake progress. |
| Fusion / footage, one desktop owner | Clean repeat of the corrected close-up recorder and optional finished-stock orbit; retain existing 56-second movie as fallback. | Exact candidate binding, actual stock removal, no stray menus, clean start/end. Stop recorder debugging at 30 minutes if blocked; use retained footage. |

Only one worker controls Fusion. Other workers handle files, Weave replay and UI without foreground interference. Existing active learning remains `learning/checks.py` and `learning/cad_cam.md`; evaluation reports/snapshots are evidence, not additional live memory.

**Checks:** reuse `BenchmarkRunner`, `evaluate_check_change` and `publish_evaluation`; no full runtime promotion-gate rewrite. Score using deterministic labels from completed simulation, not an LLM opinion. Include valid neighboring examples so a check that rejects everything cannot look good. Report runtime directly; historical avoided simulation time is a counterfactual estimate, not newly measured end-to-end savings.

**Prompt changes:** show what the judge requested, the exact edit, the later plan adopting it, and the actual verified timing comparison. The existing 384.860 → 211.037 s pair is a 45.2% within-part candidate improvement; it is not a controlled prompt-policy benchmark. A fresh old/new prompt comparison on the same five-axis target is optional only if both runs fit before feature freeze, with equal checks/model/budget/machine/tools. Report failures and inconclusive outcomes. Do not rebrand historical improvements as new eval results.

[Weave EvaluationLogger](https://docs.wandb.ai/weave/guides/evaluation/evaluation_logger) supports logging predictions and scores from existing code; a new orchestrator is unnecessary. The evaluation worker can use Astra to summarize the evidence, but simulation and deterministic scorers decide geometric validity and measured speed.

## Timeline and exit criteria

| Time | Work | Exit criterion |
| --- | --- | --- |
| 0–15 min | Select canonical cases, snapshot current working state, assign non-overlapping files, select presentation entry point. | One written artifact map; no branch merge guessing; known-good video retained. |
| 15–90 min | Parallel workstreams above. Optional single new five-axis evidence run only if desktop access is ready. | Evaluation + product view + usable film each work independently. Freeze new features at minute 90. |
| 90–120 min | Connect selected run, learned changes, evaluation and video in one narrative. | A complete three-minute walkthrough works without live CAD generation or a full Fusion run on stage. One cheap check can execute live. |
| 120–150 min | Two timed rehearsals; fix broken links, unreadable labels, wrong data binding and playback. | Both rehearsals finish under three minutes; offline/local replay survives cloud or Fusion unavailability. |
| 150–180 min | Finalize under-two-minute submission film, two-slide maximum pitch, README and submission draft; verify judge-readable repo revision. | Artifact/trace links work, claims match evidence, roster/survey/access items identified; no experimental code required for stage. External submission/publication remains a separate authorized action. |

Readiness means this acceptance list passes, not that three hours elapsed. If a track overruns, remove the optional orbit/new benchmark before risking the reliable demo.

## Three-minute stage sequence

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:20 | Five-axis indexing and final housing, one tool. | A drawing says what to make. A shop still needs a workable, efficient plan for its actual equipment. |
| 0:20–0:55 | Recorded real failure → precise simulation feedback → newly written check. | The failure changes the system, not just this attempt. |
| 0:55–1:25 | Run the learned check live on the retained next-part candidate; compare valid repair. | This later candidate was caught in 51 ms before simulation. Label historical result separately from today's fresh replay time. |
| 1:25–1:55 | Judge instruction, prompt diff, same-part verified before/after. | The fixed target stays the same; a verified plan's estimate improved from about 385 to 211 seconds. |
| 1:55–2:25 | Paired Weave evaluation and one actual trace. | These are the failures caught, valid plans retained, and measured check cost. This is how we inspect whether a lesson helps. |
| 2:25–2:50 | Five-axis stock-removal clip, finished result and downloadable CAD/CAM/NC artifacts. | This is actual indexed 3+2 Fusion verification; the simulator does not certify physical cutting or arbitrary posted NC. |
| 2:50–3:00 | One sentence and result. | Silta turns manufacturing feedback into reusable planning knowledge. |

The stage story uses two clearly named examples: prior learning evidence and the new five-axis capability. Prefer one coherent new five-axis learning story only if actually measured in time. Never splice them into a fictional single run.

## No scope expansion in this window

No simultaneous five-axis conversion, extra tools, arbitrary sculpted parts, second simulator migration, cloud Fusion hosting, sandbox repair, broad eval platform, new runtime ARIA loop, or forced speed-improvement curve. Existing ARIA review can be cited as a development contribution if its actual record is shown. Keep the machine film, the learning proof, and the product outcome central.
