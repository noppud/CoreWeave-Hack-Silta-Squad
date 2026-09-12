"""Weave tracing + W&B run metrics with graceful degradation.

The app keeps working with no W&B credentials at all.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx


@dataclass
class TelemetryStatus:
    """Status of telemetry connections."""

    weave: Literal["disabled", "pending", "synced", "failed"]
    wandb: Literal["disabled", "pending", "synced", "failed"]
    weave_url: str | None
    run_url: str | None
    detail: str | None


class _NoOpSpan:
    """No-op context manager for disabled telemetry."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Telemetry:
    """Weave tracing + W&B metrics with graceful degradation."""

    def __init__(
        self,
        entity: str | None = None,
        project: str | None = None,
        api_key: str | None = None,
        spool_path: Path | None = None,
    ) -> None:
        self.entity = entity
        self.project = project
        self.api_key = api_key
        self.spool_path = spool_path or Path("telemetry_spool")
        self.enabled = entity is not None and project is not None and api_key is not None
        self._weave_initialized = False
        self._weave_status: Literal["disabled", "pending", "synced", "failed"] = "disabled"
        self._wandb_status: Literal["disabled", "pending", "synced", "failed"] = "disabled"
        self._weave_url: str | None = None
        self._run_url: str | None = None
        self._detail: str | None = None
        self._run = None
        self._active_spans: list = []

    @classmethod
    def from_env(cls) -> Telemetry:
        """Read WANDB_API_KEY/WANDB_ENTITY/WANDB_PROJECT; returns disabled if absent."""
        api_key = os.environ.get("WANDB_API_KEY")
        entity = os.environ.get("WANDB_ENTITY")
        project = os.environ.get("WANDB_PROJECT")
        spool = os.environ.get("WANDB_SPOOL_DIR")
        spool_path = Path(spool) if spool else None
        return cls(entity, project, api_key, spool_path)

    def init_weave(self) -> None:
        """Lazy weave.init, never at import time."""
        if not self.enabled or self._weave_initialized:
            return
        try:
            import weave

            weave.init(f"{self.entity}/{self.project}")
            self._weave_initialized = True
            self._weave_status = "pending"
        except Exception as exc:
            self._weave_status = "failed"
            self._detail = f"Weave init failed: {exc}"
            self._spool_failure("weave_init", str(exc))

    def span(self, name: str, **attrs):
        """Nested trace spans; no-op when disabled."""
        if not self.enabled or not self._weave_initialized:
            return _NoOpSpan()
        try:
            # Remove sensitive keys from attrs
            safe_attrs = {
                k: v
                for k, v in attrs.items()
                if k not in ("api_key", "authorization", "auth", "token", "secret")
            }
            return self._traced_span(name, safe_attrs)
        except Exception:
            return _NoOpSpan()

    @contextmanager
    def _traced_span(self, name: str, attrs: dict):
        """Internal span tracking."""
        span_data = {"name": name, "attrs": attrs}
        self._active_spans.append(span_data)
        try:
            yield span_data
        finally:
            if self._active_spans and self._active_spans[-1] == span_data:
                self._active_spans.pop()

    def log_attempt(self, manifest, attempt) -> None:
        """W&B metrics, attempt index as the step."""
        if not self.enabled:
            return
        try:
            import wandb

            if self._run is None:
                # Initialize run with config
                self._run = wandb.init(
                    entity=self.entity,
                    project=self.project,
                    reinit=True,
                    config={
                        "commit": manifest.commit,
                        "policy_version": manifest.policy_version,
                        "origin": manifest.origin,
                        "spec_id": manifest.spec.spec_id,
                        "shop_id": manifest.shop.shop_id,
                        "cad_builder_version": "cad-1",
                        "compiler_version": "compiler-1",
                        "simulator_version": "sim-1",
                        "checker_version": "checks-1",
                    },
                )
                self._run_url = self._run.get_url()
                self._wandb_status = "pending"

            # Log metrics for this attempt
            metrics = {
                "blocking_failures": len(attempt.blocking_failures),
                "disposition": attempt.disposition,
                "attempt_index": attempt.index,
            }

            if attempt.simulation:
                sim = attempt.simulation
                metrics.update(
                    {
                        "clearance_mm": (attempt.plan.clearance_mm if attempt.plan else None),
                        "max_residual_mm": sim.max_residual_mm,
                        "max_gouge_mm": sim.max_gouge_mm,
                        "collision_count": len(sim.collisions),
                        "simulation_seconds": sim.elapsed_s,
                        "simulation_status": sim.status,
                    }
                )

            if attempt.plan:
                metrics.update(
                    {
                        "operation_count": len(attempt.plan.operations),
                        "tool_changes": len(set(op.tool_id for op in attempt.plan.operations)),
                    }
                )

            if attempt.usage:
                metrics.update(
                    {
                        "model_calls": attempt.usage.calls,
                        "prompt_tokens": attempt.usage.prompt_tokens,
                        "completion_tokens": attempt.usage.completion_tokens,
                        "model_latency_s": attempt.usage.latency_s,
                        "cost_status": attempt.usage.cost_status,
                    }
                )
                if attempt.usage.cost_usd is not None:
                    metrics["cost_usd"] = attempt.usage.cost_usd

            # Log with attempt index as step
            self._run.log(metrics, step=attempt.index)
            self._wandb_status = "pending"

        except Exception as exc:
            self._wandb_status = "failed"
            self._detail = f"W&B logging failed: {exc}"
            self._spool_failure("wandb_log", str(exc))

    def finish_run(self) -> TelemetryStatus:
        """Finish W&B run and return status."""
        if self._run is not None:
            try:
                self._run.finish()
                self._wandb_status = "synced"
            except Exception as exc:
                self._wandb_status = "failed"
                self._detail = f"W&B finish failed: {exc}"
                self._spool_failure("wandb_finish", str(exc))
        return self.status()

    def status(self) -> TelemetryStatus:
        """Current telemetry status."""
        if not self.enabled:
            return TelemetryStatus(
                weave="disabled",
                wandb="disabled",
                weave_url=None,
                run_url=None,
                detail="No W&B credentials configured",
            )
        return TelemetryStatus(
            weave=self._weave_status,
            wandb=self._wandb_status,
            weave_url=self._weave_url,
            run_url=self._run_url,
            detail=self._detail,
        )

    def _spool_failure(self, operation: str, error: str) -> None:
        """Write failed operation to spool for later inspection."""
        if not self.spool_path:
            return
        try:
            self.spool_path.mkdir(parents=True, exist_ok=True)
            import time

            timestamp = time.time()
            spool_file = self.spool_path / f"failed_{operation}_{timestamp}.json"
            spool_file.write_text(
                json.dumps(
                    {
                        "operation": operation,
                        "error": error,
                        "timestamp": timestamp,
                        "entity": self.entity,
                        "project": self.project,
                    },
                    indent=2,
                )
            )
        except Exception:
            pass

    def read_back(self, entity: str, project: str, run_id: str) -> dict | None:
        """Fetch run from W&B public API to verify it landed remotely."""
        if not self.api_key:
            return None
        try:
            url = f"https://api.wandb.ai/api/v1/runs/{entity}/{project}/{run_id}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None
