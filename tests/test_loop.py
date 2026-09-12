import pytest

from silta.loop import run_loop


def test_feedback_and_previous_draft_reach_each_revision():
    responses = iter(["first draft", "fix A", "second draft", "fix B", "final draft"])
    calls = []

    def complete(system, prompt):
        calls.append((system, prompt))
        return next(responses)

    result = run_loop("test task", complete, rounds=2)
    assert len(calls) == 5
    assert "first draft" in calls[1][1]
    assert "fix A" in calls[2][1]
    assert "second draft" in calls[3][1]
    assert "fix B" in calls[4][1]
    assert result["initial"] == "first draft"
    assert result["final"] == "final draft"
    assert len(result["revisions"]) == 2


@pytest.mark.parametrize("task,rounds", [("", 1), ("   ", 1), ("task", 0), ("task", 4)])
def test_invalid_input_never_calls_provider(task, rounds):
    def complete(system, prompt):
        pytest.fail("Provider must not be called for invalid input")

    with pytest.raises(ValueError):
        run_loop(task, complete, rounds)


def test_provider_failure_stops_without_retrying():
    calls = 0

    def complete(system, prompt):
        nonlocal calls
        calls += 1
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_loop("task", complete)
    assert calls == 1
