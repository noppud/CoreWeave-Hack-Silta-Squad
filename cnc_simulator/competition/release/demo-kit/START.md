# SILTA demo kit

Start with [the 116-second film](film.mp4). It is a silent edited recording with selectable English captions; [narration](film-narration.md) is included. The longer [complex machining reel](complex-machining.mp4) shows three actual movement-driven stock-removal replays. Neither video is live execution.

## Evidence to explain

| Claim | Supporting artifact | Boundary |
| --- | --- | --- |
| Three complex parts improve over fixed references | [Raw results](evidence/complex-results.json) | Constant-speed estimates; 1 mm cells / 3 mm tolerance |
| Timing feedback can yield a better next proposal | [Iteration audit](evidence/complex-iterations.json) | Carrier improves; manifold ties; drum gets slower and retains earlier best |
| Memory reaches later requests | [Persistence audit](evidence/memory-persistence.md) | Persistence is not causal speed improvement |
| Transfer was actually measured | [Repeated parts](evidence/repeated-memory-study.md), [new geometries](evidence/new-geometry-study.md) | No useful general memory-speed benefit established |
| ARIA advice was tested | [ARIA follow-up](evidence/aria-followup.txt), [12-case results](evidence/aria-ablation.json) | Advisory, not simulation authority |
| Hosted sandbox executes exact-failure checks | [Hosted receipt](evidence/hosted-checks.json) | This is check execution, not full stock simulation in the sandbox |
| Weave scores the three complex outcomes | [Completed evaluation links](evidence/complex-weave.json) | Network/account access required to inspect hosted records |

See [judge questions](judge-questions.md) for evidence-specific answers and [organizer refresh](organizer-refresh.md) for the latest public schedule. Source paths in the Q&A refer to the original workspace; the evidence table above provides portable copies.

## Live sequence

1. Start a fresh PDF job after reviewing its extracted dimensions.
2. While it runs, explain the fixed-target loop and show measured results.
3. Return to the actual generated CAM, checks, stock simulation, timing and saved memory. If still running, say so; use a labeled completed replay as fallback.
4. Explain that failed geometry never earns a qualifying time score. Show the actual carrier improvement and retained slower drum trial.

On the original demo computer, use `http://127.0.0.1:2744/workspace.html`. Run the included `source/live_terminal.py JOB_ID` using Python to observe its actual events. This read-only monitor does not approve a drawing or start/restart a job. `--port` can select another local server.

For a new computer, follow [source installation and complex-part commands](source/README.md). Account/model access is required for fresh Astra proposals. The source archive does not contain existing run history. The recorded results started with memory version 14; a fresh unseeded run starts at 0 and may differ.

## Scope

Indexed 3+2, flat-end mills. No simultaneous-five-axis, controller, cutting-force or production-certification claim. Native Weave Signals are not configured. Hosted checks and ARIA/Weave records are distinct from the geometric simulator. Some raw evidence retains original machine-local artifact paths for provenance; these are not portable links or bundled full run directories. This kit is local and has not been submitted or publicly hosted.
