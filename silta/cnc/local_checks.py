"""Trusted-demo Python checks in a separate process, NOT a security sandbox.

Code can still access host files and network. The clean environment, temporary
workspace and limits prevent accidental state leaks/runaways, not malicious code.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from time import monotonic

from .models import Candidate, CheckResult, JobContext

_HARNESS = """import importlib.util, json, resource
resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
spec = importlib.util.spec_from_file_location('checks', 'checks.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.check(json.load(open('input.json')))
with open('result.json', 'w') as output:
    json.dump(result, output, allow_nan=False)
"""


class LocalCheckRunner:
    def __init__(
        self, check_path: str | Path, *, version: str, sha256: str, timeout_seconds: float = 30
    ):
        self.check_path = Path(check_path)
        self.version = version
        self.sha256 = sha256
        self.timeout_seconds = timeout_seconds
        if not version or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("Check version and SHA256 are required")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("Check timeout must be within 0..60 seconds")

    def run(self, candidate: Candidate, context: JobContext) -> CheckResult:
        started = monotonic()
        candidate.verify()
        code = self.check_path.read_bytes()
        if hashlib.sha256(code).hexdigest() != self.sha256:
            raise ValueError("Pinned check code changed")
        if context.versions.get("checks") != self.version:
            raise ValueError("Check version does not match job pin")
        if len(code) > 256_000:
            raise ValueError("Check code exceeds limit")

        def failed(reason):
            return CheckResult(False, (reason,), monotonic() - started, self.version)

        with tempfile.TemporaryDirectory(prefix="silta-check-") as temporary:
            work = Path(temporary).resolve()
            artifacts = {}
            total = 0
            for index, (name, artifact) in enumerate(candidate.artifacts.items()):
                content = Path(artifact.path).read_bytes()
                if hashlib.sha256(content).hexdigest() != artifact.sha256:
                    raise ValueError("Candidate artifact changed during preparation")
                total += len(content)
                if total > 20_000_000:
                    raise ValueError("Candidate artifacts exceed limit")
                copied = work / f"candidate-{index}{Path(artifact.path).suffix}"
                copied.write_bytes(content)
                artifacts[name] = {"path": str(copied), "sha256": artifact.sha256}
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
            encoded = json.dumps(data, allow_nan=False)
            if len(encoded.encode()) > 1_000_000:
                raise ValueError("Check input exceeds limit")
            (work / "input.json").write_text(encoded)
            (work / "checks.py").write_bytes(code)
            (work / "harness.py").write_text(_HARNESS)
            environment = {
                "PATH": "/usr/bin:/bin",
                "HOME": str(work),
                "TMPDIR": str(work),
                "LANG": "C",
                "LC_ALL": "C",
            }
            process = subprocess.Popen(
                [str(Path(sys.executable).resolve()), "-I", str(work / "harness.py")],
                cwd=work,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            timed_out = False
            try:
                process.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                # Kill descendants still in our owned process group even if the
                # script's main process exited. Deliberate setsid escapes are not contained.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            if timed_out:
                return failed("check_timeout")
            if process.returncode != 0:
                return failed("check_execution_failed")
            try:
                path = work / "result.json"
                metadata = path.lstat()
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64_000:
                    return failed("invalid_check_output")
                result = json.loads(path.read_bytes())
                if (
                    not isinstance(result, dict)
                    or type(result.get("passed")) is not bool
                    or not isinstance(result.get("issues"), list)
                    or len(result["issues"]) > 100
                    or not all(isinstance(i, str) for i in result["issues"])
                    or (result["passed"] and result["issues"])
                ):
                    return failed("invalid_check_output")
                issues = tuple(
                    "".join(c for c in i if c.isprintable())[:1000] for i in result["issues"]
                )
                return CheckResult(result["passed"], issues, monotonic() - started, self.version)
            except (OSError, ValueError):
                return failed("invalid_check_output")
