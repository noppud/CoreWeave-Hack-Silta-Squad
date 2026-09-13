# Live Fusion connection and recorded parts

The Fusion control center runs locally at `http://127.0.0.1:8768`. The companion gateway serves the same app with an **View part** button, while keeping the original app bound to loopback. Its additional files do not modify the control-center implementation.

Start the control center with its usual command, then launch the gateway from the repository root:

```sh
.venv/bin/python -m silta.cnc.live_gateway --lan-host YOUR_MAC_LAN_IP
```

The gateway compiles the native helper once when its source changes. Open [the part view on this Mac](http://127.0.0.1:8810/live). To pair the full control center on another LAN computer, retrieve the private connection URL from `/live/connection` locally; keep it private. The viewing page itself contains only the part. The link pairs that browser with the same application and live view. The current connection expires four hours after gateway startup. Restart the gateway if the Mac changes networks.

The gateway is a LAN demo connection, not a public internet deployment. The pairing secret is kept under `.private/fusion-live-gateway` with restrictive permissions, passed in the initial link fragment, exchanged for an HttpOnly SameSite cookie, and removed from the browser address. Unpaired clients cannot read the app state, artifacts or live frames or start jobs. Mutating requests require the gateway's same origin and an explicitly supported app route. The gateway forwards them to the fixed loopback app; it never accepts arbitrary shell commands or destination URLs.

## What the live view does

`scripts/fusion/live_window.swift` captures one Autodesk Fusion main window, including when it is behind other windows with ScreenCaptureKit. It sends no mouse/keyboard input and makes no Fusion API calls. It writes atomic JPEG preview frames at up to 20 fps after cropping to the central part canvas. Current output is 670×480. The crop is calibrated to the current window layout and scales by window width; a different panel layout or camera framing needs visual revalidation. No application title, toolbar, trial banner, or bottom controls are included in the current frame. The gateway delivers those frames to the browser, together with window identity and a capture heartbeat. No desktop-wide recording or audio is used.

An unchanged window may produce no new visual frames while the capture heartbeat remains live. Missing, failed or stale capture processes produce an unavailable state; stale JPEGs are not served as current frames. If no main window exists, the helper waits and retries. Keep the Mac awake and the capture processes running. Manufacturing verification still needs the desktop conditions required by the runner.

The live page shows only the current part canvas. Job history and controls remain in the control center. It does not assert that the visible document is the same as whichever historical part is selected in the app. Job progress and verification come from the existing runner, not from visual animation or image interpretation.

The live preview does not create per-run MP4 recordings. Historical per-run recordings already exist, and the native verified-candidate recording workflow remains available separately.

## Recorded parts

`output/live-fusion/media-index.json` records the checked association between each file, its capture receipt, source run and verified candidate. On 2026-09-13, all seven included video hashes matched their receipts and all four candidate digests matched the corresponding best verification:

| Part | Source run | Candidate | Recordings |
| --- | --- | --- | --- |
| Octagonal housing | `demo-umc-umc-08` | `candidate-0004` | Machining and finished-stock orbit |
| Bracket | `demo-umc-umc-09` | `candidate-0004` | Finished-stock orbit |
| Cage | `demo-umc-umc-11-recovery5` | `candidate-0002` | Machining and finished-stock orbit |
| Clevis | `demo-umc-umc-12-recovery1` | `candidate-0004` | Machining and finished-stock orbit |

The control center already exposes these through each part's **Fusion recordings** tab. The complete files remain under `output/video`; the shorter pitch edits are separate assets. Thirteen/fourteen-part cohort counts elsewhere do not imply that every part has a recording.

## Validation

- Seven gateway tests cover pairing, authentication, same-origin writes, bounded forwarding, stale-frame rejection, media ranges and expiry.
- Browser validation through this Mac's LAN address paired successfully, loaded 14 part records with four video-linked parts, decoded and played a retained Fusion video, and displayed a 1440×902 live Fusion frame without JavaScript errors.
- Unpaired LAN requests to the app API returned 401.
- The public HTTPS URL also loaded in a headless mobile browser at portrait and landscape sizes, decoded the cropped image, and rejected app/private routes and a job-start request. A physical phone on cellular is awaiting user confirmation.
- No fresh manufacturing job was launched by gateway validation. It does not establish a complete upload-to-simulation run; that remains the control center runner's workflow.

Run the checks with:

```sh
.venv/bin/python -m pytest tests/test_live_gateway.py tests/test_public_fusion_view.py -q
```

## Public part view

The public visual-only origin runs with `.venv/bin/python -m silta.cnc.public_fusion_view` on loopback port 8811. Only this origin enters the temporary Cloudflare tunnel. The current URL and expiry are in `output/live-fusion/public-connection.json`. The URL works independently of the viewer's network while the Mac remains online and these processes remain running. Restarting the temporary tunnel changes the URL. The session expires four hours after gateway startup.

The public service exposes only the page, whitelisted capture status, the cropped JPEG, and a continuous MJPEG stream. It rejects all write methods, app APIs, artifacts, and pairing routes. It also refuses frames without the viewport-only marker or with a capture/heartbeat older than five seconds. Both viewing pages are text-free during normal operation and display a reconnect notice only if the picture is unavailable. The live picture reflects the current CAD or simulation scene; it does not start machining playback or claim a simulation result.

Do not tunnel ports 8768 or 8810 for this visual-sharing task. The full control center remains private.

## Motion test and streaming

Touko confirmed the public page loaded on his phone and saw a 24-second camera rotation, but reported choppy motion. The public viewer was changed from successive image requests to `/stream.mjpg`, one continuous HTTP multipart JPEG response. Native capture is capped at 20 fps; actual delivered frame rate is measured separately in `output/live-fusion/motion-test/continuous-stream-check.json`. Refresh existing viewer tabs to use this version. The private LAN-only viewer retains image polling.

The bounded test program is `output/live-fusion/motion-test/rotate_part.py`: it rotates the current part for 24 seconds, restores the original camera, and changes no geometry or CAM. This validates visual transport, not cutting or manufacturing verification. A separate cutting test requires opening an existing saved CAM run. Stream tests also check that loss of the viewport-only marker closes the connection.
