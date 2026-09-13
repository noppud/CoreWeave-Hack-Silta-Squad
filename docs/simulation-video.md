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
2. Use the existing guarded native UI transport to confirm stopped playback and select **Start of Toolpath**. Require the dialog's playback position to read near zero.
3. Start ScreenCaptureKit and wait for its recording-ready callback before pressing the observed Play control.
4. Record continuous window frames and poll Fusion's actual playback position. Completion requires observing 100%, rather than merely waiting an estimated machining duration.
5. Pause or confirm stopped playback through observed UI labels. Finalize MP4 and read back its duration, dimensions, frame rate and complete-frame count with AVFoundation.

`result["video"]` is an ordinary `{path, sha256}` artifact suitable for the campaign viewer. Results also include source position readings and UI evidence, `playback_end_observed`, `tool_position_changed`, and the recorder receipt. Add the artifact to the campaign's video collection for that specific candidate/part.

- `recorded`: end observed, changing tool positions, MP4 finalized, and no capture/control errors.
- `partial`: actual video exists, but completion, motion or stop could not be established.
- `unavailable`: no finalized video exists.

A partial clip stays explicitly partial; it cannot silently fulfill the whole-part video requirement. Recording limits are operational backstops, not claimed machining times. The movie is presentation evidence and always returns `verification_pass: false`; use the separately completed verifier result for manufacturing status.

## First live test still required

The helper compiles against the installed macOS 26 SDK and the state-machine tests pass. No foreground capture was performed during implementation. Before treating each part's video as complete, verify:

- ScreenCaptureKit inherits the expected screen-recording permission. Missing permission returns an error without opening a prompt.
- Fusion's **Time** percentage updates while playing. Earlier stock-export evidence sometimes showed a stale 0% after jumping to the end, so the recorder intentionally refuses to infer completion from that action.
- The context menu exposes **Pause** while playing and **Play** once stopped.
- Rewinding visibly restores the initial stock, machine/tool motion is visible, camera framing is useful, and the final part is shown. The module preserves `visual_review_required: true`; numerical playback progress alone does not prove stock appearance.

Keep the shared desktop available during the authorized interval. The existing native transport refuses clicks if Fusion loses foreground access or another application covers the target. The ScreenCaptureKit helper itself never focuses a window or sends input.

API verification came from the installed Apple SDK's `SCRecordingOutput.h` and `SCStream.h`; native playback controls were grounded in existing Fusion UI evidence. No simulator setting or native UI helper was modified to implement video recording.
