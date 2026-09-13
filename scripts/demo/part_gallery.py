"""Build a source-bound contact sheet of real retained Fusion CAD previews."""

import argparse
import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/presentation"
sys.path.insert(0, str(ROOT))
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
BG = "#10171d"
PANEL = "#1b252d"
WHITE = "#eff4f6"
MUTED = "#9eafb9"
GREEN = "#8dd7b0"
AMBER = "#ffd089"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(draw, xy, value, size, color=WHITE, bold=False):
    draw.text(xy, value, fill=color, font=ImageFont.truetype(BOLD if bold else FONT, size))


def read_part(path, label, short_id):
    manifest = json.loads(path.read_text())
    artifact = manifest["target"]["artifacts"]["preview"]
    preview = Path(artifact["path"])
    if sha(preview) != artifact["sha256"]:
        raise ValueError(f"Preview hash mismatch: {manifest['job_id']}")
    geometry_ref = manifest["target"]["artifacts"]["geometry"]
    geometry_path = Path(geometry_ref["path"])
    if sha(geometry_path) != geometry_ref["sha256"]:
        raise ValueError("Geometry evidence changed")
    geometry = json.loads(geometry_path.read_text())
    best = manifest.get("best_verification") or {}
    passed = best.get("status") == "passed" and best.get("completed") is True
    status = manifest["status"]
    if passed and status == "completed":
        caption, color = "Completed / verified plan", GREEN
    elif passed:
        caption, color = f"Verified candidate / job {status}", AMBER
    else:
        caption, color = f"CAD generated / job {status}", AMBER
    return {
        "label": label,
        "short_id": short_id,
        "job_id": manifest["job_id"],
        "status": status,
        "has_verified_plan": passed,
        "caption": caption,
        "color": color,
        "manifest_path": str(path.relative_to(ROOT)),
        "manifest_sha256": sha(path),
        "preview_path": str(preview.relative_to(ROOT)),
        "preview_sha256": artifact["sha256"],
        "step_sha256": manifest["target"]["artifacts"]["step"]["sha256"],
        "step_path": str(Path(manifest["target"]["artifacts"]["step"]["path"]).relative_to(ROOT)),
        "geometry_path": str(geometry_path.relative_to(ROOT)),
        "geometry_sha256": geometry_ref["sha256"],
        "mesh_sha256": sorted(b["mesh_sha256"] for b in geometry["bodies"]),
        "drawing_sha256": [x["sha256"] for x in manifest["inputs"]["drawings"]],
        "image_kind": "Retained Fusion CAD target preview; not simulated finished stock",
        "machining_seconds": best.get("machining_seconds") if passed else None,
        "verified_candidate_id": (manifest.get("best_candidate") or {}).get("id")
        if passed
        else None,
        "verified_candidate_digest": best.get("candidate_digest") if passed else None,
    }


def render_cad(part):
    """Render actual STEP triangles opaquely; preserve all topology and coordinates."""
    import numpy as np

    from silta.cnc.stock_comparison import step_mesh

    source = ROOT / part["step_path"]
    if sha(source) != part["step_sha256"]:
        raise ValueError("Retained STEP changed")
    mesh = step_mesh(source, 0.025)
    key = part["short_id"].lower().replace(" ", "-")
    mesh_path = OUT / f"part-gallery.{key}.stl"
    mesh.export(mesh_path)
    width, height = 1200, 900
    azimuth, elevation = np.deg2rad([-54, 29])
    eye = np.array(
        [
            np.cos(azimuth) * np.cos(elevation),
            np.sin(azimuth) * np.cos(elevation),
            np.sin(elevation),
        ]
    )
    right = np.array([-np.sin(azimuth), np.cos(azimuth), 0])
    up = np.cross(eye, right)
    projected = mesh.vertices @ np.stack([right, up, eye], axis=1)
    bounds = np.array([projected.min(axis=0), projected.max(axis=0)])
    scale = min(
        (width - 120) / (bounds[1, 0] - bounds[0, 0]),
        (height - 120) / (bounds[1, 1] - bounds[0, 1]),
    )
    projected[:, :2] -= bounds.mean(axis=0)[:2]
    projected[:, :2] *= scale
    projected[:, 0] += width / 2
    projected[:, 1] = height / 2 - projected[:, 1]
    pixels = np.zeros((height, width, 3), dtype=np.uint8)
    pixels[:] = (27, 37, 45)
    depth = np.full((height, width), -np.inf)
    visible_face = np.full((height, width), -1, dtype=np.int32)
    light = np.array([-0.4, -0.6, 1.0])
    light /= np.linalg.norm(light)
    shades = 0.48 + 0.48 * np.clip(mesh.face_normals @ light, 0, 1)
    colors = (shades[:, None] * np.array([224, 240, 250])).astype(np.uint8)
    # Orthographic per-pixel depth test preserves holes and occlusion; no painter sorting.
    for face_index, face in enumerate(mesh.faces):
        a, b, c = projected[face]
        xmin = max(0, int(np.floor(min(a[0], b[0], c[0]))))
        xmax = min(width - 1, int(np.ceil(max(a[0], b[0], c[0]))))
        ymin = max(0, int(np.floor(min(a[1], b[1], c[1]))))
        ymax = min(height - 1, int(np.ceil(max(a[1], b[1], c[1]))))
        if xmin > xmax or ymin > ymax:
            continue
        denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denominator) < 1e-10:
            continue
        yy, xx = np.mgrid[ymin : ymax + 1, xmin : xmax + 1].astype(float)
        xx += 0.5
        yy += 0.5
        wa = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / denominator
        wb = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / denominator
        wc = 1 - wa - wb
        z = wa * a[2] + wb * b[2] + wc * c[2]
        window = depth[ymin : ymax + 1, xmin : xmax + 1]
        mask = (wa >= -1e-8) & (wb >= -1e-8) & (wc >= -1e-8) & (z > window)
        window[mask] = z[mask]
        visible_face[ymin : ymax + 1, xmin : xmax + 1][mask] = face_index
        pixels[ymin : ymax + 1, xmin : xmax + 1][mask] = colors[face_index]
    # Visible normal discontinuities outline actual recess boundaries, not invented curves.
    normal_map = np.zeros((height, width, 3))
    covered = visible_face >= 0
    normal_map[covered] = mesh.face_normals[visible_face[covered]]
    edges = np.zeros((height, width), dtype=bool)
    edges[:, 1:] |= np.linalg.norm(np.diff(normal_map, axis=1), axis=2) > 0.35
    edges[1:, :] |= np.linalg.norm(np.diff(normal_map, axis=0), axis=2) > 0.35
    # Parallel recessed floors share a normal with the outside face: depth jumps reveal their lip.
    safe_depth = np.where(covered, depth, 0)
    threshold = max(0.5, 3 / scale)
    edges[:, 1:] |= (
        (np.abs(np.diff(safe_depth, axis=1)) > threshold) & covered[:, 1:] & covered[:, :-1]
    )
    edges[1:, :] |= (
        (np.abs(np.diff(safe_depth, axis=0)) > threshold) & covered[1:, :] & covered[:-1, :]
    )
    edge_mask = (
        np.asarray(Image.fromarray(edges.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3)))
        > 0
    )
    pixels[edge_mask & covered] = (pixels[edge_mask & covered] * 0.67).astype(np.uint8)
    image_path = OUT / f"part-gallery.{key}.png"
    Image.fromarray(pixels).save(image_path)
    part.update(
        {
            "render_path": str(image_path.relative_to(ROOT)),
            "render_sha256": sha(image_path),
            "tessellation_path": str(mesh_path.relative_to(ROOT)),
            "tessellation_sha256": sha(mesh_path),
            "tessellation_deflection_mm": 0.025,
            "render_camera": {
                "elevation_degrees": 29,
                "azimuth_degrees": -54,
                "projection": "orthographic",
            },
            "image_kind": "Opaque offline rendering of retained CAD STEP; not simulated stock",
        }
    )


def card(canvas, part, x, y, width, height=None):
    draw = ImageDraw.Draw(canvas)
    height = round(width * 0.75) if height is None else height
    image = Image.open(ROOT / part.get("render_path", part["preview_path"])).convert("RGB")
    image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
    draw.rectangle((x, y, x + width, y + height), fill=PANEL)
    canvas.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
    draw.rectangle((x, y + height, x + width, y + height + 88), fill=PANEL)
    text(draw, (x + 18, y + height + 10), part["label"], 28, bold=True)
    text(draw, (x + 18, y + height + 49), part["caption"], 21, part["color"])
    right_label = part["short_id"]
    font = ImageFont.truetype(FONT, 20)
    right_width = draw.textlength(right_label, font=font)
    text(draw, (x + width - right_width - 18, y + height + 14), right_label, 20, MUTED)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--finned-manifest",
        type=Path,
        help="Optional real UMC10 stage manifest; omitted until its target exists",
    )
    args = parser.parse_args()
    history = json.loads((ROOT / "runs/four-part-learning-summary.json").read_text())
    historical = []
    for index, item in enumerate(history["parts"]):
        letter = chr(ord("A") + index)
        historical.append(
            read_part(
                ROOT / "runs" / item["final_run"] / "manifest.json",
                "Soft jaw" if index == 0 else f"Jaw variant {letter}",
                f"Part {letter}",
            )
        )
    campaign = json.loads((ROOT / "runs/demo-campaign.json").read_text())
    indexed = []
    for suffix, label in (
        ("11", "Windowed cage"),
        ("12", "Ribbed clevis"),
        ("09", "Forked bracket"),
        ("08", "Octagonal housing"),
        ("03", "Side-pocket housing"),
        ("02", "Indexed housing"),
        ("04", "Valve feedback block"),
        ("05", "Indexed housing 05"),
        ("06", "Indexed housing 06"),
    ):
        row = next((p for p in campaign["parts"] if p["part_id"].endswith(f"umc-{suffix}")), None)
        if row is None or not row.get("manifest_path"):
            continue
        path = Path(row["manifest_path"])
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file() or not json.loads(path.read_text()).get("target"):
            continue
        indexed.append(read_part(path, label, f"UMC {suffix}"))
    parts = indexed + historical
    if args.finned_manifest:
        finned_path = args.finned_manifest.resolve()
        if finned_path.is_file() and json.loads(finned_path.read_text()).get("target"):
            parts.insert(0, read_part(finned_path, "Finned support", "UMC 10"))
    identities = [tuple(sorted(p["drawing_sha256"])) for p in parts]
    if len(set(identities)) != len(parts):
        raise ValueError("Gallery must contain distinct drawing identities")
    if len({tuple(p["mesh_sha256"]) for p in parts}) != len(parts):
        raise ValueError("Gallery must contain distinct retained geometry meshes")
    OUT.mkdir(parents=True, exist_ok=True)
    for part in parts:
        render_cad(part)
    height = 174 + ((len(parts) + 2) // 3) * 542
    canvas = Image.new("RGB", (2560, height), BG)
    draw = ImageDraw.Draw(canvas)
    text(
        draw, (40, 20), f"{len(parts)} drawings. {len(parts)} generated CAD targets.", 47, bold=True
    )
    text(draw, (42, 78), "Rendered directly from retained Fusion STEP files", 22, MUTED)
    text(draw, (1860, 78), "Indexed 3+2 and 3-axis", 22, MUTED)
    for index, part in enumerate(parts):
        card(canvas, part, 40 + (index % 3) * 835, 124 + (index // 3) * 542, 810, 430)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    text(
        draw,
        (42, height - 36),
        "CAD targets shown; verification labels refer to recorded CAM plans.",
        20,
        MUTED,
    )
    text(draw, (2020, height - 36), now, 18, MUTED)
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "part-gallery.png"
    canvas.save(png)
    variety = Image.new("RGB", (1920, 1080), BG)
    vd = ImageDraw.Draw(variety)
    text(vd, (40, 35), "Three distinct shapes. Verified CAM plans.", 48, bold=True)
    text(vd, (42, 105), "Actual retained CAD targets / completed Fusion jobs", 26, MUTED)
    preferred = ("UMC 11", "UMC 12", "UMC 10", "UMC 09", "UMC 08", "UMC 04")
    hero_ids = tuple(
        identity
        for identity in preferred
        if any(
            p["short_id"] == identity and p["status"] == "completed" and p["has_verified_plan"]
            for p in parts
        )
    )[:3]
    hero_parts = [next(p for p in parts if p["short_id"] == identity) for identity in hero_ids]
    assert all(p["status"] == "completed" and p["has_verified_plan"] for p in hero_parts)
    for index, part in enumerate(hero_parts):
        card(variety, part, 30 + index * 630, 205, 600, 600)
    text(
        vd,
        (42, 990),
        "CAD previews shown. Finished-stock verification is retained in each run.",
        25,
        MUTED,
    )
    variety_path = OUT / "part-gallery.variety.png"
    variety.save(variety_path)
    evidence = {
        "schema_version": 1,
        "generated_at": now,
        "image_path": str(png.relative_to(ROOT)),
        "image_sha256": sha(png),
        "variety_image": {
            "path": str(variety_path.relative_to(ROOT)),
            "sha256": sha(variety_path),
            "parts": [p["job_id"] for p in hero_parts],
        },
        "distinct_drawings": len(parts),
        "completed_drawings": sum(p["status"] == "completed" for p in parts),
        "parts": parts,
        "image_treatment": (
            "Opaque offline render of exact retained STEP tessellation at 0.025 mm deflection; "
            "visible normal/depth-discontinuity outlines; source and mesh hashes retained"
        ),
        "camera_capture_recommendations": [
            {
                "part": "UMC08",
                "view": (
                    "Elevated three-quarter orbit, then near-side level; "
                    "show stepped bore and three octagonal windows"
                ),
                "needed": "Fresh Fusion capture of final verified stock when available",
            },
            {
                "part": "UMC03",
                "view": (
                    "Lower three-quarter then quarter-turn; show indexed side pockets and top holes"
                ),
                "needed": ("Fresh finished-stock orbit of the completed best verified candidate"),
            },
            {
                "part": "UMC02",
                "view": "Elevated three-quarter; show bore/shoulder and side machining",
                "needed": "Fresh completed-plan stock capture if used as verified visual hero",
            },
            {
                "part": "A-D",
                "view": (
                    "Retained isometric previews compare counterbores; "
                    "a shallow side view reveals pocket depth"
                ),
                "needed": (
                    "No new capture required for CAD gallery; "
                    "fresh stock footage only if showing machining results"
                ),
            },
        ],
    }
    (OUT / "part-gallery.json").write_text(json.dumps(evidence, indent=2) + "\n")
    data = base64.b64encode(png.read_bytes()).decode()
    (OUT / "part-gallery.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Silta — generated CAD gallery</title>'
        "<style>html,body{margin:0;background:#10171d;height:100%;display:grid;place-items:center}"
        "img{display:block;width:100vw;max-height:100vh;object-fit:contain}</style>"
        f'<img alt="{len(parts)} actual Fusion CAD target previews and recorded job status" '
        f'src="data:image/png;base64,{data}">'
    )
    print(
        json.dumps(
            {
                "path": str(png),
                "parts": len(parts),
                "completed": sum(p["status"] == "completed" for p in parts),
            }
        )
    )


if __name__ == "__main__":
    main()
