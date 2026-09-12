"""Versioned policies: prompt revision plus the set of promoted early checks.

A check promoted from simulation into preflight must be recorded here with its
lineage, so a comparison can attribute a change to the validator rather than to
model variation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Policy:
    version: str
    description: str
    promoted_checks: frozenset[str] = field(default_factory=frozenset)
    planner_rules: tuple[str, ...] = ()
    provenance: str = ""

    def enabled(self, check_id: str) -> bool:
        return check_id in self.promoted_checks


BASELINE_RULES = (
    "Use only tools listed in the inventory; never invent a tool.",
    "Never change the confirmed part dimensions, material or feature positions.",
    "Choose a tool whose cutting length reaches the full depth of its feature.",
    "Cover every feature in the specification with exactly one operation.",
)

POLICY_V0 = Policy(
    version="policy-v0",
    description="Baseline: schema, preflight geometry and tool checks; clamp clearance "
    "is discovered only by the stock and collision simulator.",
    promoted_checks=frozenset(),
    planner_rules=BASELINE_RULES,
    provenance="Initial hand-written policy.",
)

POLICY_V1 = Policy(
    version="policy-v1",
    description="Baseline plus the promoted path_fixture_envelope check, which rejects a "
    "non-cutting traverse whose swept tool envelope passes below a fixture before the "
    "simulator is called.",
    promoted_checks=frozenset({"path_fixture_envelope"}),
    planner_rules=BASELINE_RULES
    + (
        "Set the clearance plane above the tallest fixture the tool traverses, "
        "with at least the shop's declared minimum fixture clearance.",
    ),
    provenance="Implemented from the ARIA recommendation recorded in "
    "policies/aria-recommendation-001.md after reviewing policy-v0 development runs.",
)

POLICIES = {p.version: p for p in (POLICY_V0, POLICY_V1)}
DEFAULT_POLICY = POLICY_V0


def get_policy(version: str) -> Policy:
    if version not in POLICIES:
        raise KeyError(f"Unknown policy version {version!r}.")
    return POLICIES[version]
