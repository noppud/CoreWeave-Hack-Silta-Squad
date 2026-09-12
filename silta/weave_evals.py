"""Publish the frozen fixture corpus to W&B Weave as a real Evaluation.

The same 12 frozen fixtures and the same deterministic scorers that
`uv run python -m silta.evaluation` reports offline, expressed as
`weave.Dataset` + `weave.Model` + `weave.Evaluation` so the results land in the
project's Evaluations tab and two policies can be compared side by side.

The scorers are deterministic geometry, not a model judging a model. Nothing here
can turn a failure green.

    uv run python -m silta.weave_evals                   # development split, both policies
    uv run python -m silta.weave_evals --split holdout   # untouched holdout, run once
    uv run python -m silta.weave_evals --live            # use the configured inference provider
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

import weave

from silta.evaluation import Fixture, load_fixtures, run_case
from silta.policy import POLICIES, get_policy

# Which check ids characterise each fixture family, for grouping in the UI.
_FAMILY_HINTS = {
    "tool_cutting_reach": "tool reach",
    "path_fixture_envelope": "fixture collision",
    "simulation_collision": "fixture collision",
    "tool_available": "missing tool",
    "pocket_corner_radius": "impossible radius",
    "tool_stickout_clearance": "holder clearance",
}


def _family(fixture: Fixture) -> str:
    """A short label for the failure family this fixture exercises."""
    expected = tuple(fixture.expectation.blocking_check_ids) + tuple(
        getattr(fixture.expectation, "accepted_blocking_check_ids", ())
    )
    for check_id in expected:
        if check_id in _FAMILY_HINTS:
            return _FAMILY_HINTS[check_id]
    if fixture.expectation.disposition.value == "passed":
        return "valid baseline"
    if fixture.expectation.disposition.value == "schema_invalid":
        return "invalid specification"
    return "other"


def build_dataset(split: str) -> weave.Dataset:
    """One row per frozen fixture, carrying its independently authored expectation."""
    rows: list[dict[str, Any]] = []
    for fixture in load_fixtures(split):  # type: ignore[arg-type]
        expectation = fixture.expectation
        accepted_dispositions = [d.value for d in getattr(expectation, "accepted_dispositions", ())]
        rows.append(
            {
                "fixture_id": fixture.fixture_id,
                "split": fixture.split,
                "family": _family(fixture),
                "description": fixture.description,
                "expected_disposition": expectation.disposition.value,
                "accepted_dispositions": accepted_dispositions,
                "expected_blocking_checks": list(expectation.blocking_check_ids),
                "accepted_blocking_checks": list(
                    getattr(expectation, "accepted_blocking_check_ids", ())
                ),
                "expected_feasible": expectation.disposition.value == "passed",
            }
        )
    return weave.Dataset(
        name=f"silta-fixtures-{split}",
        description=(
            f"Silta CNC frozen {split} corpus: {len(rows)} cases with independently authored "
            "expectations. Expected geometry is closed-form arithmetic, never derived from the "
            "CAD builder under test, so the oracle can catch a bug in it."
        ),
        rows=rows,
    )


class SiltaPolicy(weave.Model):
    """Runs the real pipeline for one fixture under one policy.

    preflight checks -> toolpath compilation -> path checks -> stock and collision
    simulation, with bounded repair. Every stage is the production code path.
    """

    policy_version: str
    max_attempts: int = 3
    use_live_inference: bool = False

    @weave.op()
    async def predict(self, fixture_id: str) -> dict[str, Any]:
        fixture = next(f for f in load_fixtures("all") if f.fixture_id == fixture_id)
        provider = _provider() if self.use_live_inference else None
        outcome = await run_case(
            fixture,
            get_policy(self.policy_version),
            provider=provider,
            max_attempts=self.max_attempts,
        )
        return {
            "disposition": outcome.disposition.value,
            "blocking_check_ids": list(outcome.blocking_check_ids),
            "feasible": outcome.disposition.value == "passed",
            "attempts": outcome.attempts,
            "simulations_run": outcome.simulations_run,
            "simulation_seconds": round(outcome.simulation_seconds, 4),
            "estimated_machining_seconds": outcome.estimated_machining_seconds,
            "clearance_mm": outcome.clearance_mm,
            "max_residual_mm": outcome.max_residual_mm,
            "max_gouge_mm": outcome.max_gouge_mm,
            "tool_changes": outcome.tool_changes,
            "wall_seconds": round(outcome.wall_seconds, 4),
            "matched_expectation": outcome.matched_expectation,
            "mismatch_reason": outcome.mismatch_reason,
            "error": outcome.error,
        }


def _provider():
    """The configured inference provider, or None when no key is present."""
    try:
        from silta.providers import WandbInferenceProvider, load_provider_from_env

        config = load_provider_from_env("planner")
        return WandbInferenceProvider(config) if config else None
    except Exception:
        return None


# --------------------------------------------------------------------------- scorers
# Deterministic. A scorer reads what the pipeline measured; none of them asks a model.


@weave.op()
def matches_expectation(
    expected_disposition: str,
    accepted_dispositions: list,
    expected_blocking_checks: list,
    accepted_blocking_checks: list,
    output: dict,
) -> dict:
    """Did the pipeline reach the outcome the frozen oracle says it should?"""
    allowed = set(accepted_dispositions) or {expected_disposition}
    disposition_ok = output["disposition"] in allowed
    actual_checks = set(output["blocking_check_ids"])
    if accepted_blocking_checks:
        checks_ok = actual_checks <= set(accepted_blocking_checks)
    else:
        checks_ok = actual_checks == set(expected_blocking_checks)
    return {"correct": bool(disposition_ok and checks_ok)}


@weave.op()
def no_false_accept(expected_feasible: bool, output: dict) -> dict:
    """A known-invalid recipe must never pass. This is the number that matters most."""
    return {"false_accept": bool(not expected_feasible and output["feasible"])}


@weave.op()
def no_false_reject(expected_feasible: bool, output: dict) -> dict:
    """A known-valid recipe must never be blocked. Guards the promoted early checks."""
    return {"false_reject": bool(expected_feasible and not output["feasible"])}


@weave.op()
def simulation_cost(output: dict) -> dict:
    """How much stock simulation the policy spent to reach its verdict."""
    return {
        "simulations_run": output["simulations_run"],
        "simulation_seconds": output["simulation_seconds"],
    }


@weave.op()
def machining_quality(output: dict) -> dict:
    """Measured cut quality, for the cases that reached simulation."""
    return {
        "max_residual_mm": output["max_residual_mm"],
        "max_gouge_mm": output["max_gouge_mm"],
        "estimated_machining_seconds": output["estimated_machining_seconds"],
    }


@weave.op()
def effort(output: dict) -> dict:
    """Candidates tried and wall clock spent."""
    return {"attempts": output["attempts"], "wall_seconds": output["wall_seconds"]}


SCORERS = [
    matches_expectation,
    no_false_accept,
    no_false_reject,
    simulation_cost,
    machining_quality,
    effort,
]


def build_evaluation(split: str, policy_version: str | None = None) -> weave.Evaluation:
    # The run label carries the split and the policy, so the Evaluations tab is readable
    # without opening each row. Weave otherwise auto-names runs "brave-star" and the like.
    label = f"silta-{split}" + (f"-{policy_version}" if policy_version else "")
    return weave.Evaluation(
        name=f"silta-{split}",
        evaluation_name=label,
        description=(
            "Deterministic geometry scorers over the frozen Silta CNC corpus. Feasibility is a "
            "conjunction: valid schema, unchanged design hash, valid CAD, every blocking check "
            "passed, full feature coverage and a successful stock/collision simulation. Unknown "
            "is not a pass, and no scorer asks a model for an opinion."
        ),
        dataset=build_dataset(split),
        scorers=SCORERS,
    )


async def run(split: str, policies: list[str], live: bool) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for version in policies:
        evaluation = build_evaluation(split, version)
        model = SiltaPolicy(
            name=f"silta-{version}",
            description=get_policy(version).description,
            policy_version=version,
            use_live_inference=live,
        )
        print(f"\n=== {split} / {version} ===")
        results[version] = await evaluation.evaluate(model)
    return results


def _summarise(version: str, payload: dict) -> str:
    def get(path: list[str], default=None):
        node: Any = payload
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    correct = get(["matches_expectation", "correct", "true_count"], 0)
    total = get(["matches_expectation", "correct", "true_count"], 0) + get(
        ["matches_expectation", "correct", "false_count"], 0
    )
    false_accept = get(["no_false_accept", "false_accept", "true_count"], 0)
    false_reject = get(["no_false_reject", "false_reject", "true_count"], 0)
    sims = get(["simulation_cost", "simulations_run", "mean"])
    return (
        f"  {version}: expectations matched {correct}/{total} · "
        f"false accepts {false_accept} · false rejects {false_reject} · "
        f"mean simulations {sims}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="development", choices=["development", "holdout", "all"])
    parser.add_argument(
        "--policy",
        action="append",
        choices=list(POLICIES),
        help="Repeatable. Defaults to every policy, so the Evaluations tab can compare them.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Plan with the configured inference provider. Consumes credits; off by default "
        "so the published evaluation stays reproducible.",
    )
    parser.add_argument("--project", default=None, help="entity/project; defaults to the env.")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()
    project = args.project or "{}/{}".format(
        os.environ.get("WANDB_ENTITY", "").strip(),
        os.environ.get("WANDB_PROJECT", "").strip(),
    )
    if project.startswith("/") or project.endswith("/"):
        parser.error("Set WANDB_ENTITY and WANDB_PROJECT, or pass --project entity/project.")
    if not os.environ.get("WANDB_API_KEY", "").strip():
        parser.error("WANDB_API_KEY is not set; a Weave evaluation has to reach the service.")

    weave.init(project)
    policies = args.policy or list(POLICIES)
    results = asyncio.run(run(args.split, policies, args.live))

    print(f"\nPublished to https://wandb.ai/{project}/weave/evaluations")
    print(f"Split: {args.split} · planner: {'live inference' if args.live else 'deterministic'}")
    for version, payload in results.items():
        print(_summarise(version, payload))


if __name__ == "__main__":
    main()
