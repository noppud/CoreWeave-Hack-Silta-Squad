"""Regression: source constraints can overwrite an earlier occurrence transform."""

from types import SimpleNamespace

import pytest

from fusion.prepare_soft_jaw_fixture import _readback_poses


def test_detects_jaw_shift_lost_after_later_assembly_write():
    fixed = [0, -1, 0, -9.649, 1, 0, 0, -13.114, 0, 0, 1, -4.26072, 0, 0, 0, 1]
    intended_moving = list(fixed)
    intended_moving[7] += 17.78
    # Observed live failure: later constrained poses returned the jaw to fixed pose.
    actual_jaw = SimpleNamespace(
        transform2=SimpleNamespace(asArray=lambda: fixed),
        bRepBodies=SimpleNamespace(item=lambda _: SimpleNamespace(volume=10)),
    )
    with pytest.raises(RuntimeError, match="Component10 rigid pose changed"):
        _readback_poses({10: actual_jaw}, {"10": intended_moving}, {10: {"volume_cm3": 10}})
