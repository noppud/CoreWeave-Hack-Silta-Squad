# Resolution-only follow-up

Two predeclared unresolved cases were rerun at 0.5 mm with a four-million-cell cap. Target, fixture, tool movements, feeds, and 3 mm tolerance were unchanged. Earlier runs stopped because their two-million-cell cap was too small.

| Case | 1 mm result | 0.5 mm result | Cells | Estimated machining seconds | Compute seconds |
| --- | --- | --- | --- | --- | --- |
| 02-hydraulic-manifold-0.708-0 | invalid / unresolved | valid / verified | 2658024 | 116.082 | 183.1 |
| 04-trunnion-cage-0.95-0 | invalid / unresolved | invalid / unresolved | 3466008 | 200.782 | 363.0 |

## Interpretation

A changed verdict from this experiment is a numerical-resolution result, not a CAM improvement or a physical measurement. The unchanged path has unchanged modeled machining time. Each original verdict still describes its original resolution; an unresolved result never becomes a pass without rerunning verification.

The exact-failure memory includes the complete job contract and implementation hashes. A changed resolution is a different contract and must not inherit an old rejection as an unconditional physical-defect claim. No memory rules, production policy, or benchmark scores are updated by this report.

The geometry backend uses floating-point signed distances, not exact arithmetic. This experiment retains the coarse 3 mm demonstration tolerance.

## 02-hydraulic-manifold-0.708-0

[]

## 04-trunnion-cage-0.95-0

[
  {
    "code": "excess_material",
    "certainty": "uncertain",
    "moves": [],
    "description": "Final stock has excess material beyond target tolerance. Resolution cannot establish a pass."
  }
]
