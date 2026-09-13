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


def test_compiled_nearest_matches_exhaustive_oracle_and_owns_snapshot():
    from silta.cnc.stock_comparison import _closest_backend

    mesh = trimesh.creation.icosphere(subdivisions=1)
    points = np.random.default_rng(104).uniform(-2, 2, (80, 3))
    oracle = trimesh.proximity.closest_point_naive(mesh, points)
    query = _closest_backend(mesh)
    coordinates, distances, faces = query(points)
    assert np.allclose(distances, oracle[1], atol=1e-10, rtol=0)
    projected = trimesh.triangles.closest_point(mesh.triangles[faces], coordinates)
    assert np.allclose(coordinates, projected, atol=1e-10, rtol=0)
    mesh.apply_translation([100, 0, 0])
    assert np.array_equal(query(points)[1], distances)


def test_compiled_nearest_rejects_nonfinite_queries():
    from silta.cnc.stock_comparison import _closest_backend

    query = _closest_backend(trimesh.creation.box())
    with pytest.raises(ValueError, match="query"):
        query(np.array([[np.nan, 0, 0]]))


def test_compiled_nearest_rejects_invalid_native_result(monkeypatch):
    import igl

    from silta.cnc.stock_comparison import _closest_backend

    class BadTree:
        def init(self, vertices, faces):
            pass

        def squared_distance(self, vertices, faces, points):
            return np.zeros(len(points)), np.full(len(points), -1), points.copy()

    monkeypatch.setattr(igl, "AABB", BadTree)
    with pytest.raises(ValueError, match="result"):
        _closest_backend(trimesh.creation.box())(np.zeros((1, 3)))


@pytest.mark.parametrize("offset,expected", [(0.126, "passed"), (0.129, "failed")])
def test_compiled_boundary_keeps_tolerance(offset, expected):
    target = trimesh.creation.box()
    stock = target.copy()
    stock.apply_translation([offset, 0, 0])
    assert compare_meshes(stock, target, 0.127)["status"] == expected


def test_exact_repeated_facets_removed_but_collinear_facets_retained(tmp_path):
    from silta.cnc.stock_comparison import load_stock_mesh

    triangles = np.array(
        [
            [[0, 0, 0], [1, 0, 0], [0, 0, 0]],
            [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
            [[0, 0, 0], [2, 0, 0], [0, 1, 0]],
        ],
        dtype=float,
    )
    mesh = trimesh.Trimesh(
        vertices=triangles.reshape(-1, 3), faces=np.arange(9).reshape(-1, 3), process=False
    )
    path = tmp_path / "raw.stl"
    mesh.export(path)
    before = path.read_bytes()
    normalized, receipt = load_stock_mesh(path)
    assert receipt["removed_face_indices"] == [0]
    assert len(normalized.faces) == 2
    assert np.count_nonzero(normalized.area_faces == 0) == 1
    assert path.read_bytes() == before


def test_normalization_does_not_close_a_real_open_surface(tmp_path):
    from silta.cnc.stock_comparison import load_stock_mesh, validate_mesh

    mesh = trimesh.creation.box()
    mesh.update_faces(np.arange(len(mesh.faces)) != 0)
    path = tmp_path / "open.stl"
    mesh.export(path)
    normalized, receipt = load_stock_mesh(path)
    assert receipt["removed_face_count"] == 0
    with pytest.raises(ValueError, match="watertight"):
        validate_mesh(normalized, "Stock")


def test_collinear_line_requires_an_exact_covering_edge():
    from silta.cnc.stock_comparison import covered_collinear_faces

    vertices = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0]]
    covered = trimesh.Trimesh(vertices=vertices, faces=[[0, 1, 2], [0, 2, 3]], process=False)
    assert covered_collinear_faces(covered).tolist() == [0]
    from silta.cnc.stock_comparison import _closest

    points, distances, indices = _closest(covered, np.array([[1.0, 0.0, 1.0]]))
    assert np.allclose(points, [[1, 0, 0]])
    assert distances.tolist() == [1.0]
    assert indices.tolist() == [1]
    uncovered = trimesh.Trimesh(vertices=vertices, faces=[[0, 1, 2], [0, 1, 3]], process=False)
    with pytest.raises(ValueError, match="covering"):
        covered_collinear_faces(uncovered)
