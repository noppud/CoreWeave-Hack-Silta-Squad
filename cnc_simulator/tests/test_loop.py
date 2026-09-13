"""Controller/gate tests use explicit role doubles; stock verdicts remain real."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from camloop.common import candidate, cheap_checks, freeze_job, load_job, save, verify_frozen
from camloop.controller import run_job
from camloop.demo import build_corpus, reference_moves
from camloop.learning import Knowledge
from camloop.playback import entry_times
from camloop.rehearsal import Rehearsal
from cncsim.geometry import sweep


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp("camloop")
    build_corpus(root)
    return root


@pytest.fixture(scope="module")
def full_loop(prepared):
    a = run_job(prepared / "jobs/part-a/job.json", prepared, "learn-a", Rehearsal)
    b = run_job(
        prepared / "jobs/part-b/job.json", prepared, "transfer-b", Rehearsal, guidance_evaluations=0
    )
    return a, b, prepared


def test_real_simulation_repair_optimization_and_transfer(full_loop):
    a, b, root = full_loop
    assert a["status"] == b["status"] == "completed", (a["reason"], b["reason"])
    assert a["attempts"][0]["result"]["validity"] == "invalid"
    assert a["attempts"][1]["result"]["validity"] == "valid"
    assert a["best"]["seconds"] < a["attempts"][1]["result"]["estimated_time_seconds"]
    assert len(a["learning"]) == 2
    assert all(item["evaluation"]["promoted"] for item in a["learning"])
    assert a["learning"][0]["evaluation"]["newly_caught_failures"] == 2
    assert a["learning"][0]["evaluation"]["false_rejections"] == 0
    assert b["loaded_knowledge"]["version"] == 2
    assert b["attempts"][0]["stage"] == "check_failed"
    assert any(i["code"] == "learned_feature_floor" for i in b["attempts"][0]["result"]["issues"])
    assert b["attempts"][0]["playback"] is None  # failure caught before simulation
    assert b["best"] is not None
    # Live and scripted knowledge are never mixed.
    live = Knowledge(root / "knowledge", "astra", root / "corpus/index.json")
    assert live.state["version"] == 0
    index = json.loads((root / "corpus/index.json").read_text())
    assert index["held_out"] == "part-b"
    assert all("part-b" not in item["path"] for item in index["cases"])


def test_playback_matches_every_move_boundary(full_loop):
    a, _, root = full_loop
    for attempt in a["attempts"]:
        if not attempt["playback"]:
            continue
        base = (root / "runs/learn-a" / attempt["playback"]).parent
        initial = np.fromfile(base / "initial.bin", dtype="u1").astype(bool)
        removal = np.fromfile(base / "removal.bin", dtype="<f4")
        trajectory = json.loads((base / "trajectory.json").read_text())
        for i, pose in enumerate(trajectory):
            expected = np.load(base / f"states/{i:05d}.npz")["nominal"].ravel()
            actual = initial & (removal > pose["elapsed_seconds"] + 1e-5)
            assert np.array_equal(actual, expected)
        assert json.loads((base / "playback.json").read_text())["final_stock_verified"]


def test_entry_time_matches_continuous_sweep():
    rng = np.random.default_rng(42)
    points = rng.uniform(-5, 5, (10000, 3))
    for a, b in [
        (np.array([0, 0, 0.0]), np.array([3, 2, 1.0])),
        (np.zeros(3), np.array([0, 0, 3.0])),
        (np.zeros(3), np.array([3, 0, 0.0])),
        (np.zeros(3), np.zeros(3)),
    ]:
        entry = entry_times(points, a, b, 2, 3)
        assert np.array_equal(np.isfinite(entry), sweep(points, a, b, 2, 0, 3))
        for fraction in [0.1, 0.4, 0.8]:
            assert np.array_equal(
                entry <= fraction, sweep(points, a, a + (b - a) * fraction, 2, 0, 3)
            )


def test_fixed_contract_feed_and_terminal_constraints(prepared):
    job = load_job(prepared / "jobs/part-a/job.json")
    plan = copy.deepcopy(job["plan"])
    plan["moves"] = reference_moves(job)
    assert cheap_checks(job, plan) == []
    plan["moves"][1]["feed_mm_per_min"] = 10000
    assert any(i["code"] == "feed_limit" for i in cheap_checks(job, plan))
    plan["moves"] = reference_moves(job)[:-1]
    assert any(i["code"] == "final_position" for i in cheap_checks(job, plan))
    plan["tolerance_mm"] = 10
    with pytest.raises(ValueError, match="fixed"):
        cheap_checks(job, plan)


def test_scoped_floor_rule_allows_deep_air_cuts(prepared):
    case = json.loads((prepared / "corpus/part-a-valid-air-cut.json").read_text())
    assert case["result"]["validity"] == "valid"
    assert (
        cheap_checks(
            case["job"], case["plan"], [dict(name="feature_floor", family="capsule_pocket")]
        )
        == []
    )


def test_frozen_mesh_cannot_change(prepared, tmp_path):
    job, fp = freeze_job(load_job(prepared / "jobs/part-a/job.json"), tmp_path / "frozen")
    Path(job["plan"]["target"]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="Frozen"):
        verify_frozen(job, fp)


def test_unrecognized_model_fields_rejected(prepared):
    job = load_job(prepared / "jobs/part-a/job.json")
    with pytest.raises(ValueError, match="unsupported"):
        candidate(job, dict(summary="bad", moves=[dict(type="rapid", to=[2, 5, 8], override=None)]))
    with pytest.raises(ValueError, match="unsupported"):
        candidate(job, dict(summary="bad", moves=[], tolerance_mm=5))


def test_active_learning_cannot_be_edited_without_evaluation(prepared, tmp_path):
    k = Knowledge(tmp_path, "rehearsal", prepared / "corpus/index.json")
    result = k.evaluate_check("feature_floor")
    assert result["promoted"]
    active = json.loads(k.path.read_text())
    active["guidance"] = "Unevaluated lesson"
    save(k.path, active)
    with pytest.raises(ValueError, match="evaluated promotions"):
        Knowledge(tmp_path, "rehearsal", prepared / "corpus/index.json")


def test_no_duplicate_or_unsupported_check_promotion(prepared, tmp_path):
    k = Knowledge(tmp_path, "rehearsal", prepared / "corpus/index.json")
    assert k.evaluate_check("feature_floor")["promoted"]
    assert not k.evaluate_check("feature_floor")["promoted"]
    with pytest.raises(ValueError, match="Unsupported"):
        k.evaluate_check("arbitrary_python")


def test_guidance_gate_rejects_regression(prepared, tmp_path, monkeypatch):
    import camloop.learning as learning

    k = Knowledge(tmp_path, "rehearsal", prepared / "corpus/index.json")
    calls = iter(
        [
            dict(validity="valid", estimated_time_seconds=10),
            dict(validity="unknown", estimated_time_seconds=1),
        ]
        * 2
    )
    monkeypatch.setattr(learning, "simulate", lambda _: next(calls))
    roles = Rehearsal(tmp_path / "evidence")
    result = k.evaluate_guidance("Use faster feeds", roles)
    assert not result["promoted"]
    assert k.state["version"] == 0


def test_unknown_never_reaches_supervisor_or_best(prepared, monkeypatch):
    import camloop.controller as controller

    monkeypatch.setattr(
        controller,
        "simulate",
        lambda *a, **k: dict(validity="unknown", issues=[], estimated_time_seconds=0.001),
    )

    class NoSupervisor(Rehearsal):
        def ask(self, role, context):
            assert role != "supervisor"
            return super().ask(role, context)

    result = run_job(
        prepared / "jobs/part-a/job.json", prepared, "unknown-test", NoSupervisor, max_attempts=1
    )
    assert result["status"] == "incomplete"
    assert result["best"] is None


def test_budget_stop_is_not_completed(prepared):
    result = run_job(
        prepared / "jobs/part-b/job.json", prepared, "budget-test", Rehearsal, max_attempts=1
    )
    assert result["status"] == "incomplete"
    assert result["best"] is None


def test_tangent_playback_membership_matches_simulator():
    a=np.array([4.1,4.1,3.35]); b=np.array([9.9,9.9,3.35])
    p=np.array([[9.900000000000002,11.500000000000002,3.5],
                [9.9,11.5-1e-10,3.5], [9.9,11.5+1e-10,3.5]])
    assert np.array_equal(np.isfinite(entry_times(p,a,b,1.6,8)), sweep(p,a,b,1.6,0,8))
