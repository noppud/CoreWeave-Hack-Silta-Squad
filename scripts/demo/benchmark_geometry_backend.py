"""Isolated retained-mesh libigl experiment; never changes production backend."""

# ruff: noqa: E402, E501
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# uv's isolated environment supplies libigl; reuse installed app libraries read-only.
sys.path.append(str(ROOT / ".venv/lib/python3.12/site-packages"))
import igl
import numpy as np
import trimesh

from silta.cnc import stock_comparison as comparison


def make_closest():
    cache = {}

    def closest(mesh, points):
        key = id(mesh)
        if key not in cache:
            vertices = np.ascontiguousarray(mesh.vertices, dtype=np.float64)
            faces = np.ascontiguousarray(mesh.faces, dtype=np.int64)
            tree = igl.AABB()
            tree.init(vertices, faces)
            cache[key] = (mesh, vertices, faces, tree)
        _, vertices, faces, tree = cache[key]
        squared, indices, coordinates = tree.squared_distance(
            vertices, faces, np.ascontiguousarray(points, dtype=np.float64)
        )
        if not np.isfinite(squared).all() or np.any(squared < -1e-14):
            raise ValueError("Invalid compiled distance")
        return coordinates, np.sqrt(np.maximum(squared, 0)), indices

    return closest


def run(full=True):
    os.nice(5)
    records = []
    original = comparison._closest
    selections = [
        ("umc02", "demo-umc-umc-02-recovery4"),
        ("umc03", "demo-umc-umc-03-recovery3"),
        ("known-failed", "learning-part-b1"),
    ]
    output = ROOT / "output/evaluation/geometry-backend-results.json"
    for label, run_id in selections:
        paths = sorted(
            (ROOT / "runs" / run_id).glob("workspace/verify-*/stock-comparison/comparison.json")
        )
        path = next(
            p
            for p in paths
            if json.loads(p.read_text())["status"]
            == ("failed" if label == "known-failed" else "passed")
        )
        retained = json.loads(path.read_text())
        for artifact in retained["artifacts"].values():
            if (
                hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest()
                != artifact["sha256"]
            ):
                raise ValueError("Retained artifact hash mismatch")
        stock = trimesh.load_mesh(retained["artifacts"]["stock"]["path"], process=True)
        target = trimesh.load_mesh(retained["artifacts"]["target_mesh"]["path"], process=True)
        row = {
            "label": label,
            "retained_comparison": str(path),
            "retained_status": retained["status"],
            "artifacts": retained["artifacts"],
            "stock_faces": len(stock.faces),
            "target_faces": len(target.faces),
            "queries": [],
        }
        compiled = make_closest()
        for source, reference in [(stock, target), (target, stock)]:
            # Every source centroid, plus vertices spread deterministically across source.
            indices = np.linspace(
                0, len(source.faces) - 1, min(10000, len(source.faces)), dtype=int
            )
            points = np.concatenate(
                [source.triangles_center[indices], source.triangles[indices].reshape(-1, 3)]
            )
            started = time.monotonic()
            a = original(reference, points)
            old_time = time.monotonic() - started
            started = time.monotonic()
            b = compiled(reference, points)
            new_time = time.monotonic() - started
            distance_delta = float(np.max(np.abs(a[1] - b[1])))
            # Face ties can differ; require returned points to lie on returned faces.
            projected = trimesh.triangles.closest_point(reference.triangles[b[2]], b[0])
            membership = float(np.max(np.linalg.norm(projected - b[0], axis=1)))
            if distance_delta > 1e-7 or membership > 1e-7:
                print("QUERY_DIAGNOSTIC", label, distance_delta, membership, flush=True)
                worst = np.argsort(np.abs(a[1] - b[1]))[-10:]
                brute = trimesh.proximity.closest_point_naive(reference, points[worst])
                print(
                    "BRUTE_DIAGNOSTIC",
                    float(np.max(np.abs(a[1][worst] - brute[1]))),
                    float(np.max(np.abs(b[1][worst] - brute[1]))),
                    flush=True,
                )
            row["queries"].append(
                {
                    "points": len(points),
                    "trimesh_seconds": old_time,
                    "libigl_seconds": new_time,
                    "distance_max_delta_mm": distance_delta,
                    "closest_point_max_delta_mm": float(
                        np.max(np.linalg.norm(a[0] - b[0], axis=1))
                    ),
                    "face_membership_max_error_mm": membership,
                    "face_index_agreement_fraction": float(np.mean(a[2] == b[2])),
                }
            )
        if full:
            for name, backend in [("trimesh", original), ("libigl", make_closest())]:
                comparison._closest = backend
                try:
                    started = time.monotonic()
                    verdict = comparison.compare_meshes(
                        stock,
                        target,
                        retained["tolerance_mm"],
                        target_deflection_mm=retained["target_deflection_mm"],
                    )
                    row[name] = {"seconds": time.monotonic() - started, "verdict": verdict}
                    print(label, name, row[name]["seconds"], verdict["status"], flush=True)
                finally:
                    comparison._closest = original
            row["same_verdict"] = (
                row["trimesh"]["verdict"]["status"] == row["libigl"]["verdict"]["status"]
            )
            row["speedup"] = row["trimesh"]["seconds"] / row["libigl"]["seconds"]
        records.append(row)
        output.write_text(
            json.dumps(
                {
                    "libigl_version": importlib.metadata.version("libigl"),
                    "numpy_version": np.__version__,
                    "trimesh_version": trimesh.__version__,
                    "scope": "Same retained STL meshes and whole-surface algorithm; _closest only replacement, in isolated process",
                    "records": records,
                },
                indent=2,
            )
        )
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries-only", action="store_true")
    args = parser.parse_args()
    run(not args.queries_only)
