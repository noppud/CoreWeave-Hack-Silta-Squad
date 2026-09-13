"""Monitoring must score finalized jobs without treating missing evidence as success."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / "scripts/demo/sponsor_review.py"
spec = importlib.util.spec_from_file_location("sponsor_review", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def call(output, ended_at="finished"):
    return SimpleNamespace(output=output, ended_at=ended_at, exception=None)


def test_live_call_is_not_scored():
    assert module.review_finalized_call(call({"job_id": "demo-umc-live"}, None)) is None


def test_false_completion_flag_requires_missing_evidence():
    result = module.review_finalized_call(
        call(
            {
                "job_id": "demo-umc-1",
                "status": "completed",
                "best_verification": {"status": "passed", "completed": True},
            }
        )
    )
    assert result["false_completion"]
    assert not result["has_verified_best"]


def test_incomplete_job_can_retain_verified_best():
    result = module.review_finalized_call(
        call(
            {
                "job_id": "demo-umc-1",
                "status": "incomplete",
                "best_candidate": {"id": "candidate"},
                "best_verification": {
                    "status": "passed",
                    "completed": True,
                    "evidence": [{"path": "e"}],
                },
            }
        )
    )
    assert result["has_verified_best"]
    assert not result["false_completion"]


def test_replay_evaluation_is_not_mistaken_for_fusion_job():
    assert module.review_finalized_call(call({"variant": "learned", "caught": 2})) is None
