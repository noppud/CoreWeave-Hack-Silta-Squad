"""Durable, atomic run persistence with pluggable backend.

Local filesystem for development, Google Cloud Storage for deployed service.
Cloud Run's local filesystem is ephemeral.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Protocol

from silta.domain import Attempt, Disposition, RunEvent, RunManifest


class Storage(Protocol):
    """Pluggable storage backend for run artifacts."""

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        """Write bytes to storage; returns a stable URI."""
        ...

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from storage."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        ...

    def list_prefix(self, prefix: str) -> list[str]:
        """List all keys with the given prefix."""
        ...


class LocalStorage:
    """Local filesystem storage with atomic writes via temp file + os.replace."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_key(self, key: str) -> Path:
        """Refuse keys containing .., absolute paths, or backslashes."""
        if ".." in key or key.startswith("/") or "\\" in key:
            raise ValueError(f"Invalid storage key: {key}")
        return self.root / key

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        """Atomic write: temp file in same directory, then os.replace."""
        target = self._validate_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name
        os.replace(tmp_path, target)
        return f"file://{target.resolve()}"

    def get_bytes(self, key: str) -> bytes:
        target = self._validate_key(key)
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        return self._validate_key(key).exists()

    def list_prefix(self, prefix: str) -> list[str]:
        prefix_path = self._validate_key(prefix)
        if not prefix_path.exists():
            return []
        if prefix_path.is_file():
            return [prefix]
        results = []
        for path in prefix_path.rglob("*"):
            if path.is_file():
                rel = path.relative_to(self.root)
                # Storage keys use '/' on every OS, like GCS object names.
                # Windows separators are rejected by _validate_key on recall.
                results.append(rel.as_posix())
        return sorted(results)


class GcsStorage:
    """Google Cloud Storage backend with lazy import."""

    def __init__(self, bucket: str, prefix: str = "") -> None:
        self.bucket_name = bucket
        self.prefix = prefix.rstrip("/")
        self._client = None
        self._bucket = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError as exc:
                raise ImportError(
                    "google-cloud-storage not installed; required for GcsStorage"
                ) from exc
            self._client = storage.Client()
            self._bucket = self._client.bucket(self.bucket_name)

    def _key(self, key: str) -> str:
        if ".." in key or key.startswith("/") or "\\" in key:
            raise ValueError(f"Invalid storage key: {key}")
        return f"{self.prefix}/{key}".lstrip("/")

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        self._ensure_client()
        blob = self._bucket.blob(self._key(key))
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket_name}/{self._key(key)}"

    def get_bytes(self, key: str) -> bytes:
        self._ensure_client()
        blob = self._bucket.blob(self._key(key))
        return blob.download_as_bytes()

    def exists(self, key: str) -> bool:
        self._ensure_client()
        blob = self._bucket.blob(self._key(key))
        return blob.exists()

    def list_prefix(self, prefix: str) -> list[str]:
        self._ensure_client()
        full_prefix = self._key(prefix)
        blobs = self._client.list_blobs(self.bucket_name, prefix=full_prefix)
        prefix_len = len(self.prefix) + 1 if self.prefix else 0
        return sorted(blob.name[prefix_len:] for blob in blobs)


def storage_from_env() -> Storage:
    """Returns GcsStorage when SILTA_ARTIFACT_BUCKET is set, else LocalStorage."""
    bucket = os.environ.get("SILTA_ARTIFACT_BUCKET")
    if bucket:
        prefix = os.environ.get("SILTA_ARTIFACT_PREFIX", "")
        return GcsStorage(bucket, prefix)
    artifact_dir = os.environ.get("SILTA_ARTIFACT_DIR", "artifacts")
    return LocalStorage(Path(artifact_dir))


class RunStore:
    """High-level run persistence built on Storage."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def append_event(self, event: RunEvent) -> None:
        """Append an event to artifacts/<job_id>/events.jsonl."""
        key = f"artifacts/{event.job_id}/events.jsonl"
        existing = b""
        if self.storage.exists(key):
            existing = self.storage.get_bytes(key)
        line = json.dumps(event.model_dump(mode="json"), separators=(",", ":")) + "\n"
        self.storage.put_bytes(key, existing + line.encode("utf-8"), "application/jsonl")

    def read_events(self, job_id: str) -> list[RunEvent]:
        """Read all events for a job."""
        key = f"artifacts/{job_id}/events.jsonl"
        if not self.storage.exists(key):
            return []
        data = self.storage.get_bytes(key).decode("utf-8")
        events = []
        for line in data.splitlines():
            if line.strip():
                events.append(RunEvent.model_validate_json(line))
        return events

    def write_attempt(self, job_id: str, attempt: Attempt) -> None:
        """Write immutable attempt; refuse to overwrite."""
        key = f"artifacts/{job_id}/attempts/{attempt.attempt_id}.json"
        if self.storage.exists(key):
            raise ValueError(f"Attempt {attempt.attempt_id} already exists; refuse to overwrite")
        data = json.dumps(attempt.model_dump(mode="json"), indent=2).encode("utf-8")
        self.storage.put_bytes(key, data, "application/json")

    def publish_manifest(self, manifest: RunManifest) -> None:
        """Atomic replace of manifest.json."""
        key = f"artifacts/{manifest.job_id}/manifest.json"
        data = json.dumps(manifest.model_dump(mode="json"), indent=2).encode("utf-8")
        self.storage.put_bytes(key, data, "application/json")

    def load_manifest(self, job_id: str) -> RunManifest:
        """Load the manifest for a job."""
        key = f"artifacts/{job_id}/manifest.json"
        data = self.storage.get_bytes(key)
        return RunManifest.model_validate_json(data)

    def list_jobs(self, session_id: str | None = None) -> list[str]:
        """List all job IDs, optionally filtered by session."""
        keys = self.storage.list_prefix("artifacts/")
        job_ids = set()
        for key in keys:
            parts = key.split("/")
            if len(parts) >= 2 and parts[0] == "artifacts":
                job_ids.add(parts[1])
        if session_id is None:
            return sorted(job_ids)
        filtered = []
        for job_id in sorted(job_ids):
            try:
                manifest = self.load_manifest(job_id)
                if manifest.session_id == session_id:
                    filtered.append(job_id)
            except Exception:
                continue
        return filtered

    def put_artifact(self, job_id: str, name: str, data: bytes, content_type: str) -> str:
        """Store an artifact and return its URI."""
        key = f"artifacts/{job_id}/{name}"
        return self.storage.put_bytes(key, data, content_type)

    def artifact_sha256(self, job_id: str, name: str) -> str:
        """Compute SHA-256 of an artifact."""
        key = f"artifacts/{job_id}/{name}"
        data = self.storage.get_bytes(key)
        return hashlib.sha256(data).hexdigest()

    def export_package(self, job_id: str, attempt_id: str) -> bytes:
        """Build export ZIP with verification."""
        manifest = self.load_manifest(job_id)
        attempt = next((a for a in manifest.attempts if a.attempt_id == attempt_id), None)
        if attempt is None:
            raise ValueError(f"Attempt {attempt_id} not found in job {job_id}")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write JSON files
            zf.writestr(
                "part_spec.json",
                json.dumps(manifest.spec.model_dump(mode="json"), indent=2),
            )
            zf.writestr(
                "shop_profile.json",
                json.dumps(manifest.shop.model_dump(mode="json"), indent=2),
            )
            if attempt.plan:
                zf.writestr(
                    "process_plan.json",
                    json.dumps(attempt.plan.model_dump(mode="json"), indent=2),
                )
            if attempt.simulation:
                zf.writestr(
                    "validation.json",
                    json.dumps(attempt.simulation.model_dump(mode="json"), indent=2),
                )

            # Write trajectory if present
            if attempt.trajectory_hash:
                try:
                    traj_key = f"artifacts/{job_id}/trajectory_{attempt_id}.json"
                    if self.storage.exists(traj_key):
                        traj_data = self.storage.get_bytes(traj_key)
                        actual_hash = hashlib.sha256(traj_data).hexdigest()
                        if actual_hash != attempt.trajectory_hash:
                            raise ValueError(
                                f"Trajectory hash mismatch: {actual_hash} != "
                                f"{attempt.trajectory_hash}"
                            )
                        zf.writestr("trajectory.json", traj_data)
                except Exception:
                    pass

            # Write CAD artifacts if present and verify hashes
            if manifest.cad_step_sha256:
                step_data = self.storage.get_bytes(f"artifacts/{job_id}/target.step")
                actual = hashlib.sha256(step_data).hexdigest()
                if actual != manifest.cad_step_sha256:
                    raise ValueError(f"STEP hash mismatch: {actual} != {manifest.cad_step_sha256}")
                zf.writestr("target.step", step_data)

            if manifest.cad_mesh_sha256:
                mesh_data = self.storage.get_bytes(f"artifacts/{job_id}/target.stl")
                actual = hashlib.sha256(mesh_data).hexdigest()
                if actual != manifest.cad_mesh_sha256:
                    raise ValueError(f"STL hash mismatch: {actual} != {manifest.cad_mesh_sha256}")
                zf.writestr("target.stl", mesh_data)

            # Setup sheet
            sheet = setup_sheet_markdown(manifest, attempt)
            zf.writestr("setup-sheet.md", sheet)

            # Manifest summary
            zf.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "job_id": manifest.job_id,
                        "attempt_id": attempt_id,
                        "origin": manifest.origin,
                        "policy_version": manifest.policy_version,
                        "commit": manifest.commit,
                        "coordinate_convention": "X/Y align with stock, Z up, stock top = 0",
                        "versions": {
                            "cad_builder": "cad-1",
                            "compiler": "compiler-1",
                            "simulator": "sim-1",
                            "checker": "checks-1",
                        },
                        "hashes": {
                            "spec_design": manifest.spec_design_hash,
                            "cad_step": manifest.cad_step_sha256,
                            "cad_mesh": manifest.cad_mesh_sha256,
                            "trajectory": attempt.trajectory_hash,
                        },
                        "disposition": attempt.disposition,
                        "limitations": list(manifest.limitations)
                        + [
                            "2.5D geometric simulation only",
                            "Estimated not measured cycle time",
                            "No G-code or postprocessor",
                            "Prototype checks, not certification",
                        ],
                    },
                    indent=2,
                ),
            )

        return buf.getvalue()


def setup_sheet_markdown(manifest: RunManifest, attempt: Attempt) -> str:
    """Generate a shop traveller markdown document."""
    spec = manifest.spec
    shop = manifest.shop
    plan = attempt.plan

    if attempt.disposition != Disposition.PASSED:
        status_line = f"**STATUS: {attempt.disposition.upper()} - NOT FOR PRODUCTION**\n\n"
    else:
        status_line = "**STATUS: PASSED VALIDATION**\n\n"

    lines = [
        "# Setup Sheet\n",
        status_line,
        f"**Job ID:** {manifest.job_id}\n",
        f"**Attempt:** {attempt.attempt_id}\n",
        f"**Policy:** {manifest.policy_version}\n",
        f"**Origin:** {manifest.origin}\n\n",
        "## Part Specification\n\n",
        f"- **Part ID:** {spec.spec_id} (rev {spec.revision})\n",
        f"- **Material:** {spec.material}\n",
        f"- **Stock:** {spec.stock_x_mm} × {spec.stock_y_mm} × {spec.stock_z_mm} mm\n",
        f"- **Features:** {len(spec.features)}\n\n",
        "## Features\n\n",
    ]

    for feat in spec.features:
        lines.append(f"- **{feat.feature_id}** ({feat.kind}): depth {feat.depth_mm} mm\n")

    lines.append("\n## Shop Configuration\n\n")
    lines.append(f"- **Shop:** {shop.display_name}\n")
    lines.append(f"- **Envelope:** {shop.envelope_x_mm} × {shop.envelope_y_mm} × ")
    lines.append(f"{shop.envelope_z_mm} mm\n")
    lines.append(f"- **Tools available:** {len(shop.tools)}\n")
    lines.append(f"- **Fixtures:** {len(shop.fixtures)}\n\n")

    if plan:
        lines.append("## Operations\n\n")
        lines.append(f"**Clearance plane:** {plan.clearance_mm} mm above stock\n\n")
        lines.append("| Op ID | Feature | Tool | Depth | Step | Feed | RPM |\n")
        lines.append("|-------|---------|------|-------|------|------|-----|\n")
        for op in plan.operations:
            lines.append(
                f"| {op.operation_id} | {op.feature_id} | {op.tool_id} | "
                f"{op.stepdown_mm} mm | {op.stepover_mm} mm | "
                f"{op.feed_mm_min} mm/min | {op.spindle_rpm} RPM |\n"
            )

        # Estimated time
        lines.append("\n## Estimated Cycle Time\n\n")
        if attempt.trajectory_hash and attempt.simulation:
            lines.append(
                f"**Total:** ~{attempt.simulation.elapsed_s:.1f} seconds "
                f"(motion only, excludes setup)\n"
            )
            lines.append(
                "\n*Assumptions: arithmetic feed/rapid calculations, "
                "no acceleration or controller overhead*\n"
            )
        else:
            lines.append("*Estimate not available*\n")

    lines.append("\n## Validation Summary\n\n")
    if attempt.checks:
        blocking = [c for c in attempt.checks if c.blocking_failure]
        if blocking:
            lines.append(f"**Blocking failures:** {len(blocking)}\n\n")
            for chk in blocking[:5]:
                lines.append(f"- {chk.check_id}: {chk.message}\n")
        else:
            lines.append("All checks passed.\n")

    if attempt.simulation:
        sim = attempt.simulation
        lines.append(f"\n**Simulation:** {sim.status}\n")
        lines.append(f"- Max residual: {sim.max_residual_mm} mm\n")
        lines.append(f"- Max gouge: {sim.max_gouge_mm} mm\n")
        lines.append(f"- Collisions: {len(sim.collisions)}\n")
        if sim.collisions:
            for col in sim.collisions[:3]:
                lines.append(f"  - {col.colliding_part} at segment {col.segment_id}\n")

    lines.append("\n## Coordinate Convention\n\n")
    lines.append("- X/Y align with the stock block\n")
    lines.append("- Z points up\n")
    lines.append("- Stock top is Z = 0\n")
    lines.append("- Features enter from +Z\n\n")

    lines.append("## Limitations\n\n")
    for lim in manifest.limitations:
        lines.append(f"- {lim}\n")
    lines.append("- 2.5D geometric simulation only\n")
    lines.append("- Estimated not measured cycle time\n")
    lines.append("- No G-code or postprocessor\n")
    lines.append("- Prototype checks, not certification\n")

    return "".join(lines)
