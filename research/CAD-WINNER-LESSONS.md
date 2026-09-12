# What CAD Sandboxes changes about our strategy

Reviewed September 12, 2026. This supersedes the generic tool-invention recommendation as the next direction to investigate, not as an approved build decision.

## Evidence and limits

Source video: `/Users/touko/Downloads/IMG_0206.MOV`, 706.67 seconds. The first roughly 3:16 covers Homebody; CAD Sandboxes follows. Reviewed sampled frames and a local machine transcript. The transcript has obvious recognition failures around 3:26–4:03 and imperfect names/technical terms. Do not quote those passages as reliable speech. Original video is not copied into the repository.

Public code inspected at commit `636c284e1ecabf73fea1ce14b0d6d58170c8f440`: [repository](https://github.com/peytoncasper/cad-sandboxes/tree/636c284e1ecabf73fea1ce14b0d6d58170c8f440). Touko reports that it won. The creator's indexed social post also claims a win, but no official judge deliberations or scorecards were found. Causal explanations below are hypotheses.

## What the stage recording actually contains

- Around 4:44–5:27: the presenter frames the shift toward longer autonomous tasks and compares CAD's future to the movement from coding autocomplete to background agents.
- Around 5:27–6:20: describes Fusion on AWS, an HTTP/SDK interface, and model state beside the terminal. Acknowledges a frozen demo/network trouble.
- Around 6:28–7:40: contrasts simple earlier geometry with a servo-driven assembly; explicitly acknowledges overlapping holes and overly thin walls. Describes pointing out the errors so the model can revise them.
- Around 7:40–8:30: switches to a recorded demonstration. Describes dimensions/specifications and SDK-driven construction.
- Around 8:49–9:49: a judge asks about editing; the answer focuses on reference frames and selecting a specific part/point with an annotation.
- Around 10:09–11:06: a judge asks about physical grounding; presenter describes selected hardware, schematics and dimensions, plus a prior example of the agent asking for a ruler measurement.
- Around 11:09–11:42: a judge asks why cloud CAD matters; presenter answers with parallel and background work.

These are paraphrases of a machine transcript, checked against sampled visuals, not a claim that every described capability completed live. The assembly shown around 7:00 is an example image; it does not alone prove successful live CAD generation or physical validation. Human-directed correction is described; automatic learning across tasks is not demonstrated in this recording.

## What the code adds

The workstation source supplies an agent-facing environment around a substantial professional tool: Fusion SDK handlers, VM/auth plumbing and geometry capture/viewing. It includes mechanical collision/clearance audit handlers. This supports a more consequential concept than merely generating a 3D picture.

However, the workstation README explicitly says the optional modeling CLI is external and unbundled, and the viewer polls published captures rather than continuously exporting Fusion. Public source is not a turnkey reproduction of all stage claims. The separate quote prototype is present in the repo but was not the main story of the recorded CAD presentation. [Workstation guide](https://github.com/peytoncasper/cad-sandboxes/blob/636c284e1ecabf73fea1ce14b0d6d58170c8f440/fusion-workstation/README.md).

## Why it could win despite a rough demo

1. **A new category of delegated work.** The audience could imagine handing an engineering assignment to an agent, as they already hand off coding tasks. That is a large implication conveyed by a small prototype.
2. **The model is central to the achievement.** The pitch attributes the newly workable long task to improved model capabilities. This is a compelling story for a model-launch event, although we cannot infer the organizers' private weighting.
3. **Professional artifacts make the work consequential.** Dimensions, parts, joints and CAD operations suggest usable engineering output. A believable path to utility can outweigh surface polish in technical judging.
4. **Domain specificity builds credibility.** The presenter can explain reference frames, component dimensions and concrete failure modes. The judge questions test those points. Acknowledging limitations gives the claim sharper boundaries.
5. **The fallback preserves enough evidence.** Delivery is fragile, but the recorded assembly and explanation preserve the core idea. We should copy the credible capability and improve delivery, not imitate the fragility.

Alternative explanations remain possible: earlier judging conversations, unseen project evidence, rubric weighting and the rest of the field. One winner does not prove demos or product quality are unimportant.

Our earlier list was too focused on mechanisms: tool invention, memory, curricula. A stronger selection question is: **what useful work becomes delegable because of this mechanism?**

## Best translation to CoreWeave

Proposed pitch: **An engineering agent that designs, tests and revises a part until it satisfies measurable constraints, and learns from those failures for the next part.**

Use one small part family, such as servo mounting brackets or assembly fixtures. Input: a component spec, mounting pattern, clearance envelope and material/geometry limits. Output: an editable CAD artifact, rendered result, verification report and the lineage of revisions.

Cycle: propose geometry → execute CAD in isolation → check collisions, hole spacing and clearances → diagnose failure → revise → retain a tested design rule/helper → evaluate on a new component spec.

The artifact and its consequence should lead the demo. The learning mechanism explains why the agent gets more dependable. Merely showing a parameter sweep is optimization; demonstrate a retained lesson on a different task if claiming cross-task improvement.

Minimum scope: one parametric part family, several editable design parameters, three deterministic checks, one real failure/revision, one unseen follow-up and a visible trace. Do not claim strength, manufacturability or certification based only on geometric checks. If structural simulation is included, use a real solver, explicit loads and assumptions; otherwise leave that claim out.

Avoid making Windows/Fusion/cloud setup the whole hackathon. Investigate a Linux-compatible CAD kernel or an already working team environment before committing. The winner's professional-tool pattern is transferable without reproducing its infrastructure. Any borrowed code also needs event-rule and license review; no implementation code was copied into this repository.

## Make sponsor use part of the causal loop

| Sponsor/tool | Necessary job in the proposed product | Proof in the demo |
| --- | --- | --- |
| CoreWeave/W&B Sandboxes | Execute candidate geometry and checks in isolated environments; compare independent candidates | Actual job results tied to each candidate, with failed candidates retained |
| Weave | Record task/attempt/tool trajectories and evaluation outcomes; our controller queries outcomes to choose what to revise/promote | Click a failed design and inspect the exact failing measurement; show version comparison |
| ARIA | Analyze logged experiment failures and propose/run a next experiment using its supported workflow | Show a specific recommendation and the measured result of testing it |
| marimo | A reproducible engineering workbench with input constraints, experiments and interactive results | Change a parameter and rerun the relevant calculation/inspection |
| TypeSafe | Candidate planner or tool-using model, only after verifying its real strengths and interface | Execute the same bounded tasks, measure actual success, and assign it a role based on evidence |

CoreWeave's disposable compute is a natural fit for trying candidate actions before adopting them. Weave should supply evidence the improvement controller actually uses, rather than only a dashboard shown after the work. ARIA can be genuinely helpful for experiment-level iteration, but its public documentation does not establish an arbitrary low-latency API for an inner loop. Do not invent one.

Sandboxes are documented as invitation-only preview; verify event access. They use containers, so do not assume they can host the winner's Windows/Fusion VM. ARIA requires a team project and enabled Smart features. Start with one working execution path and Weave; add other tools only when they complete an essential step.

Sources: [Sandboxes](https://docs.wandb.ai/sandboxes), [ARIA](https://docs.wandb.ai/aria/overview), [Weave evaluation](https://docs.wandb.ai/weave/agent-evals), [marimo/molab](https://docs.marimo.io/guides/molab/), [event](https://luma.com/coreweavehacks).

## Two alternatives using the same lesson

- **Agent that repairs brittle business automation.** A realistic workflow fails when a form/schema changes; the agent reproduces the failure in a sandbox, repairs the adapter, tests for regressions and promotes the repair. Strong Weave/Sandbox dependence and an obvious operational consequence. Keep actions inside a test service. Risk: can look like generic browser automation unless the durable recovery is unmistakable.
- **Agent that designs and verifies a small circuit.** Turn requirements into a simulated circuit, identify a failed behavior and revise components; transfer a learned strategy to a different requirement. Natural experiment/compute/workbench integration. Choose only if the team already has circuit/simulation competence and a working solver; hardware validation remains separate.

## Sponsor conversation worth having

“We want an engineering agent whose failed geometry checks become the next experiment, and whose retained lessons improve a new design. We would use your sandbox for execution and Weave evaluation as the input to the revision loop. What is the strongest supported way to connect this to ARIA today?”

This both tests product fit and discovers actual access constraints. Do not assume endorsement from a friendly discussion. The aim is a project a sponsor can explain in one sentence as evidence of what its technology enables.
