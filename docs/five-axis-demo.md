# Single-tool indexed five-axis demo

Target: `output/pdf/umc-actuator-housing.pdf` (DEMO-5X-001 Rev A). An 80 mm aluminum housing has a stepped top recess, four top bolt recesses and rounded side pockets with central bosses on all four sides. Exterior stock faces remain unchanged. One T1 12.7 mm flat end mill cuts every feature.

Machine: Autodesk's simulation-ready Haas UMC-750 Reboot. Indexed 3+2 machining rotates B/C between cutting orientations; this is not a claim of simultaneous five-axis cutting. The imported definition retains its B range of -35 to +110 degrees. Fusion read back `hasSimulationModel=True` for `user://Silta UMC750 demo.mch`.

Fixture: project-authored bolted pedestal envelope, supplied as an actual Fusion solid archive. Its base sits on the table attachment plane; G54 stock top is 230 mm above it. Underside blank attachment and rigid mounting are stated simulation assumptions. This fixture is not a load-certified commercial setup.

Runtime and loop are unchanged: Astra fast/low through the SDK; fixed CAD, learned checks, actual machine simulation plus finished-stock comparison, then the judge. Existing vise-specific three-axis checks deliberately do not claim coverage for this rotary setup. Any newly learned checks must state their applicable coordinates and scope.

Recording: ScreenCaptureKit captures only the Fusion window at up to 1920 pixels wide / 60 fps. Actual playback progress and movement are recorded separately from the verification verdict. Plan three views: machine-wide rotary motion, close cutting/stock removal, finished-part reveal. Final CAD beauty views must not be substituted for finished-stock verification.

Verified candidate: `runs/umc-actuator-v5/attempt-0001`. Actual Fusion machine verification completed with zero errors, zero warnings and zero process errors. Exported finished stock passed bidirectional comparison with the fixed CAD at 0.127 mm tolerance. Estimated machining time is 836.778 seconds. One T1 cuts all seven operations. The posted NC indexes B90 with C0/90/180/270 and returns B0/C0.

The successful setup uses `config/umc-actuator-tall-job.json` and `config/umc-tall-pedestal-g54.f3d`: 160 mm pedestal under the 70 mm blank. The earlier 60 mm pedestal produced genuine table/head collisions. An initially reversed circular-pocket boundary also failed finished-stock comparison before repair. These failures were retained, not excused. Initial five-axis integration involved developer repairs to the CAM/API source; this is not a claim of an untouched autonomous first attempt. The supervisor received the verified candidate and proposed a faster path. Further optimization was deliberately deferred to filming; a best verified candidate exists, while that one-attempt job stopped at its operational limit.

Weave trace: https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098f1-4c18-772a-9f80-bddd53c00164

The earlier four-part evidence in `docs/learning-results.md` remains the proof of learning across parts. This new candidate proves the indexed five-axis simulation integration.

Sources: [Autodesk machine library](https://cam.autodesk.com/machineslist), [Fusion tool orientation](https://help.autodesk.com/cloudhelp/ENU/Fusion-CAM/files/MFG-TOOL-ORIENTATION-OVERVIEW.htm), [Haas UMC-750](https://www.haascnc.com/machines/vertical-mills/universal-machine/models/umc-750.html).

## Demo video delivered

`output/video/silta-five-axis-demo.mp4` is a 56-second 1920×1080 H.264 presentation cut: actual UMC machine playback, close-up stock removal, and a labeled still of the finished simulated stock. The edit is reproducible with `uv run --with imageio-ffmpeg python scripts/demo/edit_fusion_video.py`. It does not synthesize machining frames. Output is encoded at 60 fps; captured frame delivery is variable.

Raw wide footage: `output/video/umc750-machine-playback.mp4`, 53.19 seconds, 2,602 delivered frames. Recorder confirmed final operation/tool position, naturally stopped playback, and changing tool positions. Evidence: `.private/five-axis/video-wide-2/result.json`.

Raw close footage: `output/video/umc750-stock-removal.mp4`. The first 47 seconds contain the selected real cutting footage. Its recorder receipt remains **partial** because a dim disabled Pause label confused the old completion detector; the timeout tail and menus are excluded from the edit. The fix was checked against the captured UI and regression tests, but a clean repeat was blocked when Fusion moved off the visible desktop. This does not change the separately passed manufacturing verification.

A final orbit recorder exists at `scripts/fusion/record_part_reveal.py` but has not yet been run on this finished part. The presentation uses an explicitly labeled finished-stock still instead. Initial/middle/final encoded video frames were decoded and visually inspected.
