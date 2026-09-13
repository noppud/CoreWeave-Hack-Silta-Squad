"""Native SDK summaries retain label-conditioned score denominators."""

import runpy
from pathlib import Path

import pytest
from weave.evaluation.eval_imperative import auto_summarize_fn

MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/demo/evaluate_learning.py")
)


def rows(catch_invalid):
    return [
        {
            "case": {"label": label},
            "proposed": {"passed": label == "valid" or not catch_invalid, "runtime_ms": 10.0},
        }
        for label in ["invalid", "invalid", "valid", "valid", "valid", "valid"]
    ]


@pytest.mark.parametrize("caught", [False, True])
def test_real_sdk_summary_uses_applicable_case_denominators(caught):
    data = rows(caught)
    scores = [MODULE["row_scores"](r["case"]["label"], r["proposed"]) for r in data]
    summary = auto_summarize_fn(scores, unscored=0)
    MODULE["validate_server_summary"](summary, MODULE["expected_summary"](data, "proposed"))
    assert summary["caught_invalid"] == {
        "true_count": 2 if caught else 0,
        "true_fraction": 1.0 if caught else 0.0,
    }
    assert summary["false_rejection"] == {"true_count": 0, "true_fraction": 0.0}
    assert summary["accepted_valid"] == {"true_count": 4, "true_fraction": 1.0}
    assert summary["runtime_ms"] == {"mean": 10.0}


def test_old_custom_summary_cannot_pass_native_score_readback():
    expected = MODULE["expected_summary"](rows(True), "proposed")
    old_output = {"caught": 2, "false_rejections": 0, "runtime_ms": 60, "output": {}}
    with pytest.raises(RuntimeError, match="native aggregate"):
        MODULE["validate_server_summary"](old_output, expected)


def test_unknown_label_cannot_be_counted_as_a_known_failure():
    with pytest.raises(ValueError, match="exact valid/invalid"):
        MODULE["row_scores"]("unknown", {"passed": False, "runtime_ms": 10})


@pytest.mark.parametrize("runtime", [float("nan"), float("inf"), -1, True])
def test_invalid_timing_cannot_make_dashboard_metric(runtime):
    with pytest.raises(ValueError, match="runtime"):
        MODULE["row_scores"]("valid", {"passed": True, "runtime_ms": runtime})
