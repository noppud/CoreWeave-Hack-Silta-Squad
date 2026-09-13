# Final demo claim audit

Read-only snapshot: September 13, 2026. All nine current indexed campaign rows
completed. The historical-plus-campaign report contains **13 completed distinct
drawings**; the separate completed UMC10 finned rehearsal brings the gallery to
**14 completed CAD previews**. Recovery attempts are not additional parts.

## Strong supported claims

- **The complex UMC11 cage completed after a manually nominated retest.** Fresh
  v7 verification accepted retained CAM at **2357.727194s**, versus the previous
  verified incumbent's **4242.119344s (44.42% reduction)** on the same fixed target.
  The operator selected the old CAM hypothesis after diagnosing an export race;
  the supervisor then stopped with that verified result. This is not autonomous
  discovery or newly learned guidance. Earlier partial-stock verdicts remain
  collection-invalidated historical records, not machining failures.
- **UMC03 now completed under v7.** Its matched fresh-verifier comparison is
  **438.955225 → 433.128113s (1.33%)**. The broader historical comparison starts
  under a different verifier and must not be presented as a matched benchmark.

- **UMC12 clevis completed with verified CAM improvement.**
  `runs/demo-umc-umc-12-recovery1/manifest.json` records three passes:
  944.089570 → 929.289544 → 908.965929 seconds, a 3.72% improvement on
  the same fixed target. Best candidate is 0004. These are Fusion estimates.
- **UMC12 close footage is real and operator-assisted.** Machine playback and
  finished-stock orbit completed with unchanged source/target visibility restored.
  After playback, root explicitly selected Start of Toolpath → End of Toolpath
  to trigger stock regeneration before the existing completion gate. Preserve
  `output/video/umc12-close-capture/operator-force-regeneration.json`; do not
  describe this take as fully unattended. The later v7 exporter incorporates
  that trigger; it does not change what happened during this recorded take.
  The portable capture receipt preserves original bytes and the exact frozen
  v6 exporter implementation. Visual review sampled seven retained frames,
  not every frame; indexed machine motion partly occludes the part near 25 seconds.

- **The UMC10 rehearsal completed.** `runs/stage-finned10-r1/manifest.json` selects
  candidate0002, fully passed, estimated machining time **338.612911 seconds**.
  Three candidates passed; candidate0001 was344.902176s. The bounded ramp-clearance
  change saved **6.289265s (1.82%)** on this same part. Candidate0003 tied the incumbent,
  so the supervisor retained0002. This is an optimization loop with a tested
  unsuccessful hypothesis, not an assertion that every revision improves.
- **Real verification and playback both occurred.** The presentation receipt records
  verification wall times28.84/27.48/27.13s and separate playback receipts with changed
  observed tool positions. Playback is presentation, not the source of the verdict.
  The accepted target display was hidden for playback and restored afterward;
  its shape was not changed by that display operation.
- **Retained checks reject known bad cases cheaply.** The published paired replay
  has six labeled historical cases: two invalid and four valid. Empty checks caught
  0/2 invalid; learned checks caught2/2 with0/4 false rejections. Median runtime was
  about24ms versus43ms. Finalized EvaluationLogger calls were read back. This is
  retrospective replay on a tiny retained set, not unseen five-axis accuracy.
- **Actual Weave integration exists.** UMC10's retained root receipt is
  [the rehearsal trace](https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/01a099b3-3037-70c2-9948-b38db54f975c).
  Paired eval links and finalized readback are in `output/evaluation/learning-evaluation.json`.
  Published custom feedback monitoring has retained receipts. The older
  `sponsor-review.json` snapshot is not proof that every newest job was monitored.
- **ARIA contributed a real development review.** `output/sponsors/aria-response.md`
  and `aria-review.json` retain the actual project-scoped gpt-5.5 response and the
  implemented bounded focus-readiness recovery. Live focus recovery took3.108s;
  later full verification also required an independent OCR correction. Do not
  attribute that correction or a controlled reliability improvement to ARIA.

## Limits to say accurately

UMC10 ran with copied shadow learning; initial and final checks/prompt file hashes
are identical and main learning promotion was disabled. It demonstrates applying
existing learning and optimizing CAM, **not a newly learned check in that rehearsal**.
The two replayed historical failures remain the clearest reusable-check evidence.

The project authored these challenge drawings under fixed80x80x70stock, AL6061,
UMC750 indexed3+2, fixture and one-tool constraints. Multiple drawings are useful
coverage, not proof of arbitrary shop-drawing generality. UMC12 now adds a
completed complex clevis and cage with fresh full verification. The cage retest
was manually nominated.
Do not count retries as parts.

The rehearsal prepared CAD/CAM for over seven minutes before release; the complete
three-candidate session took about15minutes. A three-minute presentation can show
a prepared candidate's real verification and the recorded optimization outcome.
It cannot truthfully promise fresh drawing-to-final optimization within three minutes.

Times are Fusion estimates under fixed assumptions, not machine stopwatch times.
The verdict covers internal CAM simulation and independent mesh conformity; it does
not certify postedNC, cutting physics or actual hardware. Crash/focus/export issues
have produced unknown results and required intervention. Native Signals and the
local unpublished score preview are not delivered sponsor integrations.

## Three-minute narrative

**0:00–0:25:** Show the finished finned part and moving machine. “We turn a constrained
part drawing into a machining plan, verify it in Fusion, then improve the next attempt.”
Disclose that CAD/CAM preparation occurred before the presentation. Release the
prepared verification if the stage setup is ready.

**0:25–1:10:** Show one retained actual failure, the reusable learned check and the
paired evaluation: two known bad cases caught, four valid cases preserved, roughly
43ms per check. “This moves a specific repeated mistake ahead of expensive simulation.”

**1:10–2:05:** Show UMC10's three actual verdicts and supervisor decisions:
344.90→338.61→338.61s. Explain the ramp-clearance change and why the third candidate
was not promoted. Distinguish estimated machining time from verification wall time.

**2:05–2:35:** Open the actual Weave trace/evaluation. Briefly show ARIA's specific
readiness recommendation and the resulting bounded recovery receipt. Describe
marimo as the evidence workbench, not an additional agent loop.

**2:35–3:00:** Return to the verified result. “The output is a saved candidate plus
an auditable verdict and a measured next-step improvement.” State the fixed scope
and lack of physical machining validation. Mention complicated new parts only with
their current actual status.

This prioritizes Best Loop, meaningful Weave/ARIA use, utility and working execution
from the [source audit](current-event-verification.md). It makes no award prediction.
