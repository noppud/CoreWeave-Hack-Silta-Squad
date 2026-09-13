# Judge-facing evidence and rehearsal

The saved participant handbook (`../docs/hackathon.md`) lists Best Loop, creativity, utility, technical execution, and sponsor usage, without numerical weights. The organizer listing was refreshed September 12: https://luma.com/coreweavehacks. It emphasizes self-correction and iterative improvement. The Notion handbook could not be refreshed in this pass; its saved rubric is the basis here.

## The defining interaction

Open http://127.0.0.1:2744/workspace.html. Upload the bundled bearing-pocket PDF, review the exact extracted dimensions, and run. The application freezes the target, measures a fixed reference CAM, asks Astra for a candidate, compiles movements, checks and simulates stock removal, then asks a timing-only judge. Feedback and previous attempts go back to CAM. Memory is committed for the next part. The viewer shows the actual submitted cutting sweeps.

Keep the screen on the software. Explain: “The drawing stays fixed. The agent changes how we manufacture it. Geometry and collisions are gates; machining seconds are the score.”

## Three-minute rehearsal

- 0:00–0:25: Show drawing intake and the reviewed stock/pocket dimensions. State the supported geometry and explicit 3 mm demonstration tolerance.
- 0:25–1:15: Start the job. Show the generated CAM tab while computation runs. Open an already completed job if inference is slow; label it as a completed recorded run, not live progress.
- 1:15–2:15: Show real stock-removal playback, pass/fail and measured reference versus best seconds. Expand “What changed?” only to explain a specific candidate change or failure.
- 2:15–2:40: Show loaded/saved memory and the next part. A saved version is persistence evidence, not proof of generalization. Identical compiled plans stop without another simulation.
- 2:40–3:00: State the useful output and bounds. The simulator exports movements and machined stock; it does not certify physical machining.

## What supports each criterion

| Criterion | Actual evidence | Remaining boundary |
| --- | --- | --- |
| Best Loop | Candidate history, failures, timing decisions, exact-repeat gate, persisted feedback, source manifests | No claimed memory benefit without a controlled comparison |
| Utility | Drawing to reviewed geometry to verified movements and machining estimate | PDF intake supports vertical circular/obround blind pockets only |
| Creativity | CAM optimization with immutable geometry and learned exact-failure checks | No invented teamwork or model-weight training |
| Execution | Live upload, deterministic checks, swept stock removal, downloadable result, replay, restart persistence | Indexed 3+2 core; no simultaneous five-axis physics/controller model |
| Sponsor usage | Programmatic live traces, scored evaluations, hosted sandbox checks and three ARIA review/experiment rounds; see `competition/START_HERE.md` | Native Weave Signals remain unconfigured; do not present Fusion traces as simulator traces |

## Honest comparison

The reference is the fixed `BASELINE` compiler configuration, freshly simulated on this job. It is not an intentionally broken agent attempt. A valid reference can support a percentage machining-time reduction; an invalid reference cannot. The first passing agent candidate versus best is reported separately in manifest loop evidence. Equal times mean zero improvement. No extra cost, wear or surface-finish objective is used.

Do not substitute a polished animation for simulation validity, claim arbitrary engineering PDFs, or describe the coarse verification as production ready. Do not manufacture a failed attempt to illustrate repair. Existing completed studies retain actual failure evidence under `workspace-loop-demo`.
