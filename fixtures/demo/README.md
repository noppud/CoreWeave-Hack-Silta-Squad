# Demo Fixture Files

This directory contains synthetic demonstration assets for **FIXTURE BLOCK 01**, a team-authored test part used to demonstrate the Silta CNC agent's capabilities.

## Files

### `fixture-block-01.png`
A fully dimensioned 2-view engineering drawing (top view + front section) showing:
- Stock: 80 × 60 × 20 mm, 6061-T6 aluminium
- One rounded rectangular pocket (40 × 20 mm, R3, depth 12 mm)
- Four Ø6 blind holes (depth 8 mm) at the corners
- Dimension callouts with drawing references (A1-A3 for pocket, B1-B4 for holes)
- Drill tip convention note: "HOLE DEPTH IS FULL-DIAMETER CYLINDRICAL DEPTH; 118° POINT REACHES 1.803 DEEPER"
- Title block with material, units, scale, and origin note

**This drawing is synthetic**: it is generated entirely from `silta/fixtures.py::DEMO_SPEC` by `scripts/make_demo_drawing.py` and can never drift from the specification. It is a demonstration asset only, not a real manufacturing drawing.

### `fixture-block-01-undimensioned.png`
The same top view and front section as above, but with **all dimension text, dimension lines, extension lines, and labels removed**. This represents the "undimensioned photograph" case where the agent must request dimensions rather than guess them from the drawing.

### `oracle.json`
Independent ground truth for the demonstration, including:
- Analytic geometry calculations (stock volume, pocket volume, hole volume, part volume)
- Explicit derivation formulas (e.g., `pocket_area = w*h - (4-π)*r²*d`)
- Coordinate system conventions (origin at lower-left, Z=0 at top face)
- Fixture/clamp geometry from `DEMO_SHOP`
- Home position and minimum clearance constraints
- Tool specifications (EM6-S, EM6-L, DR6)
- Three-attempt demonstration sequence:
  1. **Attempt 0** (naive): EM6-S + clearance 5mm → **reach failure** (12mm depth vs 8mm cutting length)
  2. **Attempt 1** (reach fixed): EM6-L + clearance 5mm → **collision in simulation** (traverse Z=5mm vs clamp top Z=12mm → -7mm gap)
  3. **Attempt 2** (valid): EM6-L + clearance 15mm → **pass** (traverse Z=15mm vs clamp top Z=12mm → +3mm gap = minimum required)

**Important**: The oracle is derived analytically from the drawing specification (`silta/fixtures.py::expected_geometry()`), **NOT** from the CAD builder (`silta/cad.py`). This ensures the builder cannot certify itself.

## Regenerating the Drawings

To regenerate both PNG files:

```bash
cd /path/to/konsta-demo-hackathon
PYTHONPATH=$PWD uv run python scripts/make_demo_drawing.py
```

The script reads `silta/fixtures.py::DEMO_SPEC` and outputs:
- `fixtures/demo/fixture-block-01.png` (dimensioned)
- `fixtures/demo/fixture-block-01-undimensioned.png` (undimensioned)

Generation is deterministic (given the same spec and matplotlib version).

## Verification

To verify the oracle matches the expected geometry:

```python
import json
from silta.fixtures import expected_geometry

with open("fixtures/demo/oracle.json") as f:
    oracle = json.load(f)

expected = expected_geometry()

assert abs(oracle["stock"]["volume_mm3"] - expected["stock_volume_mm3"]) < 0.01
assert abs(oracle["pocket"]["volume_mm3"] - expected["pocket_volume_mm3"]) < 0.01
assert abs(oracle["holes"]["volume_per_hole_mm3"] - expected["hole_volume_mm3"]) < 0.01
assert abs(oracle["part_volume"]["value_mm3"] - expected["part_volume_mm3"]) < 0.01
```

## Attribution

These fixtures are **team-authored demonstration assets**, not real manufacturing drawings. They are used solely to demonstrate the Silta agent's ability to:
1. Parse dimensioned engineering drawings
2. Detect missing dimensions and request them
3. Plan machining operations
4. Detect reach and clearance violations
5. Repair invalid plans

**NOT FOR MANUFACTURE**: These are synthetic test cases with simplified geometry and assumed material properties.
