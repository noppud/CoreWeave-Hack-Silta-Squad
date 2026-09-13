"""Configured coverage tests; no synthetic fixture establishes simulation pass."""

from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from silta.cnc.simulation_coverage import (
    MACHINE_COVERAGE_SOURCE,
    _inspect_machine_coverage,
    validate_simulation_coverage,
)


def _api_machine():
    names = (
        "TOOL", "TOOL_CUTTER", "TOOL_NONCUTTER", "STOCK", "FIXTURE", "MODEL",
        "MACHINE_PART", "TURRET_ACTIVE_TOOL", "TURRET_INACTIVE_TOOL", "INVALID",
    )
    enum = NS(**{"MachineItemType_" + name: i for i, name in enumerate(names)})

    def item(kind, ident):
        return NS(itemType=names.index(kind), part=NS(id=ident))

    pairs = []
    for first, second in [
        (("TOOL", "head"), ("STOCK", "table")),
        (("TOOL", "head"), ("FIXTURE", "table")),
        (("TOOL", "head"), ("MACHINE_PART", "table")),
        (("MACHINE_PART", "head"), ("MACHINE_PART", "table")),
        (("MACHINE_PART", "head"), ("STOCK", "table")),
        (("MACHINE_PART", "head"), ("FIXTURE", "table")),
    ]:
        pairs.append(NS(item1=item(*first), item2=item(*second),
                        isCheckedForCollisions=True, isIgnored=False))
    pairs.append(NS(item1=item("MACHINE_PART", "Z"), item2=item("TOOL", "head"),
                    isCheckedForCollisions=False, isIgnored=True))
    roots = []
    for ident, low, high, direction in [
        ("Z", -50.8, 0, [0, 0, 1]),
        ("Y", -20.3, 20.3, [0, -1, 0]),
        ("X", -38.1, 38.1, [-1, 0, 0]),
    ]:
        axis = NS(name=ident, hasLimits=True, physicalRange=NS(min=low, max=high, isInfinite=False),
                  direction=NS(x=direction[0], y=direction[1], z=direction[2]))
        roots.append(NS(id=ident, axis=axis, children=[]))
    kinematics = NS(parts=[NS(id="base", axis=None, children=roots)])
    elements = NS(defaultItemByType=lambda ident: {
        "interactions": pairs, "kinematics": kinematics
    }[ident])
    cam = NS(
        MachineItemType=enum,
        InteractionsMachineElement=NS(cast=lambda x: x, staticTypeId=lambda: "interactions"),
        KinematicsMachineElement=NS(cast=lambda x: x, staticTypeId=lambda: "kinematics"),
        LinearMachineAxis=NS(cast=lambda x: x),
    )
    return NS(elements=elements), cam, pairs, roots


def test_typed_readback_converts_cm_and_preserves_explicit_exclusions():
    machine, cam, pairs, roots = _api_machine()
    value = _inspect_machine_coverage(machine, cam)
    assert [a["part_id"] for a in value["axes"]] == ["X", "Y", "Z"]
    assert value["axes"][0]["minimum"] == -381
    assert value["axes"][2]["minimum"] == -508
    assert sum(p["ignored"] for p in value["pairs"]) == 1
    assert sum(p["checked"] for p in value["pairs"]) == 6
    pairs.reverse()
    roots.reverse()
    for pair in pairs:
        pair.item1, pair.item2 = pair.item2, pair.item1
    assert _inspect_machine_coverage(machine, cam) == value
    namespace = {}
    exec(MACHINE_COVERAGE_SOURCE, namespace)
    assert namespace["_inspect_machine_coverage"](machine, cam) == value


@pytest.fixture
def binding():
    machine, cam, _, _ = _api_machine()
    scope = _inspect_machine_coverage(machine, cam)
    return {
        "expected_machine_coverage": scope,
        "setups": [{"machine_coverage": deepcopy(scope), "machine_matches": True,
                    "machine_simulation_model": True, "fixture_enabled": True,
                    "fixtures": [{"body_references": ["vise"]}],
                    "models": [{"body_references": ["part"]}]}],
        "operations": [{"tool": {"geometry": {"DC": 12.7},
                                  "holder": {"segments": [{"height": 10}]}}}],
    }


def test_configured_scope_does_not_claim_stock_comparison_or_verdict(binding):
    scope = validate_simulation_coverage(binding)
    assert scope == {"machine_collisions": True, "tool_holder_fixture_collisions": True,
                     "rapid_stock_collisions": True, "axis_overtravel": True,
                     "target_stock_comparison": False}
    assert "passed" not in scope


def test_live_pair_change_rejected_even_when_machine_equivalent_claims_true(binding):
    binding["setups"][0]["machine_coverage"]["pairs"][0]["checked"] = False
    with pytest.raises(ValueError, match="pinned machine coverage"):
        validate_simulation_coverage(binding)


def test_disabled_required_category_in_pin_is_not_coverage(binding):
    for pair in binding["expected_machine_coverage"]["pairs"]:
        if {i["type"] for i in pair["items"]} == {"tool", "stock"}:
            pair["checked"] = False
    binding["setups"][0]["machine_coverage"] = deepcopy(binding["expected_machine_coverage"])
    with pytest.raises(ValueError, match="required collision pair"):
        validate_simulation_coverage(binding)


@pytest.mark.parametrize("change", [
    {"minimum": float("-inf")}, {"infinite": True}, {"has_limits": False},
    {"minimum": 0, "maximum": 0}, {"kind": "nonlinear"}, {"units": "cm"},
])
def test_unbounded_or_wrong_axis_definition_rejected(binding, change):
    binding["expected_machine_coverage"]["axes"][0].update(change)
    with pytest.raises(ValueError, match="finite linear axis"):
        validate_simulation_coverage(binding)


def test_infinite_axis_readback_uses_null_not_json_infinity():
    machine, cam, _, roots = _api_machine()
    roots[0].axis.physicalRange = NS(isInfinite=True, min=float("-inf"), max=float("inf"))
    result = _inspect_machine_coverage(machine, cam)
    assert result["axes"][2]["minimum"] is None
    assert result["axes"][2]["maximum"] is None


def test_missing_holder_geometry_cannot_claim_holder_coverage(binding):
    binding["operations"][0]["tool"].pop("holder")
    with pytest.raises(ValueError, match="cutter and holder"):
        validate_simulation_coverage(binding)
