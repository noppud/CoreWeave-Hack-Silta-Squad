# Learning transfer evidence

Snapshot: 2026-09-13T09:25:16.789033+00:00.

Different parts are not a timing learning curve. Full hashes, source excerpts and event indices are in learning-transfer.json.

13 completed distinct drawings out of 13 observed drawings. An incomplete job's verified candidate does not count as a completed drawing.

| Drawing | Inherited prompt / checks | Latest job | Best verified s | Within-part reduction |
| --- | --- | --- | --- | --- |
| A / 393e71c04e | a7cf610bce08 / d8a395e27e72 | completed | 211.037 | 384.860 → 211.037 (45.2%) |
| B / 0b57a91e4a | 481a12b310d2 / 576d826b090c | completed | 205.345 | not measured |
| C / d15fbc53f8 | 481a12b310d2 / 0addb6e1d074 | completed | 211.850 | 228.182 → 211.850 (7.2%) |
| D / 48a8b0b304 | 05e8cc6ca1cb / 0addb6e1d074 | completed | 208.573 | not measured |
| UMC02 / 700aec1f93 | 05e8cc6ca1cb / 0addb6e1d074 | completed | 371.054 | not measured |
| UMC03 / 5e121d57c3 | 05e8cc6ca1cb / 0addb6e1d074 | completed | 433.128 | 466.793 → 433.128 (7.2%) — **verifier changed; historical comparison** |
| UMC08 / 7f9b18fcd3 | fb6133ee810e / 0addb6e1d074 | completed | 1033.567 | 1065.648 → 1033.567 (3.0%) |
| UMC04 / 3e403164ec | fb6133ee810e / 0addb6e1d074 | completed | 432.384 | 466.049 → 432.384 (7.2%) |
| UMC09 / b182e79448 | fb6133ee810e / 0addb6e1d074 | completed | 208.996 | 225.140 → 208.996 (7.2%) |
| UMC05 / b48eb0f15e | fb6133ee810e / 0addb6e1d074 | completed | 707.217 | 767.855 → 707.217 (7.9%) |
| UMC06 / acdab9fc6b | fb6133ee810e / 0addb6e1d074 | completed | 511.208 | 560.900 → 511.208 (8.9%) |
| UMC11 / bf9d10c72c | fb6133ee810e / 0addb6e1d074 | completed | 2357.727 | 4242.119 → 2357.727 (44.4%) — **manually nominated retest** |
| UMC12 / d0351e3f31 | fb6133ee810e / 0addb6e1d074 | completed | 908.966 | 944.090 → 908.966 (3.7%) |

## Observed cross-part behavior

- **A → B (main_prompt):** B source sets the supplied ramp feed to 457.2 mm/min; consistent with A guidance, not a controlled counterfactual.
- **B → C (checks):** C check event rejects candidate before simulation; direct observed cross-part use.
  Rejected attempt 2 in 51.27 ms; same-attempt simulation started=False.
- **C → D (main_prompt):** D source sets 2-degree ramps and 2 mm cap; consistent with C guidance, not causal speedup.
- **C → UMC02 (main_prompt):** Initial prompt retained; different indexed drawing and machine. Inheritance alone is not effectiveness.
- **UMC03 → UMC08 (main_prompt):** First CAM retained 1 mm; later generated CAM sets 0.2 mm after supervisor feedback. Verification and causal benefit remain separate.
  Supervisor received the pinned learned prompt and requested the same clearance mechanism. This is observed reuse, not proven causal benefit.
  New part's own verified trial: 1065.647591 → 1033.567006 s (32.080585 s saved). Input, target and verifier version match; no control without learned guidance was run.
- **UMC03 → UMC04 (main_prompt):** First CAM retained 1 mm; later generated CAM sets 0.2 mm after supervisor feedback. Verification and causal benefit remain separate.
  Supervisor received the pinned learned prompt and requested the same clearance mechanism. This is observed reuse, not proven causal benefit.
  New part's own verified trial: 466.048718 → 432.383597 s (33.665121 s saved). Input, target and verifier version match; no control without learned guidance was run.
- **UMC03 → UMC09 (main_prompt):** First CAM retained 1 mm; later generated CAM sets 0.2 mm after supervisor feedback. Verification and causal benefit remain separate.
  Supervisor received the pinned learned prompt and requested the same clearance mechanism. This is observed reuse, not proven causal benefit.
  New part's own verified trial: 225.140233 → 208.995927 s (16.144306 s saved). Input, target and verifier version match; no control without learned guidance was run.

## UMC09: separate the actual supervisor trials

UMC09 inherited the same main prompt and checks and saved no new shared lesson. Its total optimization includes ramp clearance and separate approach-height changes.

| Proposed parameter change | Before / after verified seconds | Saved seconds |
| --- | --- | --- |
| rampClearanceHeight | 225.140233 → 218.719106 | 6.421127 |
| feedHeight_offset | 218.719106 → 210.076281 | 8.642825 |
| feedHeight_offset | 210.076281 → 208.995927 | 1.080354 |

These rows retain the exact instruction, event indices, version and candidate digests in JSON. All comparisons use matching input/target/verifier identities; no control run omitted the learned guidance.

## Evidence boundaries

- Different drawing times are not a learning curve; no cross-part timing causality is claimed.
- Prompt/check version continuity proves inheritance, not adoption or usefulness.
- Only completed passed verdicts with currently matching retained evidence hashes supply times.
- Same-part comparisons retain input/target/verifier identity, but historical verifier source bytes were not frozen.
- Generated source assignments are code evidence, not independent operation readback or a manufacturing verdict.
- Historical source retention is incomplete; unavailable source bytes are explicit.
- The report is a read-only snapshot; ongoing jobs require rerunning this command.

Refresh: .venv/bin/python scripts/demo/learning_transfer_report.py
