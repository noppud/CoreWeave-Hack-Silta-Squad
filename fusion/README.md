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
- `simulation`: returns `unknown`, `completed:false`, `needs_ui_verification`. Never synthesizes a pass from toolpath availability or empty issue lists.

## Verification boundary

The installed Fusion `adsk/cam.py` exposes toolpath generation, machining estimates and NC postprocessing. It does not expose a discoverable milling Simulation/Verification result class. The bridge therefore deliberately cannot approve candidates. A separate trusted UI evidence adapter must observe completed verification, covered settings and issues, bind those to the exact candidate/setup, and distinguish internal CAM simulation from posted NC verification. The displayed time is an estimate under caller-provided machine assumptions.

Do not have two agents modify Fusion concurrently. CAD/CAM scripts should be finite and return promptly: a hung script blocks the UI and cannot be safely interrupted by this file protocol. Keep existing documents; no action automatically closes or saves them to the cloud.

## Sources

- [Fusion threading/custom events](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Threading_UM.htm)
- [CAM machining time](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CAM_getMachiningTime.htm)
- [Basic milling and NCProgram sample](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BasicMillingWorkflowSample_Sample.htm)
- Locally inspected Fusion Python API: `Contents/Api/Python/packages/adsk/cam.py`, installed build `4fcc3ec853a7fe76514fe04cc5fd7741e6b2c4ff`.

Transport unit tests do not establish successful operation inside Fusion. Live import/export/CAM/UI verification remains a required integration check.
