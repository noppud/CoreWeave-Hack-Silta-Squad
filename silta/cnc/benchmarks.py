"""Real sequential benchmark execution and frozen simulator-case capture.

Factories supply production controller/sandbox adapters. The runner contains no
fallback simulator, model judge, or example score generation.
"""

from __future__ import annotations

import copy
import json
import math
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .checks import IntegrityChecks
from .evaluation import KINDS, VersionStore
from .models import (
    Artifact,
    Candidate,
    JobContext,
    JobInputs,
    Target,
    VerificationResult,
    digest_json,
)


def decode_inputs(data: dict) -> JobInputs:
    return JobInputs(**{**data, "drawings": tuple(Artifact(**row) for row in data["drawings"])})


def decode_target(data: dict) -> Target:
    return Target(
        **{
            **data,
            "artifacts": {key: Artifact(**value) for key, value in data["artifacts"].items()},
        }
    )


def decode_candidate(data: dict) -> Candidate:
    return Candidate(
        **{
            **data,
            "artifacts": {key: Artifact(**value) for key, value in data["artifacts"].items()},
        }
    )


def decode_verification(data: dict) -> VerificationResult:
    return VerificationResult(
        **{
            **data,
            "evidence": tuple(Artifact(**row) for row in data["evidence"]),
            "issues": tuple(data.get("issues", [])),
        }
    )


def verifier_hash(identity: dict) -> str:
    """Hash a pinned implementation, its configuration and declared coverage.

    Merely naming a verifier version is insufficient to reuse simulator labels.
    Include every implementation dependency relevant to the verdict as an artifact.
    """
    if not identity.get("version") or not identity.get("coverage") or not identity.get("artifacts"):
        raise ValueError(
            "Verifier identity requires version, coverage and implementation artifacts"
        )
    for value in identity["artifacts"]:
        Artifact(**value).verify()
    return digest_json(identity)


def case_input_hash(kind: str, inputs: JobInputs, target: Target, candidate: Candidate) -> str:
    return digest_json(
        {
            "inputs": inputs.digest,
            "target": target.digest,
            "candidate": candidate.digest if kind == "checks" else None,
        }
    )


def validate_case(case: dict) -> tuple[JobInputs, Target, Candidate, VerificationResult]:
    """Recompute references and validate frozen artifact bytes, including failed evidence."""
    if case.get("kind") not in {"checks", "loop"}:
        raise ValueError("Unknown benchmark case kind")
    inputs, target = decode_inputs(case["inputs"]), decode_target(case["target"])
    candidate, verification = (
        decode_candidate(case["candidate"]),
        decode_verification(case["verification"]),
    )
    inputs.verify()
    target.verify()
    candidate.verify()
    if candidate.target_digest != target.digest:
        raise ValueError("Frozen candidate does not use the accepted target")
    if case["input_hash"] != case_input_hash(case["kind"], inputs, target, candidate):
        raise ValueError("Frozen input hash does not match candidate/setup/target")
    identity = case["verifier_identity"]
    if case["verifier_hash"] != verifier_hash(identity):
        raise ValueError("Frozen verifier identity changed")
    if (
        verification.verifier_version != identity["version"]
        or verification.coverage != identity["coverage"]
    ):
        raise ValueError("Verification coverage or version does not match the frozen verifier")
    context = JobContext(inputs, target, inputs.digest, {"verifier": identity["version"]}, "")
    verification.validate(candidate, context)
    if (
        verification.completed is not True
        or verification.status not in {"passed", "failed"}
        or not verification.evidence
    ):
        raise ValueError("Cached label requires completed simulation with evidence")
    if verification.status == "failed" and not verification.issues:
        raise ValueError("Failed simulation label requires a recorded issue")
    for evidence in verification.evidence:
        evidence.verify()
    label = "valid" if verification.status == "passed" else "invalid"
    if case["label"] != label:
        raise ValueError("Cached label contradicts the recorded simulation verdict")
    if case["verification_evidence"] != [item.path for item in verification.evidence]:
        raise ValueError("Cached evidence references do not match the verification")
    return inputs, target, candidate, verification


def capture_case(
    manifest_path: str | Path,
    attempt: int,
    verifier_identity: dict,
    *,
    kind: str = "checks",
    case_id: str | None = None,
) -> dict:
    """Capture one actually recorded candidate + completed verification from a job.

    For whole-loop datasets choose one case per part/setup. Check datasets can include
    multiple valid and invalid attempts from the same part. Captured JSON becomes
    immutable when registered with register_dataset().
    """
    path = Path(manifest_path).resolve(strict=True)
    manifest = json.loads(path.read_text())
    if kind not in {"checks", "loop"}:
        raise ValueError("Case kind must be checks or loop")
    candidates = [
        event
        for event in manifest["events"]
        if event.get("event") == "candidate_created" and event.get("attempt") == attempt
    ]
    verifications = [
        event
        for event in manifest["events"]
        if event.get("event") == "verification_completed" and event.get("attempt") == attempt
    ]
    if len(candidates) != 1 or len(verifications) != 1:
        raise ValueError("Attempt needs exactly one candidate and one completed verification event")
    inputs, target = decode_inputs(manifest["inputs"]), decode_target(manifest["target"])
    candidate = decode_candidate(candidates[0]["candidate"])
    verification = decode_verification(verifications[0]["verification"])
    if (
        manifest.get("input_digest") != inputs.digest
        or manifest.get("target_digest") != target.digest
    ):
        raise ValueError("Manifest target/input digest mismatch")
    if candidates[0].get("candidate_digest") != candidate.digest:
        raise ValueError("Recorded candidate digest mismatch")
    if manifest.get("versions", {}).get("verifier") != verifier_identity["version"]:
        raise ValueError("Manifest did not pin the selected verifier")
    case = {
        "case_id": case_id or f"{manifest['job_id']}-attempt-{attempt}",
        "kind": kind,
        "inputs": asdict(inputs),
        "target": asdict(target),
        "candidate": asdict(candidate),
        "verification": asdict(verification),
        "verifier_identity": copy.deepcopy(verifier_identity),
        "input_hash": case_input_hash(kind, inputs, target, candidate),
        "verifier_hash": verifier_hash(verifier_identity),
        "label": "valid" if verification.status == "passed" else "invalid",
        "verification_evidence": [item.path for item in verification.evidence],
        "source_manifest": str(path),
        "source_attempt": attempt,
    }
    case = json.loads(json.dumps(case, allow_nan=False))
    validate_case(case)
    return case


def register_dataset(store: VersionStore, cases: list[dict]) -> str:
    if not cases or len({case.get("case_id") for case in cases}) != len(cases):
        raise ValueError("Dataset needs unique nonempty cases")
    for case in cases:
        if not isinstance(case.get("case_id"), str) or not case["case_id"]:
            raise ValueError("Every case needs an identifier")
        validate_case(case)
    if len({case["kind"] for case in cases}) != 1:
        raise ValueError("Do not mix whole-loop and check datasets")
    if cases[0]["kind"] == "checks" and {case["label"] for case in cases} != {"valid", "invalid"}:
        raise ValueError("Check dataset needs simulator-valid and simulator-invalid cases")
    return store.put("dataset", cases)


class FrozenTargetMain:
    def __init__(self, main: Any, target: Target):
        self.main, self.target = main, copy.deepcopy(target)

    def establish_target(self, inputs: JobInputs, workspace: str) -> Target:
        inputs.verify()
        self.target.verify()
        return copy.deepcopy(self.target)

    def propose(self, *args: Any, **kwargs: Any) -> Candidate:
        return self.main.propose(*args, **kwargs)


class BenchmarkRunner:
    """Callable used directly by WeaveEvaluationGate; executes cases sequentially."""

    def __init__(
        self,
        store: VersionStore,
        root: str | Path,
        make_controller: Any,
        check_runner_factory: Any,
        *,
        max_attempts: int = 20,
    ):
        self.store, self.root = store, Path(root).resolve()
        self.make_controller, self.check_runner_factory = make_controller, check_runner_factory
        if max_attempts < 1:
            raise ValueError("Benchmark max_attempts must be positive")
        self.max_attempts = max_attempts

    def __call__(
        self, kind: str, version_ref: str, frozen_cases: list[dict], job_context: JobContext
    ) -> list[dict]:
        if kind not in KINDS or self.store.get(version_ref)["kind"] != kind:
            raise ValueError("Benchmark version kind mismatch")
        versions = copy.deepcopy(job_context.versions)
        versions[kind] = version_ref
        records = []
        for case in frozen_cases:
            inputs, target, candidate, _ = validate_case(case)
            if case["kind"] != ("checks" if kind == "checks" else "loop"):
                raise ValueError("Benchmark case kind mismatch")
            identity = case["verifier_identity"]
            if versions.get("verifier") != identity["version"]:
                raise ValueError("Current verifier differs from frozen benchmark verifier")
            run_id = f"eval-{uuid.uuid4().hex}"
            record = {
                "case_id": case["case_id"],
                "input_hash": case["input_hash"],
                "verifier_hash": case["verifier_hash"],
                "version_ref": version_ref,
            }
            if kind == "checks":
                workspace = self.root / run_id
                workspace.mkdir(parents=True)
                context = JobContext(inputs, target, inputs.digest, versions, str(workspace))
                runner = IntegrityChecks(self.check_runner_factory(version_ref))
                result = runner.run(copy.deepcopy(candidate), copy.deepcopy(context))
                validate_case(case)  # Catch mutation by generated code; labels remain frozen.
                if (
                    type(result.passed) is not bool
                    or not math.isfinite(result.runtime_s)
                    or result.runtime_s < 0
                ):
                    raise ValueError("Malformed check benchmark result")
                record.update(
                    passed=result.passed,
                    runtime_ms=result.runtime_s * 1000,
                    issues=list(result.issues),
                )
                (workspace / "check-result.json").write_text(json.dumps(record, allow_nan=False))
            else:
                controller = copy.copy(self.make_controller(versions, evaluation_enabled=False))
                controller.main = FrozenTargetMain(controller.main, target)
                controller.learner = None
                controller.evaluation = None
                result = controller.run(
                    inputs, self.root, run_id, versions, max_attempts=self.max_attempts
                )
                validate_case(case)
                verified = False
                evidence: list[str] = []
                metrics = {"machining_seconds": None, "cost": None}
                if (
                    result.status == "completed"
                    and result.best_candidate
                    and result.best_verification
                ):
                    best, verdict = result.best_candidate, result.best_verification
                    context = JobContext(
                        inputs, target, inputs.digest, versions, str(self.root / run_id)
                    )
                    best.verify()
                    if best.target_digest != target.digest:
                        raise ValueError("Benchmark changed the fixed target")
                    verdict.validate(best, context)
                    if verdict.coverage != identity["coverage"]:
                        raise ValueError("Benchmark verifier coverage changed")
                    verified = verdict.status == "passed" and verdict.completed is True
                    if verified:
                        # Both metrics are required for the paired cost/time gate.
                        verdict.score("machining_seconds")
                        verdict.score("estimated_cost")
                        metrics = {
                            "machining_seconds": verdict.machining_seconds,
                            "cost": verdict.estimated_cost,
                        }
                        evidence = [item.path for item in verdict.evidence]
                record.update(
                    verified=verified,
                    verification_evidence=evidence,
                    simulation_attempts=result.simulations,
                    **metrics,
                    manifest_path=result.manifest_path,
                    reason=result.reason,
                )
            records.append(record)
        return records
