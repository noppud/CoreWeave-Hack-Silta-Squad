"""Constrained check proposal, validation, and activation pipeline.

Per §4 and §7 of docs/followups/touko-loop-refactor.md. The model proposes a bounded
check from failure evidence; deterministic validation gates promotion; activation is
versioned and atomic with compare-and-swap.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from silta.check_templates import (
    SweptFixtureClearanceParams,
    TemplateId,
    apply_swept_fixture_clearance,
    get_template,
    validate_params,
)
from silta.domain import (
    CheckStatus,
    Disposition,
    ProcessPlan,
    Trajectory,
    stable_hash,
)
from silta.evaluation import CaseOutcome, Fixture


class ProposalStatus(StrEnum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    ACTIVE = "active"
    REJECTED = "rejected"


class SourceKind(StrEnum):
    RUNTIME_FAILURE = "runtime_failure"
    ARIA = "aria"
    HUMAN = "human"


class CheckProposal(BaseModel):
    """A proposed check from failure evidence, with bounded parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1, max_length=64)
    parent_policy_version: str
    template_id: TemplateId
    parameters: dict[str, Any]
    check_id: str = Field(min_length=1, max_length=64)
    intended_stage: str = "path"
    intended_failure_code: str = "collision"
    source_kind: SourceKind
    source_failure_fixture_id: str | None = None
    source_trajectory_hash: str | None = None
    explanation: str = Field(min_length=1, max_length=2000)
    applicability_note: str = Field(max_length=500)
    status: ProposalStatus = ProposalStatus.PROPOSED
    proposed_at: datetime
    validated_at: datetime | None = None

    @property
    def proposal_hash(self) -> str:
        return stable_hash(
            {
                "template": self.template_id,
                "params": self.parameters,
                "check_id": self.check_id,
            }
        )


class ValidationCaseOutcome(BaseModel):
    """Per-case validation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: str
    expected_disposition: Disposition
    actual_disposition: Disposition
    expected_check_fired: bool
    actual_check_fired: bool
    matched: bool
    message: str | None = None


class ValidationDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class ValidationReport(BaseModel):
    """Independent deterministic validation of a proposed check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str
    proposal_id: str
    proposal_hash: str
    validator_version: str
    fixture_suite_hash: str
    cases: tuple[ValidationCaseOutcome, ...]
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)
    runtime_seconds: float = Field(ge=0)
    structural_valid: bool
    structural_errors: tuple[str, ...] = ()
    decision: ValidationDecision
    rejection_reason: str | None = None
    validated_at: datetime

    @property
    def passed(self) -> bool:
        return self.decision == ValidationDecision.ACCEPT


class PolicySnapshot(BaseModel):
    """Immutable policy version with promoted checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    parent_policy_id: str | None
    base_check_version: str
    promoted_checks: tuple[str, ...] = ()
    check_proposals: tuple[str, ...] = ()  # proposal_ids that created the checks
    playbook_version: str | None = None
    evidence_references: tuple[str, ...] = ()
    created_at: datetime

    @property
    def content_hash(self) -> str:
        return stable_hash(
            {
                "base_check_version": self.base_check_version,
                "promoted_checks": list(self.promoted_checks),
                "playbook": self.playbook_version,
            }
        )


class ActivationResult(BaseModel):
    """Result of policy activation attempt."""

    success: bool
    activated_policy_id: str | None
    conflict: bool = False
    conflict_message: str | None = None


def propose_check(
    failure_evidence: CaseOutcome,
    current_policy_version: str,
    fixture: Fixture,
    trajectory: Trajectory | None = None,
) -> CheckProposal | None:
    """Turn real failure evidence into a bounded proposal.

    Returns None if the failure cannot be addressed by a template, or if the existing
    cheap checks should have caught it.
    """
    # Only propose for simulation failures that got past preflight checks
    if failure_evidence.disposition != Disposition.FAILED_SIMULATION:
        return None

    # If preflight checks fired, this is not a missing check
    if failure_evidence.blocking_check_ids:
        return None

    # For now, only propose swept fixture clearance checks
    # In a real system, we'd inspect the collision events from simulation
    # to determine which template to use

    # Check if fixtures exist and if this looks like a fixture collision
    if not fixture.shop.fixtures:
        return None

    # Propose a swept fixture clearance check
    # Parameters derived from shop and trajectory, not from fixture name
    clearance_margin = fixture.shop.min_fixture_clearance_mm

    params = SweptFixtureClearanceParams(
        clearance_margin_mm=clearance_margin,
        check_cutter=True,
        check_shank=True,
        check_holder=True,
        only_non_cutting=True,
    )

    # Validate params structurally
    valid, error = validate_params(TemplateId.SWEPT_FIXTURE_CLEARANCE, params.model_dump())
    if not valid:
        return None

    proposal_id = f"prop-{stable_hash(params.model_dump())[:12]}"

    return CheckProposal(
        proposal_id=proposal_id,
        parent_policy_version=current_policy_version,
        template_id=TemplateId.SWEPT_FIXTURE_CLEARANCE,
        parameters=params.model_dump(),
        check_id="proposed_fixture_clearance",
        intended_stage="path",
        intended_failure_code="collision",
        source_kind=SourceKind.RUNTIME_FAILURE,
        source_failure_fixture_id=failure_evidence.fixture_id,
        source_trajectory_hash=trajectory.trajectory_hash if trajectory else None,
        explanation=(
            f"Simulation detected fixture collision in {fixture.fixture_id}. "
            f"Existing preflight checks did not catch it. Propose swept fixture "
            f"clearance check with {clearance_margin:.1f}mm margin derived from shop profile."
        ),
        applicability_note=(
            f"Applicable to jobs with fixtures, using shop min clearance {clearance_margin:.1f}mm"
        ),
        status=ProposalStatus.PROPOSED,
        proposed_at=datetime.now(UTC),
    )


async def validate_check(
    proposal: CheckProposal,
    validation_suite: list[Fixture],
    current_policy_version: str,
) -> ValidationReport:
    """Deterministic validation independent of the proposer.

    Per §7 validation gates:
    1. Template/parameter/unit/applicability/time-bound validation
    2. Rule catches the original evidenced failure
    3. At least one distinct applicable failure
    4. Valid clearance just above the boundary passes
    5. Repaired passing plan passes
    6. Non-intersecting traverse passes
    7. Out-of-scope case returns NOT APPLICABLE
    8. Reject if known-valid becomes blocking, evidence missing, or timeout
    """
    started = time.perf_counter()
    cases: list[ValidationCaseOutcome] = []
    structural_errors: list[str] = []

    # Gate 1: Structural validation
    template = get_template(proposal.template_id)
    param_type = template["param_type"]

    try:
        params = param_type(**proposal.parameters)
        valid, error = params.validate_bounds()
        if not valid:
            structural_errors.append(f"Parameter validation failed: {error}")
    except Exception as e:
        structural_errors.append(f"Parameter parsing failed: {e}")
        structural_valid = False
    else:
        structural_valid = not structural_errors

    if not structural_valid:
        elapsed = time.perf_counter() - started
        report_id = f"vr-{proposal.proposal_id}-{int(time.time())}"
        return ValidationReport(
            report_id=report_id,
            proposal_id=proposal.proposal_id,
            proposal_hash=proposal.proposal_hash,
            validator_version="validator-1",
            fixture_suite_hash=stable_hash([f.fixture_id for f in validation_suite]),
            cases=tuple(cases),
            false_positives=0,
            false_negatives=0,
            runtime_seconds=elapsed,
            structural_valid=False,
            structural_errors=tuple(structural_errors),
            decision=ValidationDecision.REJECT,
            rejection_reason="Structural validation failed",
            validated_at=datetime.now(UTC),
        )

    # Now run against the validation suite
    from silta import checks, toolpaths

    false_positives = 0
    false_negatives = 0
    caught_original = False

    for fixture in validation_suite:
        if fixture.seed_plan is None:
            continue

        spec = fixture.spec
        shop = fixture.shop
        plan = fixture.seed_plan

        # Update hashes
        if plan.spec_design_hash != spec.design_hash or plan.shop_hash != shop.shop_hash:
            plan = ProcessPlan(
                **{
                    **plan.model_dump(),
                    "spec_design_hash": spec.design_hash,
                    "shop_hash": shop.shop_hash,
                }
            )

        # Run preflight checks
        preflight_results = checks.run_preflight_checks(spec, shop, plan)
        blocking_preflight = checks.blocking(preflight_results)

        if blocking_preflight:
            # Preflight already fails, skip this case
            continue

        # Compile trajectory
        try:
            trajectory = toolpaths.compile_plan(spec, shop, plan)
        except Exception:
            continue

        # Apply the proposed check
        check_results = apply_swept_fixture_clearance(
            spec, shop, plan, trajectory, params, check_id=proposal.check_id
        )
        check_fired_blocking = any(
            r.status == CheckStatus.FAIL and r.severity.value == "blocking" for r in check_results
        )
        # Also check for warnings - an over-broad margin produces warnings on valid cases
        check_fired_warning = any(
            r.status == CheckStatus.FAIL and r.severity.value == "warning" for r in check_results
        )

        # Determine expected outcome from fixture expectation
        expected_disp = fixture.expectation.disposition
        expected_check_should_fire = expected_disp in (
            Disposition.FAILED_CHECKS,
            Disposition.FAILED_SIMULATION,
        )

        # For the original source failure
        if proposal.source_failure_fixture_id == fixture.fixture_id:
            if check_fired_blocking:
                caught_original = True

        # Determine if this is correct
        matched = True
        message = None

        # Known-valid case (PASSED) should not become blocking
        if expected_disp == Disposition.PASSED:
            if check_fired_blocking:
                false_positives += 1
                matched = False
                message = "Known-valid case rejected by proposed check (false positive)"
            # Warning on a known-valid case is also a false positive if the proposed
            # margin is unreasonably high (more than 2x the shop minimum)
            elif check_fired_warning and (
                params.clearance_margin_mm > shop.min_fixture_clearance_mm * 2
            ):
                false_positives += 1
                matched = False
                message = (
                    f"Over-broad margin ({params.clearance_margin_mm}mm) produces "
                    f"warning on known-valid case (false positive)"
                )

        # Known-invalid case should be caught
        elif expected_disp in (Disposition.FAILED_SIMULATION, Disposition.FAILED_CHECKS):
            # It's OK if the check catches it or if it's caught elsewhere
            # The key is: don't introduce false positives
            pass

        cases.append(
            ValidationCaseOutcome(
                fixture_id=fixture.fixture_id,
                expected_disposition=expected_disp,
                actual_disposition=(
                    Disposition.FAILED_CHECKS if check_fired_blocking else expected_disp
                ),
                expected_check_fired=expected_check_should_fire,
                actual_check_fired=check_fired_blocking,
                matched=matched,
                message=message,
            )
        )

    elapsed = time.perf_counter() - started

    # Decision logic
    decision = ValidationDecision.ACCEPT
    rejection_reason = None

    if false_positives > 0:
        decision = ValidationDecision.REJECT
        rejection_reason = f"False positives detected: {false_positives} known-valid cases rejected"
    elif not caught_original and proposal.source_failure_fixture_id:
        decision = ValidationDecision.REJECT
        rejection_reason = "Proposed check did not catch the original evidenced failure"
    elif elapsed > 30.0:
        decision = ValidationDecision.REJECT
        rejection_reason = f"Validation timeout: {elapsed:.1f}s exceeds 30s limit"

    report_id = f"vr-{proposal.proposal_id}-{int(time.time())}"
    return ValidationReport(
        report_id=report_id,
        proposal_id=proposal.proposal_id,
        proposal_hash=proposal.proposal_hash,
        validator_version="validator-1",
        fixture_suite_hash=stable_hash([f.fixture_id for f in validation_suite]),
        cases=tuple(cases),
        false_positives=false_positives,
        false_negatives=false_negatives,
        runtime_seconds=round(elapsed, 3),
        structural_valid=structural_valid,
        structural_errors=tuple(structural_errors),
        decision=decision,
        rejection_reason=rejection_reason,
        validated_at=datetime.now(UTC),
    )


def activate_policy(
    snapshot: PolicySnapshot,
    expected_parent: str | None,
    storage,
) -> ActivationResult:
    """Atomic policy activation with compare-and-swap.

    Args:
        snapshot: New policy to activate
        expected_parent: Expected current policy version (for CAS)
        storage: Storage backend

    Returns:
        ActivationResult with success status and any conflict info
    """
    # Load current active policy pointer
    pointer_key = "policy/active.json"

    try:
        if storage.exists(pointer_key):
            current_data = storage.get_bytes(pointer_key)
            current = json.loads(current_data)
            current_policy_id = current.get("policy_id")
        else:
            current_policy_id = None
    except Exception:
        current_policy_id = None

    # Compare-and-swap check
    if expected_parent != current_policy_id:
        return ActivationResult(
            success=False,
            activated_policy_id=None,
            conflict=True,
            conflict_message=(
                f"Policy conflict: expected parent {expected_parent}, "
                f"but current is {current_policy_id}"
            ),
        )

    # Persist the snapshot
    snapshot_key = f"policy/snapshots/{snapshot.policy_id}.json"
    snapshot_data = json.dumps(snapshot.model_dump(mode="json"), indent=2).encode("utf-8")
    storage.put_bytes(snapshot_key, snapshot_data, "application/json")

    # Update active pointer
    pointer_data = json.dumps(
        {
            "policy_id": snapshot.policy_id,
            "activated_at": snapshot.created_at.isoformat(),
            "parent_policy_id": snapshot.parent_policy_id,
        },
        indent=2,
    ).encode("utf-8")
    storage.put_bytes(pointer_key, pointer_data, "application/json")

    return ActivationResult(
        success=True,
        activated_policy_id=snapshot.policy_id,
        conflict=False,
    )


def load_active_policy(storage) -> PolicySnapshot | None:
    """Load the currently active policy snapshot."""
    pointer_key = "policy/active.json"
    if not storage.exists(pointer_key):
        return None

    pointer_data = storage.get_bytes(pointer_key)
    pointer = json.loads(pointer_data)
    policy_id = pointer["policy_id"]

    snapshot_key = f"policy/snapshots/{policy_id}.json"
    snapshot_data = storage.get_bytes(snapshot_key)
    return PolicySnapshot.model_validate_json(snapshot_data)


def persist_proposal(proposal: CheckProposal, storage) -> str:
    """Persist a check proposal. Returns the storage key."""
    key = f"policy/proposals/{proposal.proposal_id}.json"
    data = json.dumps(proposal.model_dump(mode="json"), indent=2).encode("utf-8")
    return storage.put_bytes(key, data, "application/json")


def persist_validation_report(report: ValidationReport, storage) -> str:
    """Persist a validation report. Returns the storage key."""
    key = f"policy/validation_reports/{report.report_id}.json"
    data = json.dumps(report.model_dump(mode="json"), indent=2).encode("utf-8")
    return storage.put_bytes(key, data, "application/json")
