"""Configured Fusion verification scope, independent of simulation verdicts."""

from __future__ import annotations

import inspect
import math


def _inspect_machine_coverage(machine, cam):
    """Read supported typed APIs only; distances returned in millimeters."""
    if not machine:
        return None
    interactions = cam.InteractionsMachineElement.cast(
        machine.elements.defaultItemByType(cam.InteractionsMachineElement.staticTypeId())
    )
    kinematics = cam.KinematicsMachineElement.cast(
        machine.elements.defaultItemByType(cam.KinematicsMachineElement.staticTypeId())
    )
    if not interactions or not kinematics:
        raise RuntimeError("Machine lacks readable interactions or kinematics")
    type_names = {
        getattr(cam.MachineItemType, "MachineItemType_" + name): name.lower()
        for name in (
            "TOOL",
            "TOOL_CUTTER",
            "TOOL_NONCUTTER",
            "STOCK",
            "FIXTURE",
            "MODEL",
            "MACHINE_PART",
            "TURRET_ACTIVE_TOOL",
            "TURRET_INACTIVE_TOOL",
            "INVALID",
        )
    }

    def item(value):
        return {
            "type": type_names.get(value.itemType, "enum:" + str(int(value.itemType))),
            "part_id": value.part.id,
        }

    pairs = []
    for pair in interactions:
        items = sorted(
            [item(pair.item1), item(pair.item2)], key=lambda x: (x["type"], x["part_id"])
        )
        pairs.append(
            {
                "items": items,
                "checked": bool(pair.isCheckedForCollisions),
                "ignored": bool(pair.isIgnored),
            }
        )
    pairs.sort(key=lambda p: tuple((x["type"], x["part_id"]) for x in p["items"]))
    axes = []

    def walk(parts):
        for part in parts:
            axis = part.axis
            if axis:
                linear = cam.LinearMachineAxis.cast(axis)
                rotary = None if linear else cam.RotaryMachineAxis.cast(axis)
                bounds = axis.physicalRange
                infinite = bool(bounds.isInfinite) if bounds else True
                axes.append(
                    {
                        "part_id": part.id,
                        "name": axis.name,
                        "kind": "linear" if linear else "rotary" if rotary else "unknown",
                        "has_limits": bool(axis.hasLimits),
                        "infinite": infinite,
                        "units": "mm" if linear else "radians",
                        "minimum": None if infinite else bounds.min * (10 if linear else 1),
                        "maximum": None if infinite else bounds.max * (10 if linear else 1),
                        "direction": (
                            [linear.direction.x, linear.direction.y, linear.direction.z]
                            if linear
                            else None
                        ),
                    }
                )
            walk(part.children)

    walk(kinematics.parts)
    axes.sort(key=lambda x: x["part_id"])
    return {"pairs": pairs, "axes": axes}


MACHINE_COVERAGE_SOURCE = inspect.getsource(_inspect_machine_coverage)


def validate_simulation_coverage(binding: dict) -> dict[str, bool]:
    """Return configured check categories, never a simulation pass.

    The caller binds machine_path to its pinned artifact. Expected and actual
    readbacks must match, preserving the machine's explicit collision exclusions.
    """
    expected = binding.get("expected_machine_coverage")
    if not isinstance(expected, dict) or not expected.get("pairs"):
        raise ValueError("Pinned machine collision coverage was not read")
    pairs = expected["pairs"]
    keys = [tuple((x["type"], x["part_id"]) for x in p["items"]) for p in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate machine collision pairs")
    enabled_types = {
        tuple(sorted(x["type"] for x in p["items"]))
        for p in pairs
        if p.get("checked") is True and p.get("ignored") is False
    }
    required = {
        ("stock", "tool"),
        ("fixture", "tool"),
        ("machine_part", "tool"),
        ("machine_part", "machine_part"),
        ("machine_part", "stock"),
        ("fixture", "machine_part"),
    }
    if not required <= enabled_types:
        raise ValueError("Pinned machine is missing required collision pair categories")
    axes = expected.get("axes", [])
    if len(axes) not in (3, 4, 5) or len({a.get("part_id") for a in axes}) != len(axes):
        raise ValueError("Expected three to five distinct machine axes")
    for axis in axes:
        low, high = axis.get("minimum"), axis.get("maximum")
        finite = (
            type(low) in (int, float)
            and type(high) in (int, float)
            and math.isfinite(low)
            and math.isfinite(high)
            and low < high
        )
        if axis.get("kind") == "rotary":
            if axis.get("units") != "radians":
                raise ValueError("Rotary axis limits require radians")
            continuous = (
                axis.get("infinite") is True
                and axis.get("has_limits") is False
                and low is None
                and high is None
            )
            bounded = axis.get("infinite") is False and axis.get("has_limits") is True and finite
            if not (continuous or bounded):
                raise ValueError("Rotary axis must retain bounded or explicit continuous limits")
        elif (
            axis.get("kind") != "linear"
            or axis.get("units") != "mm"
            or axis.get("has_limits") is not True
            or axis.get("infinite") is not False
            or not finite
        ):
            raise ValueError("Machine overtravel coverage requires finite linear axis limits")
    if sum(a.get("kind") == "linear" for a in axes) != 3:
        raise ValueError("Machine requires exactly three finite linear axes")
    setups = binding.get("setups", [])
    if not setups:
        raise ValueError("No simulation setup")
    for setup in setups:
        if (
            setup.get("machine_matches") is not True
            or setup.get("machine_simulation_model") is not True
            or setup.get("machine_coverage") != expected
            or setup.get("fixture_enabled") is not True
            or not setup.get("fixtures")
            or not setup.get("models")
        ):
            raise ValueError("Simulation setup does not retain the pinned machine coverage")
    operations = binding.get("operations", [])
    if not operations:
        raise ValueError("No simulation operations")
    for operation in operations:
        tool = operation.get("tool") or {}
        if not tool.get("geometry") or not (tool.get("holder") or {}).get("segments"):
            raise ValueError("Simulation needs each operation's cutter and holder geometry")
    return {
        "machine_collisions": True,
        "tool_holder_fixture_collisions": True,
        "rapid_stock_collisions": True,
        "axis_overtravel": True,
        "target_stock_comparison": False,
    }
