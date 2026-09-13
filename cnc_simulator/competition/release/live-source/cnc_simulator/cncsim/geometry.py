"""Geometry queries and conservative continuous linear sweeps, all in millimetres."""

from pathlib import Path

import numpy as np
import trimesh


class InputError(ValueError):
    pass


def number(value, name, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise InputError(f"{name} must be a finite number")
    value = float(value)
    if (positive and value <= 0) or (nonnegative and value < 0):
        raise InputError(f"{name} is out of range")
    return value


def vector(value, name):
    if not isinstance(value, list) or len(value) != 3:
        raise InputError(f"{name} must be a three-number array")
    return np.array([number(v, name) for v in value])


def keys(obj, required, optional=()):
    if not isinstance(obj, dict):
        raise InputError("Expected an object")
    missing, extra = set(required) - obj.keys(), obj.keys() - set(required) - set(optional)
    if missing or extra:
        raise InputError(f"Missing fields: {sorted(missing)}; unsupported fields: {sorted(extra)}")


class Solid:
    def __init__(self, spec, base, mesh_only=False):
        self.mesh = None
        if not isinstance(spec, dict):
            raise InputError("Geometry must be an object")
        if spec.get("type") == "box" and not mesh_only:
            keys(spec, ["type", "min", "max"])
            self.bounds = np.array([vector(spec["min"], "min"), vector(spec["max"], "max")])
            if np.any(self.bounds[1] <= self.bounds[0]):
                raise InputError("Box must have positive extents")
        elif spec.get("type") == "mesh":
            keys(spec, ["type", "path"])
            if not isinstance(spec["path"], str):
                raise InputError("Mesh path must be a string")
            path = Path(base) / spec["path"]
            self.mesh = trimesh.load_mesh(path, process=True)
            if not isinstance(self.mesh, trimesh.Trimesh) or not self.mesh.is_volume:
                raise InputError(
                    f"{path}: expected a watertight, consistently wound positive-volume mesh"
                )
            if not np.isfinite(self.mesh.vertices).all():
                raise InputError("Mesh contains nonfinite coordinates")
            self.bounds = self.mesh.bounds.copy()
        else:
            raise InputError(
                "Expected mesh geometry" if mesh_only else "Expected box or mesh geometry"
            )

    def signed(self, points):
        """Positive inside, negative outside. Batch to bound proximity-query memory."""
        if self.mesh is None:
            c = self.bounds.mean(axis=0)
            q = np.abs(points - c) - (self.bounds[1] - self.bounds[0]) / 2
            return -(np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(axis=1), 0))
        distances = np.concatenate(
            [
                trimesh.proximity.signed_distance(self.mesh, points[i : i + 2000])
                for i in range(0, len(points), 2000)
            ]
        )
        if not np.isfinite(distances).all():
            raise InputError("Mesh distance query returned nonfinite values; geometry unresolved")
        return distances

    def occupancy(self, points, pitch, guard):
        if self.mesh is None:
            lo, hi = self.bounds
            # Analytic box cells: exact boundary contact has zero volume.
            lower = np.all((points - pitch / 2 >= lo) & (points + pitch / 2 <= hi), axis=1)
            upper = np.all((points + pitch / 2 > lo) & (points - pitch / 2 < hi), axis=1)
            nominal = np.all((points >= lo) & (points <= hi), axis=1)
            return lower, upper, nominal
        d = self.signed(points)
        rho = np.sqrt(3) * pitch / 2 + guard
        return d > rho, d >= -rho, d >= 0


def sweep(points, start, end, radius, z0, z1, margin=0.0):
    """Exact point membership in a cylinder swept along a linear XYZ segment.

    Expanding radial and axial extents by rho encloses every intersecting cell;
    shrinking them by rho proves full-cell inclusion. No path sampling gaps.
    """
    r, low, high = radius + margin, z0 - margin, z1 + margin
    if r <= 0 or high < low:
        return np.zeros(len(points), dtype=bool)
    # Conservative broad phase: the swept cylinder fits inside this AABB.
    # Outward roundoff padding prevents a boundary cell from being dropped.
    if len(points) > 100_000:
        pad = max(1e-9, float(max(np.abs(start).max(),np.abs(end).max(),abs(r),abs(low),abs(high),1))*1e-12)
        lo = np.minimum(start,end) + np.array([-r,-r,low]) - pad
        hi = np.maximum(start,end) + np.array([r,r,high]) + pad
        selected = ((points[:,0]>=lo[0]) & (points[:,0]<=hi[0]) &
                    (points[:,1]>=lo[1]) & (points[:,1]<=hi[1]) &
                    (points[:,2]>=lo[2]) & (points[:,2]<=hi[2]))
        result = np.zeros(len(points),dtype=bool)
        # Chunk below the threshold to avoid recursive broad phases.
        indices = np.flatnonzero(selected)
        for i in range(0,len(indices),100_000):
            chunk=indices[i:i+100_000]
            result[chunk]=sweep(points[chunk],start,end,radius,z0,z1,margin)
        return result
    delta = end - start
    p = points - start
    if abs(delta[2]) < 1e-14:
        t0, t1 = np.zeros(len(p)), np.ones(len(p))
        feasible = (p[:, 2] >= low) & (p[:, 2] <= high)
    else:
        a, b = (p[:, 2] - high) / delta[2], (p[:, 2] - low) / delta[2]
        t0, t1 = np.maximum(0, np.minimum(a, b)), np.minimum(1, np.maximum(a, b))
        feasible = t0 <= t1
    xy2 = np.dot(delta[:2], delta[:2])
    t = np.zeros(len(p)) if xy2 == 0 else (p[:, :2] @ delta[:2]) / xy2
    t = np.maximum(t0, np.minimum(t1, t))
    radial = p[:, :2] - t[:, None] * delta[:2]
    return feasible & (np.sum(radial * radial, axis=1) <= r * r)


def voxel_mesh(mask, shape, origin, pitch):
    """Export only exposed voxel faces, without smoothing away stock."""
    grid = mask.reshape(shape)
    faces, vertices = [], []
    # Counterclockwise corner order viewed from outside.
    corners = [
        [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
        [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
        [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
        [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
        [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
        [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
    ]
    for axis in range(3):
        for side in range(2):
            neighbor = np.zeros_like(grid)
            dst, src = [slice(None)] * 3, [slice(None)] * 3
            dst[axis], src[axis] = (
                (slice(1, None), slice(None, -1))
                if side == 0
                else (slice(None, -1), slice(1, None))
            )
            neighbor[tuple(dst)] = grid[tuple(src)]
            cells = np.argwhere(grid & ~neighbor)
            if len(cells):
                v = origin + (cells[:, None, :] + np.array(corners[axis * 2 + side])) * pitch
                offset = sum(len(x) for x in vertices)
                idx = np.arange(len(cells))[:, None] * 4 + offset
                faces.append((idx + [0, 1, 2]).reshape(-1, 3))
                faces.append((idx + [0, 2, 3]).reshape(-1, 3))
                vertices.append(v.reshape(-1, 3))
    if not vertices:
        return trimesh.Trimesh(vertices=np.empty((0, 3)), faces=np.empty((0, 3), dtype=int))
    return trimesh.Trimesh(
        vertices=np.concatenate(vertices), faces=np.concatenate(faces), process=True
    )
