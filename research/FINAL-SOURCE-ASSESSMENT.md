# Latest evidence and direction assessment

Checked September 12, 2026. Retrieved the two newest Plaud recordings completely: `67fd42d32fcf59fc7b4cad5b2d4d8021` (26/26 segments) and `16ea05a3bfc667c8c455a376d8792375` (45/45). Full JSON is in ignored `.private/presentations/`. Timestamps are relative to recording start. Names/model IDs may contain ASR errors.

The first is the team's discussion of ART/open weights and asking whether training is necessary. It does not establish the rules.

The second records the mentor discussion Joel went to have. Identity/official authority is not independently verified. At 1:21–2:13 the mentor discusses decision policies/bandits without changing foundation-model weights. At 3:48–4:11, after understanding CAD, they suggest dropping ART and keeping ARIA/Weave, then possible distillation. At 4:21–5:34 they discuss traces as potential training data. At 5:54–6:20 they distinguish model-focused ARIA work from agent-focused Weave work. At 6:27–6:37 they encourage a creative connected loop. This supports our direction without establishing a requirement or prize guarantee.

Comments about consuming credits are not an optimization objective: maximize useful verified outcomes per budget. Distillation needs suitable data/model/access/time; merely tracing a frontier model does not train another model.

Fetched and checked out GitHub main at `81c2cc44e011ba5d90e6f8c127f10a4731e3d7eb`. [Konsta's transcript](https://github.com/noppud/CoreWeave-Hack-Silta-Squad/blob/81c2cc44e011ba5d90e6f8c127f10a4731e3d7eb/meta-ctx/2026-09-12-training-llm-agents-with-openpipe.md) comes from Wispr Flow, September 12, 11:43/11:57 PDT.

- 4:10–6:15: incoming drawings/CAD, shop machines/tools, output as manufacturing recipe rather than general design from scratch.
- 6:15–6:35: expensive simulation failures improve cheaper checks.
- 7:04–8:08: actual machine visualization, fewer flips, grouping by tool and production-cost improvement.
- Resumed 0:56–1:03: the team describes the adviser as associated with Weave, not a judge.
- Resumed 1:17–1:38: marimo as demo interface; avoid distorting the project for a side prize.

Correct source ambiguities: STEP is geometry, not machining instructions; ART involves post-training, not merely rearranging tool calls; speculative profit claims/prize amounts in conversation are not established facts.

Verdict: proceed with the bounded domain and generated-check loop. Main risk is a trustworthy simulator within the build window, followed by proving savings without rejecting workable plans. [Final plan](../docs/plan.md) defines both acceptance criteria and the marimo presentation. No weight-training requirement was found in the handbook, and the mentor discussion gives a compatible route.
