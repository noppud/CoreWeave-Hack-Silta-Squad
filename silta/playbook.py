"""Versioned planning playbook: propose, validate, select and persist applicable lessons.

Per §4 and §8 of docs/followups/touko-loop-refactor.md. A lesson is an instruction
that influences planning, with a structured applicability predicate. Activation is
scoped: public visitors cannot activate team-wide policy.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from silta.domain import FeatureKind, OperationKind, PartSpec, ShopProfile, ToolKind, stable_hash


class SourceKind(StrEnum):
    RUNTIME_SUPERVISOR = "runtime_supervisor"
    ARIA = "aria"
    HUMAN = "human"
    FIXTURE = "fixture"


class LessonStatus(StrEnum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    ACTIVE = "active"
    REJECTED = "rejected"
    RETIRED = "retired"


class ApplicabilityPredicate(BaseModel):
    """Structured predicate: evaluated against the part/shop, not text similarity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    part_families: tuple[str, ...] = ()  # e.g., ("fixture_block", "enclosure")
    operation_kinds: tuple[OperationKind, ...] = ()
    tool_kinds: tuple[ToolKind, ...] = ()
    feature_kinds: tuple[FeatureKind, ...] = ()
    requires_fixtures: bool | None = None
    min_depth_mm: float | None = Field(default=None, ge=0)
    max_depth_mm: float | None = Field(default=None, ge=0)

    def matches(self, spec: PartSpec, shop: ShopProfile) -> bool:
        """True if this lesson is applicable to the given spec and shop."""
        if self.part_families and not any(
            fam in spec.spec_id.lower() for fam in self.part_families
        ):
            return False
        if self.feature_kinds:
            spec_kinds = {f.kind for f in spec.features}
            if not any(k in spec_kinds for k in self.feature_kinds):
                return False
        if self.requires_fixtures is not None:
            has_fixtures = len(shop.fixtures) > 0
            if self.requires_fixtures != has_fixtures:
                return False
        if self.min_depth_mm is not None or self.max_depth_mm is not None:
            depths = [f.depth_mm for f in spec.features]
            if depths:
                max_depth = max(depths)
                if self.min_depth_mm is not None and max_depth < self.min_depth_mm:
                    return False
                if self.max_depth_mm is not None and max_depth > self.max_depth_mm:
                    return False
        return True


class PlanningLesson(BaseModel):
    """A versioned instruction that influences planning when applicable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lesson_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    revision: int = Field(ge=1)
    instruction: str = Field(min_length=1, max_length=2000)
    applicability: ApplicabilityPredicate
    source_kind: SourceKind
    source_run_id: str | None = None
    source_attempt_id: str | None = None
    source_evidence_ids: tuple[str, ...] = ()
    validation_reference: str | None = None
    status: LessonStatus
    proposed_at: datetime
    activated_at: datetime | None = None

    @property
    def lesson_version(self) -> str:
        return f"{self.lesson_id}:r{self.revision}"

    @property
    def content_hash(self) -> str:
        """Hash of instruction + applicability, not metadata."""
        return stable_hash(
            {"instruction": self.instruction, "applicability": self.applicability.model_dump()}
        )


class ActivationScope(StrEnum):
    PUBLIC_SESSION = "public_session"  # Isolated to one session
    TEAM_DEFAULT = "team_default"  # Shared team-wide


class PlanningPlaybook(BaseModel):
    """Immutable versioned collection of lessons."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    playbook_version: str = Field(min_length=1, max_length=64)
    parent_version: str | None = None
    lesson_versions: tuple[str, ...] = ()  # lesson_id:rN references
    activation_scope: ActivationScope
    created_at: datetime

    @property
    def content_hash(self) -> str:
        return stable_hash(
            {
                "lesson_versions": list(self.lesson_versions),
                "activation_scope": self.activation_scope.value,
            }
        )


def propose_lesson(
    instruction: str,
    applicability: ApplicabilityPredicate,
    source_kind: SourceKind,
    lesson_id: str | None = None,
    source_run_id: str | None = None,
    source_attempt_id: str | None = None,
    source_evidence_ids: tuple[str, ...] = (),
) -> PlanningLesson:
    """Propose a new lesson. Returns status PROPOSED."""
    if lesson_id is None:
        # Generate a unique lesson_id from content hash
        content = stable_hash({"instruction": instruction, "applicability": applicability})
        lesson_id = f"lesson-{content[:12]}"

    return PlanningLesson(
        lesson_id=lesson_id,
        revision=1,
        instruction=instruction,
        applicability=applicability,
        source_kind=source_kind,
        source_run_id=source_run_id,
        source_attempt_id=source_attempt_id,
        source_evidence_ids=source_evidence_ids,
        validation_reference=None,
        status=LessonStatus.PROPOSED,
        proposed_at=datetime.now(UTC),
        activated_at=None,
    )


def validate_lesson(lesson: PlanningLesson, validation_reference: str) -> PlanningLesson:
    """Mark a lesson as validated. Returns updated lesson with VALIDATED status."""
    if lesson.status != LessonStatus.PROPOSED:
        raise ValueError(f"Can only validate PROPOSED lessons, not {lesson.status}")
    return lesson.model_copy(
        update={"status": LessonStatus.VALIDATED, "validation_reference": validation_reference}
    )


def activate_lesson(lesson: PlanningLesson) -> PlanningLesson:
    """Mark a validated lesson as active. Returns updated lesson with ACTIVE status."""
    if lesson.status != LessonStatus.VALIDATED:
        raise ValueError(f"Can only activate VALIDATED lessons, not {lesson.status}")
    return lesson.model_copy(
        update={"status": LessonStatus.ACTIVE, "activated_at": datetime.now(UTC)}
    )


def select_applicable(
    lessons: list[PlanningLesson],
    spec: PartSpec,
    shop: ShopProfile,
    mandatory_instructions: tuple[str, ...] = (),
    max_lessons: int = 5,
    max_tokens: int = 2000,
) -> tuple[list[PlanningLesson], list[str]]:
    """Select applicable active lessons, bounded by count and token budget.

    Returns:
        - List of applicable lessons (up to max_lessons)
        - List of lesson_version strings for traceability
    """
    applicable: list[PlanningLesson] = []
    lesson_versions: list[str] = []
    token_count = 0

    # Only consider ACTIVE lessons
    active_lessons = [lesson for lesson in lessons if lesson.status == LessonStatus.ACTIVE]

    # Filter by applicability
    for lesson in active_lessons:
        if len(applicable) >= max_lessons:
            break
        if not lesson.applicability.matches(spec, shop):
            continue

        # Check for contradictions with mandatory instructions
        # (Simple check: if lesson instruction contradicts a mandatory one, skip it)
        contradicts = False
        for mandatory in mandatory_instructions:
            # Basic contradiction detection: if mandatory says "never X" and lesson says "always X"
            # This is simplified; production would need more sophisticated logic
            if "never" in mandatory.lower() and any(
                word in lesson.instruction.lower()
                for word in mandatory.lower().split()
                if word not in ("never", "not", "do")
            ):
                contradicts = True
                break
        if contradicts:
            continue

        # Estimate token count (rough: ~4 chars per token)
        estimated_tokens = len(lesson.instruction) // 4
        if token_count + estimated_tokens > max_tokens:
            break

        applicable.append(lesson)
        lesson_versions.append(lesson.lesson_version)
        token_count += estimated_tokens

    return applicable, lesson_versions


def create_playbook(
    lessons: list[PlanningLesson],
    activation_scope: ActivationScope,
    parent_version: str | None = None,
) -> PlanningPlaybook:
    """Create a new immutable playbook from active lessons."""
    lesson_versions = tuple(lesson.lesson_version for lesson in lessons)
    content_hash = stable_hash(
        {"lesson_versions": list(lesson_versions), "scope": activation_scope.value}
    )
    playbook_version = f"playbook-{content_hash[:12]}"

    return PlanningPlaybook(
        playbook_version=playbook_version,
        parent_version=parent_version,
        lesson_versions=lesson_versions,
        activation_scope=activation_scope,
        created_at=datetime.now(UTC),
    )


# Storage interface (uses the Storage protocol from silta.storage)
def persist_lesson(lesson: PlanningLesson, storage) -> str:
    """Persist an immutable lesson. Returns the storage key."""
    key = f"playbook/lessons/{lesson.lesson_id}/r{lesson.revision}.json"
    data = json.dumps(lesson.model_dump(mode="json"), indent=2).encode("utf-8")
    return storage.put_bytes(key, data, "application/json")


def persist_playbook(playbook: PlanningPlaybook, storage) -> str:
    """Persist an immutable playbook snapshot. Returns the storage key."""
    key = f"playbook/versions/{playbook.playbook_version}.json"
    data = json.dumps(playbook.model_dump(mode="json"), indent=2).encode("utf-8")
    return storage.put_bytes(key, data, "application/json")


def load_lesson(lesson_id: str, revision: int, storage) -> PlanningLesson:
    """Load a specific lesson revision."""
    key = f"playbook/lessons/{lesson_id}/r{revision}.json"
    data = storage.get_bytes(key)
    return PlanningLesson.model_validate_json(data)


def load_playbook(playbook_version: str, storage) -> PlanningPlaybook:
    """Load a specific playbook version."""
    key = f"playbook/versions/{playbook_version}.json"
    data = storage.get_bytes(key)
    return PlanningPlaybook.model_validate_json(data)
