# Silta — a CNC agent that learns from machining failures

**Submission draft; not submitted.** The portable bundle's `manifest.json` is the authority for its completed-part count. Later challenge results must be incorporated into a fresh bundle; the uploaded v0 is an older partial snapshot.

## Submission fields

| Field | Value |
| --- | --- |
| Project | Silta CNC learning demo |
| Team | Silta Squad — uniqueness to confirm |
| Repository | https://github.com/noppud/CoreWeave-Hack-Silta-Squad |
| W&B project | https://wandb.ai/silta/coreweave-hack-silta-squad |
| Track | Best Use of Weave proposed; current track selection to confirm |
| Team roster and social handles | To supply and verify |
| Participant sign-ins and surveys | Each teammate to confirm |
| Submission page and current deadline | Current organizer listing: Sunday September13,1PM in San Francisco; live AGI House form and completion still unverified |
| Hosted demo / video URL | W&B evidence artifact snapshot uploaded; final campaign/film snapshot still to refresh |

## Summary

Silta turns a drawing, a machine definition and a tool library into a fixed CAD target and a CAM plan. Astra repairs failures found by cheap code checks and real Autodesk Fusion simulation, then a supervisor uses verified machining estimates to decide whether another attempt is worthwhile. Some retained simulation failures produced reusable checks and planning guidance; later parts reuse that state. Individual runs may optimize CAM without changing either learning file.

## The actual loop

```text
Drawing + machine + tools → Astra: fixed CAD, create/revise CAM
                                    ↓
                            cheap code checks ──fail──→ repair
                                    ↓ pass
                         Fusion + finished-stock check ──fail──→ repair
                                    │                      └→ learn a check
                                    ↓ pass
                   supervisor: time, cost, simulation feedback
                         ├─ improve CAM / planning guidance → Astra
                         └─ finish → best verified plan + STEP / CAM / NC / evidence
```

Fusion API calls handle deterministic setup, CAM generation, timing and postprocessing. A fixed native UI runner collects Fusion simulation results and exports simulated stock; routine collection has no model clicking. Finished stock is compared with the frozen CAD target within the job's tolerance. Unknown or incomplete collection cannot become a pass.

The active learned state is two files: `learning/checks.py` and `learning/cad_cam.md`. Updates feed later attempts and later parts. The current live implementation saves these updates directly; the published Weave comparison is a separate retrospective evaluation, **not a live promotion gate**. The supervisor chooses to improve or finish, subject to job execution limits; the best previously verified candidate remains available when a later attempt fails.

## Measured evidence

| Evidence | Recorded result | Scope |
| --- | --- | --- |
| Same-part optimization, historical Part A | 384.860 → 211.037 seconds, **45.2% less estimated machining time** | Fixed part; verified before and after |
| Check transfer, B → C | Learned finished-side intrusion check rejected C's bad CAM in **51 ms before simulation** | Actual retained rejection and exact check source |
| Published paired Weave replay | Empty checks caught 0/2 invalid plans; learned checks caught 2/2; both accepted 4/4 valid plans | Six retained cases, five original executions per case/variant; corrected summary republishes those observations |
| Indexed UMC example | Real Fusion machining footage, indexed **3+2**, one **T1** tool | Actual machine animation; not continuous simultaneous five-axis motion |
| Completed UMC03 optimization | Fresh v7 pair438.955225 → 433.128113 seconds, **1.33%** improvement | Same fixed target and verifier; broader historical comparison uses different verifier versions |
| Completed UMC08 live recovery | Four fresh passes; best1515.202754s,6.144% below original prepared r1 candidate1 | Four clean motion/stop/restore playbacks; checks/prompt unchanged; original r1 cap/operator cleanup remains separate |
| Completed UMC10 rehearsal | 344.902176 → 338.612911 seconds, **1.82%** improvement; third candidate tied | Three passes; shadow checks/prompt unchanged; real playback separately observed |
| Completed complex UMC12 clevis | 944.089570 → 929.289544 → 908.965929 seconds, **3.72%** improvement | Three valid plans; main checks/prompt unchanged |
| Completed complex UMC11 cage | Fresh v7 retest4242.119344 → 2357.727194 seconds, **44.42%** reduction | Operator nominated retained CAM after an export-race fix; normal verification passed and supervisor stopped. Not autonomous discovery or new learning |

All nine current indexed campaign rows completed. Together with four historical parts, the selected report contains13 completed distinct drawings; the separate completed finned rehearsal brings the gallery to14. Recovery attempts are not extra parts. The newest stage-finned10-r2 rehearsal remains incomplete after a collection-unknown result, so it is not claimed as a second successful rehearsal.

Different drawings have different work, so their final times are not a controlled learning curve. These are Fusion internal CAM and bounded stock-geometry results; posted NC is an output, not separately certified by these passes. No physical machine was operated.

- [UMC12 completed optimization trace](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a099e4-2c29-7281-b519-1ad9545f6003)
- [Part A optimization trace](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098a9-7350-7b4b-adb4-e5d9c997f8c4)
- [Part B failure and learned check](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a098ae-dab2-7f63-b230-31e73a08ceca)
- [Baseline Weave evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-b76f-7744-b619-b7a569677668)
- [Learned-check Weave evaluation](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a0997e-c591-7d3f-984c-4d661ab3d124)

The linked native-summary evaluations reuse the original frozen replay; no checks or simulations were rerun for the summary repair. The learned Evaluation UI visibly shows catch 100%, false rejection 0%, acceptance 100%, runtime 43.25 ms average and 6 examples. Rates use their applicable 2 invalid/4 valid cases. See [dashboard evidence](weave-evaluation-dashboard.md); original receipts and film links are preserved.

**Judge access:** the W&B UI currently reports `Project access: PRIVATE`. The linked evaluations and artifacts work for the signed-in team; public or unauthenticated judge access has not been established. Keep the portable offline evidence bundle available locally, and settle the sharing route for the concrete final package before relying on these links during judging. No shared project visibility was changed.

## Sponsor use

**Weave:** real run traces, published paired check evaluations, and native programmatic `FusionOutcomeScorer` feedback with finalized score-call and root-feedback readback. This is deterministic post-run scoring; the Fusion scorer is not a claim of native Agents Signals coverage.

**ARIA:** reviewed actual Fusion calls and descendants, diagnosed session-readiness failures, and recommended a bounded normalization step. We adapted that recommendation, passed 16 unit tests, and observed live focus recovery in 3.108 seconds. A later successful verification also needed a separate OCR integration fix, so it is not an isolated ARIA reliability benchmark. The retained response identifies ARIA's project-scoped gpt-5.5; all project agent roles use Astra.

**marimo:** a read-only notebook exposes actual runs, candidate timing, checks and prompt changes, artifacts, video and Weave links. The stage demo can use raw Fusion and the terminal instead.

**Execution:** Astra uses the local Codex SDK with the authorized subscription login. Fusion runs on macOS. W&B hosted Sandboxes were unavailable; generated checks run in a bounded local subprocess, not an isolated security container. No hosted sandbox integration is claimed.

## Reproduce and inspect

Requirements: pinned local resources and access to the exact Fusion project/linked machine model/library references (see `config/README.md`), installed Fusion with manufacturing access, the SiltaBridge add-in running, existing native accessibility/screen-capture permissions, Astra SDK login, and a scoped W&B credential for tracing. Simulation collection requires unlocked foreground Fusion; this is not a headless service.

```sh
uv sync --locked
uv run python -m silta doctor --fusion
hsec exec --only COREWEAVE_WANDB_API_KEY -- uv run python -m silta run config/soft-jaw-job.json
uv run python scripts/demo/live_terminal.py --campaign runs/demo-campaign.json
uv run marimo run notebooks/cnc_app.py --host 127.0.0.1 --port 8791 --headless
```

See `fusion/README.md` for bridge setup, `docs/demo-runbook.md` for the three-minute presentation, and `docs/demo-evaluation.md` for evaluation scope. The separate `cnc_simulator/` application is not the source of these Fusion results.

Create a portable local evidence snapshot:

```sh
uv run python scripts/demo/package_evidence.py
```

Open the resulting `output/submission/silta-fusion-evidence-*/index.html`, or share its ZIP after review. It contains completed distinct-drawing results, separate failure/transfer proof, source hashes, STEP/NC, verification outputs, exact learning sources, published evaluation evidence and ARIA's response. Large native project archives remain source references. No upload happens by default.

For the raw stage demo, show Fusion plus `live_terminal.py` using the completed
retained UMC08 plan and the command in `docs/demo-runbook.md`. The recovery completed
four fresh passed verifications and four automatic motion/stop/display-restoration
playbacks. It retained candidate5 after candidate6 tied. This is known prepared CAD/CAM,
not fresh drawing generation during the talk; both shadow learning files stayed unchanged.
Original r1 required playback cleanup and hit its cap; finned r2/recoveries remain unknown.
[Rehearsal trace](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a09a51-6741-753f-ab92-d297767bbc73).
The final package/upload must still be refreshed; existing v0 does not contain this result.

Local presentation files: `output/presentation/silta-loop-demo.mp4` (under two minutes; exact duration in `film-evidence.json`), `output/presentation/slides.html` (two slides). The film uses retained historical and indexed Fusion footage; it is not a live capture of every campaign part.

The first [W&B evidence artifact upload](https://wandb.ai/silta/coreweave-hack-silta-squad/runs/43m1kgqx) is `silta-fusion-judge-evidence:v0`: a six-completed-drawing snapshot, with 519 uploaded entries checked against local file digests. Later local results are not included in that version. See `output/sponsors/fusion-artifact-receipt.json`; publish a new version after the final campaign and film are reviewed.

## Build provenance and remaining submission work

New repository work includes the Fusion bridge and deterministic verifier, Astra loop and supervisor, persistent learned checks/guidance, Weave instrumentation/evaluations, campaign orchestration and evidence presentation. Autodesk Fusion, its machine models/postprocessors, Astra/Codex, Weave/ARIA, marimo and geometry libraries are existing components. Imported machine/tool/drawing assets retain their source references. Team members should confirm the exact hackathon-time contribution boundary before submitting.

Concrete remaining delivery work: confirm roster/socials and each participant survey in the live form; rebuild the final local package with the completed campaign, separate stage-rehearsal statuses and final cage/clevis film provenance; review its film and links; publish/read back the intended final artifact version (v1 is not yet published); establish judge access to the private W&B project or provide the portable package; then complete the event form and retain its submission receipt. The W&B snapshot above is uploaded; event submission has not been performed. See `docs/reviews/current-event-verification.md` for the current organizer listing and remaining form questions.
