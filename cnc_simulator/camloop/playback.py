"""Export animation from the same nominal swept geometry; never supplies a verdict."""

import json
from pathlib import Path

import numpy as np
import trimesh
from cncsim.geometry import Solid, sweep
from cncsim.simulator import validate

from .common import save


def entry_times(points, a, b, radius, length):
    """First path parameter inside the continuously swept cutting cylinder."""
    p, d = points - a, b - a
    low, high = np.zeros(len(p)), np.ones(len(p))
    possible = np.ones(len(p), dtype=bool)
    if abs(d[2]) < 1e-14:
        possible &= (p[:, 2] >= 0) & (p[:, 2] <= length)
    else:
        t0, t1 = (p[:, 2] - length) / d[2], p[:, 2] / d[2]
        low = np.maximum(low, np.minimum(t0, t1))
        high = np.minimum(high, np.maximum(t0, t1))
    aa = float(d[:2] @ d[:2])
    cc = np.sum(p[:, :2] ** 2, axis=1) - radius**2
    if aa == 0:
        possible &= cc <= 0
    else:
        bb = -2 * (p[:, :2] @ d[:2])
        disc = bb**2 - 4 * aa * cc
        possible &= disc >= 0
        root = np.sqrt(np.maximum(disc, 0))
        low = np.maximum(low, (-bb - root) / (2 * aa))
        high = np.minimum(high, (-bb + root) / (2 * aa))
    entry = np.where(possible & (low <= high), low, np.inf)
    # Root and closest-point calculations can round differently at exact
    # tangencies. Use the simulator's authoritative
    # nominal membership; a degenerate tangent enters at closest feasible time.
    membership = sweep(points, a, b, radius, 0, length)
    missing = membership & ~np.isfinite(entry)
    if np.any(missing):
        zlow, zhigh = np.zeros(len(points)), np.ones(len(points))
        if abs(d[2]) >= 1e-14:
            t0, t1 = (p[:, 2] - length) / d[2], p[:, 2] / d[2]
            zlow = np.maximum(zlow, np.minimum(t0, t1))
            zhigh = np.minimum(zhigh, np.maximum(t0, t1))
        closest = np.zeros(len(points)) if aa == 0 else (p[:, :2] @ d[:2]) / aa
        closest = np.maximum(zlow, np.minimum(zhigh, closest))
        entry[missing] = closest[missing]
    return np.where(membership, entry, np.inf)


def export_playback(plan, output):
    output = Path(output)
    initial = np.load(output / "states/00000.npz")
    occupancy = initial["nominal"].ravel()
    shape, origin, pitch = initial["nominal"].shape, initial["origin"], float(initial["pitch"])
    points = origin + (np.indices(shape).reshape(3, -1).T + 0.5) * pitch
    removal = np.full(len(points), np.inf)
    steps, _ = validate(plan)
    elapsed = 0.0
    for _, kind, a, b, tool_id, seconds in steps:
        if kind == "cut":
            tool = plan["tools"][tool_id]
            t = entry_times(points, a, b, tool["diameter_mm"] / 2, tool["flute_length_mm"])
            hit = np.isfinite(t) & occupancy
            removal[hit] = np.minimum(removal[hit], elapsed + t[hit] * seconds)
        elapsed += seconds
    final = np.load(output / f"states/{len(steps):05d}.npz")["nominal"].ravel()
    if not np.array_equal(occupancy & ~np.isfinite(removal), final):
        raise ValueError(
            "Playback differs from simulator final stock; refusing misleading animation"
        )
    occupancy.astype("u1").tofile(output / "initial.bin")
    removal.astype("<f4").tofile(output / "removal.bin")
    target = trimesh.load_mesh(plan["target"]["path"])
    target.export(output / "target.ply")
    fixtures = []
    for i, spec in enumerate(plan["fixtures"]):
        solid = Solid(spec, ".")
        mesh = solid.mesh
        if mesh is None:
            mesh = trimesh.creation.box(solid.bounds[1] - solid.bounds[0])
            mesh.apply_translation(solid.bounds.mean(axis=0))
        mesh.export(output / f"fixture-{i}.ply")
        fixtures.append(f"fixture-{i}.ply")
    save(
        output / "playback.json",
        dict(
            shape=list(shape),
            origin=origin.tolist(),
            pitch=pitch,
            plan=plan,
            stock_bounds=Solid(plan["stock"], ".").bounds.tolist(),
            fixtures=fixtures,
            trajectory=json.loads((output / "trajectory.json").read_text()),
            result=json.loads((output / "result.json").read_text()),
            stock_representation="nominal voxel stock; animation is not the validity authority",
            final_stock_verified=True,
        ),
    )
