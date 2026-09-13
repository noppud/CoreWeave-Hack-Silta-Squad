# Fusion bridge

This is a real Fusion Python add-in, not a standalone emulator. It uses the installed `adsk` APIs. Add `fusion/SiltaBridge` using Fusion **Utilities → Add-ins → Scripts and Add-ins → Add-ins → +**, then Run. Alternatively copy the whole folder into `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/` and select it there. Leave Run on Startup off until the first live check passes.

The default queue is `~/Library/Application Support/Silta/FusionBridge`. `ready.json` confirms add-in startup; it is not a live health check. Call `FusionBridge().request("ping")` to confirm it responds. Both processes may use `SILTA_FUSION_BRIDGE_DIR` if configured before Fusion starts. Requests are atomic JSON files. A watcher fires a custom event; every CAD/CAM operation runs on Fusion's main thread. Responses echo request, candidate and input digests. A timed-out mutation is **not** automatically retried. Inspect `processing/`, `responses/` and `watcher-error.json` before deciding what to recover.

## Actions

- `ping`, `inspect`: document, top-level bodies, CAM operations/tool JSON and NC programs.
- `open_cad`: `path` to STEP or F3D; imports to a new document.
- `export_step`, `export_f3d`: absolute output `path`.
- `run_script`: `source`, optional `arguments`; runs authorized Python with `app`, `adsk`, `payload`, `result`. Set `result` to JSON-serializable data. The script has the user's local permissions; this is not the generated-check sandbox. Never execute untrusted check proposals here.
- `generate_toolpaths`: optional `skip_valid`; returns immediately. Poll `generation_status` across requests until completed. Generation success is not simulation success.
- `machining_time`: required `feed_scale_percent`, `rapid_feed_cm_s`, `tool_change_seconds`; returns explicit seconds and centimeter units.
- `postprocess`: `program_index`, empty unique `output_directory`; uses the NC program's explicitly selected postprocessor. If `completed` is false, poll `collect_outputs` with that directory. Postprocessing is not NC verification.
- `command_inventory`: list installed command IDs/names matching simulation, verification and collision. Discovery only, no undocumented commands executed.
- `simulation_command`: fixed `command_id` (`IronMachineSimulation`, `SimulationIssues`, `SimulationStop`, or `SimulationStockToModel`). Machine simulation requires explicit `setup_ids` and their full machine models. Command execution is not verification completion.
- `simulation_dialog`: raw `Toolkit.cmdDialog` text, active command, document and Fusion version. This command does not exit simulation. Current Fusion exposes statistics here, but its Issues summary/tree require accessibility extraction.
- `simulation`: returns `unknown`, `completed:false`, `needs_ui_verification`. Never synthesizes a pass from toolpath availability or empty issue lists.

## Verification boundary

The installed Fusion `adsk/cam.py` exposes toolpath generation, machining estimates and NC postprocessing. It does not expose a discoverable milling Simulation/Verification result class. The bridge therefore deliberately cannot approve candidates. A separate trusted UI evidence adapter must observe completed verification, covered settings and issues, bind those to the exact candidate/setup, and distinguish internal CAM simulation from posted NC verification. The displayed time is an estimate under caller-provided machine assumptions.

The application's fixed verifier now invokes these commands and uses the Codex
SDK's direct MCP call to read Fusion accessibility text. It does not start a model
turn for routine collection. `Verification: 100%` and the explicit Issues counts
are parsed together; a transport response's `completed` field merely means the
bridge request returned. Completed collisions can reject a candidate. Zero
reported errors cannot approve one without stock comparison and coverage evidence.
`SimulationStockToModel` is a cursor-point measurement, not a whole-part result.

Do not have two agents modify Fusion concurrently. CAD/CAM scripts should be finite and return promptly: a hung script blocks the UI and cannot be safely interrupted by this file protocol. Keep existing documents; no action automatically closes or saves them to the cloud.

## Scripted simulated-stock export

After the fixed runner has completed machine simulation and before it executes
`SimulationStop`, export the current simulated stock with:

```sh
uv run python -m silta.cnc.stock_export \
  --document 'Silta CAM 2-a5bff71375b7' \
  --output /absolute/new-output/finished-stock.stl \
  --evidence /absolute/new-output/export-evidence
```

Use the exact active document name and a new evidence directory/output file.
This is also callable through `silta.cnc.stock_export.StockExporter`. It requires
macOS, Xcode command-line tools (`swiftc`), existing Fusion accessibility/screen
capture access, the running bridge and an unlocked desktop. It brings Fusion to
the foreground. Do not run another Fusion worker or use the mouse during export.

The script closes an observed Issues panel, sets stock Accuracy to maximum and
reads back its numeric value (8), selects End of Toolpath, opens
Stock → Save Stock, saves under a unique local filename, verifies the binary STL,
and copies it to the requested output without overwriting files. It records raw
native accessibility/OCR observations, screenshots, document identity, geometry
and Fusion's displayed stock volume as a diagnostic when available. An unexpected/ambiguous control or
lost foreground access stops the script; an uncertain save is not blindly retried.
The original export is retained in Fusion's selected local save folder.

No model or Astra computer-use turn is involved. The Swift helper lives in
`scripts/fusion/native_ui.swift`. Four live unattended runs produced identical
triangle geometry, including after rewind and after a fresh machine simulation.
See `research/fusion-background-control.md` for the export checkpoint and
`docs/implementation-plan.md` for the completed optimization run.

`FixedFusionVerifier` now invokes this component before stopping simulation and
compares the exported geometry to the frozen STEP with `stock_comparison.py`.
The standalone command still requires an already running simulation. Export
success and volume agreement alone are never a manufacturing pass.

The comparison uses OCCT tessellation, two-way triangle distance bounds and
adaptive subdivision without aligning or editing either geometry. Coplanar patch
unions preserve holes. A failed comparison localizes leftover material or gouging;
a resource limit or malformed mesh returns unknown. It verifies exported internal
CAM simulation geometry, not posted-NC motion or cutting physics.

Live September 12 evidence: maximum-accuracy stock (4,594 triangles) passed the
0.127 mm target comparison twice, most recently in
`.private/fusion-live/stock-comparison-fixed-accuracy-v2/comparison.json`.
Fusion's displayed volume stayed coarse while the export became finer, so that
cross-check is diagnostic. Native AX supplies completion/error counts; OCR is
used only to locate export controls and read the accuracy slider.

## Sources

- [Fusion threading/custom events](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Threading_UM.htm)
- [CAM machining time](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAM_getMachiningTime.htm)
- [Basic milling and NCProgram sample](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BasicMillingWorkflowSample_Sample.htm)
- Locally inspected Fusion Python API: `Contents/Api/Python/packages/adsk/cam.py`, installed build `4fcc3ec853a7fe76514fe04cc5fd7741e6b2c4ff`.

Transport unit tests do not establish successful operation inside Fusion. Live import/export/CAM/UI verification remains a required integration check.
