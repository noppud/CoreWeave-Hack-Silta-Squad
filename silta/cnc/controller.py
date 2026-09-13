"""Authoritative control flow around external Astra, sandbox, Fusion and Weave adapters."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Protocol

from .checks import CheckRunner, IntegrityChecks
from .models import (
    Artifact,
    Candidate,
    CandidateGenerationError,
    CandidateProposalUnresolved,
    JobContext,
    JobInputs,
    JobResult,
    PromotionResult,
    ReusableProposal,
    SupervisorDecision,
    Target,
    VerificationResult,
)
from .store import JobStore


class MainAgent(Protocol):
    def establish_target(self, inputs: JobInputs, workspace: str) -> Target: ...

    def propose(
        self,
        context: JobContext,
        previous: Candidate | None,
        feedback: dict[str, Any],
        instructions: str,
        attempt: int,
    ) -> Candidate: ...


class FusionVerifier(Protocol):
    def verify(self, candidate: Candidate, context: JobContext) -> VerificationResult: ...


class Supervisor(Protocol):
    def decide(
        self,
        context: JobContext,
        candidate: Candidate,
        verification: VerificationResult,
        history: list[dict[str, Any]],
    ) -> SupervisorDecision: ...


class CheckLearner(Protocol):
    def propose_checks(
        self, context: JobContext, candidate: Candidate, verification: VerificationResult
    ) -> tuple[ReusableProposal, ...]: ...


class EvaluationGate(Protocol):
    def evaluate(self, proposal: ReusableProposal, context: JobContext) -> PromotionResult: ...


class Controller:
    def __init__(
        self,
        main: MainAgent,
        checks: CheckRunner,
        fusion: FusionVerifier,
        supervisor: Supervisor,
        learner: CheckLearner | None = None,
        evaluation: EvaluationGate | None = None,
        check_runner_factory: Callable[[str], CheckRunner] | None = None,
        learning=None,
    ):
        self.main = main
        self.checks = IntegrityChecks(checks)
        self.fusion = fusion
        self.supervisor = supervisor
        self.learner = learner
        self.evaluation = evaluation
        self.check_runner_factory = check_runner_factory
        self.learning = learning

    def run(
        self,
        inputs: JobInputs,
        root: str | Path,
        job_id: str,
        versions: dict[str, str],
        max_attempts: int = 20,
        verified_incumbent: tuple[Candidate, VerificationResult] | None = None,
    ) -> JobResult:
        """Limits are an operational stop, never a successful supervisor decision."""
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        inputs.verify()
        store = JobStore(root, job_id)
        best: Candidate | None = None
        best_verification: VerificationResult | None = None
        previous: Candidate | None = None
        attempts = simulations = 0
        feedback: dict[str, Any] = {}
        instructions = ""
        status = "incomplete"
        reason = "Operational attempt limit reached"

        def retain_learning(refs: dict[str, str]) -> None:
            """Keep evaluated source bytes as run evidence, not extra active memory."""
            if self.learning is None:
                return
            directory = store.directory / "learning-sources"
            directory.mkdir(exist_ok=True)
            sources = store.data.setdefault("learning_sources", {})
            for kind in ("main_prompt", "checks"):
                ref = refs.get(kind)
                if not ref or ref in sources:
                    continue
                obj = self.learning.get(ref)
                path = directory / (ref + (".py" if kind == "checks" else ".md"))
                path.write_text(obj["content"])
                sources[ref] = {"kind": kind, **asdict(Artifact.from_path(path))}
            store.save()

        def promote(
            proposals: tuple[ReusableProposal, ...], context: JobContext
        ) -> JobContext:
            for proposal in proposals:
                store.event("reusable_change_proposed", proposal=asdict(proposal))
                if self.learning is not None:
                    evidence = self.learning.apply(proposal, deepcopy(context))
                    result = PromotionResult(
                        proposal.id, True, "Applied directly; evaluation disabled", evidence,
                    )
                    store.event("learning_change_saved", proposal_id=proposal.id,
                                change_kind=proposal.kind, evaluation_performed=False)
                elif self.evaluation is None:
                    store.event(
                        "promotion_deferred",
                        proposal_id=proposal.id,
                        reason="No evaluation gate configured",
                    )
                    continue
                else:
                    result = self.evaluation.evaluate(proposal, deepcopy(context))
                if result.proposal_id != proposal.id or (result.promoted and not result.evidence):
                    raise ValueError("Promotion requires matching evaluation evidence")
                if self.learning is None:
                    store.event("promotion_evaluated", result=asdict(result))
                if result.promoted:
                    if (
                        proposal.kind not in {"checks", "main_prompt", "supervisor_prompt"}
                        or context.versions.get(proposal.kind) != proposal.base_version
                        or not proposal.proposed_version
                    ):
                        raise ValueError(
                            "Promoted change does not match this job's current version"
                        )
                    if proposal.kind == "checks":
                        if self.check_runner_factory is None:
                            raise ValueError("Promoted checks require a configured runner factory")
                        self.checks = IntegrityChecks(
                            self.check_runner_factory(proposal.proposed_version)
                        )
                    context = replace(context, versions={
                        **context.versions, proposal.kind: proposal.proposed_version,
                    })
                    retain_learning(context.versions)
                    store.data["current_versions"] = deepcopy(context.versions)
                    store.event(
                        "promoted_change_applied",
                        proposal_id=proposal.id,
                        change_kind=proposal.kind,
                        previous_version=proposal.base_version,
                        version=proposal.proposed_version,
                        after_attempt=attempts,
                        evidence=list(result.evidence),
                    )
            return context

        def review(candidate, verification, context):
            # Every supervisor call remains bound to an actual completed pass.
            candidate.verify()
            context.target.verify()
            context.inputs.verify()
            verification.validate(candidate, context)
            if verification.status != "passed" or not verification.completed:
                raise ValueError("Supervisor requires a completed verified candidate")
            decision = self.supervisor.decide(
                deepcopy(context), deepcopy(candidate), deepcopy(verification),
                deepcopy(store.data["events"]),
            )
            if decision.action not in ("improve", "stop"):
                raise ValueError("Invalid supervisor action")
            store.event("supervisor_decision", decision=asdict(decision),
                        versions=deepcopy(context.versions))
            context = promote(decision.reusable_proposals, context)
            if decision.action == "improve" and not decision.instructions.strip():
                raise ValueError("Improvement decision requires instructions")
            return context, decision

        try:
            inputs = store.inputs(deepcopy(inputs))
            pinned = deepcopy(versions)
            store.data["versions"] = deepcopy(pinned)
            store.data["current_versions"] = deepcopy(pinned)
            retain_learning(pinned)
            store.save()
            workspace = store.directory / "workspace"
            workspace.mkdir()
            store.event("target_generation_started")
            target = self.main.establish_target(deepcopy(inputs), str(workspace))
            target.verify()
            target = store.target(target)
            context = JobContext(inputs, target, inputs.digest, pinned, str(store.directory))
            accepted_digest = target.digest
            store.event("target_accepted", target_digest=accepted_digest)
            if verified_incumbent is not None:
                restored, verification = deepcopy(verified_incumbent)
                restored.verify()
                verification.validate(restored, context)
                if restored.target_digest != accepted_digest or verification.status != "passed":
                    raise ValueError("Resumed incumbent must be verified against the fixed target")
                best = store.candidate(restored, 0)
                evidence = store.snapshot("resumed-evidence", {
                    f"evidence-{i}": artifact for i, artifact in enumerate(verification.evidence)
                })
                best_verification = replace(verification, evidence=tuple(evidence.values()))
                previous = best
                store.data["best_candidate"] = asdict(best)
                store.data["best_verification"] = asdict(best_verification)
                store.event("verified_incumbent_resumed", candidate=asdict(best),
                            verification=asdict(best_verification))
            for attempts in range(1, max_attempts + 1):
                context.inputs.verify()
                target.verify()
                if (
                    target.digest != accepted_digest
                    or context.inputs.digest != context.input_digest
                ):
                    raise ValueError("Fixed target or manufacturing inputs changed")
                try:
                    store.event("candidate_generation_started", attempt=attempts)
                    candidate = self.main.propose(
                        deepcopy(context),
                        deepcopy(previous),
                        deepcopy(feedback),
                        instructions,
                        attempts,
                    )
                except CandidateProposalUnresolved as error:
                    store.event("cam_proposal_unresolved", attempt=attempts,
                                issues=error.issues, instructions=instructions)
                    if best is None or best_verification is None:
                        raise
                    context, decision = review(best, best_verification, context)
                    if decision.action == "stop":
                        status, reason = "completed", "Supervisor selected the best verified plan"
                        break
                    instructions = decision.instructions
                    previous = best
                    feedback = {"stage": "supervisor", "unresolved_proposal": error.issues,
                                "verification": asdict(best_verification)}
                    continue
                except CandidateGenerationError as error:
                    feedback = deepcopy(error.feedback)
                    store.event("cam_generation_failed", attempt=attempts, feedback=feedback)
                    continue
                candidate.verify()
                candidate = store.candidate(candidate, attempts)
                store.event(
                    "candidate_created",
                    attempt=attempts,
                    candidate=asdict(candidate),
                    candidate_digest=candidate.digest,
                    versions=deepcopy(context.versions),
                )
                check = self.checks.run(deepcopy(candidate), deepcopy(context))
                store.event(
                    "checks_completed", attempt=attempts, result=asdict(check),
                    versions=deepcopy(context.versions),
                )
                previous = candidate
                if not check.passed:
                    feedback = {"stage": "checks", "issues": list(check.issues)}
                    continue
                # Check code must not mutate the frozen candidate or trusted inputs.
                candidate.verify()
                target.verify()
                simulations += 1
                store.event("verification_started", attempt=attempts)
                verification = self.fusion.verify(deepcopy(candidate), deepcopy(context))
                candidate.verify()
                target.verify()
                verification.validate(candidate, context)
                if verification.evidence:
                    saved_evidence = store.snapshot(
                        f"verification-{attempts:04d}",
                        {f"evidence-{i}": item for i, item in enumerate(verification.evidence)},
                    )
                    verification = replace(verification, evidence=tuple(saved_evidence.values()))
                store.event(
                    "verification_completed", attempt=attempts, verification=asdict(verification)
                )
                if not verification.completed or verification.status == "unknown":
                    reason = (
                        "Fusion verification is incomplete or unknown; "
                        "access/result needs resolving"
                    )
                    break
                if verification.status == "failed":
                    feedback = {
                        "stage": "simulation",
                        "issues": list(verification.issues),
                        "feedback": verification.feedback,
                    }
                    if self.learner:
                        context = promote(
                            self.learner.propose_checks(
                                deepcopy(context), deepcopy(candidate), deepcopy(verification)
                            ),
                            context,
                        )
                    continue
                if best_verification is not None and (
                    verification.verifier_version != best_verification.verifier_version
                    or verification.coverage != best_verification.coverage
                ):
                    raise ValueError(
                        "Verification scope/version changed; results are not comparable"
                    )
                if best_verification is None or verification.score(
                    inputs.objective
                ) < best_verification.score(inputs.objective):
                    best, best_verification = candidate, verification
                    store.data["best_candidate"] = asdict(best)
                    store.data["best_verification"] = asdict(best_verification)
                    store.event("incumbent_updated", candidate_id=best.id)
                context, decision = review(candidate, verification, context)
                if decision.action == "stop":
                    status, reason = "completed", "Supervisor selected the best verified plan"
                    break
                instructions = decision.instructions
                previous = best
                feedback = {"stage": "supervisor", "verification": asdict(best_verification)}
        except Exception as error:
            reason = f"{type(error).__name__}: {error}"
            store.event("execution_interrupted", reason=reason)
        result = JobResult(
            job_id,
            status,
            reason,
            best,
            best_verification,
            attempts,
            simulations,
            str(store.manifest_path),
        )
        store.data.update({"status": status, "reason": reason, "result": asdict(result)})
        store.save()
        return result
