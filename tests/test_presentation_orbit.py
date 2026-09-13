"""Camera trajectory and early validation; these tests do not run Fusion."""

import math

import pytest

from fusion.SiltaBridge.presentation import orbit, orbit_parameters, orbit_pose


@pytest.mark.parametrize(
    "key,value",
    [
        ("seconds", float("nan")),
        ("seconds", float("inf")),
        ("seconds", 4.99),
        ("seconds", 30.01),
        ("seconds", True),
        ("radius_mm", 0),
        ("height_mm", -3),
        ("eye_z_mm", float("nan")),
        ("sweep_degrees", 0),
        ("sweep_degrees", 361),
        ("start_angle_degrees", float("inf")),
        ("target_mm", [0, 0, float("nan")]),
        ("target_mm", [0, 0]),
        ("target_mm", [True, 0, 0]),
        ("document", ""),
    ],
)
def test_invalid_orbit_rejected_before_app_access_or_adsk_import(key, value):
    class UntouchedApp:
        def __getattribute__(self, name):
            raise AssertionError("Invalid request accessed Fusion")

    with pytest.raises(ValueError):
        orbit(UntouchedApp(), {"document": "Exact", key: value})


def test_orbit_is_closed_with_eased_endpoints_and_constant_radius():
    p = orbit_parameters({"document": "Exact"})
    begin, end = orbit_pose(p, 0), orbit_pose(p, 1)
    assert end == pytest.approx(begin)
    for u in (0, 0.1, 0.25, 0.5, 0.75, 0.9, 1):
        eye = orbit_pose(p, u)
        assert all(math.isfinite(v) for v in eye)
        assert math.hypot(eye[0], eye[1]) == pytest.approx(380)
        assert eye[2] == 430
    start_step = math.dist(orbit_pose(p, 0), orbit_pose(p, 0.001))
    middle_step = math.dist(orbit_pose(p, 0.5), orbit_pose(p, 0.501))
    assert start_step < middle_step / 1000
    assert orbit_parameters({"document": "Exact", "seconds": 5})["seconds"] == 5
    assert orbit_parameters({"document": "Exact", "seconds": 30})["seconds"] == 30
