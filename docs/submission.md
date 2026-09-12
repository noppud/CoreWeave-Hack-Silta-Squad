# Silta CNC — submission draft and demo script

Status: planning draft, not submitted. Product and sponsor claims below are **intended behavior** until backed by implementation evidence. Rewrite into completed-work language only after verification.

## Project

- Project name: Silta CNC (working name)
- Team name: Silta Squad (confirm uniqueness)
- Repository: https://github.com/noppud/CoreWeave-Hack-Silta-Squad
- Track: Best Loop Design; provisionally Best Use of Weave. Verify explicit Best Loop enrollment and whether multiple sponsor tracks are selectable in AGI House.
- W&B project URL: TBD
- Live demo URL: TBD — required full application on GCP Cloud Run; see [deployment plan](deployment.md).
- Demo recording, under two minutes: TBD

## Summary

Proposed three-sentence summary, to use only once implemented:

Silta CNC turns a dimensioned part drawing and a shop's available tools into a 3D CAD model and a checked machining plan through chat. Its agent repairs tool-reach and collision failures using deterministic feedback, then replays the resulting machining simulation. W&B records each attempt, ARIA helps identify checks that should happen earlier, and a marimo workbench shows whether those changes reduce failed simulations on new parts.

## Team

TODO: List every participating member, their role, and their X and/or LinkedIn handle. Confirm each person's AGI House sign-in and participant survey.

## How it works

Dimensioned drawing → user-confirmed part specification → deterministic CadQuery solid/STEP → model-generated machining recipe → cheap checks → deterministic toolpaths → geometric stock-removal/collision simulation → structured failure feedback → repaired recipe. Maximum three candidate plans plus time/call/spend limits; repeated/unsupported/unsatisfiable cases stop visibly. The target design remains fixed while manufacturing decisions change.

Across jobs, ARIA analyzes W&B development runs. A reviewed recommendation becomes a versioned check/policy, tested on fixed recipes and separate holdout examples. This is runtime repair and policy improvement; no model weights are trained in the planned MVP.

## Evidence

Fill from real artifacts; do not replace TBD with intended outcomes:

| Evidence | Measured result / link |
| --- | --- |
| Live drawing-to-plan job ID and commit | TBD |
| Explicit naive challenge recipe and input hashes | TBD |
| Initial blocking failure | TBD |
| Structured feedback and actual model repair diff | TBD |
| Before/after target hash unchanged | TBD |
| Collision segment and repaired simulation result | TBD |
| STEP roundtrip and final stock measurements | TBD |
| Before/after simulations, attempts, latency and cost | TBD |
| Weave trace + W&B run/project | TBD |
| ARIA recommendation referencing actual development runs | TBD |
| Implemented policy/check change and controlled comparison | TBD |
| Holdout counts and denominators, including failures | TBD |
| Runnable marimo notebooks and recorded replay manifest | TBD |

## Sponsor tools and protocols

Planned roles; retain only completed integrations and exact model/provider IDs:

- CoreWeave/W&B Serverless Inference: planning/repair calls if activated; OpenRouter for a tested alternate/vision route as needed.
- Weave: nested agent/tool traces and deterministic evaluations.
- W&B Models: versioned experiment metrics and run/artifact lineage.
- ARIA: actual experiment analysis informing a measured next iteration.
- marimo: chat/3D workbench and reproducible evaluation notebook.
- CadQuery, Python state machine, anywidget/Three.js: trusted geometry, orchestration and result visualization.
- MCP: optional development-time W&B inspection only if actually connected/used; otherwise omit. A2A and RL training: none in MVP.

A synthetic setup trace, visible ARIA button or unused dependency does not establish meaningful usage. Record molab only if the notebook really ran there; local marimo use remains valid product integration.

## What we built at the hackathon

Planning baseline is commit `81c2cc4`: Python CLI, W&B request/tracing wiring, fake-provider tests and event/context docs. Verify when that baseline was built before describing it as hackathon work. Planned new work: CNC domain/fixtures, CAD, checks/compiler/simulator, chat and viewer, bounded controller, experiments and ARIA-guided change. Attribute third-party libraries, hosted models and any imported assets/datasets. Commit timestamps alone do not establish all originality claims.

## Three-minute demo outline

| Time | Screen/action | Presenter point |
| --- | --- | --- |
| 0:00–0:15 | Drawing, machine/tools, short chat request | A shop needs a recipe that fits its equipment. |
| 0:15–0:35 | Confirmed dimensions and 3D target | The requested part becomes real STEP; manufacturing decisions are separate. |
| 0:35–1:00 | Explicit naive challenge recipe; failed reach check | Cheap checks catch the short tool; show exact repair. |
| 1:00–1:35 | Collision replay, offending segment, clearance repair | Simulation generates the feedback used by the agent. |
| 1:35–2:00 | Successful stock-removal replay and downloads | Same requested part; checked recipe and inspectable artifacts. |
| 2:00–2:30 | Preloaded Weave trace/W&B results and ARIA recommendation | One analyzed failure becomes an earlier check on another fixture. |
| 2:30–2:50 | marimo comparison of old/new policy | Show measured counts and any failures; distinguish estimates from measurements. |
| 2:50–3:00 | Final result | Prototype geometric verification, with general CAM/physical machining left for later. |

Preload sponsor tabs and a completed real run; do not spend the presentation waiting on remote pages. Start live only if rehearsed within budget. Switch to a visibly labeled recording/replay on service delay; never pretend recorded inference is live.

## Recording under two minutes

Target 110 seconds: 15 s input/confirmation, 20 s model/recipe, 30 s failure and actual repair, 25 s successful simulation, 15 s W&B/ARIA/marimo comparison, 5 s final artifact. Add concise captions identifying recorded replay, prototype simulation and measured results. Include no API keys or irrelevant personal/customer information.

## Likely judge questions

- **What learns?** Plans repair from deterministic feedback; cross-task policy/check versions improve after experiment analysis. Model weights do not change.
- **Is this real simulation?** Geometric stock removal plus cutter/shank/holder/fixture checks for a restricted 2.5D family. Show trajectory and collision artifacts; no claim of full machine physics.
- **Why all these sponsors?** Inference creates plans; Weave reveals attempts; W&B measures runs; ARIA selects a tested next improvement; marimo is the interactive product and evaluation surface.
- **Was the failure staged?** The naive recipe is an explicitly labeled challenge fixture. Also provide separately measured fresh model attempts and held-out examples.
- **Does it manufacture arbitrary parts?** No. State the supported part/operation family, unknown cases and lack of controller-ready G-code.
- **How much time/money does it save?** Report measured application/check/simulation differences; machining estimates use declared assumptions and are not validated shop savings.

## Final submission checklist

- [ ] Real outcomes replace every evidence TBD; remove any unimplemented claims.
- [ ] Final name/roster/socials, eligibility and every participant survey confirmed.
- [ ] Correct public repository/release commit and reproducible setup verified.
- [ ] Live HTTPS app passes the complete workflow in a fresh browser; record deployed revision and remote test job.
- [ ] Best Loop enrollment and sponsor track selection checked in authenticated platform.
- [ ] W&B project link, trace, ARIA evidence, marimo entry points and recording work for judges.
- [ ] Three-minute rehearsal, Zoom share and offline replay ready.
- [ ] One teammate submits by target 12:15 PM Sunday; official working deadline 1 PM Pacific.
- [ ] Read back submitted project URL/confirmation and timestamp.
