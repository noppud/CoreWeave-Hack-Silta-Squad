# Validation Policy Versions

This directory records the lineage of promoted validation checks and planner prompt revisions.

## Promotion Process

A model or analysis tool (such as ARIA) may PROPOSE a rule, but a rule only enters the validator as **reviewed code**, versioned, with recorded evidence:

1. **Development set comparison:** Run the candidate policy on the frozen development set (currently 8 fixtures) including known-valid boundary cases.
2. **Correctness verification:** Confirm zero false accepts (known-invalid plans passing) and zero false rejects (known-valid plans failing). Any false rejection requires the check to be revised or the boundary case to be updated if the expectation was wrong.
3. **Holdout evaluation:** After the candidate policy is frozen, evaluate it on the untouched holdout set (currently 4 fixtures) exactly once. Holdout results are recorded but NEVER used to tune the policy.
4. **Code review:** The promoted check is implemented as deterministic geometric code in `silta/checks.py`, versioned, with its check ID and version recorded in `silta/policy.py`.
5. **Evidence recording:** The comparison results, boundary cases tested, and any false positive/negative findings are documented in this directory (e.g., `aria-recommendation-001.md`).

## Development/Holdout Discipline

- **Development fixtures** (`fixtures/development/`) are used for tuning, boundary testing, and iterative refinement.
- **Holdout fixtures** (`fixtures/holdout/`) are evaluated ONCE per policy version, AFTER the policy is frozen, to validate that correctness is preserved on unseen cases.
- If holdout results ever inform tuning or prompt revision, that holdout set must be RETIRED and replaced with fresh unseen fixtures.

The split prevents overfitting to the evaluation set: a policy that passes development and holdout has been tested against known patterns AND unseen cases.

## Policy Lineage

- **policy-v0:** Baseline. Schema validation, preflight geometry checks, and tool reach checks. Clamp clearance failures are discovered only by simulation.
- **policy-v1:** Baseline plus promoted `path_fixture_envelope` check (version 2). Rejects non-cutting traverses whose swept tool envelope definitely overlaps a fixture, before simulation. Warns when clearance is thin but defers uncertain cases to simulation to avoid false rejection.

See individual recommendation files (e.g., `aria-recommendation-001.md`) for the provenance, measured results, and external gates for each policy revision.

## Check Versioning

Each check has:
- **check_id:** Stable identifier (e.g., `path_fixture_envelope`)
- **check_version:** Increment when the check's logic changes (e.g., version 1 → version 2 after correcting the holder-radius bug)
- **policy_version:** The policy that enables the check (e.g., `policy-v1`)

Versioning allows comparisons to attribute changes to the validator versus model variation, and preserves the correction history (e.g., version 1 of `path_fixture_envelope` was wrong and falsely rejected a valid holdout case; version 2 fixed it).

## File Naming

Recommendation files are numbered sequentially:
- `aria-recommendation-001.md` — first cross-task improvement
- `aria-recommendation-002.md` — second improvement (if any)

Each file records:
- The analysis prompt and intended workflow
- What was actually implemented (human or ARIA-recommended)
- Measured comparison on development and holdout
- External gates satisfied or outstanding
- Honest limitations

No fabricated results. No invented ARIA conversations. Complete honesty about what is real and what remains an external gate.
