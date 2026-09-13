# Live Fusion connection and recorded parts

The Fusion control center runs locally at `http://127.0.0.1:8768`. The companion gateway serves the same app with an **Open live Fusion** button, while keeping the original app bound to loopback. Its additional files do not modify the control-center implementation.

Start the control center with its usual command, then launch the gateway from the repository root:

```sh
.venv/bin/python -m silta.cnc.live_gateway --lan-host YOUR_MAC_LAN_IP
```

The gateway compiles the native helper once when its source changes. Open [Live Fusion on this Mac](http://127.0.0.1:8810/live), select **Show connection link**, and copy that private link into a browser on another computer connected to the same network. The link pairs that browser with the same application and live view. The current connection expires four hours after gateway startup. Restart the gateway if the Mac changes networks.

The gateway is a LAN demo connection, not a public internet deployment. The pairing secret is kept under `.private/fusion-live-gateway` with restrictive permissions, passed in the initial link fragment, exchanged for an HttpOnly SameSite cookie, and removed from the browser address. Unpaired clients cannot read the app state, artifacts or live frames or start jobs. Mutating requests require the gateway's same origin and an explicitly supported app route. The gateway forwards them to the fixed loopback app; it never accepts arbitrary shell commands or destination URLs.

## What the live view does

`scripts/fusion/live_window.swift` captures one visible Autodesk Fusion main window with ScreenCaptureKit. It sends no mouse/keyboard input and makes no Fusion API calls. It writes atomic JPEG preview frames at up to 8 fps with a maximum width of 1440 pixels. The gateway delivers those frames to the browser, together with window identity and a capture heartbeat. No desktop-wide recording or audio is used.

An unchanged window may produce no new visual frames while the capture heartbeat remains live. Missing, failed or stale capture processes produce an unavailable state; stale JPEGs are not served as current frames. If no visible main window exists, the helper waits and retries. Fusion must be visible for capture startup, and our existing verification still needs its unlocked foreground desktop.

The live page shows the actual current Fusion window and the control center's active job ID separately. It does not assert that the visible document is the same as whichever historical part is selected in the app. Job progress and verification come from the existing runner, not from visual animation or image interpretation.

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
- The test client was another browser context on this same Mac using its LAN interface. A second physical device and any different-network route remain untested.
- No fresh manufacturing job was launched by gateway validation. It does not establish a complete upload-to-simulation run; that remains the control center runner's workflow.

Run the checks with:

```sh
.venv/bin/python -m pytest tests/test_live_gateway.py -q
```
