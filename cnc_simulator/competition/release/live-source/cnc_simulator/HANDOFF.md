# Source and live-viewer handoff

`simulator-source.tar.gz` contains the engine, CAM code, example geometry, tests, live viewer, local Three.js modules, and downloaded UMC-750 geometry with provenance. It contains no recorded job history, credentials, or virtual environment. `source-manifest.json` lists every file hash. This archive is local; it has not been published to GitHub.

Extract into a new directory. From the extracted `cnc_simulator` folder:

```sh
uv venv --python 3.12
uv pip install -e '.[test,report,agent,live]'
.venv/bin/python -m cncsim examples/pocket.json --output output-pocket
.venv/bin/python -m pytest tests --ignore=tests/test_machine_assets.py -q
.venv/bin/python -m camloop.live --port 2745
```

Open http://127.0.0.1:2745/workspace.html. Installation must be editable (`-e`) for the live service to resolve its adjacent viewer assets. The deterministic simulator does not require an account or a model. PDF extraction and CAM generation require the existing authorized Codex/ChatGPT account and Astra access; no credentials are bundled. Weave tracing is optional and needs separate scoped credentials.

The fresh viewer starts with no jobs and memory version 0. Use Try example, review the extracted dimensions, and run it. This is a new run, not replay of the retained benchmark. The model may take time or reject an input. Port 2745 avoids disrupting the existing main demo at 2744.

The excluded `test_machine_assets.py` tests provenance of the older VF2/Fusion reference assets, including files outside this standalone folder. It is not part of the UMC programmatic engine. Those four tests passed in the complete original workspace; the remaining suite is tested here. Do not silently skip them in a full repository checkout.

This handoff does not contain the recorded study, competition film, or the existing live job/memory history. Those remain separately under the main workspace's `competition/` and `workspace-*` folders. It is not a production machining system: indexed 3+2, flat-end mills, coarse demo geometry, constant-speed timing.
