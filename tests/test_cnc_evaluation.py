import pytest

from silta.cnc.evaluation import (
    VersionStore,
    evaluate_check_change,
    evaluate_loop_change,
)


def plan(case="part", verified=True, seconds=100, cost=10, attempts=2):
    return dict(
        case_id=case,
        input_hash="drawing-target-machine-setup",
        verifier_hash="verifier-v1",
        verified=verified,
        machining_seconds=seconds,
        cost=cost,
        simulation_attempts=attempts,
        verification_evidence=["fusion-result.json"],
    )


def check_cases():
    return [
        dict(
            case_id=label,
            label=label,
            input_hash=f"candidate-{label}",
            verifier_hash="v1",
            verification_evidence=["verified.json"],
            verification_timing={"elapsed_ms": 10000},
        )
        for label in ("valid", "invalid")
    ]


def check_runs(cases, valid_pass=True, invalid_pass=True, runtime=1):
    return [
        {
            **case,
            "passed": valid_pass if case["label"] == "valid" else invalid_pass,
            "runtime_ms": runtime,
            "runtime_samples_ms": [runtime] * 5,
        }
        for case in cases
    ]


def test_loop_only_compares_matched_successes_and_never_rewards_failed_zero_cost():
    before = [plan("simple"), plan("hard", False, None, None)]
    after = [plan("simple", seconds=90, cost=9), plan("hard", False, 0, 0)]
    result = evaluate_loop_change(before, after)
    assert result.eligible
    assert result.summary["matched_successes"] == 1
    assert result.summary["cost"] == {"baseline": 10, "proposed": 9}
    assert "cost_delta" not in result.rows[0]["scores"]  # hard sorts first


def test_lost_completion_cannot_be_offset_by_speed():
    result = evaluate_loop_change(
        [plan("a"), plan("b")], [plan("a", seconds=1, cost=1), plan("b", False, 0, 0)]
    )
    assert not result.eligible
    assert any("Lost verified" in reason for reason in result.reasons)


def test_tradeoff_is_not_silently_promoted():
    assert not evaluate_loop_change([plan()], [plan(seconds=90, cost=11)]).eligible
    assert not evaluate_loop_change([plan()], [plan()]).eligible


@pytest.mark.parametrize(
    "mutation",
    [
        {"verifier_hash": "changed"},
        {"input_hash": "changed"},
        {"verification_evidence": []},
        {"cost": float("nan")},
        {"verified": "passed"},
        {"machining_seconds": -1},
    ],
)
def test_invalid_or_unmatched_evidence_rejected(mutation):
    proposed = {**plan(), **mutation}
    with pytest.raises(ValueError):
        evaluate_loop_change([plan()], [proposed])


def test_more_success_does_not_compare_different_part_costs():
    result = evaluate_loop_change([plan("hard", False, None, None)], [plan("hard", cost=10000)])
    assert result.eligible
    assert result.summary["cost"] == {"baseline": None, "proposed": None}


def test_duplicate_or_missing_case_rejected():
    with pytest.raises(ValueError):
        evaluate_loop_change([plan(), plan()], [plan()])
    with pytest.raises(ValueError):
        evaluate_loop_change([plan("a")], [plan("b")])


def test_check_detects_failure_without_false_rejection():
    cases = check_cases()
    result = evaluate_check_change(cases, check_runs(cases), check_runs(cases, invalid_pass=False))
    assert result.eligible
    bad = evaluate_check_change(
        cases, check_runs(cases), check_runs(cases, valid_pass=False, invalid_pass=False)
    )
    assert not bad.eligible


def test_check_new_escape_rejected_even_with_lower_runtime():
    cases = check_cases()
    result = evaluate_check_change(
        cases, check_runs(cases, invalid_pass=False), check_runs(cases, runtime=0.1)
    )
    assert not result.eligible


def test_cached_label_invalidated_by_changed_input_or_verifier():
    cases = check_cases()
    old, new = check_runs(cases), check_runs(cases, invalid_pass=False)
    new[0]["input_hash"] = "modified-fixture"
    with pytest.raises(ValueError, match="input_hash"):
        evaluate_check_change(cases, old, new)


def test_check_evaluation_needs_both_labels():
    cases = check_cases()[:1]
    with pytest.raises(ValueError, match="both"):
        evaluate_check_change(cases, check_runs(cases), check_runs(cases))


def receipt(result, base, new):
    return dict(
        status="published",
        result_digest=result.digest,
        baseline_ref=base,
        proposed_ref=new,
        weave_refs=["weave:///team/project/call/real-call"],
    )


def test_promotion_requires_publication_and_keeps_immutable_versions_for_rollback(tmp_path):
    store = VersionStore(tmp_path)
    base = store.put("main_prompt", "initial prompt")
    new = store.put("main_prompt", "improved prompt")
    store.initialize("main_prompt", base)
    result = evaluate_loop_change([plan()], [plan(seconds=90, cost=9)])
    with pytest.raises(ValueError, match="published"):
        store.promote("main_prompt", base, new, result, {})
    store.promote("main_prompt", base, new, result, receipt(result, base, new))
    assert store.active()["main_prompt"] == new
    assert store.get(base)["content"] == "initial prompt"
    store.rollback("main_prompt", new, base)
    assert store.active()["main_prompt"] == base


def test_publication_is_bound_to_result_and_candidate(tmp_path):
    store = VersionStore(tmp_path)
    base, new = [store.put("checks", x) for x in ("v1", "v2")]
    store.initialize("checks", base)
    cases = check_cases()
    result = evaluate_check_change(cases, check_runs(cases), check_runs(cases, invalid_pass=False))
    wrong = receipt(result, base, new)
    wrong["proposed_ref"] = base
    with pytest.raises(ValueError):
        store.promote("checks", base, new, result, wrong)
    assert store.active()["checks"] == base


def test_object_corruption_detected(tmp_path):
    store = VersionStore(tmp_path)
    ref = store.put("dataset", check_cases())
    (tmp_path / "objects" / f"{ref}.json").write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        store.get(ref)


def test_concurrent_stale_promotion_rejected(tmp_path):
    store = VersionStore(tmp_path)
    base, new, stale = [store.put("main_prompt", value) for value in ("1", "2", "3")]
    store.initialize("main_prompt", base)
    result = evaluate_loop_change([plan()], [plan(seconds=90, cost=9)])
    store.promote("main_prompt", base, new, result, receipt(result, base, new))
    with pytest.raises(ValueError, match="current baseline"):
        store.promote("main_prompt", base, stale, result, receipt(result, base, stale))
    assert store.active()["main_prompt"] == new


def test_controller_gate_runs_versions_and_promotes_only_after_publication(tmp_path):
    from silta.cnc.evaluation import WeaveEvaluationGate
    from silta.cnc.models import ReusableProposal

    store = VersionStore(tmp_path)
    base, new = [store.put("main_prompt", x) for x in ("old", "new")]
    store.initialize("main_prompt", base)
    cases = [plan()]
    dataset = store.put("dataset", cases)
    proposal = ReusableProposal("change", "main_prompt", base, new, "", "reduce cycle time")
    calls = []

    def runner(kind, version, frozen, context):
        calls.append(version)
        assert frozen == cases
        return [{**plan(seconds=90 if version == new else 100), "version_ref": version}]

    def publish(project, result, **kwargs):
        assert store.active()["main_prompt"] == base
        assert kwargs["frozen_cases"] == cases
        assert kwargs["version_artifacts"][new]["content"] == "new"
        return receipt(result, base, new)

    gate = WeaveEvaluationGate(store, "team/project", dataset, runner, publish)
    result = gate.evaluate(proposal, None)
    assert result.promoted, result.reason
    assert calls == [base, new]
    assert store.active()["main_prompt"] == new


def test_cloud_failure_never_promotes(tmp_path):
    from silta.cnc.evaluation import WeaveEvaluationGate
    from silta.cnc.models import ReusableProposal

    store = VersionStore(tmp_path)
    base, new = [store.put("supervisor_prompt", x) for x in ("old", "new")]
    store.initialize("supervisor_prompt", base)
    dataset = store.put("dataset", [plan()])
    proposal = ReusableProposal("change", "supervisor_prompt", base, new, "", "improve")

    def runner(kind, version, cases, context):
        return [{**plan(seconds=90 if version == new else 100), "version_ref": version}]

    def publish(*args, **kwargs):
        raise ConnectionError("Weave unavailable")

    result = WeaveEvaluationGate(store, "team/project", dataset, runner, publish).evaluate(
        proposal, None
    )
    assert not result.promoted
    assert "Weave unavailable" in result.reason
    assert store.active()["supervisor_prompt"] == base


def test_useful_new_check_can_add_small_cost_but_not_erase_simulation_savings():
    cases = check_cases()
    result = evaluate_check_change(
        cases, check_runs(cases), check_runs(cases, invalid_pass=False, runtime=10)
    )
    assert result.eligible
    assert result.summary["added_runtime_upper_ms"] == 18
    assert result.summary["saved_verification_ms"] == 10000
    assert result.summary["runtime_budget_ms"] == 1000
    costly = evaluate_check_change(
        cases, check_runs(cases), check_runs(cases, invalid_pass=False, runtime=600)
    )
    assert not costly.eligible
    assert any("savings budget" in reason for reason in costly.reasons)


def test_timing_noise_alone_never_promotes_identical_check_behavior():
    cases = check_cases()
    result = evaluate_check_change(
        cases, check_runs(cases, runtime=10), check_runs(cases, runtime=9)
    )
    assert not result.eligible
    assert "No demonstrated improvement" in result.reasons


def test_check_timing_requires_repetitions_and_uses_conservative_sample_spread():
    cases = check_cases()
    before, after = check_runs(cases), check_runs(cases, invalid_pass=False)
    after[0]["runtime_samples_ms"] = [1]
    with pytest.raises(ValueError, match="5 replay samples"):
        evaluate_check_change(cases, before, after)
    after = check_runs(cases, invalid_pass=False)
    after[0]["runtime_samples_ms"] = [1, 1, 1, 1, 1001]
    result = evaluate_check_change(cases, before, after)
    assert not result.eligible
    assert any("ceiling" in reason for reason in result.reasons)


def test_check_gain_needs_observed_simulation_duration_not_machining_time():
    cases = check_cases()
    del cases[1]["verification_timing"]
    with pytest.raises(ValueError, match="verification elapsed_ms"):
        evaluate_check_change(cases, check_runs(cases), check_runs(cases, invalid_pass=False))
