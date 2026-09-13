# Capture one verified Fusion candidate

The standalone helper records actual complete machine playback and a close camera orbit of the finished stock. It does not generate CAM, produce a new machining verdict, save the cloud document, or change playback speed. It preserves the simulator's existing Machine/Tool/Stock display settings. The close orbit can include machine context; visually inspect both clips before using them in the film.

First inspect the exact source without touching Fusion:

```sh
.venv/bin/python scripts/demo/capture_verified_candidate.py runs/stage-finned10-r1/manifest.json
```

After the campaign releases Fusion and the presenter has established visible Machine, Tool and Stock in the rehearsed display, run:

```sh
.venv/bin/python scripts/demo/capture_verified_candidate.py runs/stage-finned10-r1/manifest.json --capture --output output/video/finned10-verified-capture --max-seconds 840 --orbit-seconds 16
```

For a second close machining pass, repeat with a new directory and `--framing close`. This uses the known camera API centered on the stock at a 300 mm view height, compared with the default 850 mm wide view. It still records actual complete playback before the finished-stock orbit; there is no synthetic camera or tool motion.

Use a new output directory each time. Replace the manifest with the completed UMC11/UMC12 job when one is available. The helper takes the shared Fusion campaign lock, so it cannot run alongside the campaign. It reopens the exact saved best candidate cloud version, checks its candidate digest, accepted target geometry, assigned machine/fixture and generated toolpaths, then hides only bodies marked as accepted targets. Fixtures are preserved.

`SimulationVideo` observes the recorded playback reaching its known final operation/pose and confirms tool motion. After a complete recording, the existing v6 `StockExporter` must observe finished stock regeneration and save a retained STL before proceeding to the bounded camera orbit, using the same `WindowRecorder`, `presentation_camera` action and stationary-tool check as `record_part_reveal.py`. No unobserved speed-setting control is used. Requested output rate is60fps; actual source frame counts/rate are retained from the recorder, not claimed to be60nativefps.

Outputs in the new directory:

- `machine-playback.mp4`: actual Fusion window recording, including its playback completion evidence under `machine/`.
- `finished-stock-orbit.mp4`: actual close camera orbit of the current final simulation stock; the target CAD bodies remain hidden.
- `finished-stock.stl` and `stock-export/`: regenerated stock plus the v6 readiness/export observations. This is presentation evidence, not a new geometry verdict.
- `capture-receipt.json`: exact source manifest hash, candidate ID/digest, saved cloud reference, verified machining estimate, machine/toolpath binding, display before/hide/restore states, media/evidence hashes, original source-code hashes and all errors.

Cleanup always attempts `SimulationStop`, then restores the exact original target-body visibility. Failed or mismatched restoration makes the whole capture receipt `capture_failed`. Partial machine playback or unconfirmed stock regeneration skips the orbit. The stock gate may take up to its bounded collection timeout after the machine video finishes. The default successful state is `recorded_requires_visual_review`, not a new verified manufacturing pass. The tests use doubles only; a live run of this helper remains required before calling its full orchestration demonstrated.
