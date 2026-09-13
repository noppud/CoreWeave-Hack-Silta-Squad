# CoreWeave Hacks: Agent Loops — event brief

Checked September 12, 2026. Public organizer sources, personal confirmation mail, the Notion participant handbook linked in Luma announcements, and four Plaud presentation transcripts were reviewed.

## Schedule and prizes

September 12–13 at 400 Alabama St, suite 202, San Francisco. All times PDT.

| Saturday | Sunday |
| --- | --- |
| 09:00 doors/breakfast | 09:00 doors |
| 10:30 kickoff | 13:00 submission deadline/lunch |
| 11:15 build starts | 13:30 judging |
| 18:30 dinner | 15:30 presentations |
| 21:00 office closes | 16:30 awards |

Named awards: Best Loop Design, robot dog (~$4k), $2k cash and Fully Connected presentation; Most Production-Ready, F1 tickets (~$1–2k each) and $1k; Weave $1k; ARIA $1k; marimo $500; social demo $1k; TypeSafe, two Hugging Face Microducks and swag (~$1k).

The production award is described as a later decision at Fully Connected, September 29–October 1. Confirm its eligibility and follow-up requirements. Capacity is 200; every teammate should register individually. [Organizer listing](https://luma.com/coreweavehacks).

## Theme and people

The organizer emphasizes agents improving through repeated action and feedback, including memory, generated tools, training and evaluation. The advertised total exceeds $20k in prizes; it is not an all-cash pool.

CoreWeave/W&B hosts with AGI House, marimo and TypeSafe. The sponsor event page lists Emmanuel Turlay (Weave), Julia Rose (ARIA), Konstantin Taletskiy (marimo), Ryan Biddy, Mo Tiwari (DeepMind), Nirav Patel (Okta), and others. This suggests an audience familiar with agent tooling and reliability; it does not establish scoring weights. TypeSafe is bringing a model for participants. Robots are advertised onsite, but programmable access is unverified. [W&B event page](https://wandb.ai/site/resources/events/coreweave-hacks-agent-loops-hackathon-with-weights-biases-and-agi-house/).

## Tool capabilities and integration implications

| Tool | Verified capability | Implication for our build |
| --- | --- | --- |
| Weave | Trace agents, score trajectories, compare agent versions and evaluation results | Make the improvement claim inspectable; retain failed runs as well as successful ones |
| ARIA | Analyze and run experiments, propose next steps, build reports; requires a team project in multi-tenant cloud and enabled Smart features | Verify account access early; do not assume it is an unrestricted model API |
| marimo/molab | Python notebooks in hosted compute with sharing and app presentation | Useful for an experiment cockpit and reproducible results; confirm event GPU availability |
| TypeSafe | Event promises access to its model | Verify interface, credits, latency, tool support and prize requirements before making it critical |

Sources: [Weave agent evaluation](https://docs.wandb.ai/weave/agent-evals), [agent tracing](https://docs.wandb.ai/weave/guides/tracking/trace-agents), [ARIA overview](https://docs.wandb.ai/aria/overview), [molab documentation](https://docs.marimo.io/guides/molab/), [TypeSafe](https://typesafe.ai/).

Weave records/evaluates an agent; it does not itself provide the execution sandbox. Generated tools need a separate bounded runtime.

## Confirmed access

Touko's personal mailbox contains the September 1 Luma approval and September 12 AGI House confirmation. The latter confirms the CoreWeave office location. Private ticket links are intentionally omitted.

The GitHub invitation from noppud was accepted, and the empty `noppud/CoreWeave-Hack-Silta-Squad` repository was cloned into this workspace. No starter implementation existed at clone time.

## Participant handbook: now verified

The [Notion handbook](https://wandbai.notion.site/CoreWeave-Hacks-Participant-Handbook-3c9e2f5c7ef380eab21ecdde12620caf) was opened through Luma announcements and read in full. It is accessible in the current browser. No Notion editing access was needed or established.

- W&B tools are required; the guide offers $100 of inference credits through its request process. Credit receipt, training and sandbox access are separate, unverified matters.
- Teams may have up to five members. Work must be built during the hackathon; connections to an existing project must be disclosed and only weekend work is judged.
- Both preliminary and final demos are strictly three minutes, with at most one or two slides and follow-up questions. The checklist requests a recording under two minutes; prepare it even though another paragraph calls video optional.
- Submit through [AGI House](https://app.agihouse.org/events/coreweave-hacks-agent-loops-hackathon-with-weights). All team members must sign in and complete the participant survey; one submits. Include team names, description of the agent and its improvement, repo, sponsor/protocol usage and track.
- Include the W&B project link; it need not be public. GitHub instructions conflict between public repository and public-or-access-instructions. Prepare judge-readable source and confirm private-repo access if choosing that route.
- Rubric: self-correction/improvement, meaningful agent teamwork, usefulness, working implementation/reasonable architecture, and meaningful sponsor use. No numerical weights are provided.
- No model-weight-training requirement is stated. The MCP guidance supports improving agents using runs/traces/evaluations. See [CNC architecture and presentation evidence](CNC-ARCHITECTURE.md).

The handbook contains stale June 6/7 schedule headings and conflicting prize/template language. Use September 12/13 from the current organizer listing and AGI page for the event dates; submission is Sunday 13:00 PDT. Remaining questions are award stacking, exact production-award follow-up/eligibility, conflicting repo/video wording, and live sponsor account entitlements.

## Organizer calibration

Ask a representative: “Would a failure that autonomously creates a tested reusable tool, then improves on unseen tasks, be a strong example of Best Loop Design? What evidence would you want to see?”

The handbook and kickoff presentations support tools, memory and control-flow improvement without weight training. An organizer's additional preference could still inform strategy, but should not be mistaken for a rule unless stated as one.
