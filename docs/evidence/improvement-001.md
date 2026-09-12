# Cross-Task Improvement 001 — Fixture Envelope Check

**Summary:** A recurring simulation failure (low traverse hitting a fixture) was promoted to an earlier geometric check, catching the failure before simulation on later parts while preserving correctness on all boundary cases.

## What Failed

Under baseline policy (policy-v0), fixture `dev_03_clamp_collision` passed all preflight checks but failed in the stock-and-collision simulator: a non-cutting traverse with insufficient clearance struck a fixture solid. The simulator caught this, but simulation is expensive compared to geometric checks.

## Evidence Produced

Development runs under policy-v0 showed:
- 8 fixtures evaluated
- 4 simulations run
- 1 simulation failure (`dev_03_clamp_collision` — traverse collision with fixture)
- 8/8 expectations matched (0 false accepts, 0 false rejects)

The failure pattern: a compiled trajectory whose non-cutting segment swept tool envelope overlaps a fixture solid.

## What Changed

Promoted the `path_fixture_envelope` check (version 2) from simulator into PATH validation stage under policy-v1.

**Mechanism:** For every non-cutting traverse, test each modelled tool part (cutter, shank, holder) at its own radius and height against each fixture solid:
- Definite overlap → blocking failure before simulation
- Clearance below shop minimum but no definite overlap → warning, defer to simulator
- Uncertain cases → defer to simulator (avoids false rejection)

**Lineage:** Version 1 of this check was WRONG (compared holder radius at tip height) and falsely rejected holdout fixture `holdout_03_valid_complex`. The boundary fixtures caught this. Version 2 corrected it.

## What Was Measured

**Development set (8 fixtures):**
- policy-v0: 8/8 matched, 0 false accepts, 0 false rejects, 4 simulations
- policy-v1: 8/8 matched, 0 false accepts, 0 false rejects, 3 simulations
- **Result:** 1 simulation saved (`dev_03_clamp_collision` moved from `failed_simulation` to `failed_checks`)

**Holdout set (4 fixtures, evaluated once after policy-v1 frozen):**
- policy-v0: 4/4 matched, 0 false accepts, 0 false rejects, 2 simulations
- policy-v1: 4/4 matched, 0 false accepts, 0 false rejects, 2 simulations
- **Result:** 0 simulations saved (the check did not trigger on holdout cases; correctness preserved)

**Aggregate:**
- Expectation matches: 12/12 (100%) under both policies
- False accepts: 0 under both policies
- False rejects: 0 under both policies
- Correctness preserved on all known-valid and known-invalid boundary cases

## Which Split

Development set was used for tuning and iterative check refinement (including the version 1 → version 2 correction). Holdout was evaluated once after policy-v1 was frozen and has never been used for tuning.

## External Gate (Outstanding)

**ARIA analysis** is an outstanding external gate:
- Requires W&B Multi-tenant Cloud with organization Smart features
- Requires uploaded baseline batch and ARIA conversation in W&B UI
- No W&B API key is currently configured
- No runs have been uploaded
- No ARIA conversation has occurred

The intended ARIA prompt (from docs/architecture.md section 11):
> Compare policy v0 development runs. Which failure consumes the most avoidable simulation calls? Cite run IDs. Propose one conservative early check and valid boundary cases that could be falsely rejected. Do not use holdout results.

This change was human-authored after reviewing the development pattern. When the external gate is satisfied, the actual ARIA response will be recorded and compared against this implemented change.

## Honest Limitations

- **Small corpus:** 12 fixtures (8 dev, 4 holdout) is a small evaluation set
- **Counts, not claims:** These are raw counts demonstrating mechanism, not performance guarantees
- **One saved simulation:** Demonstrates the check works; not a performance result
- **Holdout showed no savings:** The specific holdout cases did not trigger the promoted check, which is legitimate — holdout validates correctness, not savings on every case
- **ARIA not yet run:** This documents what was implemented and measured locally; the intended ARIA workflow remains an external gate

## Files

- Policy: `silta/policy.py` (POLICY_V1)
- Check: `silta/checks.py` (`check_path_fixture_envelope`)
- Fixtures: `fixtures/development/*.json`, `fixtures/holdout/*.json`
- Evaluation: `notebooks/evaluations.py` (runnable marimo app)
- Recommendation: `policies/aria-recommendation-001.md` (full provenance and lineage)

This is a complete and honest record of what was implemented, what was measured, and what remains an external gate. No fabricated results. No invented ARIA conversations.
