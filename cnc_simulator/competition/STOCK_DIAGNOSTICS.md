# Why these two plans failed verification

Post-run analysis of retained lower/upper stock masks, using the same target distance backend and cell-radius guard. The verifier, target, movement plan, and saved failure keys are unchanged. These are numerical envelopes, not physical measurements.

| Case | Original gate | Maximum excess-distance envelope | Cells possibly beyond 3 mm | Cells definitely beyond 3 mm |
|---|---|---|---:|---:|
| Manifold, cleanup off | Fail: unresolved | 0–3.768 mm | 34 | 0 |
| Same manifold strategy, cleanup on | Pass | 0–1.945 mm | 0 | 0 |
| Cage, stepover 0.95 | Fail: unresolved | 0–19.946 mm | 1066 | 0 |

The manifold's possible-excess envelope crosses the 3 mm tolerance before cleanup and falls below it after cleanup. This supports the recorded numerical gate transition. It does not prove the original physical part had a defect. The cage envelope remains too loose to certify the plan; a large upper bound is not a measured 19.946 mm defect.

`stock-diagnostics.json` includes snapshot/target hashes and the bounding region of possible excess material in part coordinates. A final stock mask does not identify which move caused a residual, so affected moves remain unassigned. The separate 0.5 mm attempt hit the configured resource limit and did not adjudicate either unresolved failure.


## Completed resolution follow-up

The two cases were rerun with unchanged movements and 3 mm tolerance at 0.5 mm resolution, with a four-million-cell budget. The manifold now passes; the high-stepover cage remains unresolved. The earlier resource-limit records remain preserved. [Full follow-up](resolution-refinement/REPORT.md). This is not a timing improvement: both plans retain exactly the same estimated machining seconds.
