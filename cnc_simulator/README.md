> Current decision contract: `passed` is a boolean. `validity` is `valid` or `invalid`.
> Numerical uncertainty fails the gate with `verification: unresolved`; it is not a
> third decision and does not claim a proven physical collision. Input errors fail too.

# Programmatic CNC simulator

The autonomous CAM loops and local 3D viewer are documented in [LOOPS.md](LOOPS.md).
The instructions below cover the independent deterministic simulator.

A standalone Python API and CLI for one-setup, fixed +Z tool-axis, three-axis milling.
There is no Fusion, desktop automation, model call, agent, service, or optimization
framework dependency. **Only compare estimated time among `valid` plans.** `passed: false` plans are ineligible; there is no cost, wear, or finish objective.

## Run

From this folder, with Python 3.10+:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m cncsim examples/pocket.json --output output-pocket
.venv/bin/python -m pytest -q
```

Alternatively use `uv venv --python 3.12` and `uv pip install -e '.[test]'`.
`requirements-lock.txt` records the exact tested Python 3.12 environment; install
it with `pip install -r requirements-lock.txt` from this folder for pinned versions.
The committed STL and JSON are sufficient to run the example; `manifold3d` is only
used by `examples/make_example.py` to regenerate the frozen example CAD.

CLI stdout is JSON. Exit status: `0` pass, `1` fail, `2` input rejection.
Bad inputs return null timing; geometry resource limits return fail (`passed: false`, `verification: unresolved`) with the
already calculated timing. The API raises `InputError` for invalid input.

```python
import json
from pathlib import Path
from cncsim import simulate

path = Path("examples/pocket.json")
result = simulate(json.loads(path.read_text()), base_dir=path.parent, output_dir="output-pocket")
if result["validity"] == "valid":
    score = result["estimated_time_seconds"]  # lower is better
```

## Input contract

`examples/pocket.json` is a complete input. Unknown fields and movement types are
rejected to avoid silently dropping motion semantics. All coordinates and lengths
are **millimetres**, times seconds, speeds mm/min. All geometry shares one world
frame; there are no implicit transforms, offsets or setup changes.

| Field | Meaning |
|---|---|
| `units` | Must be `"mm"` |
| `target` | `{ "type": "mesh", "path": "part.stl" }`; fixed target solid |
| `stock` | Mesh, or `{ "type": "box", "min": [x,y,z], "max": [x,y,z] }` |
| `fixtures` | List of stock-format solids; empty list allowed |
| `tools` | Mapping from tool ID to cylindrical cutter/shaft/holder dimensions below |
| `initial_position`, `initial_tool` | Explicit tool-tip XYZ and already loaded tool |
| `travel_limits` | `{ "min": [x,y,z], "max": [x,y,z] }` for the **tool tip** in this frame |
| `moves` | Ordered structured movements below |
| `tolerance_mm` | Positive signed-distance geometry tolerance |
| `resolution_mm` | Positive cubic voxel pitch; reduce to investigate unresolved geometry or clearance |
| `rapid_mm_per_min` | Positive vector rapid speed |
| `tool_change_seconds` | Nonnegative duration per explicit change |
| `max_cells` | Optional grid budget, default 2,000,000; maximum 20,000,000 |

Paths are relative to the plan directory in the CLI and `base_dir` in the API.
Meshes must be finite, closed, consistently wound positive-volume solids with no
self intersections, overlapping shells or degenerate geometry. Watertightness and
winding are checked; comprehensive self-intersection certification is not provided.
Use prevalidated CAD tessellations. STL/PLY are recommended; units are never inferred.
Target bytes are hashed and are never modified. Use a separate output directory.

Each tool has six positive dimensions:

```json
{
  "diameter_mm": 4,
  "flute_length_mm": 8,
  "shaft_diameter_mm": 4,
  "shaft_length_mm": 4,
  "holder_diameter_mm": 6,
  "holder_length_mm": 4
}
```

The flat cutting cylinder extends from tip Z through `flute_length_mm`; the
noncutting shaft starts there, and the holder starts at the shaft end. Cylinders
are coaxial along +Z. The cutter's bottom and sides cut, allowing plunges.
No taper, ball nose, spindle body, runout, deflection or material physics is modeled.

Supported movements:

```json
{"type":"cut", "to":[4,5,3], "feed_mm_per_min":120}
{"type":"rapid", "to":[4,5,8]}
{"type":"dwell", "seconds":1}
{"type":"tool_change", "tool":"T2"}
```

Every translation is a continuous straight line, including simultaneous XYZ
motion. Positions persist between moves. Dwell does not remove material. An
explicit tool change installs the new geometry at the current tip and adds the
configured duration, including repeated same-tool changes. The initial loaded
tool is free. Retracts, approach moves and travel to/from a tool-change location
must be explicit. Tool-changing hardware motion is outside the model.

**No G-code dialect is supported.** G-code, arcs, spindle commands, canned cycles,
rotary axes, cutter compensation, coordinate modes and unsupported JSON commands
are rejected. Convert them externally into explicit supported movements with
known semantics before calling the simulator.

## Removal, constraints and numerical uncertainty

The stock is a dense cubic grid. For each cell the simulator tracks:

- **lower**: the whole cell is definitely material;
- **upper**: the cell may contain material;
- **nominal**: center-sampled material for the exported approximation and volume estimate.

Continuous swept-cylinder membership is solved analytically: the cylinder's Z
interval restricts the path parameter, then the closest XY point on that interval
is evaluated. This handles plunges and diagonal motion without gaps between path
samples. Expanding the cylinder radius and both Z caps by the cell half-diagonal
plus a numerical guard encloses possible intersections. Shrinking them establishes
full-cell removal. Stock lower occupancy subtracts possible removal; upper
occupancy subtracts definite removal. The target is only queried, never machined.

Target and mesh occupancy use Trimesh signed distances (positive inside), batched
for memory. See [Trimesh proximity documentation](https://trimesh.org/trimesh.proximity.html).
Boxes use analytic cell overlap. The grid encloses stock, target **and fixtures**;
small obstacles are represented by possible occupancy even without an interior
cell center. The cell budget prevents an unbounded grid allocation.

Geometry tolerance has an explicit volumetric meaning: final stock must lie within
the target dilated by tolerance, and must contain the target eroded by tolerance.
This is not a surface-finish test or a general surface Hausdorff certification.
Features thinner than twice the tolerance may disappear under this contract.
Material removed inside the required target core is a gouge; stock outside the
allowed target envelope is excess. An initially undersized stock is also checked.

The simulator checks continuous cutter/shaft/holder sweeps against fixtures,
shaft/holder against stock, noncutting rapid cutter movement against stock, and
all tip segment endpoints against travel limits. A straight segment between
in-limit endpoints stays in the axis-aligned travel box. Cutting edges touching
stock during a `cut` are expected and remove material. Cutter placement at the
initial pose or a tool change must be clear of stock. Dwell preserves stock.

Stock collisions use pre-move stock. If a cutter could clear a suspected
shaft/holder collision earlier within the same move, the gate **fails**, with `verification: unresolved` unless another definite violation is established. This conservative treatment
avoids asserting an invalid collision ordering; splitting the move or refining
resolution can help. Exact touching/near-clearance can also fail as unresolved;
geometry tolerance is never used to forgive fixture or rapid collisions.

A definite violation or remaining uncertainty makes the plan `invalid` with
`passed: false`; only fully resolved checks produce `valid` and `passed: true`. No nominal mesh or volume
estimate can override this. Conservative bounds can be wide, especially near
surfaces and on coarse grids. Smaller cells cost memory and time, and do not
necessarily resolve exact tangencies. The distance backend uses floating point,
not formally verified exact arithmetic; guarantees are conditional on valid input
meshes and reliable distance queries. This is an optimization-loop simulator, not
a machine safety certification.

## Timing and output

Cutting time is total commanded cut path length / feed, including air cuts,
plunges and retracts. Rapid time is Euclidean path length / configured rapid
speed. Add explicit dwells and each fixed tool-change duration. No acceleration,
jerk, controller lookahead, axis-specific speed caps, blending, spindle ramp,
loading or probing is modeled. These are ideal constant-speed estimates, **not
controller-accurate cycle times**. The entire submitted plan is timed even when
invalid, but only valid plans can enter a time comparison. Feeds are trusted commanded
inputs: the caller must bound them to physically admissible values. This simulator
does not infer cutting-force or machine feed capability limits, so unconstrained
feed optimization would trivially favor arbitrarily large feeds.

The JSON includes `validity`, `issues` with codes, certainty and affected zero-based
`moves`, `estimated_time_seconds`, and `time_breakdown` (`cutting`, `rapid`, `dwell`,
`tool_changes`). Move `-1` denotes initial placement. Final-state geometry issues
have `moves: []`, since excess or initially missing material may have no responsible
movement; per-cut gouging issues identify the responsible moves. Additional fields
record the target hash, grid uncertainty, bounded and nominal volumes, and artifacts.

With `--output` / `output_dir`, files include:

- `result.json` and `trajectory.json` (start/end tip poses, tool IDs, elapsed time).
- `final_stock.ply`, the unsmoothed nominal voxel boundary mesh.
- `final_stock_lower.ply` and `final_stock_upper.ply`, bounding stock meshes.
- `states/00000.npz`, etc., for the initial stock and each move boundary. Each has
  XYZ-indexed `lower`, `upper`, `nominal` boolean grids, `origin`, `pitch`, position,
  tool ID, move index and elapsed time. Cell `(i,j,k)` spans `origin + pitch*[i,j,k]`
  through that location plus one pitch on each axis.

The API's optional `on_step(state)` callback gets independent flat occupancy arrays
with `shape` to reshape them. These are move-boundary snapshots, not animation
frames; use the trajectory or split movements to obtain finer visualization steps.
No snapshots are kept in memory when neither a callback nor output is requested.
Resource-limit results do not have stock artifacts. Exported meshes are voxel
approximations and can contain nonmanifold corner contacts; they are not replacement CAD.

## Verification example

The example starts with a 12 × 10 × 6 mm block. A radius-2 mm flat mill plunges to
Z=3 at (4,5), traverses to (8,5), and retracts, making a capsule-shaped pocket:

- Overall pocket: 8 × 4 mm; depth: 3 mm.
- Analytical removed volume: `3 * (4*4 + pi*2^2) = 85.699112 mm³`.
- Frozen target uses 128-sided circular ends; its tessellation differs from the
  analytical removed volume by about 0.01514 mm³.
- At 0.2 mm resolution, nominal removed volume is 85.92 mm³ (about 0.26% error).
- At 0.6 mm tolerance the plan passes. Estimated time: 7 s cutting + 0.2 s rapid
  + 1 s dwell + 4 s tool change = **12.2 s**.
- Doubling feed preserves validity and reduces estimated time to **8.7 s**.

Tests cover pocket dimensions/volume, target immutability, stock bounds and exports,
overdeep cuts, missed material, rapid-through-stock, cutter/shaft/holder fixture
collisions, noncutting stock collisions, overtravel, tiny fixtures, undersized stock,
uncertainty, continuous diagonal sweeps, hand-calculated timing, mesh stock, invalid
inputs and resource limits.


Indexed machine study: see [INDEXED-MACHINING.md](INDEXED-MACHINING.md) for the
standalone downloaded Haas UMC-750, the multi-face housing, indexed B/C API,
actual swept-stock playback and explicit limits.
