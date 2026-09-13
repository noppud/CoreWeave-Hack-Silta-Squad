import numpy as np
import pytest
import trimesh

from silta.cnc.stock_comparison import compare_meshes, step_mesh


def test_identical_closed_geometry_passes_with_whole_surface_bounds():
    target = trimesh.creation.box([10, 8, 4])
    result = compare_meshes(target.copy(), target, 0.127)
    assert result["status"] == "passed"
    assert all(row["upper_bound_mm"] <= 0.127 for row in result["directions"].values())


def test_equal_volume_in_wrong_location_fails_without_alignment():
    target = trimesh.creation.box([10, 8, 4])
    stock = target.copy()
    stock.apply_translation([1, 0, 0])
    result = compare_meshes(stock, target, 0.127)
    assert result["status"] == "failed"
    assert result["stock_volume_mm3"] == pytest.approx(result["target_volume_mm3"])
    assert result["issues"]


def test_missing_hole_is_leftover_even_when_outer_bounds_match():
    target = trimesh.creation.annulus(r_min=1, r_max=3, height=2, sections=32)
    stock = trimesh.creation.cylinder(radius=3, height=2, sections=32)
    assert np.allclose(target.bounds, stock.bounds)
    result = compare_meshes(stock, target, 0.127)
    assert result["status"] == "failed"
    assert any(issue["type"] == "leftover_material" for issue in result["issues"])


def test_oversized_hole_is_gouge():
    target = trimesh.creation.annulus(r_min=1, r_max=3, height=2, sections=32)
    stock = trimesh.creation.annulus(r_min=1.5, r_max=3, height=2, sections=32)
    result = compare_meshes(stock, target, 0.127)
    assert result["status"] == "failed"
    assert any(issue["type"] == "gouge" for issue in result["issues"])


def test_open_stock_surface_cannot_pass():
    target = trimesh.creation.box([10, 8, 4])
    stock = target.copy()
    stock.update_faces(np.arange(len(stock.faces) - 1))
    with pytest.raises(ValueError, match="watertight"):
        compare_meshes(stock, target, 0.127)


def test_budget_exhaustion_is_unknown():
    target = trimesh.creation.box([10, 8, 4])
    result = compare_meshes(target.copy(), target, 0.127, max_triangles=1)
    assert result["status"] == "unknown"


def test_borderline_tessellation_uncertainty_cannot_be_rounded_to_pass():
    target = trimesh.creation.box([1, 1, 1])
    stock = target.copy()
    stock.apply_translation([0.125, 0, 0])
    result = compare_meshes(stock, target, 0.127, target_deflection_mm=0.005, max_triangles=2000)
    assert result["status"] == "unknown"


def test_step_tessellation_preserves_mm_size_and_placement(tmp_path):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    shape = BRepPrimAPI_MakeBox(gp_Pnt(-5, -4, -4), 10, 8, 4).Shape()
    path = tmp_path / "target.step"
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Write(str(path))
    mesh = step_mesh(path, 0.005)
    assert mesh.is_volume
    assert np.allclose(mesh.bounds, [[-5, -4, -4], [5, 4, 0]])
    assert mesh.volume == pytest.approx(320)
