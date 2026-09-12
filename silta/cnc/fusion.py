"""Local file transport to the Fusion main-thread add-in (no mock simulator)."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

DEFAULT_BRIDGE_DIR = Path.home() / "Library/Application Support/Silta/FusionBridge"


class FusionBridge:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(
            directory or os.environ.get("SILTA_FUSION_BRIDGE_DIR", DEFAULT_BRIDGE_DIR)
        )

    def request(
        self,
        action: str,
        payload: dict | None = None,
        *,
        candidate_hash: str = "",
        input_digest: str = "",
        timeout: float = 120.0,
    ) -> dict:
        """Submit once. Timeout does not cancel Fusion or retry a mutation."""
        request_id = uuid.uuid4().hex
        requests = self.directory / "requests"
        requests.mkdir(parents=True, exist_ok=True)
        response = self.directory / "responses" / f"{request_id}.json"
        body = dict(
            request_id=request_id,
            action=action,
            payload=payload or {},
            candidate_digest=candidate_hash,
            input_digest=input_digest,
        )
        temporary = requests / f".{request_id}.tmp"
        temporary.write_text(json.dumps(body), encoding="utf-8")
        temporary.replace(requests / f"{request_id}.json")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if response.exists():
                result = json.loads(response.read_text(encoding="utf-8"))
                for field in ("request_id", "candidate_digest", "input_digest"):
                    if result.get(field) != body[field]:
                        raise ValueError(f"Fusion response {field} mismatch")
                return result
            time.sleep(0.1)
        raise TimeoutError(
            f"Fusion request {request_id} timed out; inspect {response}; do not blindly retry"
        )

    def verify(self, candidate, context):
        from .models import Artifact, VerificationResult

        candidate.verify()
        reply = self.request(
            "simulation", candidate_hash=candidate.digest, input_digest=context.input_digest
        )
        # This bridge has no verified milling-results API. Even if a script writes
        # a forged response, it cannot turn this adapter into an approving verifier.
        return VerificationResult(
            status="unknown",
            completed=False,
            input_digest=context.input_digest,
            candidate_digest=candidate.digest,
            verifier_version="fusion-bridge-v1",
            evidence=tuple(Artifact.from_path(path) for path in reply.get("evidence", [])),
            coverage="Fusion API inspection only; requires completed UI verification",
            issues=("needs_ui_verification",),
            feedback=reply,
        )
