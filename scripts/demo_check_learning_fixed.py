"""Demonstrate the check learning pipeline with CORRECT validation.

Fixes both bugs:
1. Good proposal is ACCEPTED (catches original collision)
2. Over-broad proposal is REJECTED (falsely blocks known-valid boundary case)
"""

import asyncio
import json
from pathlib import Path

from silta import checks, simulation, toolpaths
from silta.check_learning import (
    CheckProposal,
    SourceKind,
    ValidationDecision,
    validate_check,
)
from silta.check_templates import SweptFixtureClearanceParams, TemplateId
from silta.domain import utc_now
from silta.evaluation import Fixture
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, reach_repaired_plan


def load_promotion_fixtures() -> list[Fixture]:
    """Load promotion fixtures for validation."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "promotion"
    fixtures: list[Fixture] = []
    for path in sorted(fixtures_dir.glob("*.json")):
        fixtures.append(Fixture.from_file(path))
    return fixtures


async def main():
    print("=" * 80)
    print("FIXED DEMONSTRATION: Check Learning Pipeline")
    print("=" * 80)
    print()

    # Step 1: Verify the clamp collision exists
    print("Step 1: Verify reach_repaired_plan() collision")
    print("-" * 80)

    spec = DEMO_SPEC
    shop = DEMO_SHOP
    plan = reach_repaired_plan()

    print(f"Plan: {plan.plan_id}, clearance: {plan.clearance_mm}mm")
    print(f"Clamp front top: Z={shop.fixtures[0].z_max_mm}mm")
    print(
        f"Expected gap: {plan.clearance_mm} - {shop.fixtures[0].z_max_mm} = "
        f"{plan.clearance_mm - shop.fixtures[0].z_max_mm}mm (NEGATIVE = collision)"
    )

    # Compile and check
    trajectory = toolpaths.compile_plan(spec, shop, plan)
    sim_result, _replay = simulation.simulate(spec, shop, plan, trajectory)

    print(f"Simulation: {sim_result.status}, collisions: {len(sim_result.collisions)}")
    if sim_result.collisions:
        col = sim_result.collisions[0]
        print(
            f"  First collision: {col.colliding_part} vs {col.obstacle_id} "
            f"at ({col.x_mm}, {col.y_mm}, {col.z_mm}), penetration {col.penetration_mm}mm"
        )

    # Also test existing path_fixture_envelope check
    from silta.policy import POLICY_V1

    path_results_v1 = checks.run_path_checks(spec, shop, plan, trajectory, POLICY_V1)
    fixture_check = [r for r in path_results_v1 if r.check_id == "path_fixture_envelope"]
    if fixture_check:
        fc = fixture_check[0]
        print(
            f"  path_fixture_envelope v2: {fc.status}, gap={fc.actual}mm (required {fc.required}mm)"
        )
        print("  ^ This is what our template must reproduce")

    print()
    print("Step 2: Propose check with correct parameters")
    print("-" * 80)

    # Create proposal with parameters derived from shop
    params = SweptFixtureClearanceParams(
        clearance_margin_mm=shop.min_fixture_clearance_mm,  # 3.0mm from shop
        check_cutter=True,
        check_shank=True,
        check_holder=True,
        only_non_cutting=True,
    )

    good_proposal = CheckProposal(
        proposal_id="good-proposal",
        parent_policy_version="policy-v0",
        template_id=TemplateId.SWEPT_FIXTURE_CLEARANCE,
        parameters=params.model_dump(),
        check_id="proposed_fixture_clearance",
        intended_stage="path",
        intended_failure_code="collision",
        source_kind=SourceKind.RUNTIME_FAILURE,
        source_failure_fixture_id="prom_02_original_collision",  # Matches promotion fixture
        source_trajectory_hash=trajectory.trajectory_hash,
        explanation=(
            f"Clearance {plan.clearance_mm}mm insufficient for clamp at "
            f"Z={shop.fixtures[0].z_max_mm}mm. Propose check with "
            f"{params.clearance_margin_mm}mm margin from shop profile."
        ),
        applicability_note=f"Shops with fixtures, {params.clearance_margin_mm}mm margin",
        proposed_at=utc_now(),
    )

    print(f"Proposal ID: {good_proposal.proposal_id}")
    print(f"Source fixture: {good_proposal.source_failure_fixture_id}")
    print(f"Parameters: {json.dumps(good_proposal.parameters, indent=2)}")

    print()
    print("Step 3: Validate against promotion fixtures")
    print("-" * 80)

    promotion_fixtures = load_promotion_fixtures()
    print(f"Loaded {len(promotion_fixtures)} promotion fixtures:")
    for f in promotion_fixtures:
        print(f"  - {f.fixture_id}: {f.description[:60]}...")

    print()
    print("Validating good proposal...")
    good_report = await validate_check(good_proposal, promotion_fixtures, "policy-v0")

    print()
    print("=" * 80)
    print("VALIDATION REPORT: GOOD PROPOSAL")
    print("=" * 80)
    print(f"Decision: {good_report.decision}")
    print(f"Structural valid: {good_report.structural_valid}")
    print(f"False positives: {good_report.false_positives}")
    print(f"False negatives: {good_report.false_negatives}")
    print(f"Runtime: {good_report.runtime_seconds:.3f}s")
    print(f"Cases evaluated: {len(good_report.cases)}")

    if good_report.rejection_reason:
        print(f"Rejection reason: {good_report.rejection_reason}")

    print()
    print("Per-case results:")
    for case in good_report.cases:
        status = "✓" if case.matched else "✗"
        print(
            f"  {status} {case.fixture_id}: "
            f"expected={case.expected_disposition.value}, "
            f"actual={case.actual_disposition.value}, "
            f"check_fired={case.actual_check_fired}"
        )
        if case.message:
            print(f"     {case.message}")

    if good_report.decision == ValidationDecision.ACCEPT:
        print()
        print("✓✓✓ GOOD PROPOSAL ACCEPTED ✓✓✓")
    else:
        print()
        print("✗✗✗ BUG: GOOD PROPOSAL REJECTED ✗✗✗")

    print()
    print("=" * 80)
    print("Step 4: Test over-broad proposal (50mm margin)")
    print("=" * 80)

    bad_params = SweptFixtureClearanceParams(
        clearance_margin_mm=50.0,  # Absurdly high
        check_cutter=True,
        check_shank=True,
        check_holder=True,
        only_non_cutting=True,
    )

    bad_proposal = CheckProposal(
        proposal_id="over-broad",
        parent_policy_version="policy-v0",
        template_id=TemplateId.SWEPT_FIXTURE_CLEARANCE,
        parameters=bad_params.model_dump(),
        check_id="over_broad_clearance",
        intended_stage="path",
        intended_failure_code="collision",
        source_kind=SourceKind.HUMAN,
        explanation="Deliberately over-strict for testing rejection",
        applicability_note="Too strict",
        proposed_at=utc_now(),
    )

    print(f"Testing over-broad proposal with {bad_params.clearance_margin_mm}mm margin")
    print("Expected: REJECT (falsely blocks prom_01_boundary_exact with 3.0mm gap)")
    print()

    bad_report = await validate_check(bad_proposal, promotion_fixtures, "policy-v0")

    print("VALIDATION REPORT: OVER-BROAD PROPOSAL")
    print(f"Decision: {bad_report.decision}")
    print(f"False positives: {bad_report.false_positives}")
    print(f"Cases evaluated: {len(bad_report.cases)}")

    if bad_report.rejection_reason:
        print(f"Rejection reason: {bad_report.rejection_reason}")

    print()
    print("Per-case results:")
    for case in bad_report.cases:
        status = "✓" if case.matched else "✗"
        print(
            f"  {status} {case.fixture_id}: "
            f"expected={case.expected_disposition.value}, "
            f"actual={case.actual_disposition.value}, "
            f"check_fired={case.actual_check_fired}"
        )
        if case.message:
            print(f"     {case.message}")

    if bad_report.decision == ValidationDecision.REJECT:
        print()
        print("✓✓✓ OVER-BROAD PROPOSAL CORRECTLY REJECTED ✓✓✓")
        print(
            "This rejection, driven by boundary fixture prom_01_boundary_exact, "
            "is the most valuable output of F4."
        )
    else:
        print()
        print("✗✗✗ BUG: OVER-BROAD PROPOSAL ACCEPTED ✗✗✗")

    print()
    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
