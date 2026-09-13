# Silta: a raw Fusion demo in under three minutes

Show actual machining, three concrete parts, one learned check and one reused planning lesson. Then expose the running loop. The film is a separate 114-second submission asset; do not play the whole film inside this talk.

## Spoken script · approximately 2:45

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:18 | Release the prepared live verification. Show the film's first eight seconds, then return to Fusion. | “We prepared this drawing's CAD and CAM before the talk. I’m starting its real Fusion verification now. Here is recorded machining from an earlier completed job: a Haas UMC-750, one cutter, indexed three-plus-two—not simultaneous five-axis.” |
| 0:18–0:38 | CAD previews: UMC08 octagon, UMC09 fork, UMC05 manifold. | “These are three actual generated targets: an octagonal housing, a forked bracket, and a service manifold. Each has a completed, verified CAM plan. These images are CAD previews; the film ends with actual simulated stock from the cage and clevis.” |
| 0:38–1:03 | Slide 1; point through the loop once. | “Astra keeps the CAD target fixed and revises the machining plan. Cheap checks catch known mistakes. Fusion verifies the motion and finished stock. Failures return for repair and can teach a new check. Only a pass reaches the supervisor, which decides whether another improvement is worth trying.” |
| 1:03–1:28 | Slide 2: B → C. Then the indexed learning evidence at film 80–88 seconds, or its static frame. | “In our earlier three-axis experiment, a simulation failure became a check that caught the repeated mistake on another part in 51 milliseconds. For indexed machining, the transferred lesson was planning guidance: reduce air-ramp clearance when stock clearance allows it. Verified estimates improved about six percent on one fixed part, then three percent on the octagon.” |
| 1:28–1:48 | Corrected learned Weave evaluation; show its six cases. | “Weave compares the original and learned checks on six retained cases. The learned checks catch both failures; the original catches neither. Both accept all four valid plans. The code, case outcomes and timings are inspectable. This is historical replay, not an unseen-parts benchmark.” |
| 1:48–2:30 | Live terminal: actual stage, candidate source, checks, prompt versions; Fusion when it runs. | “This is the autonomous SDK run. Here are its CAM code, checks and planning guidance. Routine Fusion setup and result collection are deterministic. The model makes machining decisions. The terminal reports the actual stage. When verification finishes, the supervisor receives machining time and feedback, then improves the plan or returns its best verified candidate.” |
| 2:30–2:45 | Actual current result; if pending, use the explicit fallback below. | “The output is CAD, CAM, posted NC and verification evidence—and guidance the next job can reuse. We improve the process while keeping the requested part fixed.” |

If verification is still running, say: **“This run is still at [observed stage]. Here is the recorded verified example.”** Show film 104–114 seconds, clearly labeled recorded. Do not promise the live result within the speech. A collection failure stays a failure; an orbit is camera motion, not a new machining test.

## Before the audience arrives

Use two screens: Fusion stays visible on the compute screen, owned by one worker; the presentation screen holds the film, selected CAD images, two slides and authenticated Weave tabs. Use large raw-terminal/editor text. No website tour or sign-in onstage.

The provisional preferred live input is **UMC08, the octagonal part**. A fresh
shadow-learning rehearsal, `stage-octagon08-r1`, is running; it is **not yet a
validated live presentation**. Use its actual result and playback receipt before
relying on it. The completed campaign UMC08 is separate recorded evidence.

The earlier finned rehearsal `stage-finned10-r1` remains completed: three verified
candidates and observed motion in three playbacks,344.902176→338.612911 seconds
(1.82%). The fresh finned r2 and two recoveries remain incomplete because stock
completion was not observed after the CAM repair. See the
[collection diagnostic](reviews/finned-rehearsal-collection.md). UMC07 is an unrun
alternative, not a rehearsed fallback.

Only after the campaign releases Fusion, prepare one real UMC08 job from a terminal in the repository:

```sh
cd /Users/touko/work/helios-one/repos/coreweavehack
export SILTA_STAGE_JOB="stage-octagon08-$(date -u +%Y%m%dT%H%M%SZ)"
printf '%s\n' "$SILTA_STAGE_JOB"
hsec exec --only COREWEAVE_WANDB_API_KEY -- .venv/bin/python scripts/demo/stage_fusion_demo.py config/demo-campaign/umc-08-job.json --prepare --show-playback --job-id "$SILTA_STAGE_JOB"
```

The helper generates CAD/CAM and runs checks, then prints **“Fusion verification has NOT run”** and waits for Enter. Press Enter at the talk's start. Preparation and live verification times are recorded separately. The helper copies learning into a shadow directory and never promotes changes to the campaign's learning. Use a fresh job ID on each attempt. UMC08 is a previously used campaign drawing, not a never-seen live input. Fresh rehearsal timing remains pending. For comparison only, the historical finned r1 rehearsal took 442.52 seconds to prepare CAD/CAM/checks, followed by a 41.79-second presenter pause; its first actual verification took 28.84 seconds. Those wall times are separate from the 344.90-second machining estimate. All playback receipts record target visibility restoration. The shadow checks/prompt ended with their original hashes and remain separate files from main learning. See the [rehearsal receipt](../runs/stage-finned10-r1-presentation.json).

In a second terminal, substitute the exact job ID printed above:

```sh
cd /Users/touko/work/helios-one/repos/coreweavehack
export SILTA_VIEW_JOB='paste-the-printed-job-id-here'
.venv/bin/python scripts/demo/live_terminal.py --job "$SILTA_VIEW_JOB" --width 120 --height 40
```

This viewer is read-only. It shows the actual CAM/check source and recorded versions, candidate status, verification and recent events. For a stable plain snapshot:

```sh
.venv/bin/python scripts/demo/live_terminal.py --job "$SILTA_VIEW_JOB" --once
```

Before relying on the stage helper, inspect `runs/<job-id>-presentation.json`: its `verifications` must contain a completed `passed` verdict; its `playbacks` must report `tool_motion_observed: true`. `job_finished` alone does not prove either. `--show-playback` presents the already-verified candidate afterward; its presentation receipt does not supply the manufacturing verdict. Full rehearsal success must come from that actual receipt, not unit tests.

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
