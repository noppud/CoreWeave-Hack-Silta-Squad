"""Independent controls for covered zero-area facets versus genuine surface holes."""

import numpy as np
import pytest
import trimesh

from silta.cnc.stock_comparison import (
    compare_meshes,
    covered_collinear_faces,
    load_stock_mesh,
    validate_mesh,
)


def split_edge_box():
    """Join an unsplit face edge to two split edges with one zero-area facet."""
    box = trimesh.creation.box()
    a, b, c = box.faces[0]
    midpoint = len(box.vertices)
    vertices = np.vstack([box.vertices, (box.vertices[a] + box.vertices[b]) / 2])
    # The last facet closes only the topological edge subdivision, with no area.
    faces = np.vstack([box.faces[1:], [a, midpoint, c], [midpoint, b, c], [a, b, midpoint]])
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def write_export(mesh, path):
    # Include a raw repeated-coordinate facet as present in the real exporter.
    a, b, _ = mesh.faces[0]
    exported = trimesh.Trimesh(
        vertices=mesh.vertices,
        faces=np.vstack([mesh.faces, [a, b, a]]),
        process=False,
    )
    exported.export(path)
    return path.read_bytes()


def test_covered_edge_subdivision_preserves_closed_box_surface(tmp_path):
    path = tmp_path / "stock.stl"
    original = write_export(split_edge_box(), path)
    normalized, receipt = load_stock_mesh(path)
    assert receipt["removed_face_count"] == 1
    assert len(receipt["covered_collinear_face_indices"]) == 1
    assert normalized.is_volume
    assert compare_meshes(normalized, trimesh.creation.box(), 0.127)["status"] == "passed"
    assert path.read_bytes() == original


@pytest.mark.parametrize("missing_positive_face", range(13))
def test_zero_area_facets_cannot_conceal_any_box_surface_hole(tmp_path, missing_positive_face):
    mesh = split_edge_box()
    assert mesh.area_faces[missing_positive_face] > 0
    mesh.update_faces(np.arange(len(mesh.faces)) != missing_positive_face)
    path = tmp_path / "open.stl"
    original = write_export(mesh, path)
    with pytest.raises(ValueError, match="watertight|covering"):
        normalized, _ = load_stock_mesh(path)
        validate_mesh(normalized, "Open stock")
    assert path.read_bytes() == original


def test_underflowed_area_is_not_mistaken_for_exact_collinearity():
    mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1e-200, 0, 0], [0, 1e-200, 0]],
        faces=[[0, 1, 2]],
        process=False,
    )
    assert mesh.area_faces[0] == 0  # Floating arithmetic underflow, not exact zero area.
    with pytest.raises(ValueError, match="not exactly collinear"):
        covered_collinear_faces(mesh)
