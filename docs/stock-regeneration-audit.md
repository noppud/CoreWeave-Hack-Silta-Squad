# Stock export regeneration audit — 2026-09-13

A machine-verification pass is separate from completion of Fusion's displayed stock regeneration. UMC11 recovery1 exposed a concrete collection race: Save Stock could export while the bottom-right **Stock generation** indicator was still progressing.

## Retained evidence

All paths below are under `runs/demo-umc-umc-11-recovery1/`. Original candidate artifacts and verdicts remain retained; these observations do not retroactively establish a machining pass or fail.

| Candidate | Save filename entered | Immediately after Save | Export/UI volume difference |
|---|---|---|---|
| 1 | `verification-0001/evidence-31.json`: 66.6% | `evidence-33.json`: 100.0% | 480.584832 mm³ |
| 2 | `verification-0002/evidence-31.json`: 23.5% | `evidence-33.json`: 37.6% | 51,823.339276 mm³ |
| 3 | `verification-0003/evidence-48.json`: 62.0% | `evidence-50.json`: 71.0% | 16,117.155401 mm³ |

The paired PNGs provide visual confirmation, including candidate2 `verification-0002/evidence-32.png`: its unique filename is visible in the Save Stock dialog while Stock generation reads 23.5%. Candidate2's raw export is `silta-stock-c6702263cf9444deba4b8d63fbb8ee5f.stl`; candidate3's is `silta-stock-6829ab6d72804259a5d08674229ddc5b.stl`.

The 149 manifest-pinned evidence artifacts across these three verifications matched their recorded SHA-256 hashes during the audit. Documents, candidate digests and export filenames are distinct and bound correctly. The evidence identifies a regeneration timing race, not a stale candidate-ID substitution. Large volume disagreement alone was not used to infer the cause; the visible progress during Save is the concrete evidence.

`simulation-before.json` and `simulation-after.json` in each retained stock-export directory still report raw Time 0.0%,  and expose an in-process-stock warning. These raw values cannot stand in for a regeneration-completion signal. A completed, stable re-export of the same candidate is required before judging its machining coverage.

## v6 collection boundary

`fusion-fixed-ui-stock-v6-stock-generation-ready` preserves the existing geometric comparison and machine-verification requirements. After maximum stock accuracy and the observed End of Toolpath command, export waits for actual stock-generation progress:

- Observe generation and then its disappearance, or an explicit 100% reading.
- Require repeated complete/idle observations with a stable final operation and XYZ position; verify playback is stopped using the existing observed Play control.
- Reject malformed/ambiguous progress, changed document, moving playback, or a bounded 180-second timeout. Mere absence of progress without any observed generation is **not** completion.
- Recheck for restarted partial generation immediately before and after Save. A stable STL file alone never proves finished stock.

`stock-readiness.json` and numbered raw simulation observations retain the sequence and final position. Failure is a collection failure, not a generated manufacturing-check lesson. The polling interval only determines observation cadence; it is not a fixed regeneration delay.

This change is unit-tested with the actual observed partial-progress sequences. Live validation of both slow UMC11 and a fast previously verified part remains required. A fast run whose progress is never observable fails closed until a supported positive completion signal is established.

## First live v6 observation

`runs/demo-umc-umc-11-recovery2` completed the new stock-readiness gate on its resumed retained CAM candidate. The receipt `workspace/verify-96aec267f15843659fad32969034dcf4/stock-export/stock-readiness.json` records 18 samples: initially no progress, then 8.0%, 9.7%, 18.6%, 21.1%, 32.2%, 33.5%, 40.7%, 52.7%, 54.5%, 63.9%, 74.0%, 79.4%, 85.1%, 96.1%, 97.7%, 100.0%,  then idle, with stopped playback confirmed. Initial absence was not accepted.

The completed export volume was 266,327.132454 mm³ against the retained tessellated target 266,279.784572 mm³, compared with 283,030.155401 mm³ in recovery1 candidate 3's partial export. This live result supports the extraction-race diagnosis; volume proximity is not a conformity verdict.

The fresh v6 verification remains **unknown / incomplete**: stock-to-target passed its bounded surface test, but target-to-stock reached the resource bound after 1,582,000 processed triangles with 418,668 unresolved. `verification-0001/evidence-96.json` retains the exact comparison. Candidate digest is `89922baa83f2191b8decea6b78acde3ad35930f2262fd007a4efde0722c8e31e`. An offline larger-budget investigation is separate from this recorded verdict; it has not been substituted into the run. Fast-part validation remains separate.

## Separate offline budget probe

`output/evaluation/umc11-v6-comparison-budget-probe.json` records a subsequent **offline numerical pass** on the unchanged v6 exported STL and target, with an 8,000,000-triangle /300-second-per-direction budget. Stock-to-target processed 894,368 subtriangles in 14.85 seconds; target-to-stock processed 2,095,020 in 62.93 seconds. Both bounded tests passed at the unchanged 0.127 mm tolerance, using the same comparison algorithm. Maximum observed sample deviation was 0.01113 mm; the conservative upper bounds are retained separately in the JSON.

This is a retained-mesh numerical probe, not a new Fusion run or a replacement for recovery2's recorded unknown verdict. The source STL SHA-256 is `23919a87d3e7f5e079d6ddd95821a933ad80aeff807c453dc0cf08747f6a4cbb`. The current comparison defaults now provide the same larger resource budget and record it under `resource_budget`. More computation did not alter the tolerance or accepted target. Fast-part stock-readiness validation remains pending separately.

## v7 explicit regeneration trigger

The UMC12 close capture completed its machine video, but its post-playback export initially observed no new generation because playback was already at the end. During that retained capture, an operator explicitly selected Start of Toolpath and then End of Toolpath. The existing gate then observed generation (including 39.4%, 68.3%, 80.7%, 100%) and stable completion. `output/video/umc12-close-capture/operator-force-regeneration.json` records this intervention; it must not be described as fully automatic capture.

`fusion-fixed-ui-stock-v7-explicit-stock-regeneration` now always selects **Start of Toolpath → End of Toolpath** after maximum accuracy and before the existing readiness gate. This reuses the known native menu controls. **Regenerate on rewind must already be enabled** in Fusion's simulation Display settings; its enabled state was observed in this setup. The exporter does not guess or toggle that setting. Missing generation still fails collection instead of treating idle as completion. The export receipt records the trigger sequence and prerequisite.

The v7 trigger change requires a fresh automated live run. It does not rewrite the UMC12 capture intervention or any existing verification.
