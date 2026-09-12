# Joel / marimo feedback — inspectable live demo

Implement in the existing workbench and custom anywidget, preserving the engineering pipeline.

1. **State ownership:** Python supplies authoritative geometry/results and explicit initial/reset camera commands. Browser owns smooth orbit, pinch/zoom and animation; keep interaction local without uploading the scene or triggering notebook evaluation. Camera and story changes never rerun CAD, simulation or inference.
2. **Custom CAD widget:** extend `PartViewer` with camera presets, target/stock overlays, touch gestures, keyboard controls, and useful initialization. Keep the fixed engineering coordinates unchanged.
3. **Inspectable product:** display the attempt selector; synchronize viewer, check ledger and inspected plan. Show relevant read-only source alongside visual controls and exported artifacts.
4. **Storytelling:** two interactive story views (drawing/constraints and failure/repair), plus full inspection. Use actual run results; story changes and slider interaction remain reactive without new jobs. Two views respect the handbook's at-most-two-slide guidance.
5. **Try it on a phone:** mobile layout, large controls, pinch zoom, a same-product HTTPS link and locally generated QR code. Never encode localhost, session IDs or credentials. No external QR service.

Validation: Python trait/control and QR tests; notebook lint; desktop and 390px browser workflow (attempt switch, paused rotation, camera preset, visibility, story mode, no extra job); remote revision verification. Reuse actual scene/trajectory evidence. Device emulation is distinct from testing a physical phone.

Sources checked: [marimo anywidget](https://docs.marimo.io/api/inputs/anywidget/), [anywidget](https://anywidget.dev/en/getting-started/). marimo supports custom widgets and reactive UI; these changes implement the product-specific state contract.

## Implemented contract

- `silta/viewer.py`: `PartViewer.scene` is authoritative Python data. `camera_command={preset, revision}` is an explicit Python command, including initialization; repeat commands increment revision. `view_mode` selects the target, replay stock, or overlay. Camera operations leave geometry and engineering axes unchanged.
- `silta/static/viewer.js`: orbit, one-finger drag, two-pointer pinch, wheel, arrow keys, R reset, playback speed and scrubbing remain local. No per-frame or per-gesture scene upload. Pause/start is explicit. Disposed widgets release listeners and animation resources. Trajectory/tool/stock geometry is reused until its corresponding segment, tool or keyframe changes.
- `notebooks/workbench.py`: `Inspect`, `Story 1 · The part`, and `Story 2 · The repair` are reactive presentation views. Selecting an attempt changes the CAD replay, evidence ledger, JSON recipe and downloaded package together. The job execution cell has no dependency on story, camera, visibility or attempt controls. Only explicit run controls/settings start a new job.
- Read-only code inspection displays the actual camera command, CAD construction and timing functions, alongside a repository link. It does not expose arbitrary files or environment values.
- `silta/presentation.py`: creates the QR SVG locally with `qrcode`; `SILTA_PUBLIC_URL` overrides the verified public application URL. HTTP, local/private addresses and embedded credentials are rejected; query strings and fragments are stripped. Every visitor creates an independent session. The link opens the live app; it does not share the presenter's job/session.
- Viewer styles are scoped to the CAD container so the notebook's light theme cannot override dark control colors. Phone controls use 44px minimum touch targets, and tables scroll within their own region.

## Demonstration sequence

1. Open the public workbench and let its real run complete. Keep the initial result visible, including failure if no plan passes.
2. Choose **Story 1 · The part**, **Top**, and **Target design**. Rotate the part to show that the drawing-derived design remains fixed.
3. Choose **Story 2 · The repair** and **Overlay**. Select the failed simulation attempt and press **Play** to inspect the collision. Select the passing attempt, when present, and compare its check ledger and recipe. The story explicitly reports runs with no verified plan.
4. Return to **Inspect**. Open the source accordion, inspect JSON and download the selected attempt's artifact package. Operator controls require **Apply and re-run** to change the planning run.
5. Open **Try it on your phone · QR code**. Judges scan the public URL and get their own interactive session.

## Verification recorded 2026-09-12

- Python regression suite: 118 passed at the verification snapshot.
- New Python checks cover camera isolation, rejected presets/modes, public QR URLs, token stripping, QR quiet zone, complete mesh triangles and consistent replay-grid dimensions.
- `node --test tests/viewer_interaction.test.mjs`: paused orbit redraw, pinch direction, pointer cancellation, Z-up presets and disposed handler cleanup passed.
- `marimo check notebooks/workbench.py`, scoped Ruff checks and JavaScript syntax validation passed.
- Chrome desktop: switching stories, camera, layers and selected attempt retained job `job-d246ab5d01af`; failed attempt selection updated the viewer and export links.
- Chrome at 390 × 844: document width was 390px, QR rendered, CAD controls remained readable, keyboard orbit and Play worked. A later real inference run passed and its evidence ledger rendered correctly.
- Physical iOS/Android device scanning and multi-user load capacity remain unmeasured. Touch handling is unit-tested; viewport emulation does not prove every phone/GPU/browser combination.
- Model-generated results can vary. One observed live run reached review after three failures; another passed. Presentation text follows actual outcomes, never a canned success.

Deployment evidence will be recorded below after the new Cloud Run revision is ready.

Live verification completed: the public workbench showed the interactive CAD controls, story selector, memory diagram and GCS-backed memory inspector. Cloud Run traffic was on `silta-00009-7b8` after a concurrent deployment; observed job `job-01fa364c6569` passed fresh simulation. The dedicated three-minute presenter workflow lives in `docs/demo-3min.md` and `notebooks/demo.py`; its local startup command is `make present`.
