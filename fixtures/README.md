# Silta CNC Evaluation Fixtures

Frozen evaluation corpus split before any tuning on 2026-09-12.

## Split Summary

| Split | Count | Purpose |
|-------|-------|---------|
| Development | 8 | Policy tuning, ARIA analysis, validator development |
| Holdout | 4 | Final unbiased evaluation after policy freeze |
| **Total** | **12** | Complete frozen corpus |

## Development Fixtures (8)

| ID | File | Failure Mode | Expected Disposition | Key Check(s) |
|----|------|--------------|----------------------|--------------|
| dev_01 | `01_valid_baseline.json` | None (valid) | `passed` | All pass |
| dev_02 | `02_tool_reach_fail.json` | Tool too short | `failed_checks` | `tool_cutting_reach` |
| dev_03 | `03_clamp_collision.json` | Low traverse hits clamp | `failed_simulation` (v0), `failed_checks` (v1) | `path_fixture_envelope` (v1) |
| dev_04 | `04_missing_tool.json` | Tool not in inventory | `failed_checks` | `tool_available` |
| dev_05 | `05_corner_radius_fail.json` | Tool radius too large | `failed_checks` | `pocket_corner_radius` |
| dev_06 | `06_excessive_depth.json` | Feature deeper than stock | `schema_invalid` | (PartSpec validation) |
| dev_07 | `07_boundary_clearance_exact.json` | **Boundary: exact minimum clearance** | `passed` | Guards v1 false-positive |
| dev_08 | `08_boundary_reach_exact.json` | **Boundary: exact reach** | `passed` | Guards false-positive |

**Boundary fixtures (dev_07, dev_08)** are the most critical: they must PASS with the exact minimum allowable values to guard promoted checks against false rejection.

## Holdout Fixtures (4)

| ID | File | Failure Mode | Expected Disposition | Key Check(s) |
|----|------|--------------|----------------------|--------------|
| holdout_01 | `01_unknown_units.json` | Unknown units | `schema_invalid` | (PartSpec validation) |
| holdout_02 | `02_boundary_corner_exact.json` | **Boundary: exact corner fit** | `passed` | Guards false-positive |
| holdout_03 | `03_valid_complex.json` | None (valid, complex) | `passed` | All pass |
| holdout_04 | `04_stickout_fail.json` | Stickout too short | `failed_checks` | `tool_stickout_clearance` |

## Independently Authored Expectations

Every fixture carries an `expectation` block with:

1. **Expected terminal disposition**: `passed`, `failed_checks`, `failed_simulation`, `schema_invalid`
2. **Blocking check IDs**: which checks must fail (if any)
3. **Analytic geometry**: volumes, depths, clearances computed by hand or closed-form arithmetic

The expectations are **not derived from the CAD builder or simulator**. They are calculated independently using:
- Basic solid geometry (rectangular pockets, cylindrical holes, conical drill tips)
- Drawing dimensions from the spec
- Explicit formulas documented in the `notes` field

This independence ensures the oracle can catch bugs in the CAD builder, compiler, or simulator.

## Usage Rules

1. **Development fixtures** are used for:
   - Initial policy baseline (POLICY_V0)
   - ARIA analysis of failures
   - Promoted check development (POLICY_V1)
   - Iterative tuning

2. **Holdout fixtures** are used **only** for:
   - Final evaluation after policy freeze
   - Unbiased measurement of improvement
   - **Never** for tuning or informing validator changes

3. **If holdout informs tuning**, it must be retired and replaced with fresh fixtures.

4. **Boundary fixtures** (dev_07, dev_08, holdout_02) are the most important: a policy that falsely rejects a valid boundary case has a critical false-positive bug.

## Coverage

The corpus covers:
- ✅ Valid baseline cases (simple and complex)
- ✅ Tool reach failure
- ✅ Fixture collision (low clearance)
- ✅ Missing tool reference
- ✅ Impossible corner radius
- ✅ Unknown units
- ✅ Excessive depth (breaks through stock)
- ✅ Tool stickout failure
- ✅ **Boundary cases at exact limits** (clearance, reach, corner radius)

## Verification

Every fixture is:
1. Schema-validated against domain contracts
2. Checked for internal consistency (spec/shop/plan hashes)
3. Verified against analytic expectations
4. Frozen — never edited to make a result green

**False acceptance** (passing a known-invalid recipe) is the most serious error. The scoring harness surfaces it prominently.
