"""Version-pinned checks on W&B hosted sandboxes; no local execution fallback.

Uses cwsandbox 1.14.2's per-instance W&B authentication. wandb 0.30.0
deprecates wandb.sandbox in favor of this API. Credentials stay outside guests.
Generated module contract: check(data: dict) -> {"passed": bool, "issues": list[str]}.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from time import monotonic

from .models import Candidate, CheckResult, JobContext


class SandboxUnavailable(RuntimeError):
    """Infrastructure/access failure, not evidence that a candidate is invalid."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"W&B sandbox unavailable: {code}")


_HARNESS = b"""import contextlib, importlib.util, json, os, resource
resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
data = json.load(open('/tmp/input.json'))
with (open(os.devnull, 'w') as sink,
      contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink)):
    spec = importlib.util.spec_from_file_location('learned_checks', '/tmp/checks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.check(data)
with open('/tmp/result.json', 'w') as output:
    json.dump(result, output, allow_nan=False)
"""


class HostedCheckRunner:
    def __init__(
        self,
        check_path: str | Path,
        *,
        version: str,
        sha256: str,
        api_key: str,
        entity: str,
        project: str = "coreweave-hack-silta-squad",
        container_image: str = "python:3.12.13-slim",
        timeout_seconds: float = 30,
        sdk=None,
    ):
        self.check_path = Path(check_path)
        self.version = version
        self.sha256 = sha256
        self._api_key = api_key
        self.entity = entity
        self.project = project
        self.container_image = container_image
        self.timeout_seconds = timeout_seconds
        self._sdk = sdk  # Explicit SDK double only in tests.
        if not api_key or not entity:
            raise ValueError("W&B API key and entity are required")
        if not version or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("Check version and SHA256 are required")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("Check timeout must be within 0..60 seconds")

    def _load_sdk(self):
        if self._sdk is not None:
            return self._sdk
        try:
            import cwsandbox
        except ImportError:
            raise SandboxUnavailable("sdk_missing") from None
        if cwsandbox.__version__ != "1.14.2":
            raise SandboxUnavailable("sdk_version_mismatch")
        return cwsandbox

    def _safe_issue(self, value: str) -> str:
        value = value.replace(self._api_key, "[redacted]")
        return "".join(c for c in value if c.isprintable())[:1000]

    def run(self, candidate: Candidate, context: JobContext) -> CheckResult:
        started = monotonic()
        candidate.verify()
        code = self.check_path.read_bytes()
        if hashlib.sha256(code).hexdigest() != self.sha256:
            raise ValueError("Pinned check code changed")
        if context.versions.get("checks") != self.version:
            raise ValueError("Check version does not match job pin")
        if len(code) > 256_000:
            raise ValueError("Check code exceeds upload limit")
        sdk = self._load_sdk()
        artifacts = {}
        uploads = {}
        total_bytes = 0
        for index, (name, artifact) in enumerate(candidate.artifacts.items()):
            data = Path(artifact.path).read_bytes()
            if hashlib.sha256(data).hexdigest() != artifact.sha256:
                raise ValueError("Candidate artifact changed during upload preparation")
            total_bytes += len(data)
            if total_bytes > 20_000_000:
                raise ValueError("Candidate artifacts exceed check upload limit")
            remote = f"/tmp/candidate-{index}{Path(artifact.path).suffix}"
            uploads[remote] = data
            artifacts[name] = {"path": remote, "sha256": artifact.sha256}
        data = {
            "candidate": {
                "digest": candidate.digest,
                "parameters": candidate.parameters,
                "artifacts": artifacts,
            },
            "constraints": {
                "machine": context.inputs.machine,
                "tools": context.inputs.tools,
                "setup": context.inputs.setup,
                "tolerances": context.inputs.tolerances,
            },
            "input_digest": context.input_digest,
        }
        encoded = json.dumps(data, allow_nan=False).encode()
        if len(encoded) > 1_000_000:
            raise ValueError("Check JSON input exceeds upload limit")
        auth = sdk.AuthHeaders(
            headers={
                "x-wandb-api-key": self._api_key,
                "x-entity-id": self.entity,
                "x-project-name": self.project,
            },
            strategy="wandb_api_key",
        )
        try:
            with sdk.Sandbox.run(
                auth=auth,
                placement_mode="serverless",
                container_image=self.container_image,
                max_lifetime_seconds=180,
                request_timeout_seconds=45,
                resources={"cpu": "1", "memory": "512Mi"},
                network=sdk.NetworkOptions(deny_egress=True, deny_ingress=True),
                environment_variables={},
                tags=["silta-cnc-checks"],
            ) as sandbox:
                uploads.update(
                    {
                        "/tmp/checks.py": code,
                        "/tmp/input.json": encoded,
                        "/tmp/harness.py": _HARNESS,
                    }
                )
                for path, contents in uploads.items():
                    sandbox.write_file(path, contents, timeout_seconds=30).result()
                process = sandbox.exec(
                    ["python", "-I", "/tmp/harness.py"], timeout_seconds=self.timeout_seconds
                ).result()
                if process.returncode != 0:
                    return CheckResult(
                        False, ("check_execution_failed",), monotonic() - started, self.version
                    )
                output = sandbox.read_file("/tmp/result.json", timeout_seconds=30).result()
                if len(output) > 64_000:
                    raise ValueError("Check output exceeds limit")
                result = json.loads(output)
                if (
                    not isinstance(result, dict)
                    or type(result.get("passed")) is not bool
                    or not isinstance(result.get("issues"), list)
                    or len(result["issues"]) > 100
                    or not all(isinstance(i, str) for i in result["issues"])
                ):
                    raise ValueError("Invalid check output schema")
                if result["passed"] and result["issues"]:
                    raise ValueError("Passing check cannot contain issues")
                return CheckResult(
                    result["passed"],
                    tuple(self._safe_issue(i) for i in result["issues"]),
                    monotonic() - started,
                    self.version,
                )
        except (json.JSONDecodeError, ValueError):
            return CheckResult(
                False, ("invalid_check_output",), monotonic() - started, self.version
            )
        except Exception as error:
            # Do not propagate SDK request repr, HTTP headers or guest output.
            message = str(error).lower()
            if any(
                t in message for t in ("not enabled", "entitlement", "not entitled", "not enrolled")
            ):
                code = "organization_not_enabled"
            elif "auth" in type(error).__name__.lower() or "unauthenticated" in message:
                code = "authentication_failed"
            elif "permission" in message or "forbidden" in message:
                code = "access_denied"
            elif "timeout" in type(error).__name__.lower():
                code = "timeout"
            else:
                code = "execution_service_error"
            raise SandboxUnavailable(code) from None
