# Indexed housing study

This extension uses the actual Haas UMC-750 Reboot model from Autodesk's machine
library. The downloaded F3D and MCH, their source URLs and SHA-256 hashes are under
`assets/umc750/`. A one-time Fusion import tessellated the model. Neither simulation
nor playback calls Fusion. Machine geometry includes separate XYZ, B, C and spindle
components. It is an illustrative machine model, not a certified collision model.

The reference-inspired housing starts as a diameter 100 mm, height 80 mm billet.
Its frozen target has a deep central cavity, eight recessed radial panels, eight
radial openings, and eight flange holes. This is an original demonstration design;
the photograph does not supply dimensions or an engineering drawing to reproduce.

From the repository root:

```sh
cnc_simulator/.venv/bin/python cnc_simulator/scripts/build_housing.py
cnc_simulator/.venv/bin/python cnc_simulator/scripts/simulate_housing.py
cnc_simulator/.venv/bin/python cnc_simulator/scripts/export_housing_view.py
cnc_simulator/.venv/bin/python cnc_simulator/scripts/build_housing_surfaces.py
cnc_simulator/.venv/bin/python cnc_simulator/scripts/shade_housing_surfaces.py
cnc_simulator/.venv/bin/python cnc_simulator/scripts/serve_housing.py
```

Open http://127.0.0.1:2740/housing.html. Use Machining, Whole machine, Finished stock,
the timeline, or orbit the view. Record video captures the actual WebGL playback to
`workspace-housing/housing-machining.webm` through a same-origin loopback endpoint.
The renderer subtracts convex swept cutting-tool meshes from the initial stock; it
never replaces the billet with the target mesh. These display meshes use inscribed
64-sided cutting cylinders, and stock updates at completed checkpoints (every 24
moves and each index). Display volume decreases monotonically and is checked against
the authoritative conservative voxel volume bounds. Mesh normals preserve creases.
The separate voxel removal timeline is also verified against the final NPZ stock.
Display surfaces do not replace the conservative voxel verifier or certify geometry.

## Callable behavior

`cncsim.simulate` accepts an optional `indexing` configuration and `index` movements.
The ordinary three-axis contract is unchanged. Indexed moves specify `b_degrees`
and `c_degrees`. Cutting and linear travel use absolute world XYZ with the spindle
fixed along +Z. B rotates about -Y through `pivot_mm`; C rotates about -Z through
the table origin. Stock and every configured fixture remain in a canonical part
frame, with `work_offset_mm` locating that frame on the table. Tool-tip coordinates
plus fixed gauge length minus head mount give machine XYZ travel coordinates.

Index moves remove no material. Intermediate index poses use angular intervals with
conservative motion inflation, so a collision between samples cannot automatically
pass. Linear cuts query the same persistent stock in the rotated frame. Both stock
bounds and nominal stock survive indexing. Fixtures rotate with the table. Results
include `time_breakdown.indexing`, in addition to cutting, rapid, dwell and tool
changes. Axis rotations use simultaneous constant angular speeds and settle time.
Callbacks and trajectory JSON include `bc_degrees`; `snapshot_stride` can reduce
saved NPZ checkpoint count while callbacks still receive every move.

## Current limits

- Indexed 3+2, not simultaneous five-axis cutting or a six-axis robot.
- Flat-end tools with cylindrical cutting, shaft and holder sections.
- The fixture is a simplified supporting pedestal, not a proven clamping design.
- Whole-machine self-collision, enclosure interference, clamp forces, tool loading,
  chip evacuation, spindle dynamics and acceleration are not certified.
- One fixed gauge length across tools in an indexed plan. C is unlimited; B and XYZ
  have explicit limits. No arbitrary rotating machine architecture is inferred.
- The housing uses 1.5 mm stock cells and 4.5 mm demonstration tolerance. A passing
  result at this resolution is not production dimensional verification.
- Numerical uncertainty fails verification. Failed plans can be visualized but
  cannot receive an optimization score or be accepted by a timing judge.
- The housing CAM seed is deterministic Python. The ten-part Astra optimization
  benchmark still covers its documented pocket families; housing agent planning
  and cross-part housing learning have not been demonstrated.

The original ten-part results and videos remain in `workspace-judge-v2/`, with their
original verifier evidence. This extension does not retroactively re-certify them.

## Verified run

The revised seed passes the fixed 4.5 mm demonstration tolerance at 1.5 mm resolution.
Estimated time: 1501.448 seconds (25:01), including 33 seconds of indexing and
15 seconds of tool changes. The first seed failed due to possible excess material;
overlapping passes resolved it without changing the frozen target or tolerance.
The current test suite passed 51 tests. No claim of production readiness or
learned optimization of this housing follows from those results.
