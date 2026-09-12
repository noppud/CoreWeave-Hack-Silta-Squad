"""Atomic manifests and immutable artifact snapshots for each job."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Artifact, Candidate, JobInputs, Target


def _name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value):
        raise ValueError(f"Invalid artifact or job identifier: {value!r}")
    return value


class JobStore:
    def __init__(self, root: str | Path, job_id: str):
        self.directory = Path(root).resolve() / _name(job_id)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.manifest_path = self.directory / "manifest.json"
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "job_id": job_id,
            "status": "running",
            "events": [],
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.save()

    def save(self) -> None:
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, prefix=".manifest-")
        try:
            with os.fdopen(descriptor, "w") as file:
                json.dump(self.data, file, indent=2, sort_keys=True, allow_nan=False)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.manifest_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def event(self, kind: str, **payload: Any) -> None:
        self.data["events"].append({"event": kind, "at": datetime.now(UTC).isoformat(), **payload})
        self.save()

    def snapshot(self, group: str, artifacts: dict[str, Artifact]) -> dict[str, Artifact]:
        destination = self.directory / _name(group)
        destination.mkdir(exist_ok=False)
        result = {}
        for key, artifact in artifacts.items():
            artifact.verify()
            target = destination / (_name(key) + Path(artifact.path).suffix)
            shutil.copyfile(artifact.path, target)
            copied = Artifact.from_path(target)
            if copied.sha256 != artifact.sha256:
                raise ValueError("Artifact changed while snapshotting")
            target.chmod(0o444)
            result[key] = copied
        return result

    def inputs(self, inputs: JobInputs) -> JobInputs:
        inputs.verify()
        pins: dict[str, Artifact] = {}

        def collect(artifact: Artifact) -> Artifact:
            pins[f"artifact-{len(pins):04d}"] = artifact
            return artifact

        # Work with a deep independent copy; preserve arbitrary catalog/provenance
        # metadata while relocating only explicit {path, sha256} artifact records.
        prepared = inputs.map_artifacts(collect)
        artifacts = self.snapshot("inputs", pins)
        relocated = iter(artifacts.values())
        result = prepared.map_artifacts(lambda _: next(relocated))
        result.verify()
        if result.digest != prepared.digest:
            raise ValueError("Input identity changed while snapshotting artifacts")
        self.data["inputs"] = asdict(result)
        self.data["input_digest"] = result.digest
        self.save()
        return result

    def target(self, target: Target) -> Target:
        result = replace(target, artifacts=self.snapshot("target", target.artifacts))
        self.data["target"] = asdict(result)
        self.data["target_digest"] = result.digest
        self.save()
        return result

    def candidate(self, candidate: Candidate, attempt: int) -> Candidate:
        return replace(
            candidate, artifacts=self.snapshot(f"attempt-{attempt:04d}", candidate.artifacts)
        )
