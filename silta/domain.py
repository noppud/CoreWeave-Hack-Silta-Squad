"""Versioned data contracts for Silta CNC.

Canonical units are millimetres, seconds, RPM and mm/min. Input units are kept on
the specification and converted at the boundary; unknown units are never guessed.
Coordinates: X/Y align with the stock block, Z points up, stock top is Z = 0.
Features are entered from +Z with a fixed Z tool axis.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1"
# Execution-identity hash algorithm; bump when execution_payload changes shape.
FINGERPRINT_VERSION = "fp2"

Mm = Annotated[float, Field(gt=-1e4, lt=1e4, allow_inf_nan=False)]
PosMm = Annotated[float, Field(gt=0, lt=1e4, allow_inf_nan=False)]
Ident = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]


class Contract(BaseModel):
    """Strict base: unknown fields are a contract violation, not a warning."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


def stable_hash(payload: object) -> str:
    """Content hash used for artifact lineage. Order-independent for dicts."""
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- units


class Units(StrEnum):
    MM = "mm"
    INCH = "inch"
    UNKNOWN = "unknown"


_TO_MM = {Units.MM: 1.0, Units.INCH: 25.4}


def to_mm(value: float, units: Units) -> float:
    """Convert at the boundary. Unknown units must be clarified, never assumed."""
    if units == Units.UNKNOWN:
        raise ValueError("Unknown units must be clarified before conversion.")
    if not math.isfinite(value):
        raise ValueError("Non-finite dimension.")
    return value * _TO_MM[units]


# ------------------------------------------------------------------------- sources


class SourceAsset(Contract):
    asset_id: Ident
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime: Literal["image/png", "image/jpeg", "application/pdf", "text/plain"]
    byte_length: int = Field(gt=0, le=20_000_000)
    display_filename: str = Field(min_length=1, max_length=200)
    page_refs: tuple[int, ...] = ()


# ------------------------------------------------------------------------ features


class FeatureKind(StrEnum):
    POCKET_RECT_ROUNDED = "pocket_rect_rounded"
    HOLE_BLIND = "hole_blind"


class DrillTipConvention(StrEnum):
    """States what a blind-hole `depth_mm` measures."""

    CYLINDRICAL_DEPTH = "cylindrical_depth"  # full-diameter depth, tip goes deeper
    TOTAL_TIP_DEPTH = "total_tip_depth"  # including the conical point


class Feature(Contract):
    feature_id: Ident
    kind: FeatureKind
    depth_mm: PosMm
    # Pocket geometry (rectangle in stock coordinates, axis-aligned).
    x_min_mm: Mm | None = None
    x_max_mm: Mm | None = None
    y_min_mm: Mm | None = None
    y_max_mm: Mm | None = None
    corner_radius_mm: PosMm | None = None
    # Hole geometry.
    center_x_mm: Mm | None = None
    center_y_mm: Mm | None = None
    diameter_mm: PosMm | None = None
    drill_tip: DrillTipConvention | None = None
    drill_point_angle_deg: Annotated[float, Field(gt=0, lt=180)] | None = None
    drawing_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _kind_fields(self) -> Feature:
        if self.kind is FeatureKind.POCKET_RECT_ROUNDED:
            missing = [
                n
                for n in ("x_min_mm", "x_max_mm", "y_min_mm", "y_max_mm", "corner_radius_mm")
                if getattr(self, n) is None
            ]
            if missing:
                raise ValueError(f"Pocket {self.feature_id} missing {', '.join(missing)}.")
            if self.x_max_mm <= self.x_min_mm or self.y_max_mm <= self.y_min_mm:
                raise ValueError(f"Pocket {self.feature_id} has non-positive extents.")
            half = min(self.x_max_mm - self.x_min_mm, self.y_max_mm - self.y_min_mm) / 2
            if self.corner_radius_mm > half:
                raise ValueError(f"Pocket {self.feature_id} corner radius exceeds half its width.")
        else:
            missing = [
                n
                for n in ("center_x_mm", "center_y_mm", "diameter_mm", "drill_tip")
                if getattr(self, n) is None
            ]
            if missing:
                raise ValueError(f"Hole {self.feature_id} missing {', '.join(missing)}.")
        return self

    @property
    def tip_extra_mm(self) -> float:
        """Extra depth reached by the conical drill point below the cylindrical depth."""
        if self.kind is not FeatureKind.HOLE_BLIND:
            return 0.0
        angle = self.drill_point_angle_deg or 118.0
        return (self.diameter_mm / 2.0) / math.tan(math.radians(angle / 2.0))

    @property
    def total_tip_depth_mm(self) -> float:
        """Depth of the deepest point of the tool below the stock top."""
        if self.kind is not FeatureKind.HOLE_BLIND:
            return self.depth_mm
        if self.drill_tip is DrillTipConvention.TOTAL_TIP_DEPTH:
            return self.depth_mm
        return self.depth_mm + self.tip_extra_mm

    @property
    def cylindrical_depth_mm(self) -> float:
        """Depth of the full-diameter portion below the stock top."""
        if self.kind is not FeatureKind.HOLE_BLIND:
            return self.depth_mm
        if self.drill_tip is DrillTipConvention.TOTAL_TIP_DEPTH:
            return max(0.0, self.depth_mm - self.tip_extra_mm)
        return self.depth_mm


class PartSpec(Contract):
    schema_version: str = SCHEMA_VERSION
    spec_id: Ident
    revision: int = Field(ge=1)
    units: Units
    material: str = Field(min_length=1, max_length=80)
    stock_x_mm: PosMm
    stock_y_mm: PosMm
    stock_z_mm: PosMm
    features: tuple[Feature, ...] = Field(min_length=1, max_length=64)
    confirmed_at: datetime | None = None
    source_asset_ids: tuple[Ident, ...] = ()

    @model_validator(mode="after")
    def _geometry(self) -> PartSpec:
        if self.units is Units.UNKNOWN:
            raise ValueError("A confirmed specification cannot carry unknown units.")
        ids = [f.feature_id for f in self.features]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate feature IDs.")
        for f in self.features:
            if f.total_tip_depth_mm >= self.stock_z_mm:
                raise ValueError(f"Feature {f.feature_id} breaks through the stock bottom.")
            if f.kind is FeatureKind.POCKET_RECT_ROUNDED:
                inside = 0 <= f.x_min_mm and f.x_max_mm <= self.stock_x_mm
                inside &= 0 <= f.y_min_mm and f.y_max_mm <= self.stock_y_mm
            else:
                r = f.diameter_mm / 2
                inside = 0 <= f.center_x_mm - r and f.center_x_mm + r <= self.stock_x_mm
                inside &= 0 <= f.center_y_mm - r and f.center_y_mm + r <= self.stock_y_mm
            if not inside:
                raise ValueError(f"Feature {f.feature_id} lies outside the stock.")
        return self

    @property
    def design_hash(self) -> str:
        """Identity of the customer's requested shape; repair must never change it."""
        return stable_hash(
            {
                "units": self.units.value,
                "material": self.material,
                "stock": [self.stock_x_mm, self.stock_y_mm, self.stock_z_mm],
                "features": sorted(
                    (f.model_dump(mode="json") for f in self.features),
                    key=lambda d: d["feature_id"],
                ),
            }
        )


class SpecProposal(Contract):
    """Model output before human confirmation. Unknowns stay unknown."""

    proposal_id: Ident
    spec_id: Ident
    revision: int = Field(ge=1)
    units: Units
    material: str | None = None
    stock_x_mm: float | None = None
    stock_y_mm: float | None = None
    stock_z_mm: float | None = None
    features: tuple[Feature, ...] = ()
    unresolved_fields: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence: dict[str, str] = Field(default_factory=dict)
    origin: Literal["example", "typed", "vision", "fixture"] = "typed"
    provider: str | None = None
    model: str | None = None

    @property
    def ready(self) -> bool:
        return not self.unresolved_fields and self.units is not Units.UNKNOWN


# ----------------------------------------------------------------------- shop side


class ToolKind(StrEnum):
    END_MILL = "end_mill"
    DRILL = "drill"


class OperationKind(StrEnum):
    POCKET_RASTER = "pocket_raster"
    DRILL = "drill"


class EntryStrategy(StrEnum):
    PLUNGE = "plunge"
    RAMP = "ramp"


class Tool(Contract):
    tool_id: Ident
    kind: ToolKind
    diameter_mm: PosMm
    cutting_length_mm: PosMm
    stickout_mm: PosMm
    shank_diameter_mm: PosMm
    holder_diameter_mm: PosMm
    center_cutting: bool = True
    point_angle_deg: Annotated[float, Field(gt=0, lt=180)] | None = None
    allowed_operations: tuple[OperationKind, ...] = Field(min_length=1)
    feed_mm_min: PosMm
    spindle_rpm: Annotated[float, Field(gt=0, le=60_000)]

    @model_validator(mode="after")
    def _envelope(self) -> Tool:
        if self.stickout_mm < self.cutting_length_mm:
            raise ValueError(f"Tool {self.tool_id} stickout is shorter than its cutting length.")
        if self.kind is ToolKind.DRILL and self.point_angle_deg is None:
            raise ValueError(f"Drill {self.tool_id} must declare a point angle.")
        return self


class FixtureSolid(Contract):
    """Axis-aligned clamp/vise geometry in stock coordinates. Not decoration."""

    fixture_id: Ident
    x_min_mm: Mm
    x_max_mm: Mm
    y_min_mm: Mm
    y_max_mm: Mm
    z_min_mm: Mm
    z_max_mm: Mm

    @model_validator(mode="after")
    def _extents(self) -> FixtureSolid:
        if self.x_max_mm <= self.x_min_mm or self.y_max_mm <= self.y_min_mm:
            raise ValueError(f"Fixture {self.fixture_id} has non-positive extents.")
        if self.z_max_mm <= self.z_min_mm:
            raise ValueError(f"Fixture {self.fixture_id} has non-positive height.")
        return self


class ShopProfile(Contract):
    schema_version: str = SCHEMA_VERSION
    shop_id: Ident
    display_name: str = Field(min_length=1, max_length=80)
    envelope_x_mm: PosMm
    envelope_y_mm: PosMm
    envelope_z_mm: PosMm
    axes: tuple[Literal["X", "Y", "Z"], ...] = ("X", "Y", "Z")
    max_feed_mm_min: PosMm
    max_spindle_rpm: Annotated[float, Field(gt=0, le=60_000)]
    tools: tuple[Tool, ...] = Field(min_length=1, max_length=64)
    fixtures: tuple[FixtureSolid, ...] = ()
    home_x_mm: Mm
    home_y_mm: Mm
    home_z_mm: Mm
    min_fixture_clearance_mm: PosMm = 3.0
    rapid_feed_mm_min: PosMm = 8000.0
    tool_change_seconds: Annotated[float, Field(ge=0, le=600)] = 12.0
    setup_seconds: Annotated[float, Field(ge=0, le=3600)] = 120.0

    @model_validator(mode="after")
    def _unique(self) -> ShopProfile:
        ids = [t.tool_id for t in self.tools]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate tool IDs in inventory.")
        return self

    def tool(self, tool_id: str) -> Tool | None:
        return next((t for t in self.tools if t.tool_id == tool_id), None)

    @property
    def shop_hash(self) -> str:
        return stable_hash(self)


# ----------------------------------------------------------------------- the recipe


class Setup(Contract):
    setup_id: Ident
    description: str = Field(min_length=1, max_length=200)


class Operation(Contract):
    operation_id: Ident
    setup_id: Ident
    feature_id: Ident
    tool_id: Ident
    kind: OperationKind
    stepdown_mm: PosMm
    stepover_mm: PosMm
    entry: EntryStrategy
    feed_mm_min: PosMm
    spindle_rpm: Annotated[float, Field(gt=0, le=60_000)]
    peck_depth_mm: PosMm | None = None


class ProcessPlan(Contract):
    """The machining recipe. Contains data only; never executable code."""

    schema_version: str = SCHEMA_VERSION
    plan_id: Ident
    policy_version: str = Field(min_length=1, max_length=32)
    spec_design_hash: str
    shop_hash: str
    setups: tuple[Setup, ...] = Field(min_length=1, max_length=8)
    operations: tuple[Operation, ...] = Field(min_length=1, max_length=64)
    clearance_mm: PosMm
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _references(self) -> ProcessPlan:
        setup_ids = {s.setup_id for s in self.setups}
        seen: set[str] = set()
        for op in self.operations:
            if op.operation_id in seen:
                raise ValueError(f"Duplicate operation ID {op.operation_id}.")
            seen.add(op.operation_id)
            if op.setup_id not in setup_ids:
                raise ValueError(f"Operation {op.operation_id} references unknown setup.")
        return self

    @property
    def execution_payload(self) -> dict:
        """Everything that changes what the machine would actually do.

        Cosmetic plan/operation IDs and notes are excluded, and setups are
        referenced by position so renaming one does not change execution identity.
        Feed, spindle speed and peck depth are included: leaving them out made two
        plans with materially different cycle times share a fingerprint, so a
        genuinely new candidate was mistaken for a repeat.
        """
        setup_index = {s.setup_id: i for i, s in enumerate(self.setups)}
        return {
            "clearance": round(self.clearance_mm, 6),
            "setup_count": len(self.setups),
            "operations": [
                {
                    "setup": setup_index.get(o.setup_id, -1),
                    "feature": o.feature_id,
                    "tool": o.tool_id,
                    "kind": o.kind.value,
                    "stepdown": round(o.stepdown_mm, 6),
                    "stepover": round(o.stepover_mm, 6),
                    "entry": o.entry.value,
                    "feed": round(o.feed_mm_min, 6),
                    "spindle": round(o.spindle_rpm, 6),
                    "peck": None if o.peck_depth_mm is None else round(o.peck_depth_mm, 6),
                }
                for o in self.operations
            ],
        }

    @property
    def fingerprint(self) -> str:
        """Detects a repair that proposed the same candidate again.

        Prefixed with its algorithm version: a hash from an older definition is a
        different kind of identity and must never be compared as if it were equal.
        """
        return f"{FINGERPRINT_VERSION}:{stable_hash(self.execution_payload)}"


# --------------------------------------------------------------------------- checks


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Severity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class CheckStage(StrEnum):
    SCHEMA = "schema"
    PREFLIGHT = "preflight"
    PATH = "path"
    SIMULATION = "simulation"


class CheckResult(Contract):
    check_id: str = Field(min_length=1, max_length=64)
    check_version: str = "1"
    stage: CheckStage
    status: CheckStatus
    severity: Severity
    message: str = Field(min_length=1, max_length=400)
    feature_id: str | None = None
    operation_id: str | None = None
    segment_id: str | None = None
    actual: float | str | None = None
    required: float | str | None = None
    units: str | None = None
    evidence: dict[str, str | float | int | bool] = Field(default_factory=dict)
    repair_hint: str | None = Field(default=None, max_length=400)

    @property
    def blocking_failure(self) -> bool:
        return self.status is CheckStatus.FAIL and self.severity is Severity.BLOCKING


# ---------------------------------------------------------------------- trajectory


class MotionKind(StrEnum):
    RAPID = "rapid"
    FEED = "feed"
    RETRACT = "retract"
    DWELL = "dwell"
    TOOL_CHANGE = "tool_change"


class Segment(Contract):
    segment_id: Ident
    operation_id: str | None
    tool_id: str | None
    kind: MotionKind
    start_x_mm: Mm
    start_y_mm: Mm
    start_z_mm: Mm
    end_x_mm: Mm
    end_y_mm: Mm
    end_z_mm: Mm
    feed_mm_min: float = Field(ge=0)
    cutting: bool = False
    duration_s: float = Field(ge=0)

    @property
    def length_mm(self) -> float:
        return math.dist(
            (self.start_x_mm, self.start_y_mm, self.start_z_mm),
            (self.end_x_mm, self.end_y_mm, self.end_z_mm),
        )


class Trajectory(Contract):
    schema_version: str = SCHEMA_VERSION
    trajectory_id: Ident
    plan_id: Ident
    spec_design_hash: str
    shop_hash: str
    compiler_version: str
    initial_x_mm: Mm
    initial_y_mm: Mm
    initial_z_mm: Mm
    segments: tuple[Segment, ...] = Field(min_length=1, max_length=20000)
    max_step_mm: PosMm = 0.5

    @property
    def trajectory_hash(self) -> str:
        return stable_hash(self)

    @property
    def estimated_seconds(self) -> float:
        return sum(s.duration_s for s in self.segments)


# --------------------------------------------------------------------- simulation


class SimulationStatus(StrEnum):
    PASS = "pass"
    COLLISION = "collision"
    INCOMPLETE_REMOVAL = "incomplete_removal"
    GOUGE = "gouge"
    UNSUPPORTED = "unsupported"


class CollisionEvent(Contract):
    segment_id: str
    operation_id: str | None
    obstacle_id: str
    obstacle_kind: Literal["fixture", "stock"]
    colliding_part: Literal["cutter", "shank", "holder"]
    x_mm: Mm
    y_mm: Mm
    z_mm: Mm
    penetration_mm: float = Field(ge=0)


class FeatureCoverage(Contract):
    feature_id: str
    target_depth_mm: float
    achieved_depth_mm: float
    removed_fraction: float = Field(ge=0, le=1)


class SimulationResult(Contract):
    schema_version: str = SCHEMA_VERSION
    simulation_id: Ident
    trajectory_hash: str
    status: SimulationStatus
    method: str = "heightfield_2_5d"
    grid_mm: PosMm
    collisions: tuple[CollisionEvent, ...] = ()
    coverage: tuple[FeatureCoverage, ...] = ()
    max_residual_mm: float = Field(ge=0)
    max_gouge_mm: float = Field(ge=0)
    residual_threshold_mm: float = Field(gt=0)
    gouge_threshold_mm: float = Field(gt=0)
    elapsed_s: float = Field(ge=0)
    keyframe_count: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        return self.status is SimulationStatus.PASS


# ------------------------------------------------------------------------ attempts


class Disposition(StrEnum):
    PASSED = "passed"
    FAILED_CHECKS = "failed_checks"
    FAILED_SIMULATION = "failed_simulation"
    SCHEMA_INVALID = "schema_invalid"
    CANCELLED = "cancelled"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ERROR = "error"


class ModelUsage(Contract):
    provider: str
    model: str
    calls: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    latency_s: float = Field(ge=0)
    cost_usd: float | None = None
    cost_status: Literal["known", "unknown", "not_applicable"] = "unknown"


class Attempt(Contract):
    schema_version: str = SCHEMA_VERSION
    attempt_id: Ident
    job_id: Ident
    index: int = Field(ge=0)
    parent_attempt_id: str | None = None
    policy_version: str
    origin: Literal["live", "replay", "fixture"] = "live"
    plan: ProcessPlan | None = None
    plan_source: Literal[
        "naive_seed", "model", "deterministic_planner", "repair", "memory_recipe"
    ] = "model"
    checks: tuple[CheckResult, ...] = ()
    trajectory_hash: str | None = None
    simulation: SimulationResult | None = None
    usage: ModelUsage | None = None
    disposition: Disposition
    repair_diff: tuple[str, ...] = ()
    memory_episode_ids: tuple[str, ...] = ()
    memory_lesson_ids: tuple[str, ...] = ()
    memory_recipe_episode_id: str | None = None
    started_at: datetime
    finished_at: datetime

    @property
    def blocking_failures(self) -> tuple[CheckResult, ...]:
        return tuple(c for c in self.checks if c.blocking_failure)


class JobState(StrEnum):
    EMPTY = "empty"
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    NEEDS_CLARIFICATION = "needs_clarification"
    CONFIRMED = "confirmed"
    CAD_BUILDING = "cad_building"
    PLANNING = "planning"
    CHECKING = "checking"
    COMPILING = "compiling"
    PATH_CHECKING = "path_checking"
    SIMULATING = "simulating"
    REPAIRING = "repairing"
    SUPERVISING = "supervising"
    OPTIMIZING = "optimizing"
    FINALIZING = "finalizing"
    PASSED = "passed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCELLED = "cancelled"
    FAILED = "failed"
    SERVICE_UNAVAILABLE = "service_unavailable"


ACTIVE_STATES = frozenset(
    {
        JobState.EXTRACTING,
        JobState.CAD_BUILDING,
        JobState.PLANNING,
        JobState.CHECKING,
        JobState.COMPILING,
        JobState.PATH_CHECKING,
        JobState.SIMULATING,
        JobState.REPAIRING,
    }
)

TERMINAL_STATES = frozenset(
    {
        JobState.PASSED,
        JobState.NEEDS_HUMAN_REVIEW,
        JobState.BUDGET_EXHAUSTED,
        JobState.CANCELLED,
        JobState.FAILED,
        JobState.SERVICE_UNAVAILABLE,
    }
)


class Budget(Contract):
    max_attempts: int = Field(default=3, ge=1, le=6)
    max_model_calls: int = Field(default=6, ge=0, le=24)
    max_optimization_attempts: int = Field(default=1, ge=0, le=3)
    job_deadline_s: float = Field(default=120.0, gt=0, le=900)
    call_timeout_s: float = Field(default=45.0, gt=0, le=300)
    max_output_tokens: int = Field(default=4000, gt=0, le=32000)
    supervised_loop_enabled: bool = Field(default=False)


class RunManifest(Contract):
    schema_version: str = SCHEMA_VERSION
    job_id: Ident
    session_id: str
    origin: Literal["live", "replay", "fixture"]
    state: JobState
    policy_version: str
    commit: str | None = None
    spec: PartSpec
    shop: ShopProfile
    spec_design_hash: str
    cad_step_sha256: str | None = None
    cad_mesh_sha256: str | None = None
    attempts: tuple[Attempt, ...] = ()
    best_attempt_id: str | None = None
    weave_url: str | None = None
    wandb_run_url: str | None = None
    telemetry_status: Literal["synced", "pending", "disabled", "failed"] = "disabled"
    created_at: datetime
    updated_at: datetime
    limitations: tuple[str, ...] = ()


class RunEvent(Contract):
    """Persisted before publication; the UI renders these, never hidden state."""

    sequence: int = Field(ge=0)
    job_id: Ident
    attempt_id: str | None = None
    type: Literal[
        "state_changed",
        "assistant_message",
        "spec_proposal",
        "artifact_ready",
        "check_completed",
        "repair_diff",
        "simulation_started",
        "collision_detected",
        "attempt_completed",
        "supervisor_decision",
        "optimization_started",
        "incumbent_updated",
        "plan_selected",
        "telemetry_status",
        "planner_fallback",
        "job_completed",
        "memory_read",
        "memory_written",
        "memory_unavailable",
    ]
    timestamp: datetime
    payload: dict = Field(default_factory=dict)


# ------------------------------------------------------------------- optimization


class VerificationEvidence(Contract):
    """References to the checks and simulation that verified a candidate."""

    check_set_hash: str
    check_results_hash: str
    simulation_hash: str | None = None
    trajectory_hash: str | None = None


class CandidateMetrics(Contract):
    """Objective metrics and verification status of one candidate."""

    candidate_id: str
    attempt_id: str
    spec_design_hash: str
    shop_hash: str
    trajectory_hash: str | None
    simulator_version: str | None
    check_set_version: str
    verified: bool
    verification_evidence: VerificationEvidence | None = None
    estimated_motion_seconds: float = Field(ge=0)
    estimated_total_machining_seconds: float = Field(ge=0)
    tool_changes: int = Field(ge=0)
    setups: int = Field(ge=0, le=8)
    minimum_clearance_mm: float | None = Field(default=None, ge=0)
    max_residual_mm: float | None = Field(default=None, ge=0)
    max_gouge_mm: float | None = Field(default=None, ge=0)
    wall_time_s: float = Field(ge=0)
    simulation_calls: int = Field(ge=0)
    inference_cost_usd: float | None = Field(default=None, ge=0)
    estimated_machining_cost_usd: float | None = Field(default=None, ge=0)
    cost_estimation_model: str | None = None
    cost_currency: str | None = None


class OptimizationObjective(StrEnum):
    ESTIMATED_TOTAL_MACHINING_SECONDS = "estimated_total_machining_seconds"
    ESTIMATED_MACHINING_COST_USD = "estimated_machining_cost_usd"


class SupervisorStopReason(StrEnum):
    OBJECTIVE_SATISFIED = "objective_satisfied"
    NO_PROMISING_CHANGE = "no_promising_change"
    NO_IMPROVEMENT = "no_improvement"
    REPEATED_CANDIDATE = "repeated_candidate"
    OPTIMIZATION_LIMIT = "optimization_limit"
    BUDGET_LIMIT = "budget_limit"
    OPTIMIZATION_INCOMPLETE = "optimization_incomplete"


class SupervisorAction(StrEnum):
    IMPROVE = "improve"
    FINISH = "finish"


class SupervisorDecision(Contract):
    """Model-backed optimization decision with controller-enforced bounds."""

    decision_id: str
    input_attempt_ids: tuple[str, ...]
    incumbent_id: str | None
    objective: OptimizationObjective
    evidence_refs: tuple[str, ...] = ()
    action: SupervisorAction
    explanation: str = Field(min_length=1, max_length=500)
    planning_instruction: str | None = Field(default=None, max_length=1000)
    expected_metric_improvement: str | None = None
    stop_reason: SupervisorStopReason | None = None
