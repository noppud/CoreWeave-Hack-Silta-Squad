"""Data contracts for the machining loop; no model-generated verdict is trusted here."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


class CandidateGenerationError(RuntimeError):
    """Completed CAM generation failed; send the observed details back for repair."""

    def __init__(self, feedback: dict):
        self.feedback = feedback
        super().__init__("Fusion did not generate usable toolpaths")


class CandidateProposalUnresolved(ValueError):
    """The planner declined a CAM proposal before executing its source."""

    def __init__(self, issues: list[str]):
        self.issues = list(issues)
        super().__init__("cam needs clarification: " + "; ".join(issues))


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def file_digest(path: str | Path) -> str:
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str

    @classmethod
    def from_path(cls, path: str | Path) -> Artifact:
        path = Path(path).resolve(strict=True)
        return cls(str(path), file_digest(path))

    def verify(self) -> None:
        if file_digest(self.path) != self.sha256:
            raise ValueError(f"Artifact changed: {self.path}")


def _map_artifact_records(value: Any, transform: Callable[[dict], dict]) -> Any:
    """Visit explicit JSON artifact pins without interpreting unrelated metadata."""
    if isinstance(value, dict):
        mapped = {key: _map_artifact_records(item, transform) for key, item in value.items()}
        return transform(mapped) if "path" in mapped and "sha256" in mapped else mapped
    if isinstance(value, (list, tuple)):
        return type(value)(_map_artifact_records(item, transform) for item in value)
    return value


@dataclass(frozen=True)
class JobInputs:
    drawings: tuple[Artifact, ...]
    machine: dict[str, Any]
    tools: dict[str, Any]
    setup: dict[str, Any]
    tolerances: dict[str, Any]
    cost_assumptions: dict[str, Any] = field(default_factory=dict)
    objective: Literal["machining_seconds", "estimated_cost"] = "machining_seconds"

    @property
    def digest(self) -> str:
        data = asdict(self)
        data["drawings"] = [item.sha256 for item in self.drawings]
        # Artifact storage locations are transport details. Their content hashes
        # and all non-path metadata remain part of the manufacturing identity.
        return digest_json(
            _map_artifact_records(
                data, lambda record: {key: value for key, value in record.items() if key != "path"}
            )
        )

    def map_artifacts(self, transform: Callable[[Artifact], Artifact]) -> JobInputs:
        """Return independent inputs with every explicitly pinned artifact mapped."""

        def map_record(record: dict) -> dict:
            mapped = transform(Artifact(record["path"], record["sha256"]))
            return {**record, "path": mapped.path, "sha256": mapped.sha256}

        data = _map_artifact_records(asdict(self), map_record)
        data["drawings"] = tuple(Artifact(**record) for record in data["drawings"])
        return JobInputs(**data)

    def verify(self) -> None:
        if not self.drawings or not all((self.machine, self.tools, self.setup, self.tolerances)):
            raise ValueError("Drawings, machine, tools, setup and tolerances are required")
        if self.objective not in ("machining_seconds", "estimated_cost"):
            raise ValueError("Unsupported optimization objective")

        def verify_artifact(artifact: Artifact) -> Artifact:
            artifact.verify()
            return artifact

        self.map_artifacts(verify_artifact)


@dataclass(frozen=True)
class Target:
    artifacts: dict[str, Artifact]
    acceptance_evidence: str

    @property
    def digest(self) -> str:
        return digest_json({k: v.sha256 for k, v in self.artifacts.items()})

    @classmethod
    def from_paths(cls, paths: dict[str, str], acceptance_evidence: str) -> Target:
        return cls(
            {key: Artifact.from_path(path) for key, path in paths.items()}, acceptance_evidence
        )

    def verify(self) -> None:
        if not self.artifacts or not self.acceptance_evidence.strip():
            raise ValueError("Target requires CAD artifacts and acceptance evidence")
        for artifact in self.artifacts.values():
            artifact.verify()


@dataclass(frozen=True)
class Candidate:
    id: str
    target_digest: str
    artifacts: dict[str, Artifact]
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return digest_json(
            {
                "target": self.target_digest,
                "artifacts": {k: v.sha256 for k, v in self.artifacts.items()},
                "parameters": self.parameters,
            }
        )

    @classmethod
    def from_paths(
        cls,
        id: str,
        target_digest: str,
        paths: dict[str, str],
        parameters: dict[str, Any] | None = None,
    ) -> Candidate:
        return cls(
            id,
            target_digest,
            {k: Artifact.from_path(v) for k, v in paths.items()},
            parameters or {},
        )

    def verify(self) -> None:
        if not self.id or not self.artifacts:
            raise ValueError("Candidate needs an id and machining artifacts")
        for artifact in self.artifacts.values():
            artifact.verify()


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    issues: tuple[str, ...] = ()
    runtime_s: float = 0.0
    version: str = "fixed-v1"


@dataclass(frozen=True)
class VerificationResult:
    status: Literal["passed", "failed", "unknown"]
    completed: bool
    input_digest: str
    candidate_digest: str
    verifier_version: str
    evidence: tuple[Artifact, ...]
    coverage: str
    issues: tuple[str, ...] = ()
    machining_seconds: float | None = None
    estimated_cost: float | None = None
    feedback: dict[str, Any] = field(default_factory=dict)

    def validate(self, candidate: Candidate, context: JobContext) -> None:
        if self.input_digest != context.input_digest or self.candidate_digest != candidate.digest:
            raise ValueError("Verification does not match the exact candidate and setup")
        expected = context.versions.get("verifier")
        if expected and self.verifier_version != expected:
            raise ValueError("Verification does not match the pinned verifier version")
        if self.status not in ("passed", "failed", "unknown"):
            raise ValueError("Invalid verification status")
        if self.status == "passed":
            if not self.completed or not self.evidence or not self.coverage or self.issues:
                raise ValueError("Pass requires completed verification, evidence and no issues")
            if not self.verifier_version:
                raise ValueError("Verifier version is required")
            for evidence in self.evidence:
                evidence.verify()
            self.score(context.inputs.objective)

    def score(self, objective: str) -> float:
        value = getattr(self, objective)
        if value is None or not math.isfinite(value) or value < 0:
            raise ValueError(f"Missing or invalid comparable metric: {objective}")
        return value


@dataclass(frozen=True)
class ReusableProposal:
    id: str
    kind: Literal["checks", "main_prompt", "supervisor_prompt"]
    base_version: str
    proposed_version: str
    artifact_path: str
    reason: str


@dataclass(frozen=True)
class PromotionResult:
    proposal_id: str
    promoted: bool
    reason: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class SupervisorDecision:
    action: Literal["improve", "stop"]
    instructions: str = ""
    reusable_proposals: tuple[ReusableProposal, ...] = ()


@dataclass(frozen=True)
class JobContext:
    inputs: JobInputs
    target: Target
    input_digest: str
    versions: dict[str, str]
    job_directory: str


@dataclass(frozen=True)
class JobResult:
    job_id: str
    status: Literal["completed", "incomplete"]
    reason: str
    best_candidate: Candidate | None
    best_verification: VerificationResult | None
    attempts: int
    simulations: int
    manifest_path: str
