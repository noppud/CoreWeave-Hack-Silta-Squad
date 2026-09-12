"""Deterministic CAD construction and export.

The model never supplies code. It supplies a validated `PartSpec`, and only the
trusted primitives below turn that into a solid. The STEP file is the *target
design*; it carries no machining recipe and no check status.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from silta.domain import Feature, FeatureKind, PartSpec

BUILDER_VERSION = "cad-1"

# Numerical tolerances for comparing an OCCT solid against the analytic oracle.
VOLUME_REL_TOL = 1e-3
LENGTH_ABS_TOL_MM = 1e-3


@dataclass(frozen=True)
class CadResult:
    step_path: Path
    mesh_path: Path
    step_sha256: str
    mesh_sha256: str
    volume_mm3: float
    bbox_mm: tuple[float, float, float]
    reimported_volume_mm3: float
    solid_valid: bool
    builder_version: str = BUILDER_VERSION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rounded_rect_profile(cx: float, cy: float, width: float, height: float, radius: float):
    """A rounded rectangle drawn as lines and arcs, rather than rect-then-fillet.

    `.rect(...).fillet(r)` asks OCCT to round an existing corner, which fails outright
    when the radius reaches half the narrow width — the corners become tangent and the
    fillet operation raises `BRep_API: command not done`. That shape is legal: a pocket
    whose radius is half its width is a slot with semicircular ends, and the domain
    validator accepts it. Constructing the profile directly covers the whole legal
    range, degenerate cases included, and matches the closed-form area to machine
    precision.
    """
    import cadquery as cq

    half_w, half_h = width / 2.0, height / 2.0
    flat_x = width - 2 * radius > 1e-9
    flat_y = height - 2 * radius > 1e-9

    wp = cq.Workplane("XY").center(cx, cy).moveTo(-half_w + radius, -half_h)
    if flat_x:
        wp = wp.lineTo(half_w - radius, -half_h)
    wp = wp.radiusArc((half_w, -half_h + radius), -radius)
    if flat_y:
        wp = wp.lineTo(half_w, half_h - radius)
    wp = wp.radiusArc((half_w - radius, half_h), -radius)
    if flat_x:
        wp = wp.lineTo(-half_w + radius, half_h)
    wp = wp.radiusArc((-half_w, half_h - radius), -radius)
    if flat_y:
        wp = wp.lineTo(-half_w, -half_h + radius)
    wp = wp.radiusArc((-half_w + radius, -half_h), -radius)
    return wp.close()


def _cut_pocket(solid, feature: Feature):
    width = feature.x_max_mm - feature.x_min_mm
    height = feature.y_max_mm - feature.y_min_mm
    cx = (feature.x_min_mm + feature.x_max_mm) / 2
    cy = (feature.y_min_mm + feature.y_max_mm) / 2
    cutter = _rounded_rect_profile(cx, cy, width, height, feature.corner_radius_mm).extrude(
        -feature.depth_mm
    )
    return solid.cut(cutter)


def _cut_hole(solid, feature: Feature):
    import cadquery as cq

    radius = feature.diameter_mm / 2
    cylindrical = feature.cylindrical_depth_mm
    tip = feature.tip_extra_mm
    cutter = (
        cq.Workplane("XY")
        .center(feature.center_x_mm, feature.center_y_mm)
        .circle(radius)
        .extrude(-cylindrical)
    )
    if tip > 0:
        cone = (
            cq.Workplane("XY")
            .center(feature.center_x_mm, feature.center_y_mm)
            .workplane(offset=-cylindrical)
            .circle(radius)
            .workplane(offset=-tip)
            .circle(1e-4)
            .loft(combine=True)
        )
        cutter = cutter.union(cone)
    return solid.cut(cutter)


def build_solid(spec: PartSpec):
    """Trusted primitives only: stock box, then feature subtraction."""
    import cadquery as cq

    solid = cq.Workplane("XY").box(
        spec.stock_x_mm, spec.stock_y_mm, spec.stock_z_mm, centered=(False, False, False)
    )
    # Stock top must sit at Z = 0; the box above spans 0..stock_z.
    solid = solid.translate((0, 0, -spec.stock_z_mm))
    for feature in spec.features:
        if feature.kind is FeatureKind.POCKET_RECT_ROUNDED:
            solid = _cut_pocket(solid, feature)
        elif feature.kind is FeatureKind.HOLE_BLIND:
            solid = _cut_hole(solid, feature)
        else:  # pragma: no cover - the enum is closed
            raise ValueError(f"Unsupported feature kind {feature.kind}.")
    return solid


def build_and_export(spec: PartSpec, out_dir: Path) -> CadResult:
    """Build, export STEP + STL, then reimport the STEP and measure it again."""
    from cadquery import exporters, importers

    out_dir.mkdir(parents=True, exist_ok=True)
    solid = build_solid(spec)
    shape = solid.val()
    if not shape.isValid():
        raise ValueError("CAD builder produced an invalid solid for a valid specification.")
    volume = shape.Volume()
    if volume <= 0:
        raise ValueError("CAD builder produced a non-positive volume.")
    bb = shape.BoundingBox()

    step_path = out_dir / "target.step"
    mesh_path = out_dir / "target.stl"
    exporters.export(solid, str(step_path))
    exporters.export(solid, str(mesh_path), tolerance=0.05, angularTolerance=0.2)

    reimported = importers.importStep(str(step_path)).val()
    return CadResult(
        step_path=step_path,
        mesh_path=mesh_path,
        step_sha256=_sha256(step_path),
        mesh_sha256=_sha256(mesh_path),
        volume_mm3=volume,
        bbox_mm=(bb.xlen, bb.ylen, bb.zlen),
        reimported_volume_mm3=reimported.Volume(),
        solid_valid=True,
    )


def verify_against_oracle(result: CadResult, expected: dict) -> list[tuple[str, bool, str]]:
    """Compare the built solid with independently calculated expectations."""
    checks: list[tuple[str, bool, str]] = []

    def close(actual: float, want: float, rel: float = VOLUME_REL_TOL) -> bool:
        return math.isclose(actual, want, rel_tol=rel, abs_tol=LENGTH_ABS_TOL_MM)

    want_volume = expected["part_volume_mm3"]
    checks.append(
        (
            "cad_volume",
            close(result.volume_mm3, want_volume),
            f"{result.volume_mm3:.3f} mm3 vs analytic {want_volume:.3f} mm3",
        )
    )
    want_bbox = expected["bbox_mm"]
    checks.append(
        (
            "cad_bounding_box",
            all(close(a, b) for a, b in zip(result.bbox_mm, want_bbox, strict=True)),
            f"{result.bbox_mm} vs {tuple(want_bbox)}",
        )
    )
    checks.append(
        (
            "step_roundtrip_volume",
            close(result.reimported_volume_mm3, result.volume_mm3),
            f"reimported {result.reimported_volume_mm3:.3f} mm3",
        )
    )
    return checks


def mesh_arrays(mesh_path: Path) -> dict:
    """Read a binary or ASCII STL into flat arrays for the browser viewer."""
    import numpy as np

    raw = mesh_path.read_bytes()
    if raw[:5].lower() == b"solid" and b"facet normal" in raw[:2048]:
        positions: list[float] = []
        for line in raw.decode("utf-8", "replace").splitlines():
            parts = line.split()
            if parts and parts[0] == "vertex":
                positions.extend(float(v) for v in parts[1:4])
        vertices = np.asarray(positions, dtype=np.float32)
    else:
        count = int.from_bytes(raw[80:84], "little")
        body = np.frombuffer(raw, dtype=np.uint8, offset=84)
        body = body[: count * 50].reshape(count, 50)
        floats = body[:, 12:48].copy().view(np.float32).reshape(count, 9)
        vertices = floats.reshape(-1).astype(np.float32)
    positions_out = [round(float(v), 4) for v in vertices]
    return {"positions": positions_out, "triangle_count": len(positions_out) // 9}
