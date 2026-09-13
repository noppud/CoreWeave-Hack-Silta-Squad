# Control-center demo run

Use `http://127.0.0.1:8768/` on the Fusion worker Mac.

## Learning walkthrough

1. Press **Play loop**. One timeline runs through all 14 archived parts.
2. Start at zero knowledge; failures return the same part to code generation.
3. Simulation failure adds a check. A slow judge result adds a planning memory.
4. The walkthrough ends with **five memories and six checks**. New additions continue through the later parts.
5. Use the tiny ▷ markers to find footage. Hover distinguishes machining footage from a finished-part orbit.
6. Pause or scrub anywhere; accumulated knowledge follows the timeline position.

The walkthrough uses example failure/learning transitions. Its decreasing running machining average reflects the long-to-short ordering of archived parts. **History** retains the actual run chronology and measured evidence separately.

## Uploaded drawing and live Fusion

Use `/Users/touko/Downloads/ribbed-clevis.pdf`.

Presenter opening: “This is a compressed replay of our agent’s real run. We’ll run its final machining simulation live.”

1. **New drawing** → upload `ribbed-clevis.pdf`.
2. Confirm **Replay → live Fusion**, then press **Open run**.
3. Show the drawing, accepted CAD, progressively revealed source, first CAM-generation failure, corrected attempts and verification results.
4. The replay advances automatically through source, checks, and simulation evidence. Recorded machining estimates are 15.73 → 15.49 → 15.15 minutes, a 3.72% reduction on the same clevis.
5. At the final simulation stage, the recorded Fusion machining video starts automatically. After playback completes, the view automatically shows its verification, judge decision, and final result. There are no stage-skipping controls.
6. Keep the live picture visible through cutting and indexing. The sidebar retains the uploaded drawing and target CAD.
7. Hold the completed stock for questions. **Reset** releases the worker and returns to upload.

If the live feed or playback fails, **Video fallback** uses the matching clevis machining recording and explicitly labels it. Reset after the presentation.

Only the exact prepared PDF selects this replay. It binds to saved clevis candidate-0004; no new Astra job is launched behind the replay. Ordinary uploaded PDFs use the separate fresh-generation path. Keep the Fusion desktop unlocked and the native capture running.

## Rehearsal evidence

Browser rehearsal session: `drawing-b4d56e8a3f88`.
Source/job binding and native observer receipts are under `output/live-fusion/demo-sessions/` and `output/live-fusion/demo-observed/`.

Two complete uploaded-PDF browser rehearsals passed:

| Session | Prepare | First motion after cue | Completed final position |
| --- | ---: | ---: | ---: |
| drawing-b4d56e8a3f88 | 5.20 s | 6.75 s | 71.48 s |
| drawing-cd052057116d | 2.81 s | 6.45 s | 74.18 s |

The first native visible cut was bounded between 7.56 and 8.37 seconds after cue by the saved frame sequence. Both runs reached the retained final position, and the finished clevis was visibly inspected. The final presentation camera was restored to 240 mm span after a subsequent zoom change.

Recording fallback was actively playing at 7.18 s of its 69.70 s duration with the recording label. Reset returned to upload and the backend confirmed SimulationStop. Reload/reconnection to the second live session passed without another start/play call. The completed view is held for presentation.

25 Python tests and 17 JavaScript tests passed; lint and browser console checks passed. The main canvas's ordered machining-time chart was corrected to match the downward walkthrough trend. Compact Replay / Live / Recording labels identify the displayed source.
