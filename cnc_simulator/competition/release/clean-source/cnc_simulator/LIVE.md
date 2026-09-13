# Live machining workspace

Open http://127.0.0.1:2744/workspace.html. This is a separate software view, with no slideshow or scripted execution.

```sh
uv pip install -e '.[test,report,agent,live]'
.venv/bin/python -m camloop.live
```

Upload a PDF, inspect Astra's extracted dimensions and source quotes, then confirm the dimensions and explicitly select the 3 mm geometry demo. The job generates frozen CAD, calls Astra for CAM, compiles actual movements, runs fixed and saved checks, simulates removal, exports candidate stock playback, and calls the timing-only judge. Up to three CAM candidates run. Each candidate's output, issues and timing judgment appear in the job. Feedback persists across jobs in `workspace-live/memory.json`; the initial memory is copied from the completed five-part study.

PDF support is deliberately bounded: text-based, dimensioned drawings; pre-sized box/cylinder stock; vertical blind circular or obround pockets. No scanned drawing interpretation, islands, side features, outer profiles, threads or inferred missing dimensions. Unsupported drawings stop at intake. Stock is centered in X/Y, bottom Z=0; extracted coordinates are reviewed before use. The uploaded file is preserved. This is not arbitrary-PDF engineering reconstruction.

The fixed simulation uses 1 mm cells and 3 mm tolerance, even if a drawing specifies tighter tolerance. The review button explicitly accepts that coarse demo and the interface shows the drawing tolerance separately. The result does not certify the tighter tolerance or physical manufacturing feasibility.

The browser polls persisted job state once per second. Actual generated movements appear in an XY projection; simulation reports computed movement counts and tool positions. After each computation completes, the corresponding actual cutter-sweep stock replay is loaded. Animated playback is accelerated, not wall-clock streaming of each geometry-kernel operation. Refreshing or switching jobs does not restart model calls. Only the explicit confirmation button starts CAM.

The local service binds 127.0.0.1:2744, requires same-origin mutations, limits PDFs to 12 MB / 10 pages, rejects duplicate run submissions, and serializes machining jobs to protect shared memory. All application model calls request Astra fast/low. No model call is inside the simulator.

## Tests

`workspace-live/integration-test.json` records real HTTP/PDF/model/simulation test results for two distinct PDFs, unsupported geometry, non-PDF input and duplicate starts. `scripts/test_live_api.py` reproduces that sequence alongside the first browser-driven bearing-pocket run. `tests/test_live.py` covers bounded spec validation. Full suite output is in `workspace-live/tests.log`.

## Loop evidence

New jobs now simulate the fixed reference CAM before Astra planning, provide the full measured attempt history to CAM, and stop identical compiled toolpaths before redundant simulation. The main view keeps a compact reference/best comparison and candidate strip; detailed reasoning remains collapsed. `manifest.loop_evidence` separates baseline savings from within-run savings and explicitly does not infer a causal memory benefit. See `JUDGING.md` for the source-bounded three-minute rehearsal and remaining sponsor-integration gap.
