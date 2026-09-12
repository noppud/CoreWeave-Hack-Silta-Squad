# Classification and directions that could win

Update: [The CAD Sandboxes stage demo and code review](CAD-WINNER-LESSONS.md) sharpen this shortlist toward a useful engineering outcome. Treat the ranked mechanisms below as building blocks; the newer note is the current recommendation.

Recommendation as of September 12: build a small agent that turns failure into a reusable capability. Make the improvement visible and independently measurable. Choose the application after testing sponsor reaction and the first end-to-end loop.

## Apply Touko's framework

| Framework axis | Classification | Consequence |
| --- | --- | --- |
| Primary scoring mode | Technical-first, with a strong product/demo layer; inferred, not an official rubric | Spend effort on a real improvement mechanism and making it understandable |
| Challenge style | Open-ended creativity constrained by a sponsor theme | Surprise judges with what the loop achieves while making sponsor use substantive |
| Judging mode | Submission plus scheduled judging and presentations; detailed format unknown | Prepare a short live demonstration and a recorded fallback |
| Best initial target | Best Loop Design, with Weave as the most natural additional fit | Build one coherent project; verify multi-award rules before assuming eligibility |
| Sponsor motive | Plausibly wants proof its tooling helps agents improve | Show the exact trace, evaluation, change and outcome |
| Team advantage | Fast product/demo execution; potentially factory-domain specificity | Favor a visual, bounded environment over a broad autonomous platform |

The event theme and awards support this classification: [event page](https://luma.com/coreweavehacks). Your playbook's principle is to match the scoring system; it does not mean technical difficulty alone wins.

For this event, the strongest story is: **the agent fails; it changes something durable; the next unfamiliar task goes better; we can show why.** Repeatedly calling a model until it succeeds is a weaker improvement claim. Updating tools, memory or policy can be enough for a compelling loop without attempting weight training, subject to organizer confirmation.

## Ranked general directions

These ranks are qualitative judgments, not win probabilities. Competitor strength and exact judging weights are unknown.

| Rank | Direction | Memorable moment | What improves | Main risk |
| --- | --- | --- | --- | --- |
| 1 | Agent that invents its own tools | A failed task creates a new tested tool; a new task becomes easy | Persistent tool library and routing | Looks like a coding wrapper unless transfer is demonstrated |
| 2 | Agent training arena | Two versions race through unseen challenges after one trains | Strategy, memory or tool use | Reward hacking; a pretty arena can hide weak learning |
| 3 | Factory agent that learns from mistakes | A disruption that broke yesterday's plan is handled correctly today | Scheduling/decision heuristics | Domain explanation takes too long; simulation realism |
| 4 | Memory that repairs itself | Correct an agent once; it handles a new related situation and rejects stale advice | Structured memory and applicability rules | Crowded concept; retrieval improvements may be subtle |
| 5 | Agents that evolve a reliable team | System identifies a bad specialist and changes team composition | Routing, checks and division of work | Latency and complexity; “more agents” is not inherently useful |

### 1. Agent that invents its own tools — strongest default

One sentence: “When this agent hits a task it cannot do reliably, it builds and verifies a tool so it does not need to struggle again.”

Choose one small domain: messy tabular data, document reconciliation, or constrained scheduling. A task fails an external check. The agent inspects the trace, proposes a helper, tests it in isolation, and admits it to its tool library only after a regression suite passes. A new task reuses the tool.

Demo: baseline attempts a task and fails a visible assertion; the failed assertion leads to a named tool appearing on screen; replay an unseen related task; compare correctness and model calls with the baseline. Include a bad candidate rejected by the test gate if it occurs in the recorded run.

Measure: held-out task success, regression count, tool reuse across different tasks, calls/cost per successful task. Keep the base model and budget comparable.

Smallest credible build: one domain, one generated tool format, a bounded runtime, a verifier the agent cannot edit, versioned tool registry, Weave traces, and a clear before/after view. General-purpose tool marketplaces and arbitrary integrations are outside the minimum.

Sponsor fit: Weave gives the trace-to-improvement evidence; marimo can expose experiments; TypeSafe is interesting if its actual interface works well for the chosen task. Add ARIA only if it meaningfully analyzes or drives the experiments.

Kill criterion: if new tools only solve the exact example that generated them, there is no strong transfer story. Narrow the domain or switch to the arena.

### 2. Agent training arena — highest visual upside

One sentence: “Watch an agent train against its own weaknesses, then beat its earlier self on challenges it has never seen.”

Use a compact deterministic environment: warehouse routing, a resource puzzle, or a simulated repair mission. An evaluator identifies failure classes; a curriculum generates practice variants; a learner updates a persistent strategy or skill library; the champion is selected using a separate validation set. Lock away a final test set.

Demo: side-by-side old/new agents on identical unseen seeds, with task state and progress visibly changing. Let a judge select among prevalidated challenge families. Label replay and live runs distinctly.

Measure: success on fixed held-out seeds, actions/time needed, robustness after a rule change. Compare to an equally budgeted baseline. A beautiful simulation is presentation, not the learning evidence.

Smallest credible build: one environment and one learning mechanism. Avoid training a large model or writing a general game engine. A policy/memory update is faster to verify than a training infrastructure project.

Kill criterion: the baseline already solves everything or the evaluator can be gamed. Adjust difficulty before improving visuals.

### 3. Factory agent that learns from operational mistakes — strongest distinctive application

One sentence: “Every production disruption teaches the planning agent how to avoid that class of mistake next time.”

Use clearly labeled synthetic factory jobs, machines, deadlines and setup constraints. The agent proposes a schedule; a deterministic simulator checks hard constraints and computes tardiness; a critic identifies a failure pattern; the agent updates a heuristic or writes a scheduling helper; the new version is evaluated on different job sets.

Demo: a machine outage makes the original plan miss deliveries; the first recovery also makes a specific mistake; the agent learns; a different outage is recovered from with fewer late jobs. A before/after Gantt chart makes the consequence legible.

Measure: late jobs, total tardiness, changeover time, constraint violations and compute cost against both the original agent and a simple scheduling heuristic. Make no claim of real-factory deployment.

Why it may stand out: the loop has a recognizable economic consequence, and Touko's factory context can help make constraints specific. This remains contingent on the rest of the team's interests and skills.

Kill criterion: most of the pitch is explaining the factory rather than showing the improvement. Reduce to three machines and one disruption type.

### 4. Memory that repairs itself — reliable backup

One sentence: “An agent that learns the right lesson from a mistake and knows when that lesson no longer applies.”

After a failure, write a scoped memory with evidence and applicability conditions. Validate it on related and unrelated tasks. When conditions change, retire the stale memory and rerun the suite.

Demo: correct a recurring error once, then show generalization on a fresh task, followed by a changed rule that invalidates the old memory. Compare against no memory and naive append-only memory.

Metrics: correction retention, transfer success, unrelated-task regressions and stale-memory errors. The important invention is selective retention and revision, not a larger prompt.

### 5. Evolving agent teams — only with a sharp bounded task

One sentence: “This agent team uses its failure history to decide who should do what and which checks are worth the cost.”

Try reconciliation or structured research with verifiable outputs. Evaluate specialist reliability, change routing/checks, and test the new configuration. Compare to a single agent and a fixed team at similar cost. Limit to two or three roles; an animated graph of chatting agents is insufficient evidence.

## Evidence design common to every direction

Separate development examples, validation examples used for promotion, and untouched final tests. Preserve version IDs and random seeds. Include failures, average results and worst cases; record latency and cost alongside quality. Use deterministic checks wherever the task permits. If an LLM scores subjective quality, retain its rubric and avoid relying on the same agent's opinion of itself.

Distinguish actual parameter training from changes to prompts, tools, memory, or orchestration. State exactly what changed and what survived between runs. Choose difficulty where there is real headroom without sabotaging the baseline.

Present four visible objects: task state, the failure, the durable change, and the measured result. Weave's trajectory and version comparisons fit this pattern directly. [Weave evaluation guide](https://docs.wandb.ai/weave/agent-evals).

## Decision and build plan

Use the playbook's technical-first allocation as a starting point: understand the target and constraints early, then spend most effort on the smallest impressive working loop. Do not mechanically reserve one third for research when the event is already underway.

1. Verify rules, sponsor access and demo format; get a representative's reaction to the top two directions.
2. In the first implementation hour, run one baseline task and score it. If that is not possible, simplify the environment.
3. Build one complete improvement cycle before styling the UI. Capture actual artifacts from each step.
4. Before Saturday closing, aim for a repeatable full demo and recorded fallback. Sunday is for held-out evaluation, narrative, rehearsal and submission.
5. Aim to freeze features by Sunday 11:00 and have submission materials ready by 12:00, one hour ahead of the listed deadline. These are internal targets, not organizer rules.

Suggested ownership for a team with enough members: loop/runtime, environment/evaluation, visual experience, and presenter/integration. Combine roles for a smaller team; do not infer team-size eligibility from this allocation.

Practical stack: keep React/TypeScript for a polished visual experience if useful, and use Python for the evaluation loop when it saves time with sponsor examples. Skip authentication, billing, broad settings, and database setup unless the core demonstration requires them. A marimo app alone may be enough for an experiment-led project.

## Suggested demo narrative

“Agents keep making the same class of mistake. Here is ours doing it. Watch what it changes. Now here is a different task, and here is the measured improvement. This is the trace and test that let us trust the change.”

Prepare a 90-second version and a 3-minute version until the actual limit is known. Lead with the visible failure-to-improvement moment. Finish with one honest limitation and the next experiment.

Default choice: direction 1. Choose direction 2 if the team can make the environment visually excellent quickly. Choose direction 3 if the team wants a credible domain application and can make its consequences instantly clear. Avoid combining all three into one oversized project.
