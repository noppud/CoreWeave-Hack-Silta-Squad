# Actual Fusion playback videos

`silta.cnc.simulation_video` records the live Fusion document window to H.264 MP4 using Apple's ScreenCaptureKit. It does not reconstruct tool motion, render a replacement machine, or turn screenshots into a movie. It uses no model calls. macOS 15+ and existing screen-recording/accessibility access are required.

## Call from the campaign

Open the exact accepted candidate and its machine simulation through the existing Fusion adapter first. Select the required setups and show the machine, tool/holder and stock. Notify the user before beginning the foreground recording interval.

```python
from silta.cnc.simulation_video import SimulationVideo

result = SimulationVideo(
    document=exact_fusion_document_name,
    evidence=part_directory / "video-evidence",  # new directory
).record(part_directory / "machining.mp4", max_seconds=300, fps=60)
```

Equivalent CLI:

```sh
python -m silta.cnc.simulation_video --document '<exact active document name>' --output '<new path>/machining.mp4' --evidence '<new path>/video-evidence' --max-seconds 300 --fps 60
```

Only `record()` operates Fusion. Construction is inert. The native helper compiles locally with `swiftc`; ffmpeg and additional Python packages are unnecessary. The helper records only the matched Fusion window, without desktop audio, microphone audio or other application windows. Rendering is capped at 1920 pixels wide while preserving aspect ratio; 30 and 60 fps are supported.

## Sequence and result

1. Read the exact document and active machine-simulation command through the bridge.
2. Use the existing guarded native UI transport to confirm stopped playback and select **Start of Toolpath**. First calibrate the final operation and tool XYZ through **End of Toolpath**, then rewind and require a near-zero start.
3. Start ScreenCaptureKit and wait for its recording-ready callback before pressing the observed Play control.
4. Record continuous window frames and poll Fusion's actual playback position. Completion requires reaching the calibrated final operation/XYZ and observing stopped playback (Play rather than Pause). Fusion’s Time percentage is per operation and resets between operations; it is never a whole-program completion signal.
5. Pause or confirm stopped playback through observed UI labels. Finalize MP4 and read back its duration, dimensions, frame rate and complete-frame count with AVFoundation.

`result["video"]` is an ordinary `{path, sha256}` artifact suitable for the campaign viewer. Results also include source position readings and UI evidence, `playback_end_observed`, `tool_position_changed`, and the recorder receipt. Add the artifact to the campaign's video collection for that specific candidate/part.

- `recorded`: end observed, changing tool positions, MP4 finalized, and no capture/control errors.
- `partial`: actual video exists, but completion, motion or stop could not be established.
- `unavailable`: no finalized video exists.

A partial clip stays explicitly partial; it cannot silently fulfill the whole-part video requirement. Recording limits are operational backstops, not claimed machining times. The movie is presentation evidence and always returns `verification_pass: false`; use the separately completed verifier result for manufacturing status.

## Live status

The helper compiles and the state-machine tests pass. A real Fusion window capture now passed: 1920 x 1204 H.264, 4.85 seconds, 61 changing frames during controlled camera movement (`.private/five-axis/capture-motion-smoke-v2`). A decoded frame was visually inspected. This proves capture, not machine playback. The live test fixed WindowServer initialization and matching Fusion's unsaved-document/window suffixes. Before treating each machining video as complete, verify:

- ScreenCaptureKit inherits the expected screen-recording permission. Missing permission returns an error without opening a prompt.
- Fusion’s final operation/XYZ must match the calibrated endpoint and playback must have stopped naturally. Numerical per-operation percentages cannot establish this.
- The context menu exposes **Pause** while playing and **Play** once stopped.
- Rewinding visibly restores the initial stock, machine/tool motion is visible, camera framing is useful, and the final part is shown. The module preserves `visual_review_required: true`; numerical playback progress alone does not prove stock appearance.

Keep the shared desktop available during the authorized interval. The existing native transport refuses clicks if Fusion loses foreground access or another application covers the target. The ScreenCaptureKit helper itself never focuses a window or sends input.

API verification came from the installed Apple SDK's `SCRecordingOutput.h` and `SCStream.h`; native playback controls were grounded in existing Fusion UI evidence. No simulator setting or native UI helper was modified to implement video recording.

### Five-axis live recording, September 12

Actual whole-program machine capture passed on the UMC-750 candidate (`.private/five-axis/video-wide-2/result.json`): 53.19 s, 1920×1204, 2,602 delivered frames. The final operation and XYZ matched the calibrated End of Toolpath and Play was enabled. Fusion's per-operation percentage reset between operations, so the recorder was corrected to use this endpoint instead.

The close take exposed a second UI detail: disabled Pause remains visible beside enabled Play. `menu_play_enabled` checks the known light-theme control contrast when both are present; unknown contrast fails closed. The original close receipt stays partial. A repeat is still needed to exercise this latest fix end-to-end. Native window capture and simulation verification are separate results.

The delivered presentation edit is `output/video/silta-five-axis-demo.mp4`. It includes actual machining footage and a labeled final-stock still; see `docs/five-axis-demo.md` for provenance and limits. Optional editing uses `imageio-ffmpeg` through `uv run --with`, without adding it to runtime dependencies.
