# SILTA control center

A local application backed by Fusion job manifests, emitted source, original PDFs,
retained CAD/stock meshes, capture receipts, and shared learning files.

Run from the repository root:

```sh
.venv/bin/python -m silta.cnc.control_center --port 8768
```

Open `http://127.0.0.1:8768`. Use `--review-only` to disable job starts.
Poppler (`pdfinfo`, `pdftoppm`) renders original PDF pages. The 3D viewer uses the
installed Three.js package under `cnc_simulator/viewer/node_modules`.

The default screen is a spatial loop matching the whiteboard: CAD/CAM at upper
left, checks below it, Fusion to the right, and the judge returning feedback.
Planning memories are part of the agent. Input PDF and retained output flank the
loop. Each stage opens only its own content: Simulation opens its matched machining
recording (or the live feed for the active local job); Checks opens a list of
actual Python check sources; CAD/CAM opens the saved planning memories; Output
and completed part cards open only the final simulated-stock model; Input opens
the PDF; Judge opens its decisions. There is no shared inspector or media tab bar. Parts, history, and
learnings open as overlays, without navigating away.

The central evidence panel compares the original PDF and rotatable simulated
stock, plays matched historical footage, or shows the saved six-case check eval
(0/2 invalid cases caught by baseline, 2/2 by learned checks, 4/4 valid accepted).
These are retained-case results, not a new or held-out evaluation.

**Play loop** starts one continuous walkthrough across all 14 retained parts.
The presentation orders parts by descending archived machining estimate.
It starts with zero learned checks and memories, and accumulates six checks and five memories.
Additions continue into the final parts. Tiny play markers identify parts with
footage, with a tooltip distinguishing machining from a finished-part orbit. Failed checks return to code;
failed simulation adds a check before new code; a slow judge decision adds a
planning memory before a faster-plan attempt. Every retry keeps the same CAD.
Checks and memories carry into subsequent parts. The single scrubber, previous /
next step controls, and numbered part boundaries span the entire sequence.

The walkthrough uses example outcomes with real archived drawings, code,
recordings and saved guidance, plus four display-only Python check examples
and two planning-memory examples. Example checks are labelled when opened
and are never installed into the worker. It never executes a job or writes
learning files. The downward running-average trend reflects the selected part
order; it is not a measured causal improvement from learning.
Its first-pass chart is labelled as walkthrough outcomes; machining estimates
come from archived parts. **History** remains the actual recorded event log and
supports continuous recorded replay with candidate-matched source and footage.
Both views expose the accumulated learning graphs on the main canvas.

- **Drawing:** original PDF, page controls and source download.
- **Astra:** emitted CAD/CAM Python and selected posted NC, when available.
- **Checks:** retained learned rules, their actual Python, scope, originating
  failure and observed cross-part reuse. Baseline checks are not labelled learned.
- **Fusion:** rotate accepted CAD and verified finished-stock meshes; play
  candidate-associated recordings; inspect the current live Fusion window.
- **Judge:** recorded decisions and source evidence.
- **Memory:** the current shared planning paragraphs, with full text and saved
  change history available on click.

## Live execution

Uploading alone only stores the PDF. Start launches the existing Astra CNC CLI
with a new job ID, at most three CAM attempts, and a private copy of shared
learning for the run. Exact known PDFs receive their matching setup. New PDFs
use `config/control-center-umc-profile.json`: a fixed UMC750 shop, tooling, stock,
fixture, material and verification context. The agent must report missing critical
dimensions and setup conflicts. This does not claim unrestricted manufacturability
of every PDF. Credentials enter only the child process through hsec.

Job status, source files and events refresh every five seconds. New intake jobs
appear in the part library once their actual manifest exists. Upload, mocked
launch behavior and artifact/UI paths were checked; no fresh full machining run
was launched solely to validate this UI.

The companion `silta.cnc.live_gateway` task provides paired LAN access and a
read-only Fusion window capture. When that capture has a fresh heartbeat and
frame, Live Fusion copies only the JPEG into a registered display artifact and
refreshes at up to four frames per second. Otherwise it reports the capture unavailable. It never calls the bridge to
take a fallback image: a bridge script can exit active machining simulation. The live window may differ from the
selected historical job and is labelled accordingly. It is not a verification
verdict. See `docs/live-fusion-connection.md` for the separate-computer setup.

The server binds to loopback and rejects cross-origin mutations. Only registered
artifacts are served; private directories, credentials and raw worker logs are
excluded. Keep the server running during an active job; process ownership is local
to that server process.

## Evidence and integrations

The present gallery contains 14 retained parts, including seven verified-source
recordings attached to four parts. The 27-part pitch animation is illustrative
and is not imported as completed-job evidence.

W&B's documented HTML embed is for Reports. No supported native embed was found
for the existing Weave eval view, so the requested optional eval dashboard is
omitted. The canvas uses the existing local saved check-eval artifact, with its
six cases inspectable. Per-job Weave trace links remain in job details. No evals are republished
or modified by this application.

## Validation

```sh
.venv/bin/pytest -q tests/test_control_center.py tests/test_cnc_view.py
.venv/bin/ruff check silta/cnc/control_center.py tests/test_control_center.py
node --check applications/control-center/app.js
node --check applications/control-center/model.js
node --test tests/test_control_center_*.mjs
```

### Learning and recorded playback

The walkthrough and recorded replay share one continuous timeline. Part changes
never reset its scrubber. Seeking reconstructs the learning available at that
position, including when moving backward. In walkthrough mode, stage inspectors
and Learnings show only the checks and memories accumulated so far.

Recorded replay preserves actual failures, repairs and optimization decisions.
A run memory is an instruction passed to the next CAM attempt; it is distinct
from a shared prompt saved across runs. Historical runs without a saved check
do not invent one. Recorded charts compare first and best verified machining
estimates on matched parts and retain the saved six-case check evaluation.

Live PDF coordination is documented in
`output/live-fusion/ui-integration-contract.md`. A fresh upload does not yet
invoke automatic framed simulation playback. Uploaded jobs currently copy root
learning into separate run directories; learning is not automatically promoted
between independent live uploads. The walkthrough's accumulation does not
change this backend behavior.

### ARIA panel

Ask ARIA opens a contextual side panel. It shows the retained ARIA project review, actual check-eval counts, implementation follow-through, and expandable original response. Suggested questions can be edited. Copy question + open ARIA copies a prompt with the selected recorded run, trace URL, timing summary, recent events, eval versions, and saved learning references, then opens W&B. The user pastes and sends there. No model call or job launch occurs in the local UI, and no live embedded-chat capability is implied. A prepared-text fallback is available if clipboard access is denied.

`aria.mjs` constructs context from explicit recorded fields. No code files, arbitrary summary fields, or demo state enter the context. W&B's current frame restrictions require the external chat handoff.

## Prepared PDF demo

The exact `silta-clevis-demo.pdf` opens a separate **Replay** flow.
`staged-replay.mjs` builds the sequence from archived clevis events and source.
It preserves the first generation failure, repaired attempts and measured
verification results; it invents no saved check or memory for this run.
The overlay shows the uploaded PDF, progressively revealed saved source, accepted CAD and estimates.
The simulation stage automatically calls the reserved demo playback
endpoint once Fusion is ready; the picture receives a live label only with playback state and a
fresh native frame. Recorded fallback has its own label. Unknown PDFs retain
the ordinary fresh-generation path. Backend matching/preparation/playback and
rehearsal receipts are owned by the companion live-Fusion task.

Two full uploaded-PDF rehearsals, fallback, Reset, and reload reconnection passed. See `docs/control-center-rehearsal.md` for measured timings and the presenter sequence. The main canvas time chart uses descending part estimates; recorded History remains chronological.

The upload replay holds code for 22 seconds and simulation results and judge decisions for 14 seconds. Stages follow drawing → CAD/CAM → checks → simulation → judge → output. The final candidate waits for a recorded Fusion machining video presented as the active simulation before its recorded verification and judge result. Video completion advances automatically. The upload run has no Next, Previous, Pause, or manual simulation cue; historical timelines retain their navigation controls.
