"""Contract doubles exercise the fixed runner; no simulated manufacturing labels."""

import copy
import json
from pathlib import Path

import pytest
from test_cnc_ui_verifier import BridgeDouble, case  # noqa: F401
from test_simulation_coverage import _api_machine
from test_simulation_report import snapshot

from silta.cnc.fixed_verifier import FixedFusionVerifier
from silta.cnc.simulation_coverage import _inspect_machine_coverage


class FixedBridge(BridgeDouble):
    def __init__(self):
        super().__init__()
        self.binding = copy.deepcopy(self.binding)
        machine, cam, _, _ = _api_machine()
        scope = _inspect_machine_coverage(machine, cam)
        self.binding["expected_machine_coverage"] = scope
        self.binding["setups"][0]["machine_coverage"] = copy.deepcopy(scope)
        self.binding["operations"][0]["tool"] = {
            "geometry": {"DC": 12.7},
            "holder": {"segments": [{"height": 10}]},
        }

    def request(self, action, payload=None):
        return {"status": "ok", **super().request(action, payload)}


class Reader:
    def __init__(self, texts, after_read=None):
        self.texts = iter(texts)
        self.after_read = after_read

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        if self.after_read:
            self.after_read()
        return {"raw_text": next(self.texts), "raw_mcp_response": {"test_double": True}}


def test_fixed_failure_waits_for_completion_and_keeps_raw_evidence(case):  # noqa: F811
    bridge = FixedBridge()
    reader = Reader([snapshot(percent=30), snapshot()])
    verifier = FixedFusionVerifier(bridge, lambda _: reader, poll_seconds=0)
    result = verifier.verify(*case)
    assert result.status == "failed" and result.completed
    assert result.feedback["summary"]["errors"] == 54
    assert "Fixture+Cutter" in result.issues
    assert result.machining_seconds == 360
    assert bridge.actions.count("simulation_command") == 3
    assert any(Path(a.path).name == "native-read-0001.json" for a in result.evidence)
    assert result.feedback["configured_coverage"]["tool_holder_fixture_collisions"] is True
    assert result.feedback["configured_coverage"]["target_stock_comparison"] is False


@pytest.mark.parametrize("text", [snapshot(errors=0), snapshot(process=1)])
def test_clear_issues_or_process_error_cannot_create_pass(case, text):  # noqa: F811
    result = FixedFusionVerifier(FixedBridge(), lambda _: Reader([text])).verify(*case)
    assert result.status == "unknown" and not result.completed


def test_failure_label_rejected_if_candidate_changes_during_simulation(case):  # noqa: F811
    bridge = FixedBridge()

    def change_setup():
        bridge.binding = copy.deepcopy(bridge.binding)
        bridge.binding["setups"][0]["name"] = "Changed setup"

    result = FixedFusionVerifier(
        bridge, lambda _: Reader([snapshot()], after_read=change_setup)
    ).verify(*case)
    assert result.status == "unknown"
    assert "changed during verification" in result.issues[0]


def test_clear_issues_retains_configured_scope_and_only_stock_comparison_gap(case):  # noqa: F811
    verifier = FixedFusionVerifier(FixedBridge(), lambda _: Reader([snapshot(errors=0)]))
    result = verifier.verify(*case)
    assert result.status == "unknown"
    assert result.issues == ("Target STEP and explicit linear_plus_minus_mm are required",)
    assert result.feedback["configured_coverage"]["axis_overtravel"] is True
    assert result.feedback["configured_coverage"]["target_stock_comparison"] is False
    evidence = {Path(a.path).name: json.loads(Path(a.path).read_text()) for a in result.evidence}
    before = evidence["candidate-binding.json"]["binding"]
    after = evidence["candidate-binding-after.json"]["binding"]
    assert before == after
    assert any(p["ignored"] for p in before["expected_machine_coverage"]["pairs"])


def test_disabled_required_check_stops_before_simulation_and_preserves_readback(case):  # noqa: F811
    bridge = FixedBridge()
    for pair in bridge.binding["setups"][0]["machine_coverage"]["pairs"]:
        if {i["type"] for i in pair["items"]} == {"stock", "tool"}:
            pair["checked"] = False

    def forbidden_reader(_):
        raise AssertionError("Reader must not open when configured coverage is invalid")

    result = FixedFusionVerifier(bridge, forbidden_reader).verify(*case)
    assert result.status == "unknown"
    assert "pinned machine coverage" in result.issues[0]
    assert "simulation_command" not in bridge.actions
    assert any(Path(a.path).name == "candidate-binding.json" for a in result.evidence)


def test_changed_collision_scope_during_verification_cannot_be_accepted(case):  # noqa: F811
    bridge = FixedBridge()

    def change_scope():
        bridge.binding = copy.deepcopy(bridge.binding)
        bridge.binding["setups"][0]["machine_coverage"]["pairs"][0]["checked"] = False

    result = FixedFusionVerifier(
        bridge, lambda _: Reader([snapshot(errors=0)], after_read=change_scope)
    ).verify(*case)
    assert result.status == "unknown"
    assert "changed during verification" in result.issues[0]
    assert any(Path(a.path).name == "candidate-binding-after.json" for a in result.evidence)


def test_stock_is_collected_before_simulation_stops_and_pass_reaches_metrics(case):  # noqa: F811
    bridge = FixedBridge()

    def stock_check(document, context, directory):
        assert bridge.actions.count("simulation_command") == 2
        return {"status": "passed", "issues": [], "method": "explicit contract double"}

    result = FixedFusionVerifier(
        bridge, lambda _: Reader([snapshot(errors=0)]), stock_check=stock_check
    ).verify(*case)
    assert result.status == "passed" and result.completed
    assert result.machining_seconds == 360
    assert result.feedback["configured_coverage"]["target_stock_comparison"] is True
    assert bridge.actions.count("simulation_command") == 3


def test_stock_mismatch_rejects_zero_collision_plan_and_returns_repair_coordinates(case):  # noqa: F811
    result = FixedFusionVerifier(
        FixedBridge(),
        lambda _: Reader([snapshot(errors=0)]),
        stock_check=lambda *args: {
            "status": "failed",
            "issues": [
                {"type": "leftover_material", "minimum_deviation_mm": 0.2, "point_mm": [1, 2, 3]}
            ],
        },
    ).verify(*case)
    assert result.status == "failed" and result.completed
    assert "leftover_material" in result.issues[0]
    assert result.feedback["target_stock_comparison"]["issues"][0]["point_mm"] == [1, 2, 3]


def test_stock_collection_failure_never_becomes_pass(case):  # noqa: F811
    def failed_export(*args):
        raise RuntimeError("Mac locked before export")

    result = FixedFusionVerifier(
        FixedBridge(), lambda _: Reader([snapshot(errors=0)]), stock_check=failed_export
    ).verify(*case)
    assert result.status == "unknown" and not result.completed
    assert "Mac locked" in result.issues[0]
