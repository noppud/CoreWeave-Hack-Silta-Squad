"""Demonstrate the check learning pipeline using real evidence.

Per §7: demonstrate proposal from real failure, validation with acceptance, and
rejection of an over-broad proposal.
"""

import asyncio
import json

from silta import checks, simulation, toolpaths
from silta.check_learning import (
    CheckProposal,
    SourceKind,
    ValidationDecision,
    propose_check,
    validate_check,
)
from silta.check_templates import SweptFixtureClearanceParams, TemplateId
from silta.domain import Disposition, utc_now
from silta.evaluation import CaseOutcome, load_fixtures
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, reach_repaired_plan
from silta.policy import POLICY_V0


async def main():
    print("=" * 80)
    print("DEMONSTRATION: Check Learning Pipeline")
    print("=" * 80)
    print()

    # Step 1: Get the real clamp collision failure
    print("Step 1: Simulating reach_repaired_plan() against DEMO_SPEC/DEMO_SHOP")
    print("-" * 80)

    spec = DEMO_SPEC
    shop = DEMO_SHOP
    plan = reach_repaired_plan()

    # Run checks
    preflight_results = checks.run_preflight_checks(spec, shop, plan)
    blocking_preflight = checks.blocking(preflight_results)

    print(f"Preflight checks: {len(blocking_preflight)} blocking failures")

    if not blocking_preflight:
        # Compile trajectory
        trajectory = toolpaths.compile_plan(spec, shop, plan)

        # Run path checks
        path_results = checks.run_path_checks(spec, shop, plan, trajectory, POLICY_V0)
        blocking_path = checks.blocking(path_results)
        print(f"Path checks: {len(blocking_path)} blocking failures")

        if not blocking_path:
            # Simulate
            print("Running simulation...")
            sim_result, _replay = simulation.simulate(spec, shop, plan, trajectory)
            print(f"Simulation status: {sim_result.status}")
            print(f"Collisions: {len(sim_result.collisions)}")

            if sim_result.collisions:
                for col in sim_result.collisions[:3]:
                    print(
                        f"  - {col.colliding_part} vs {col.obstacle_id} at segment {col.segment_id}"
                    )

            # Create fake fixture for this case
            from silta.evaluation import Fixture, FixtureExpectation

            fake_fixture = Fixture(
                fixture_id="demo-clamp-collision",
                split="development",
                description="Real clamp collision from reach_repaired_plan",
                spec=spec,
                shop=shop,
                seed_plan=plan,
                expectation=FixtureExpectation(
                    disposition=Disposition.FAILED_SIMULATION,
                    blocking_check_ids=(),
                    geometry={"clearance_mm": 5.0, "clamp_top_mm": 12.0},
                ),
            )

            # Create failure evidence
            failure_evidence = CaseOutcome(
                fixture_id="demo-clamp-collision",
                policy_version="policy-v0",
                disposition=Disposition.FAILED_SIMULATION,
                blocking_check_ids=(),
                attempts=1,
                simulations_run=1,
                simulation_seconds=sim_result.elapsed_s,
                estimated_machining_seconds=None,
                clearance_mm=plan.clearance_mm,
                min_fixture_clearance_mm=shop.min_fixture_clearance_mm,
                max_residual_mm=None,
                max_gouge_mm=None,
                tool_changes=0,
                wall_seconds=1.0,
                matched_expectation=False,
                mismatch_reason=None,
            )

            print()
            print("Step 2: Proposing check from failure evidence")
            print("-" * 80)

            proposal = propose_check(failure_evidence, "policy-v0", fake_fixture, trajectory)

            if proposal:
                print(f"Proposal ID: {proposal.proposal_id}")
                print(f"Template: {proposal.template_id}")
                print(f"Check ID: {proposal.check_id}")
                print(f"Explanation: {proposal.explanation[:100]}...")
                print(f"Parameters: {json.dumps(proposal.parameters, indent=2)}")

                print()
                print("Step 3: Validating the proposed check")
                print("-" * 80)

                # Load validation fixtures
                validation_suite = load_fixtures("development")
                print(f"Validation suite: {len(validation_suite)} fixtures")

                report = await validate_check(proposal, validation_suite, "policy-v0")

                print()
                print("VALIDATION REPORT")
                print(f"  Report ID: {report.report_id}")
                print(f"  Decision: {report.decision}")
                print(f"  Structural valid: {report.structural_valid}")
                print(f"  False positives: {report.false_positives}")
                print(f"  False negatives: {report.false_negatives}")
                print(f"  Runtime: {report.runtime_seconds:.2f}s")
                print(f"  Cases evaluated: {len(report.cases)}")

                if report.rejection_reason:
                    print(f"  Rejection reason: {report.rejection_reason}")

                if report.decision == ValidationDecision.ACCEPT:
                    print()
                    print("✓ PROPOSAL ACCEPTED")
                else:
                    print()
                    print("✗ PROPOSAL REJECTED")

            else:
                print("No proposal generated (fixtures missing or other reason)")

    print()
    print("Step 4: Demonstrating rejection of over-broad proposal")
    print("-" * 80)

    # Create deliberately over-broad proposal
    bad_params = SweptFixtureClearanceParams(
        clearance_margin_mm=50.0,  # Maximum allowed but too strict
        check_cutter=True,
        check_shank=True,
        check_holder=True,
        only_non_cutting=True,
    )

    bad_proposal = CheckProposal(
        proposal_id="deliberately-bad",
        parent_policy_version="policy-v0",
        template_id=TemplateId.SWEPT_FIXTURE_CLEARANCE,
        parameters=bad_params.model_dump(),
        check_id="over_broad_clearance",
        intended_stage="path",
        intended_failure_code="collision",
        source_kind=SourceKind.HUMAN,
        explanation="Deliberately over-strict check for demonstration",
        applicability_note="Too strict",
        proposed_at=utc_now(),
    )

    print(f"Testing over-broad proposal with {bad_params.clearance_margin_mm}mm margin")
    validation_suite = load_fixtures("development")
    bad_report = await validate_check(bad_proposal, validation_suite, "policy-v0")

    print()
    print("OVER-BROAD PROPOSAL VALIDATION")
    print(f"  Decision: {bad_report.decision}")
    print(f"  False positives: {bad_report.false_positives}")
    print(f"  Cases evaluated: {len(bad_report.cases)}")

    if bad_report.rejection_reason:
        print(f"  Rejection reason: {bad_report.rejection_reason}")

    if bad_report.decision == ValidationDecision.REJECT:
        print()
        print("✓ OVER-BROAD PROPOSAL CORRECTLY REJECTED")
    else:
        print()
        print("⚠ Over-broad proposal was accepted (validation suite may lack suitable cases)")

    print()
    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
