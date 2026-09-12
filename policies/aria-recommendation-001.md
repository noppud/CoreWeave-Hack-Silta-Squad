# ARIA Recommendation 001 — Fixture Envelope Check

**Status:** ARIA analysis is an **OUTSTANDING EXTERNAL GATE**. This recommendation records the intended workflow and documents what was actually implemented and measured locally.

## External Gate Requirements (Not Yet Satisfied)

ARIA analysis requires:
- W&B Multi-tenant Cloud with organization Smart features enabled
- A W&B team project with baseline batch uploaded
- ARIA conversation using uploaded run metrics

**Current state:** No W&B API key is configured; no runs have been uploaded to a W&B project; no ARIA conversation has occurred.

## Intended ARIA Prompt

When the external gate is satisfied, the following prompt from docs/architecture.md section 11 will be put to ARIA:

> Compare policy v0 development runs. Which failure consumes the most avoidable simulation calls? Cite run IDs. Propose one conservative early check and valid boundary cases that could be falsely rejected. Do not use holdout results.

This prompt is designed to identify recurring simulation failures that could be caught earlier with geometric checks.

## Implemented Change (Human-Authored and Measured Locally)

**Change:** The `path_fixture_envelope` check was promoted from the stock/collision simulator into the PATH validation stage.

**Check ID:** `path_fixture_envelope`
**Check Version:** 2
**Policy Version:** `policy-v1` enables this check
**Provenance:** Human-authored after reviewing policy-v0 development run patterns

### Mechanism

For every non-cutting traverse (rapid, retract, tool change), the check tests each modelled tool part (cutter, shank, holder) at its OWN radius and its OWN height above the tool tip against each fixture solid:

- **Blocking failure:** A definite geometric overlap between the swept tool envelope and a fixture solid blocks the plan before simulation.
- **Warning only:** When clearance is thinner than the shop's declared minimum but no definite overlap exists, the check issues a warning and defers to the simulator rather than falsely rejecting a potentially valid path.
- **Uncertain cases:** Marginal cases remain simulator-evaluated to avoid false rejection of valid paths.

This check operates on compiled trajectory geometry, not on abstract plan parameters, so it sees the actual swept envelopes.

### Check Lineage and Correction

**Version 1 (WRONG):** An initial implementation compared the holder's radius against the tool tip's height, which falsely rejected `holdout_03_valid_complex`, a known-valid fixture. The frozen boundary fixtures caught this error.

**Version 2 (CURRENT):** Corrected to compare each tool part's radius at its own height above the tip, eliminating the false rejection while preserving the intended collision detection.

The failure and correction of version 1 is the most credible part of this story and demonstrates the value of boundary-case fixtures.

## Measured Results

Development set (8 fixtures):
- **policy-v0:** 8/8 expectations matched, 0 false accepts, 0 false rejects, 4 simulations run
- **policy-v1:** 8/8 expectations matched, 0 false accepts, 0 false rejects, 3 simulations run
- **Result:** 1 simulation saved (fixture `dev_03_clamp_collision` moved from `failed_simulation` to `failed_checks`)

Holdout set (4 fixtures, evaluated once after policy-v1 was frozen):
- **policy-v0:** 4/4 expectations matched, 0 false accepts, 0 false rejects, 2 simulations run
- **policy-v1:** 4/4 expectations matched, 0 false accepts, 0 false rejects, 2 simulations run
- **Result:** 0 simulations saved (the promoted check did not trigger on these holdout cases)

### Scoring Details

All cases under both policies:
- Expectation matches: 12/12 (100%)
- False accepts: 0
- False rejects: 0
- Correctness preserved: all known-valid plans remain valid, all known-invalid plans remain invalid

## Honest Limitations

- **Small corpus:** 12 fixtures (8 development, 4 holdout) is a small evaluation set.
- **Counts, not reliability claims:** These are raw counts demonstrating the check's mechanism, not performance guarantees for production use.
- **One saved simulation:** Saving one simulation on 8 development cases demonstrates the check works, but is not a performance result. The real value is catching this failure family before expensive simulation on future parts.
- **Holdout showed no savings:** The specific holdout cases did not trigger the promoted check, which is legitimate — holdout validates correctness preservation, not necessarily savings on every case.

## Next Steps

When W&B Multi-tenant Cloud access with organization Smart features is verified:
1. Upload baseline and revised batches to a W&B team project
2. Execute the ARIA prompt above using W&B UI
3. Record the actual ARIA response, cited run IDs, and conversation reference
4. Compare ARIA's recommendation against this implemented change
5. Update this file with the actual ARIA conversation outcome

Until then, this file records what was implemented, why it was implemented, and what was measured — with complete honesty about the provenance and the external gate that remains unsatisfied.
