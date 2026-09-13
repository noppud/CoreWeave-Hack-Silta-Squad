# Agent starting point

Read [docs/project-context.md](docs/project-context.md) before changing SILTA's loops, demo, metrics, or pitch. It consolidates Joel's design decisions from the development chat and distinguishes product intent, scripted presentation behavior, implemented code, and proposed work.

Then use the source and evidence relevant to the task:

- [README.md](README.md): runtime entry point and commands.
- [docs/implementation-plan.md](docs/implementation-plan.md): current implementation plus chronological checkpoints; later entries may supersede earlier status.
- [docs/aria-loop-review.md](docs/aria-loop-review.md): ARIA collaboration, risks, proposed Weave evaluation work, and the outer architecture-review loop.
- [demo/README.md](demo/README.md): standalone timeline, deck sources, and checks.
- [docs/demo-3min.md](docs/demo-3min.md): separately maintained pitch notes.

Preserve these distinctions:

- Two per-part feedback loops: simulation failures teach checks; the speed judge gives CAM improvement guidance. ARIA's “Loop 4” is a development review, not the runtime judge.
- The 54-part timeline uses scripted data. Real manufacturing claims require matching run evidence and measurement definitions.
- Current shared learning updates directly; Weave evaluation-gated promotion is a proposal, not an implemented default merely because evaluation code exists.
- The current CLI requires drawing artifacts and manufacturing configuration; the demo's text-prompt input is broader product intent.
- Accepted CAD and manufacturing constraints stay fixed during CAM optimization. Test-gate success does not replace simulation.
- Learned instructions/checks persist; this does not update foundation-model weights.

Use the latest explicit user direction when it supersedes these notes. Check the branch and current code before relying on historical summaries, preserve other agents' work, and document new evidence or changed decisions in the relevant project files.
