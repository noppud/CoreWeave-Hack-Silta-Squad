# ARIA in the shop control center

Research checked September 13, 2026. The contextual findings panel and copy/open handoff are now implemented. No chat backend or automation has been enabled.

## Product recommendation

Keep the loop as the main canvas. Add one Ask button that opens a contextual assistant drawer. Its context is the selected part, recorded run IDs, measured stage timings, saved evaluation results, and versioned checks/memories. Suggested questions: What slowed this part down? Which checks helped? What should we test next?

Responses should contain a short finding, a relevant chart or comparison, links to the underlying runs, and one proposed experiment. An experiment card progresses from Proposed to Tested to Saved memory/check only when the corresponding work actually occurs. The existing demo trend data stays outside the analysis dataset.

ARIA is a suitable experiment analyst: it can analyze W&B runs and Weave traces, explain failures, generate charts/reports, retain project memories, and recommend experiments. CNC execution remains with the existing local Fusion worker; ARIA's W&B Launch capability is not an established way to control desktop Fusion.

## What is supported today

- W&B's own ARIA chat supports context, images, run references, history, and an undocked window.
- W&B UI automations can trigger ARIA from run changes, artifact events, and supported metric alerts. Each starts a new conversation; the documented limit is three conversations per minute per automation.
- ARIA can generate W&B reports. A local findings drawer can display retained analysis with source links; automatic return of arbitrary chat responses into our UI needs a separately verified integration.
- W&B MCP supports building our own assistant over runs, traces, artifacts, and evaluations. That would be our Astra assistant using W&B tools, rather than the ARIA service.

## Direct embedding blocker

The actual project page returned `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'` on this check. An ordinary cross-origin iframe cannot embed ARIA. No public ARIA conversational API or embeddable chat SDK was found in the reviewed official documentation. The current Python SDK explicitly cannot create or list ARIA automations; configure those in W&B itself.

Ask the onsite ARIA team: Is there a supported conversation API or embeddable component for a third-party product, with project context, streamed responses and conversation IDs? Until confirmed, use Open in ARIA with its undocked window, plus real saved findings in our drawer. Do not promise live native ARIA chat through an invented endpoint or an iframe proxy.

## Prize fit

The current organizer listing confirms Best Use of ARIA at $1,000 and names Julia Rose from the ARIA team as a judge. It does not publish a detailed numeric ARIA rubric. The local recording of the ARIA presentation, approximately 4:13–5:00, states that actual ARIA conversations are traced and available for judging. This is presentation guidance, not a promise of eligibility or winning.

Recommended demonstration: a shop question → ARIA reads actual evaluation/run evidence → identifies a recurring failure or time cost → proposes one change → the existing runner tests it → the dashboard links the result and adopted learning back to that analysis. Preserve the real conversation and report. A branded chat alone is weaker evidence than an analysis that changes a tested decision.

Existing foundation: `output/sponsors/aria-review.json` and `aria-response.md` retain actual ARIA diagnosis of Fusion session readiness. The adapted focus-recovery change passed 16 unit tests and has a narrow 3.108-second live recovery observation. It does not isolate an end-to-end completion improvement; a later successful verification also required an independent OCR fix.

## Sources

- Organizer and prizes: https://luma.com/coreweavehacks
- ARIA overview and project memories: https://docs.wandb.ai/aria/overview
- Chat and undocking: https://docs.wandb.ai/aria/chat
- ARIA event automations: https://docs.wandb.ai/models/automations/create-automations/aria
- SDK limitations: https://docs.wandb.ai/models/automations/api
- Experiment execution: https://docs.wandb.ai/aria/autoresearch
- W&B MCP: https://github.com/wandb/wandb-mcp-server
- Private presentation evidence: `.private/presentations/e7926f87d7678042e580e9e546dda3e6.json` (keep raw transcript local)
- Existing implementation evidence: `docs/sponsor-evidence.md`, `output/sponsors/aria-review.json`
