import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh
from cncsim import InputError, simulate
from cncsim.geometry import sweep, voxel_mesh
from cncsim.simulator import validate

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def plan():
    return json.loads((EXAMPLES / "pocket.json").read_text())


def run(plan, **kwargs):
    return simulate(plan, base_dir=EXAMPLES, **kwargs)


def has(result, code, certainty="definite"):
    return any(i["code"] == code and i["certainty"] == certainty for i in result["issues"])


@pytest.fixture(scope="module")
def pocket(tmp_path_factory):
    plan = json.loads((EXAMPLES / "pocket.json").read_text())
    states = []
    out = tmp_path_factory.mktemp("pocket")
    before = hashlib.sha256((EXAMPLES / "pocket_target.stl").read_bytes()).hexdigest()
    original = copy.deepcopy(plan)
    result = run(plan, output_dir=out, on_step=states.append)
    assert plan == original
    assert before == hashlib.sha256((EXAMPLES / "pocket_target.stl").read_bytes()).hexdigest()
    return result, states, out


def test_pocket_geometry_volume_and_dimensions(pocket):
    result, states, out = pocket
    assert result["validity"] == "valid", result["issues"]
    expected = 3 * (4 * 4 + math.pi * 2**2)
    metrics = result["stock_metrics"]
    assert metrics["removed_nominal_volume_mm3"] == pytest.approx(expected, rel=0.015)
    lo, hi = metrics["removed_volume_bounds_mm3"]
    assert lo <= expected <= hi
    a, b = states[0], states[-1]
    centers = np.array(a["origin"]) + (np.indices(a["shape"]).reshape(3, -1).T + 0.5) * a["pitch"]
    removed = centers[a["nominal"] & ~b["nominal"]]
    # Radius 2, center-line X=4..8, Y=5, bottom=3, top=6.
    assert removed.min(axis=0) - a["pitch"] / 2 == pytest.approx([2, 3, 3], abs=0.2)
    assert removed.max(axis=0) + a["pitch"] / 2 == pytest.approx([10, 7, 6], abs=0.2)
    mesh = trimesh.load_mesh(out / "final_stock.ply")
    assert mesh.is_volume
    assert mesh.volume == pytest.approx(metrics["final_nominal_volume_mm3"], abs=0.001)
    assert len(states) == 7
    assert len(list((out / "states").glob("*.npz"))) == 7
    for state in states:
        assert np.all(~state["lower"] | state["nominal"])
        assert np.all(~state["nominal"] | state["upper"])
    # Earlier snapshots are independent and successive stock only decreases.
    assert all(
        np.all(~y["nominal"] | x["nominal"]) for x, y in zip(states, states[1:], strict=False)
    )
    assert json.loads((out / "result.json").read_text())["validity"] == "valid"


def test_timing_and_faster_valid_plan(pocket, plan):
    result, _, _ = pocket
    # Feed: (5+4+5)/120*60=7, rapid 2/600*60=.2, dwell=1, change=4.
    assert result["time_breakdown"] == pytest.approx(
        dict(cutting=7, rapid=0.2, dwell=1, tool_changes=4)
    )
    assert result["estimated_time_seconds"] == pytest.approx(12.2)
    for move in plan["moves"]:
        if move["type"] == "cut":
            move["feed_mm_per_min"] *= 2
    fast = run(plan)
    assert fast["validity"] == "valid"
    assert fast["estimated_time_seconds"] == pytest.approx(8.7)
    assert fast["estimated_time_seconds"] < result["estimated_time_seconds"]


def test_overdeep(plan):
    plan["moves"][2]["to"][2] = 1
    plan["moves"][3]["to"][2] = 1
    result = run(plan)
    assert result["validity"] == "invalid"
    assert has(result, "gouge")
    assert any(2 in i["moves"] for i in result["issues"] if i["code"] == "gouge")


def test_missed_material(plan):
    plan["moves"] = plan["moves"][:2]
    result = run(plan)
    assert result["validity"] == "invalid"
    assert has(result, "excess_material")


def test_rapid_through_stock(plan):
    plan["moves"][2] = dict(type="rapid", to=[4, 5, 3])
    result = run(plan)
    assert result["validity"] == "invalid"
    assert has(result, "rapid_through_stock")


@pytest.mark.parametrize("z,section", [(7, "cutter"), (17, "shaft"), (21, "holder")])
def test_fixture_collision(plan, z, section):
    plan["fixtures"] = [dict(type="box", min=[3, 4, z], max=[5, 6, z + 1])]
    result = run(plan)
    assert result["validity"] == "invalid"
    assert any(
        i["code"] == "fixture_collision"
        and section in i["description"]
        and i["certainty"] == "definite"
        for i in result["issues"]
    )


def test_noncutting_stock_collision(plan):
    for tool in plan["tools"].values():
        tool["flute_length_mm"] = 1
        tool["shaft_diameter_mm"] = 7
    result = run(plan)
    assert result["validity"] == "invalid"
    assert has(result, "noncutting_stock_collision")


def test_overtravel(plan):
    plan["moves"].append(dict(type="rapid", to=[31, 5, 8]))
    result = run(plan)
    assert result["validity"] == "invalid"
    assert has(result, "axis_overtravel")


def test_numerical_uncertainty_is_not_pass(plan):
    plan["tolerance_mm"] = 0.01
    result = run(plan)
    assert result["validity"] == "invalid"
    assert result["passed"] is False
    assert result["verification"] == "unresolved"
    assert any(i["certainty"] == "uncertain" for i in result["issues"])


def test_tiny_fixture_not_silently_missed(plan):
    plan["fixtures"] = [dict(type="box", min=[4.01, 5.01, 8.01], max=[4.02, 5.02, 8.02])]
    result = run(plan)
    assert result["validity"] == "invalid"
    assert any(i["code"] == "fixture_collision" for i in result["issues"])


def test_undersized_stock(plan):
    plan["stock"]["max"][0] = 10
    result = run(plan)
    assert result["validity"] == "invalid"
    assert has(result, "missing_material")


def test_resource_limit(plan):
    plan["max_cells"] = 2
    result = run(plan)
    assert result["validity"] == "invalid"
    assert result["passed"] is False
    assert result["verification"] == "unresolved"
    assert has(result, "resource_limit", "uncertain")
    assert result["estimated_time_seconds"] == pytest.approx(12.2)


@pytest.mark.parametrize(
    "move",
    [
        dict(type="arc", to=[0, 0, 0]),
        dict(type="cut", to=[0, 0, 0], feed_mm_per_min=0),
        dict(type="rapid", to=[0, 0, float("nan")]),
        dict(type="rapid", to=[0, 0, 0], ignored_command="G91"),
        dict(type="tool_change", tool="missing"),
        dict(type="dwell", seconds=-1),
    ],
)
def test_bad_movements_rejected(plan, move):
    plan["moves"].append(move)
    with pytest.raises(InputError):
        validate(plan)


def test_diagonal_timing(plan):
    plan["moves"] = [
        dict(type="cut", to=[5, 9, 8], feed_mm_per_min=60),
        dict(type="rapid", to=[5, 9, 20]),
        dict(type="dwell", seconds=2),
        dict(type="tool_change", tool="T2"),
    ]
    _, timing = validate(plan)
    assert timing == pytest.approx(dict(cutting=5, rapid=1.2, dwell=2, tool_changes=4))


def test_continuous_sweep_between_endpoints_and_diagonal():
    points = np.array([[5, 0, 1], [5, 1.1, 1], [10, 0, 1], [5, 0, 4], [5, 0, 3]])
    a, b = np.array([0, 0, 0]), np.array([10, 0, 2])
    # Point at X=5,Z=1 lies halfway down a simultaneous XYZ sweep, even though
    # neither endpoint cylinder reaches it. Z=3 is reachable at t=.5.
    actual = sweep(points, a, b, 1, 0, 2)
    assert actual.tolist() == [True, False, False, False, True]


def test_mesh_stock_and_empty_mesh_export(plan, tmp_path):
    stock = trimesh.creation.box([12, 10, 6])
    stock.apply_translation([6, 5, 3])
    stock.export(tmp_path / "stock.stl")
    plan["stock"] = dict(type="mesh", path=str(tmp_path / "stock.stl"))
    result = run(plan)
    assert result["validity"] == "valid", result["issues"]
    empty = voxel_mesh(np.zeros(8, dtype=bool), (2, 2, 2), np.zeros(3), 1)
    empty.export(tmp_path / "empty.ply")
    assert (tmp_path / "empty.ply").exists()


def test_invalid_mesh_rejected(plan, tmp_path):
    mesh = trimesh.creation.box()
    mesh.update_faces(np.arange(len(mesh.faces) - 1))
    mesh.export(tmp_path / "open.stl")
    plan["target"]["path"] = str(tmp_path / "open.stl")
    with pytest.raises(InputError, match="watertight"):
        run(plan)


def test_cli_rejects_gcode_as_json(tmp_path):
    path = tmp_path / "unsupported.json"
    path.write_text('{"moves": [{"type": "G2"}]}')
    proc = subprocess.run(
        [sys.executable, "-m", "cncsim", str(path), "--output", str(tmp_path / "out")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result["validity"] == "invalid"
    assert result["passed"] is False
    assert result["verification"] == "input_error"
    assert result["estimated_time_seconds"] is None


def test_output_cannot_overwrite_target(plan, tmp_path):
    target = tmp_path / "final_stock.ply"
    trimesh.load_mesh(EXAMPLES / "pocket_target.stl").export(target)
    before = target.read_bytes()
    plan["target"]["path"] = str(target)
    with pytest.raises(InputError, match="separate directory"):
        run(plan, output_dir=tmp_path)
    assert target.read_bytes() == before


def test_malformed_geometry(plan):
    plan["stock"] = []
    with pytest.raises(InputError, match="Geometry must be an object"):
        run(plan)
