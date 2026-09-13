# Source and live-viewer handoff

`simulator-source.tar.gz` contains the engine, CAM code, example geometry, tests, live viewer, local Three.js modules, and downloaded UMC-750 geometry with provenance. It contains no recorded job history, credentials, or virtual environment. `source-manifest.json` lists every file hash. This archive is local; it has not been published to GitHub.

Extract into a new directory. From the extracted `cnc_simulator` folder:

```sh
uv venv --python 3.12
uv pip install -e '.[test,report,agent,live]'
.venv/bin/python -m cncsim examples/pocket.json --output output-pocket
.venv/bin/python -m pytest tests -q
.venv/bin/python -m camloop.live --port 2745
```

Open http://127.0.0.1:2745/workspace.html. Installation must be editable (`-e`) for the live service to resolve its adjacent viewer assets. The deterministic simulator does not require an account or a model. PDF extraction and CAM generation require the existing authorized Codex/ChatGPT account and Astra access; no credentials are bundled. Weave tracing is optional and needs separate scoped credentials.

The fresh viewer starts with no jobs and memory version 0. Use Try example, review the extracted dimensions, and run it. This is a new run, not replay of the retained benchmark. The model may take time or reject an input. Port 2745 avoids disrupting the existing main demo at 2744.

The legacy `test_machine_assets.py` is intentionally not included in this archive. It tests provenance of the older VF2/Fusion reference assets, including files outside this standalone folder. It is not part of the UMC programmatic engine. Those four tests passed in the complete original workspace; the remaining suite is tested here. The original full-workspace test module remains unchanged.

This handoff does not contain the recorded study, competition film, or the existing live job/memory history. Those remain separately under the main workspace's `competition/` and `workspace-*` folders. It is not a production machining system: indexed 3+2, flat-end mills, coarse demo geometry, constant-speed timing.

## Reproduce the complex-part run

From the extracted `cnc_simulator` directory, with the editable install above:

```sh
.venv/bin/python competition/run_complex_parts.py --workspace workspace-complex-fresh
.venv/bin/python scripts/serve_indexed.py --workspace workspace-complex-fresh --port 2746
```

Open http://127.0.0.1:2746/study.html. The command freezes three complex targets, simulates a fixed reference and two Astra revisions per part, saves all verdicts, commits sequential memory, and exports actual swept-stock playback. It refuses to overwrite an existing workspace. Fresh runs start at memory version 0; use `--memory-seed /absolute/path/memory.json` only to deliberately seed prior history. Original recorded results began at version 14 and are not promised for a fresh run. This is a complexity test, not a controlled memory-benefit evaluation. Model access is required; CAD generation alone can be checked with `--prepare-only` in a separate new workspace.

The study page can record browser replay videos. After capture, encode and verify them with:

```sh
.venv/bin/python scripts/encode_indexed_videos.py workspace-complex-fresh --reel-name three-complex-parts.mp4
```

The encoder waits for browser captures; it does not generate simulated motion independently. Complex trials may take several minutes per part.

For raw live events, run `.venv/bin/python competition/live_terminal.py JOB_ID --port 2745` alongside the browser. Use the actual job id from the URL. The observer retries transient reads, never restarts jobs, and explicitly reports unverified observation if the connection remains unavailable.
