# Selected fixture preparation

`prepare_soft_jaw_fixture.py` imports a **new fixture-only document** from the pinned
Haas 05-0404 archive. It never changes the accepted CAD or source file. Call its
`apply(app, payload)` through the Fusion bridge on the main thread:

```python
payload = {
    "config_path": "/absolute/path/config/soft-jaw-job.json",
    "output_directory": "/absolute/path/new-output-directory",
    "supports": {
        "dimensions_mm": [152.4, 12.7, 38.1],
        "source_url": "https://www.haastooling.com/p/09-0108"
    }
}
```

The optional supports are two conservative solid envelopes of the selected
Haas 6 × 0.5 × 1.5in parallels. Their drilled holes are omitted. They sit against
the jaws and outside the through-slot footprints. Actual base faces determine
placement; actual gripping-face bounds determine the resulting clamp depth
instead of forcing the earlier 6.35mm assumption. Without this explicit input,
no supports are inserted and the unsupported bottom gap remains unresolved.

Outputs: source-pinned F3D, preview, occurrence transforms and JSON report with
actual BRep stock/fixture and conservative slot-envelope intersections. A thin
probe under each parallel measures the amount of actual base material under its
footprint; this is contact evidence to review, not a workholding certification.
The report never marks the setup ready. Unknown Boolean results remain unknown.

Actual source assembly constraints identify RigidGroup2 as the moving assembly:
Components 5,7,8,14,15. RigidGroup1 contains the fixed base and jaw10, including
Components 1,2,3,4,6,9,10,11,12,13,16,17. Slider3 joins Component7 to Component1.
The helper translates the right-hand moving group by -177.8mm along source X;
the left jaw stays fixed. It checks both actual rigid-group memberships before
accepting the prepared grouping. Every source occurrence must match the expected identity transform,
component count and jaw opening before mutation. The fresh copy's joints and rigid groups are suppressed before placement, and
any grounded occurrences are ungrounded; each change is reported. This exports
a static fixture assembly rather than a functioning jaw mechanism. The original
archive remains unchanged. Actual group memberships must agree with both prepared groups. All geometry changes are rigid; every intended occurrence matrix
and body volume is checked after all transforms and again before export, as well
as the resulting planar jaw positions.

Placement is in **part G54 coordinates**, not machine table coordinates. The
machine attachment/table transform, actual contact patches and clamp force are
still separate requirements. Runtime can use the exported pinned fixture after
its geometric measurements and machine placement are accepted. The third live attempt succeeded in Fusion2705.1.15. The exported archive was reopened and all19 bodies retained their positions. The pinned result and measurements are in config/haas-vise-with-parallels-g54.f3d and config/fixture-preparation-report.json. The two parallel footprints have61.46% and62.42% bed material coverage: they span the center recess and rest on side lands. All stock/fixture and through-slot envelope checks were clear. This establishes fixture geometry and contact, not machine placement or cutting-load validity.
