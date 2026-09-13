# Silta: a raw Fusion demo in under three minutes

Show actual machining, three concrete parts, one learned check and one reused planning lesson. Then expose the running loop. The film is a separate 114-second submission asset; do not play the whole film inside this talk.

## Spoken script · approximately 2:45

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:18 | Start the retained-plan recheck. Show the film's first eight seconds, then return to Fusion. | “We prepared this drawing's CAD and CAM before the talk. I’m starting its real Fusion verification now. Here is recorded machining from an earlier completed job: a Haas UMC-750, one cutter, indexed three-plus-two—not simultaneous five-axis.” |
| 0:18–0:38 | CAD previews: UMC08 octagon, UMC09 fork, UMC05 manifold. | “These are three actual generated targets: an octagonal housing, a forked bracket, and a service manifold. Each has a completed, verified CAM plan. These images are CAD previews; the film ends with actual simulated stock from the cage and clevis.” |
| 0:38–1:03 | Slide 1; point through the loop once. | “Astra keeps the CAD target fixed and revises the machining plan. Cheap checks catch known mistakes. Fusion verifies the motion and finished stock. Failures return for repair and can teach a new check. Only a pass reaches the supervisor, which decides whether another improvement is worth trying.” |
| 1:03–1:28 | Slide 2: B → C. Then the indexed learning evidence at film 80–88 seconds, or its static frame. | “In our earlier three-axis experiment, a simulation failure became a check that caught the repeated mistake on another part in 51 milliseconds. For indexed machining, the transferred lesson was planning guidance: reduce air-ramp clearance when stock clearance allows it. Verified estimates improved about six percent on one fixed part, then three percent on the octagon.” |
| 1:28–1:48 | Corrected learned Weave evaluation; show its six cases. | “Weave compares the original and learned checks on six retained cases. The learned checks catch both failures; the original catches neither. Both accept all four valid plans. The code, case outcomes and timings are inspectable. This is historical replay, not an unseen-parts benchmark.” |
| 1:48–2:30 | Live terminal: actual stage, candidate source, checks, prompt versions; Fusion when it runs. | “This is the autonomous SDK run. Here are its CAM code, checks and planning guidance. Routine Fusion setup and result collection are deterministic. The model makes machining decisions. The terminal reports the actual stage. When verification finishes, the supervisor receives machining time and feedback, then improves the plan or returns its best verified candidate.” |
| 2:30–2:45 | Actual current result; if pending, use the explicit fallback below. | “The output is CAD, CAM, posted NC and verification evidence—and guidance the next job can reuse. We improve the process while keeping the requested part fixed.” |

If verification is still running, say: **“This run is still at [observed stage]. Here is the recorded verified example.”** Show film 104–114 seconds, clearly labeled recorded. Do not promise the live result within the speech. A collection failure stays a failure; an orbit is camera motion, not a new machining test.

## Before the audience arrives

Use two screens: Fusion stays visible on the compute screen, owned by one worker; the presentation screen holds the film, selected CAD images, two slides and authenticated Weave tabs. Use large raw-terminal/editor text. No website tour or sign-in onstage.

The preferred live input is **UMC08, the octagonal part**, resumed from the completed
`stage-octagon08-r1-recovery1` run using the retained-live command below. All four
fresh verifications passed and all four playbacks showed tool motion, successful
SimulationStop and target restoration without cleanup errors. The supervisor stopped
and retained candidate5 at1515.202754s after candidate6 provided no improvement.
The same fixed CAD improved6.144% from original r1 candidate1 at1614.396515s.

Original `stage-octagon08-r1` hit its attempt cap and had a playback cleanup failure
requiring operator intervention. Those receipts remain separate; the later recovery's
clean playback does not rewrite that history. Both learning files stayed unchanged.
See [completed rehearsal evidence](reviews/live-rehearsal.md).

The earlier finned rehearsal `stage-finned10-r1` remains completed: three verified
candidates and observed motion in three playbacks,344.902176→338.612911 seconds
(1.82%). The fresh finned r2 and two recoveries remain incomplete because stock
completion was not observed after the CAM repair. See the
[collection diagnostic](reviews/finned-rehearsal-collection.md). UMC07 is an unrun
alternative, not a rehearsed fallback.

Use the retained-live command below after Fusion is idle. This avoids fresh CAD/CAM
preparation during the speech and copies learning into a new shadow directory.
The terminal viewer is read-only and must name the exact new job ID.

For campaign history rather than the staged job:

```sh
.venv/bin/python scripts/demo/live_terminal.py --campaign runs/demo-campaign.json
.venv/bin/python scripts/demo/verify_demo.py
```

Current snapshot: all nine indexed campaign rows completed; four historical drawings bring that report to 13 completed drawings. The separate finned rehearsal makes 14 completed gallery previews. Recheck the report before speaking; retries are not parts.

## Assets and evidence

- [114-second film](../output/presentation/silta-loop-demo.mp4) and [film evidence](../output/presentation/film-evidence.json). Actual UMC08 machine footage; final five seconds each of UMC11 cage and UMC12 clevis stock orbits. Historical A/B/C graphics are separate experiments. [UMC08 capture receipt](../output/presentation/film-umc08-source-receipt.json), [Cage capture receipt](../output/video/umc11-close-capture-r3/capture-receipt-portable.json), [clevis capture receipt](../output/video/umc12-close-capture/capture-receipt-portable-v2.json). The cage capture was automatic; the clevis take retains its operator-assisted rewind.
- [Octagon CAD](../output/presentation/part-gallery.umc-08.png), [fork CAD](../output/presentation/part-gallery.umc-09.png), [manifold CAD](../output/presentation/part-gallery.umc-05.png), [full gallery](../output/presentation/part-gallery.png) and [source hashes/status snapshot](../output/presentation/part-gallery.json). UMC05 is a service-manifold variant in the indexed housing family; the gallery label currently reads “Indexed housing 05.” These are exact retained STEP renders, not stock photographs.
- [Two offline slides](../output/presentation/slides.html). Slide 2's additional 45.2% metric is the historical fixed-part A experiment, 384.860379 → 211.037438 seconds. It is not the octagon's improvement or a controlled prompt-policy test.
- [Indexed lesson graphic](../output/presentation/film-indexed-learning.png), [transfer report](../output/evaluation/learning-transfer.json): UMC03 historical verified candidates 466.793213 → 438.955225 seconds (the film preserves that earlier snapshot; the job has since completed); UMC08 completed plan 1065.647591 → 1033.567006. The same conditional ramp-clearance lesson is recorded in both. Do not claim a new learned manufacturing check in the indexed campaign.
- [Baseline Weave evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-b76f-7744-b619-b7a569677668), [learned evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-c591-7d3f-984c-4d661ab3d124), [corrected native-summary receipt](../output/evaluation/native-summary-20260913T064011Z/publication.json). Six original retained cases; five earlier executions per case/variant aggregated into each row. Learned catch rate 100% of two invalid cases, false rejection 0% of four valid cases. Dashboard 43.25 ms is a mean of per-case medians, not machining time. Original replay/film sources are preserved.
- [Published evidence artifact receipt](../output/sponsors/fusion-artifact-receipt.json) and [W&B artifact run](https://wandb.ai/silta/coreweave-hack-silta-squad/runs/43m1kgqx). **The existing v0 is an earlier partial snapshot**, not the current film or final campaign package. For judge delivery, use the reviewed final bundle's own index and manifest once built; do not substitute a newer filename into this old publication claim.

## Q&A and boundaries

- Historical learned checks were saved directly; the replay evaluation came afterward. It was not an enforced historical promotion gate. Across-part final machining times are not a controlled learning curve.
- [ARIA's actual review](../output/sponsors/aria-response.md) diagnosed a recurring Fusion session-readiness failure. The adapted preflight passed 16 tests and recovered focus in a live attempt. A later full pass also needed a separate OCR repair. Say “ARIA helped improve the runner”; do not claim an isolated causal reliability benchmark.
- [Native Weave scores](../output/sponsors/fusion-native-scores.json) are deterministic `FusionOutcomeScorer` feedback with server readback. Native Agents Signals coverage for Fusion is not established.
- Fusion verifies internal CAM motion plus bounded finished-stock comparison. Posted NC is delivered, but that internal simulation is not separate certification of the posted program or physical cutting validation.
- The earlier learning sequence included integration recoveries. Do not present it as one uninterrupted autonomous batch.

## New complex-part option: UMC12 clevis

Use the clevis alongside the octagon and fork to show distinct geometry. Its completed run has three verified CAM estimates: **944.09 → 929.29 → 908.97 seconds (3.72% faster)** on the same fixed part. The machine uses indexed 3+2 orientations and the configured T1 tool; this is not simultaneous five-axis cutting. No new learned-check claim follows from this result.

Spoken line: “Here is the more complex clevis. The agent verified three CAM plans, reducing the estimated machining time by 3.72%. This recording shows the real machine simulation and its finished stock.”

If describing autonomy, add: “This capture needed one operator rewind to regenerate stock. That exact trigger is now in the script.” The original receipt and operator sidecar remain unchanged. Use `output/video/umc12-close-capture/capture-receipt-portable-v2.json` for the film-tail validator; it freezes all six original implementation sources, including the exact v6 exporter and records the sampled visual review. The take contains an operator intervention and should not be called unattended.

Read its actual loop in the terminal:

```sh
.venv/bin/python scripts/demo/live_terminal.py --job demo-umc-umc-12-recovery1
```

## Completed cage: a separate manual hypothesis

UMC11 recovery5 completed with freshly verified CAM at **2357.73 seconds**, versus
its earlier v7 verified incumbent at **4242.12 seconds: 44.42% less estimated time**.
Show [the separately labeled cage chart](../output/evaluation/cage-manual-retest.png).
Say: “We manually nominated an older CAM plan after fixing an export race. The
normal verifier accepted it, and the supervisor retained it.” This is not an
agent-discovered improvement or new learning. Keep this separate from the six-part
[verified optimization chart](../output/evaluation/verified-improvements.png).

UMC03 also now completed: its matched v7 pair is 438.955225 → 433.128113 seconds
(1.33%). The film's earlier historical comparison stays frozen. Do not substitute
current totals into its old source-bound cards.

```sh
.venv/bin/python scripts/demo/live_terminal.py --job demo-umc-umc-11-recovery5
```

## Preferred retained-octagon live command

The source recovery is completed and its four clean playback receipts are retained.
This command starts a new recheck of its saved best plan; it does not recreate the
original drawing-to-CAD preparation. Future results must still be observed.

Say: “This is a known part whose CAD and CAM were prepared earlier. We are rechecking
the retained plan live; afterward Astra makes a fresh supervisor decision.” This is
not an unseen drawing demonstration. The supervisor may immediately stop or may
request further optimization; the latter is not guaranteed to finish during the talk.

In an idle, unlocked Fusion session with Machine and Tool visible, use a fresh job ID
and copy the rehearsal's learning state into a separate directory:

```sh
cd /Users/touko/work/helios-one/repos/coreweavehack
SILTA_LIVE_JOB="stage-octagon08-live-$(date +%Y%m%d-%H%M%S)"
SILTA_LIVE_SHADOW="runs/${SILTA_LIVE_JOB}-shadow-learning"
mkdir "$SILTA_LIVE_SHADOW"
cp runs/stage-octagon08-r1-shadow-learning/checks.py "$SILTA_LIVE_SHADOW/checks.py"
cp runs/stage-octagon08-r1-shadow-learning/cad_cam.md "$SILTA_LIVE_SHADOW/cad_cam.md"
hsec exec --only COREWEAVE_WANDB_API_KEY -- .venv/bin/python scripts/demo/resume_fusion_job.py \
  runs/stage-octagon08-r1-recovery1/manifest.json \
  config/demo-campaign/umc-08-job.json \
  --job-id "$SILTA_LIVE_JOB" --max-attempts 6 \
  --learning-directory "$SILTA_LIVE_SHADOW" \
  --show-playback --playback-seconds 15
```

The resume retains the accepted target and selected CAM candidate, then performs
fresh verification; any new CAM identities are allocated above retained IDs.
Learning updates remain in this new shadow directory. Existing stage receipts are
not rewritten. `run-receipt.json` records recovery/learning provenance and separate
presentation receipts under `runs/<job>-playback/<candidate>/`.

Inspect the verdict and playback separately: require a completed passed verification,
observed tool motion, successful SimulationStop and restored target display with no
cleanup errors. A moving tool alone is insufficient. Explicit playback lasts15s;
observed total presentation work was about38s, including setup/cleanup, and is distinct
from verification time. The outer traced call includes presentation delay.

In a second terminal, use the printed job ID:

```sh
.venv/bin/python scripts/demo/live_terminal.py --job stage-octagon08-live-YYYYMMDD-HHMMSS
```
