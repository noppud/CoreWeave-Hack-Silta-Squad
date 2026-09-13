"""Fixed integrity checks composed with an isolated, version-pinned check runner."""

from __future__ import annotations

from time import monotonic
from typing import Protocol

from .models import Candidate, CheckResult, JobContext


class CheckRunner(Protocol):
    def run(self, candidate: Candidate, context: JobContext) -> CheckResult: ...


class IntegrityChecks:
    """Integrity is mandatory; learned manufacturing checks cannot replace it."""

    def __init__(self, generated: CheckRunner):
        self.generated = generated

    def run(self, candidate: Candidate, context: JobContext) -> CheckResult:
        started = monotonic()
        issues = []
        try:
            context.inputs.verify()
            context.target.verify()
            candidate.verify()
            if context.inputs.digest != context.input_digest:
                issues.append("Manufacturing inputs changed")
            if candidate.target_digest != context.target.digest:
                issues.append("Candidate changes the accepted CAD target")
        except (ValueError, OSError) as error:
            issues.append(str(error))
        if issues:
            return CheckResult(False, tuple(issues), monotonic() - started)
        result = self.generated.run(candidate, context)
        if result.passed and result.issues:
            raise ValueError("Check runner returned pass with issues")
        expected = context.versions.get("checks")
        if expected and result.version != expected:
            raise ValueError("Check runner did not execute the pinned check version")
        return result
