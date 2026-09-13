"""Parse Fusion's observed Issues text without a model or an inferred pass.

The Issues summary establishes verification progress and reported counts. Its
tree may omit offscreen cells, so the detail list is explicitly only what was
observed. Zero errors alone does not establish a target-stock comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IssuesReport:
    percent: float
    errors: int
    warnings: int
    process_errors: int
    observed_details: tuple[str, ...]

    @property
    def completed(self) -> bool:
        return self.percent == 100

    @property
    def result(self) -> str:
        # Process failure is not a completed manufacturing judgment. A completed
        # run with collisions is a useful failure even before stock comparison;
        # a zero-error run still requires the other approval evidence.
        if not self.completed or self.process_errors:
            return "unknown"
        return "failed" if self.errors else "requires_stock_comparison"


_SUMMARY = re.compile(
    r"Verification:\s*(\d+(?:\.\d+)?)%\s*\|\s*Errors:\s*(\d+)"
    r"\s*\|\s*Warnings:\s*(\d+)\s*\|\s*Process:\s*(\d+)"
)


def parse_issues_ax(text: str) -> IssuesReport:
    """Require the actual Issues widget's summary, never a generic '100%' label."""
    if not re.search(r"(?m)^Window:.*App: Fusion\.", text):
        raise ValueError("Expected a full Fusion accessibility snapshot")
    summaries = []
    details = []
    for line in text.splitlines():
        if ".SimulationIssuesWidget.verificationLabel" in line:
            match = _SUMMARY.search(line)
            if match is None:
                raise ValueError("Fusion Issues summary format is unrecognized")
            summaries.append(match.groups())
        if ".SimulationIssuesWidget.SimulationIssuesTreeView" in line:
            match = re.match(r"\s*\d+ container (.+), ID: ", line)
            if match:
                details.append(match.group(1))
    if len(summaries) != 1:
        raise ValueError("Expected exactly one Fusion Issues summary")
    percent, errors, warnings, process = summaries[0]
    report = IssuesReport(float(percent), int(errors), int(warnings), int(process), tuple(details))
    if not 0 <= report.percent <= 100:
        raise ValueError("Invalid verification percentage")
    return report
