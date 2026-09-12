"""The Weave evaluation harness must stay correct without touching the network.

`silta.weave_evals` publishes to W&B when run, so these tests exercise only the
pure parts: dataset construction from the frozen corpus, and the deterministic
scorers. No `weave.init`, no HTTP.
"""

from silta.evaluation import load_fixtures
from silta.weave_evals import (
    SCORERS,
    build_dataset,
    effort,
    machining_quality,
    matches_expectation,
    no_false_accept,
    no_false_reject,
    simulation_cost,
)

_REQUIRED_ROW_KEYS = {
    "fixture_id",
    "split",
    "family",
    "description",
    "expected_disposition",
    "accepted_dispositions",
    "expected_blocking_checks",
    "accepted_blocking_checks",
    "expected_feasible",
}


def test_dataset_covers_every_frozen_fixture():
    for split in ("development", "holdout"):
        rows = list(build_dataset(split).rows)
        assert len(rows) == len(load_fixtures(split))
        assert {r["fixture_id"] for r in rows} == {f.fixture_id for f in load_fixtures(split)}
        for row in rows:
            assert _REQUIRED_ROW_KEYS <= set(row)
            assert row["split"] == split


def test_dataset_rows_are_json_safe():
    """Weave serialises rows; a pydantic object or tuple in there would surprise us."""
    for split in ("development", "holdout"):
        for row in build_dataset(split).rows:
            for key, value in row.items():
                assert isinstance(value, str | bool | int | float | list | type(None)), (
                    f"{split}/{row['fixture_id']} field {key} is {type(value).__name__}"
                )


def _output(**overrides):
    base = {
        "disposition": "passed",
        "blocking_check_ids": [],
        "feasible": True,
        "attempts": 1,
        "simulations_run": 1,
        "simulation_seconds": 0.2,
        "estimated_machining_seconds": 287.4,
        "clearance_mm": 15.0,
        "max_residual_mm": 0.0,
        "max_gouge_mm": 0.0,
        "tool_changes": 1,
        "wall_seconds": 0.3,
        "matched_expectation": True,
        "mismatch_reason": None,
        "error": None,
    }
    base.update(overrides)
    return base


def test_matches_expectation_accepts_either_allowed_disposition():
    """A promoted check moves a failure earlier without changing that it is a failure."""
    kwargs = {
        "expected_disposition": "failed_simulation",
        "accepted_dispositions": ["failed_simulation", "failed_checks"],
        "expected_blocking_checks": [],
        "accepted_blocking_checks": ["simulation_collision", "path_fixture_envelope"],
    }
    late = _output(disposition="failed_simulation", blocking_check_ids=[], feasible=False)
    early = _output(
        disposition="failed_checks",
        blocking_check_ids=["path_fixture_envelope"],
        feasible=False,
    )
    assert matches_expectation(output=late, **kwargs)["correct"] is True
    assert matches_expectation(output=early, **kwargs)["correct"] is True

    wrong = _output(disposition="passed", feasible=True)
    assert matches_expectation(output=wrong, **kwargs)["correct"] is False


def test_false_accept_and_false_reject_are_distinct_and_exclusive():
    invalid_but_passed = _output(feasible=True)
    assert no_false_accept(expected_feasible=False, output=invalid_but_passed)["false_accept"]
    assert not no_false_reject(expected_feasible=False, output=invalid_but_passed)["false_reject"]

    valid_but_blocked = _output(feasible=False, disposition="failed_checks")
    assert no_false_reject(expected_feasible=True, output=valid_but_blocked)["false_reject"]
    assert not no_false_accept(expected_feasible=True, output=valid_but_blocked)["false_accept"]

    correct = _output(feasible=True)
    assert not no_false_accept(expected_feasible=True, output=correct)["false_accept"]
    assert not no_false_reject(expected_feasible=True, output=correct)["false_reject"]


def test_cost_and_quality_scorers_report_what_was_measured():
    out = _output(simulations_run=2, simulation_seconds=0.44, max_residual_mm=0.1, attempts=3)
    assert simulation_cost(output=out) == {"simulations_run": 2, "simulation_seconds": 0.44}
    assert machining_quality(output=out)["max_residual_mm"] == 0.1
    assert effort(output=out)["attempts"] == 3


def test_every_scorer_is_registered():
    """A scorer that is written but not registered silently measures nothing."""
    names = {s.name if hasattr(s, "name") else s.__name__ for s in SCORERS}
    assert {
        "matches_expectation",
        "no_false_accept",
        "no_false_reject",
        "simulation_cost",
        "machining_quality",
        "effort",
    } <= {n.split(".")[-1] for n in names}
