"""Trusted CAM feedback built from executed checks, toolpaths and simulation."""

from pydantic import BaseModel, ConfigDict

from silta.domain import (
    Attempt,
    CheckResult,
    CollisionEvent,
    FeatureCoverage,
    ShopProfile,
    Trajectory,
)
from silta.toolpaths import estimated_seconds


class CamMeasurement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: str
    plan_fingerprint: str | None
    spec_design_hash: str | None
    trajectory_hash: str | None
    disposition: str
    checks: tuple[CheckResult, ...]
    estimated_machining_seconds: float | None
    segment_count: int | None
    simulation_status: str | None
    simulation_seconds: float | None
    grid_mm: float | None
    collisions: tuple[CollisionEvent, ...]
    collision_count: int
    material_removal_measured: bool
    max_residual_mm: float | None
    max_gouge_mm: float | None
    residual_threshold_mm: float | None
    gouge_threshold_mm: float | None
    coverage: tuple[FeatureCoverage, ...]


def measurement_for(
    attempt: Attempt, trajectory: Trajectory | None, shop: ShopProfile
) -> CamMeasurement:
    """Unknown measurements stay null, especially after collision early-exit."""
    sim = attempt.simulation
    removal_measured = bool(sim and not sim.collisions and sim.coverage)
    return CamMeasurement(
        attempt_id=attempt.attempt_id,
        plan_fingerprint=attempt.plan.fingerprint if attempt.plan else None,
        spec_design_hash=attempt.plan.spec_design_hash if attempt.plan else None,
        trajectory_hash=attempt.trajectory_hash,
        disposition=attempt.disposition.value,
        checks=attempt.checks,
        estimated_machining_seconds=estimated_seconds(trajectory, shop, attempt.plan)
        if trajectory and attempt.plan
        else None,
        segment_count=len(trajectory.segments) if trajectory else None,
        simulation_status=sim.status.value if sim else None,
        simulation_seconds=sim.elapsed_s if sim else None,
        grid_mm=sim.grid_mm if sim else None,
        collisions=sim.collisions[:3] if sim else (),
        collision_count=len(sim.collisions) if sim else 0,
        material_removal_measured=removal_measured,
        max_residual_mm=sim.max_residual_mm if removal_measured else None,
        max_gouge_mm=sim.max_gouge_mm if removal_measured else None,
        residual_threshold_mm=sim.residual_threshold_mm if sim else None,
        gouge_threshold_mm=sim.gouge_threshold_mm if sim else None,
        coverage=sim.coverage if removal_measured else (),
    )
