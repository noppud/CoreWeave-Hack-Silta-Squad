"""UI-independent application interface.

marimo is one client of this module; nothing here imports marimo. Sessions are
isolated: a job and its artifacts belong to the session that created them, and a
request from another session is refused rather than served.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from silta.controller import JobController, JobOutcome, JobRequest
from silta.domain import (
    ACTIVE_STATES,
    Budget,
    JobState,
    PartSpec,
    ProcessPlan,
    RunEvent,
    RunManifest,
    ShopProfile,
    SourceAsset,
    SpecProposal,
    Units,
    utc_now,
)
from silta.interpreter import (
    InterpretRequest,
    example_proposal,
    interpret_drawing,
    interpret_text,
)
from silta.memory import LearningMemory
from silta.storage import RunStore, storage_from_env
from silta.telemetry import Telemetry

MAX_UPLOAD_BYTES = 8_000_000
ALLOWED_MIME = {"image/png", "image/jpeg", "application/pdf", "text/plain"}


class AccessDenied(PermissionError):
    """A session asked for something owned by a different session."""


class ConflictError(RuntimeError):
    """A stale revision or an already-active job."""


def _safe_display_name(filename: str) -> str:
    """A human-readable label for an upload, never a path.

    Storage keys are always generated ids, so this is display-only — but it still ends
    up in manifests, setup sheets and logs, so it must not carry path separators or
    parent-directory hops. `Path(name).name` alone is not enough: on POSIX it does not
    treat a backslash as a separator, so a Windows-style name survives intact.
    """
    candidate = re.split(r"[\\/]", filename)[-1]
    candidate = candidate.replace("..", "").strip().strip(".")
    candidate = re.sub(r"[\x00-\x1f\x7f]", "", candidate)
    return candidate[:200] or "upload"


def repository_commit() -> str | None:
    # A deployed image has no .git, so the build stamps the commit into the
    # environment instead.
    stamped = os.environ.get("SILTA_COMMIT", "").strip()
    if stamped:
        return stamped
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass
class Session:
    session_id: str
    proposals: dict[str, SpecProposal] = field(default_factory=dict)
    specs: dict[str, PartSpec] = field(default_factory=dict)
    assets: dict[str, SourceAsset] = field(default_factory=dict)
    asset_bytes: dict[str, bytes] = field(default_factory=dict)
    jobs: list[str] = field(default_factory=list)
    idempotency: dict[str, str] = field(default_factory=dict)
    active_job: str | None = None


@dataclass(frozen=True)
class RunRequest:
    session_id: str
    spec: PartSpec
    shop: ShopProfile
    policy_version: str = "policy-v0"
    seed_plan: ProcessPlan | None = None
    budget: Budget = field(default_factory=Budget)
    origin: str = "live"
    idempotency_key: str | None = None
    expected_spec_revision: int | None = None
    memory_enabled: bool = True


class SiltaService:
    def __init__(
        self,
        *,
        store: RunStore | None = None,
        telemetry: Telemetry | None = None,
        provider=None,
        vision_provider=None,
        artifact_root: Path | None = None,
    ) -> None:
        self.store = store or RunStore(storage_from_env())
        self.telemetry = telemetry or Telemetry.from_env()
        self.provider = provider
        self.vision_provider = vision_provider
        self.artifact_root = artifact_root or Path(
            os.environ.get("SILTA_ARTIFACT_DIR", "artifacts")
        )
        self.memory = LearningMemory(self.store.storage)
        self.controller = JobController(
            provider=provider, telemetry=self.telemetry, memory=self.memory
        )
        self._sessions: dict[str, Session] = {}
        self._outcomes: dict[str, JobOutcome] = {}
        self._job_sessions: dict[str, str] = {}
        self.commit = repository_commit()

    # ------------------------------------------------------------- sessions

    def session(self, session_id: str) -> Session:
        return self._sessions.setdefault(session_id, Session(session_id=session_id))

    def new_session_id(self) -> str:
        return f"s-{uuid.uuid4().hex[:12]}"

    def _own(self, session_id: str, job_id: str) -> None:
        owner = self._job_sessions.get(job_id)
        if owner is None:
            try:
                owner = self.store.load_manifest(job_id).session_id
            except Exception as exc:  # missing or unreadable run
                raise AccessDenied(f"Unknown job {job_id}.") from exc
        if owner != session_id:
            raise AccessDenied("This job belongs to another session.")

    # --------------------------------------------------------------- upload

    def add_asset(self, session_id: str, filename: str, data: bytes, mime: str) -> SourceAsset:
        """Store an upload under a generated ID. A filename never becomes a path."""
        if mime not in ALLOWED_MIME:
            raise ValueError(f"Unsupported file type {mime}.")
        if not data:
            raise ValueError("Empty upload.")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError(
                f"File is {len(data) / 1e6:.1f} MB; the limit is {MAX_UPLOAD_BYTES / 1e6:.0f} MB."
            )
        asset = SourceAsset(
            asset_id=f"asset-{uuid.uuid4().hex[:12]}",
            sha256=hashlib.sha256(data).hexdigest(),
            mime=mime,  # type: ignore[arg-type]
            byte_length=len(data),
            display_filename=_safe_display_name(filename),
        )
        session = self.session(session_id)
        session.assets[asset.asset_id] = asset
        session.asset_bytes[asset.asset_id] = data
        return asset

    # ----------------------------------------------------------------- spec

    async def propose_spec(
        self,
        *,
        session_id: str,
        message: str,
        asset_ids: tuple[str, ...] = (),
        use_example: bool = False,
    ) -> SpecProposal:
        session = self.session(session_id)
        if use_example:
            proposal = example_proposal()
        else:
            assets = tuple(session.assets[a] for a in asset_ids if a in session.assets)
            request = InterpretRequest(
                message=message,
                assets=assets,
                asset_bytes={
                    a: session.asset_bytes[a] for a in asset_ids if a in session.asset_bytes
                },
            )
            if assets and any(a.mime.startswith("image/") for a in assets):
                with self.telemetry.span("interpret_drawing"):
                    proposal = await interpret_drawing(request, self.vision_provider)
            else:
                with self.telemetry.span("interpret_text"):
                    proposal = interpret_text(request)
        session.proposals[proposal.proposal_id] = proposal
        return proposal

    def confirm_spec(
        self,
        *,
        session_id: str,
        proposal_id: str,
        edits: dict | None = None,
        expected_revision: int,
    ) -> PartSpec:
        """Freeze a revision. Unknown units can never be confirmed."""
        session = self.session(session_id)
        proposal = session.proposals.get(proposal_id)
        if proposal is None:
            raise AccessDenied("Unknown proposal for this session.")
        if proposal.revision != expected_revision:
            raise ConflictError(
                f"The proposal moved to revision {proposal.revision}; you confirmed "
                f"revision {expected_revision}. Review it again."
            )
        merged = proposal.model_copy(update=dict(edits or {}))
        if merged.units is Units.UNKNOWN:
            raise ValueError("Units must be resolved before the specification can be confirmed.")
        missing = [
            name
            for name in ("stock_x_mm", "stock_y_mm", "stock_z_mm", "material")
            if getattr(merged, name) in (None, "")
        ]
        if missing:
            raise ValueError("Still missing: " + ", ".join(missing))
        if not merged.features:
            raise ValueError("A specification needs at least one feature.")
        spec = PartSpec(
            spec_id=merged.spec_id,
            revision=merged.revision,
            units=merged.units,
            material=merged.material,
            stock_x_mm=merged.stock_x_mm,
            stock_y_mm=merged.stock_y_mm,
            stock_z_mm=merged.stock_z_mm,
            features=merged.features,
            confirmed_at=utc_now(),
            source_asset_ids=tuple(session.assets),
        )
        session.specs[spec.spec_id] = spec
        return spec

    def revise_spec(self, *, session_id: str, spec: PartSpec, edits: dict) -> PartSpec:
        """An input edit creates a new revision and invalidates dependent artifacts."""
        session = self.session(session_id)
        revised = spec.model_copy(
            update={**edits, "revision": spec.revision + 1, "confirmed_at": utc_now()}
        )
        PartSpec.model_validate(revised.model_dump())
        session.specs[revised.spec_id] = revised
        if session.active_job:
            self.cancel_job(session_id, session.active_job)
        return revised

    # ------------------------------------------------------------------ run

    async def run_job(self, request: RunRequest) -> AsyncIterator[RunEvent]:
        session = self.session(request.session_id)
        if request.expected_spec_revision is not None:
            if request.spec.revision != request.expected_spec_revision:
                raise ConflictError(
                    "The specification was edited after this run was requested. "
                    "Review the new revision and run again."
                )
        if request.idempotency_key and request.idempotency_key in session.idempotency:
            existing = session.idempotency[request.idempotency_key]
            for event in self.store.read_events(existing):
                yield event
            return
        if session.active_job and self._is_active(session.active_job):
            raise ConflictError("This session already has a job running. Cancel it first.")

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        job_request = JobRequest(
            session_id=request.session_id,
            spec=request.spec,
            shop=request.shop,
            policy_version=request.policy_version,
            budget=request.budget,
            origin=request.origin,
            seed_plan=request.seed_plan,
            job_id=job_id,
            idempotency_key=request.idempotency_key,
            expected_spec_revision=request.expected_spec_revision,
            artifact_dir=self.artifact_root / job_id,
            commit=self.commit,
            memory_enabled=request.memory_enabled,
        )
        session.jobs.append(job_id)
        session.active_job = job_id
        self._job_sessions[job_id] = request.session_id
        if request.idempotency_key:
            session.idempotency[request.idempotency_key] = job_id

        async for event in self.controller.run(job_request):
            self.store.append_event(event)  # persist before publishing
            yield event

        outcome = self.controller.outcomes[job_id]
        self._outcomes[job_id] = outcome
        session.active_job = None
        self._publish(job_request, outcome)

    def _is_active(self, job_id: str) -> bool:
        outcome = self.controller.outcomes.get(job_id)
        return outcome is not None and outcome.state in ACTIVE_STATES

    def _publish(self, request: JobRequest, outcome: JobOutcome) -> None:
        """Write artifacts first, then the manifest that references them."""
        job_id = request.job_id
        cad = outcome.cad
        step_sha = mesh_sha = None
        if cad is not None:
            step_sha = self.store.put_artifact(
                job_id, "target.step", cad.step_path.read_bytes(), "application/step"
            )
            mesh_sha = self.store.put_artifact(
                job_id, "target.stl", cad.mesh_path.read_bytes(), "model/stl"
            )
            step_sha, mesh_sha = cad.step_sha256, cad.mesh_sha256
        for attempt in outcome.attempts:
            self.store.write_attempt(job_id, attempt)
            trajectory = outcome.trajectories.get(attempt.attempt_id)
            if trajectory is not None:
                self.store.put_artifact(
                    job_id,
                    f"trajectory-{attempt.attempt_id}.json",
                    trajectory.model_dump_json(indent=2).encode(),
                    "application/json",
                )
        manifest = RunManifest(
            job_id=job_id,
            session_id=request.session_id,
            origin=request.origin,  # type: ignore[arg-type]
            state=outcome.state,
            policy_version=request.policy_version,
            commit=self.commit,
            spec=request.spec,
            shop=request.shop,
            spec_design_hash=request.spec.design_hash,
            cad_step_sha256=step_sha,
            cad_mesh_sha256=mesh_sha,
            attempts=tuple(outcome.attempts),
            best_attempt_id=outcome.best_attempt_id,
            telemetry_status=self.telemetry.status().weave,  # type: ignore[arg-type]
            weave_url=self.telemetry.status().weave_url,
            wandb_run_url=self.telemetry.status().run_url,
            created_at=utc_now(),
            updated_at=utc_now(),
            limitations=(
                "Geometric 2.5D stock-removal and collision simulation only; no cutting "
                "forces, deflection, chatter or machine dynamics.",
                "Estimated machining time is arithmetic from feeds and declared constants, "
                "not measured shop performance.",
                "No G-code, postprocessor or controller execution is produced.",
                "Prototype checks; not a manufacturing certification.",
            ),
        )
        self.store.publish_manifest(manifest)

    def cancel_job(self, session_id: str, job_id: str) -> None:
        self._own(session_id, job_id)
        self.controller.cancel(job_id)

    def load_run(self, session_id: str, job_id: str) -> RunManifest:
        self._own(session_id, job_id)
        return self.store.load_manifest(job_id)

    def outcome(self, session_id: str, job_id: str) -> JobOutcome | None:
        self._own(session_id, job_id)
        return self.controller.outcomes.get(job_id)

    def export_package(self, session_id: str, job_id: str, attempt_id: str) -> bytes:
        self._own(session_id, job_id)
        return self.store.export_package(job_id, attempt_id)

    def list_jobs(self, session_id: str) -> list[str]:
        return list(self.session(session_id).jobs)

    async def provider_capabilities(self) -> dict:
        if self.provider is None:
            return {
                "configured": False,
                "detail": "No inference provider is configured; the deterministic planner "
                "is used and is labelled as such.",
            }
        try:
            return {"configured": True, **(await self.provider.capabilities())}
        except Exception as exc:
            return {"configured": True, "error": type(exc).__name__, "detail": str(exc)}


def default_service() -> SiltaService:
    """Build the service from the environment, tolerating absent credentials."""
    from dotenv import load_dotenv

    load_dotenv()
    provider = None
    vision = None
    try:
        from silta.providers import WandbInferenceProvider, load_provider_from_env

        config = load_provider_from_env("planner")
        if config is not None:
            provider = WandbInferenceProvider(config)
        vision_config = load_provider_from_env("vision")
        if vision_config is not None:
            vision = WandbInferenceProvider(vision_config)
    except Exception:
        provider = None
    return SiltaService(provider=provider, vision_provider=vision)


async def run_to_completion(service: SiltaService, request: RunRequest) -> list[RunEvent]:
    return [event async for event in service.run_job(request)]


def sync_run(service: SiltaService, request: RunRequest) -> list[RunEvent]:
    return asyncio.run(run_to_completion(service, request))


def summarise(events: list[RunEvent]) -> dict:
    completed = next((e for e in reversed(events) if e.type == "job_completed"), None)
    return {
        "state": (completed.payload.get("state") if completed else JobState.FAILED.value),
        "attempts": completed.payload.get("attempts") if completed else 0,
        "message": completed.payload.get("message") if completed else "no completion event",
        "events": len(events),
    }
