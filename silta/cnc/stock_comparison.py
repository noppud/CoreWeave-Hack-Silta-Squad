"""Bounded two-way surface comparison of Fusion stock against the accepted STEP.

No alignment, target editing, or model judgment. Distances are in the shared
part coordinate frame, in mm. A completed result concerns exported geometry;
it does not certify cutting physics or posted NC motion.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import trimesh

from .models import file_digest

COMPARISON_VERSION = "bidirectional-adaptive-mesh-v1"


def step_mesh(path: Path, deflection_mm: float) -> trimesh.Trimesh:
    from OCP.BRep import BRep_Tool
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError("Accepted STEP could not be read")
    reader.SetSystemLengthUnit(1.0)  # OCCT system unit expressed in millimetres.
    if not reader.TransferRoots():
        raise ValueError("Accepted STEP has no transferable shapes")
    shape = reader.OneShape()
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise ValueError("Accepted STEP is not a valid BRep")
    mesher = BRepMesh_IncrementalMesh(shape, deflection_mm, False, 0.1, True)
    if not mesher.IsDone():
        raise ValueError("Target STEP tessellation did not complete")
    vertices, faces = [], []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        location = TopLoc_Location()
        mesh = BRep_Tool.Triangulation_s(face, location)
        if mesh is None:
            raise ValueError("Target face lacks triangulation")
        offset = len(vertices)
        for i in range(1, mesh.NbNodes() + 1):
            p = mesh.Node(i).Transformed(location.Transformation())
            vertices.append((p.X(), p.Y(), p.Z()))
        for i in range(1, mesh.NbTriangles() + 1):
            a, b, c = mesh.Triangle(i).Get()
            if face.Orientation() == TopAbs_REVERSED:
                b, c = c, b
            faces.append((offset + a - 1, offset + b - 1, offset + c - 1))
        explorer.Next()
    result = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    validate_mesh(result, "Target")
    return result


def validate_mesh(mesh, name: str):
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError(f"{name} is not a triangle mesh")
    if not np.isfinite(mesh.vertices).all() or not mesh.is_volume:
        raise ValueError(f"{name} must be finite, watertight, consistently wound, positive volume")
    if np.any(mesh.area_faces <= 0):
        raise ValueError(f"{name} has degenerate triangles")


def _closest(mesh, points):
    rows = [
        trimesh.proximity.closest_point(mesh, points[i : i + 1000])
        for i in range(0, len(points), 1000)
    ]
    return tuple(np.concatenate([row[j] for row in rows]) for j in range(3))


def _planar_regions(mesh):
    """Coplanar connected facets, with holes preserved in their 2-D union."""
    import shapely

    by_face = {}
    regions = []
    for face_ids in mesh.facets:
        if len(face_ids) < 3:
            continue
        normal = mesh.face_normals[face_ids[0]]
        origin = mesh.triangles[face_ids[0], 0]
        delta = mesh.triangles[face_ids] - origin
        if np.max(np.abs(delta @ normal)) > 1e-8:
            continue
        u = mesh.triangles[face_ids[0], 1] - origin
        u = u / np.linalg.norm(u)
        basis = np.stack((u, np.cross(normal, u)), axis=1)
        polygon = shapely.union_all(shapely.polygons(delta @ basis))
        if not polygon.is_valid:
            continue
        # Covers includes the boundary. No buffer is added that could fill a hole.
        index = len(regions)
        regions.append((origin, normal, basis, polygon))
        by_face.update((int(face), index) for face in face_ids)
    return by_face, regions


def _planar_upper(triangles, nearest_faces, by_face, regions):
    import shapely

    result = np.full(len(triangles), np.inf)
    groups = {}
    for i, face in enumerate(nearest_faces):
        if int(face) in by_face:
            groups.setdefault(by_face[int(face)], []).append(i)
    for region, indices in groups.items():
        origin, normal, basis, polygon = regions[region]
        delta = triangles[indices] - origin
        projected = shapely.polygons(delta @ basis)
        covered = shapely.covers(polygon, projected)
        # The triangles in this patch depart from its mathematical plane by at
        # most 1e-8 mm, as checked above; retain that allowance in the bound.
        distances = np.abs(delta @ normal).max(axis=1) + 1e-8
        result[np.asarray(indices)[covered]] = distances[covered]
    return result


def directed_surface(
    source, target, tolerance_mm, error_margin_mm, *, max_triangles=2_000_000, timeout=120
) -> dict:
    """Prove each source triangle stays within a tolerance band of target.

    Upper bounds use distance to one target triangle (a convex set), which
    is bounded by the maximum distance at source vertices; and surface distance
    is 1-Lipschitz, so centroid distance + triangle radius bounds every point.
    A projection fully covered by a coplanar target patch also permits a plane
    distance bound. Patch unions preserve holes and do not expand boundaries.
    Unresolved triangles are split into four. A few random samples never pass.
    """
    validate_mesh(source, "Source")
    validate_mesh(target, "Reference")
    started = time.monotonic()
    pending = source.triangles.copy()
    by_face, regions = _planar_regions(target)
    processed = 0
    max_lower = 0.0
    max_upper = 0.0
    worst_point = None
    while len(pending):
        if processed + len(pending) > max_triangles or time.monotonic() - started > timeout:
            return {
                "status": "unknown",
                "reason": "Surface comparison resource bound reached",
                "processed_triangles": processed,
                "unresolved_triangles": len(pending),
                "observed_max_mm": max_lower,
            }
        # Bound per-batch proximity allocations without sampling away any faces.
        triangles, pending = pending[:2000], pending[2000:]
        centers = triangles.mean(axis=1)
        sample = np.concatenate((centers, triangles.reshape(-1, 3)))
        _, distances, nearest_faces = _closest(target, sample)
        if not np.isfinite(distances).all():
            raise ValueError("Non-finite surface distances")
        index = int(distances.argmax())
        observed = float(distances[index])
        if observed > max_lower:
            max_lower, worst_point = observed, sample[index].tolist()
        if observed - error_margin_mm > tolerance_mm:
            point = sample[index]
            signed = float(trimesh.proximity.signed_distance(target, point[None, :])[0])
            return {
                "status": "failed",
                "observed_max_mm": max_lower,
                "minimum_deviation_mm": observed - error_margin_mm,
                "point_mm": point.tolist(),
                "point_inside_reference": signed > 0,
                "processed_triangles": processed + len(triangles),
            }
        center_distance = distances[: len(centers)]
        # Exact distance to a selected convex target triangle bounds distance
        # to the entire reference surface, even when the nearest face changes.
        reference = target.triangles[nearest_faces[: len(centers)]]
        vertex_upper = np.zeros(len(triangles))
        for i in range(3):
            closest = trimesh.triangles.closest_point(reference, triangles[:, i])
            vertex_upper = np.maximum(
                vertex_upper, np.linalg.norm(closest - triangles[:, i], axis=1)
            )
        radius = np.linalg.norm(triangles - centers[:, None], axis=2).max(axis=1)
        patch_upper = _planar_upper(triangles, nearest_faces[: len(centers)], by_face, regions)
        upper = np.minimum(np.minimum(vertex_upper, patch_upper), center_distance + radius)
        upper += error_margin_mm
        accepted = upper <= tolerance_mm
        if accepted.any():
            max_upper = max(max_upper, float(upper[accepted].max()))
        unresolved = triangles[~accepted]
        processed += len(triangles)
        if len(unresolved):
            a, b, c = unresolved[:, 0], unresolved[:, 1], unresolved[:, 2]
            ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
            children = np.concatenate(
                [np.stack(v, axis=1) for v in [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]]
            )
            pending = np.concatenate((pending, children))
    return {
        "status": "passed",
        "observed_max_mm": max_lower,
        "upper_bound_mm": max_upper,
        "worst_sample_mm": worst_point,
        "processed_triangles": processed,
        "seconds": time.monotonic() - started,
    }


def compare_meshes(
    stock, target, tolerance_mm, *, target_deflection_mm=0.0, max_triangles=2_000_000, timeout=120
) -> dict:
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0:
        raise ValueError("A finite positive drawing tolerance is required")
    if not 0 <= target_deflection_mm < tolerance_mm / 2:
        raise ValueError("Target tessellation error must be smaller than half the tolerance")
    validate_mesh(stock, "Exported stock")
    validate_mesh(target, "Target")
    directions = {}
    for name, source, reference in [
        ("stock_to_target", stock, target),
        ("target_to_stock", target, stock),
    ]:
        directions[name] = directed_surface(
            source,
            reference,
            tolerance_mm,
            target_deflection_mm + 1e-6,
            max_triangles=max_triangles,
            timeout=timeout,
        )
    failed = [name for name, row in directions.items() if row["status"] == "failed"]
    status = (
        "failed"
        if failed
        else (
            "passed" if all(row["status"] == "passed" for row in directions.values()) else "unknown"
        )
    )
    issues = []
    for name in failed:
        row = directions[name]
        gouge = row["point_inside_reference"] == (name == "stock_to_target")
        issues.append(
            {
                "type": "gouge" if gouge else "leftover_material",
                "point_mm": row["point_mm"],
                "minimum_deviation_mm": row["minimum_deviation_mm"],
                "direction": name,
            }
        )
    return {
        "status": status,
        "method": COMPARISON_VERSION,
        "tolerance_mm": tolerance_mm,
        "target_deflection_mm": target_deflection_mm,
        "directions": directions,
        "issues": issues,
        "stock_volume_mm3": float(stock.volume),
        "target_volume_mm3": float(target.volume),
        "scope": "Bidirectional whole-surface conformity of exported meshes in fixed mm frame",
        "limitations": [
            "Numerical geometry verification, not cutting physics",
            "Fusion stock tessellation is the observed simulation representation",
        ],
    }


def compare_stock_to_step(
    stock_path: Path, step_path: Path, tolerance_mm: float, directory: Path
) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    deflection = min(0.005, tolerance_mm / 20)
    target = step_mesh(step_path, deflection)
    target_path = directory / "target-tessellation.stl"
    target.export(target_path)
    stock = trimesh.load_mesh(stock_path, process=True)
    result = compare_meshes(stock, target, tolerance_mm, target_deflection_mm=deflection)
    result["artifacts"] = {
        "stock": {"path": str(stock_path), "sha256": file_digest(stock_path)},
        "target_step": {"path": str(step_path), "sha256": file_digest(step_path)},
        "target_mesh": {"path": str(target_path), "sha256": file_digest(target_path)},
    }
    (directory / "comparison.json").write_text(json.dumps(result, indent=2))
    return result
