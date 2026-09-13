"""Reproduce six project-authored indexed CNC drawings and pinned job inputs.

No Fusion execution, generated CAM, machine verdicts or runtime/model changes.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
PDF_ROOT = ROOT / "output/pdf/demo-campaign"
CONFIG_ROOT = ROOT / "config/demo-campaign"
BASE = ROOT / "config/umc-actuator-tall-job.json"


def side(width, height, center_z, depth, island=12, center_u=0):
    return dict(
        width_mm=width,
        height_mm=height,
        center_u_mm=center_u,
        center_z_mm=center_z,
        depth_mm=depth,
        corner_radius_mm=8,
        island_diameter_mm=island,
    )


PARTS = [
    dict(
        id="umc-02",
        name="Compact sensor node",
        split="training",
        top_center_mm=[0, 0],
        recess=[42, 5, 32, 16],
        holes=[26, 14, 6],
        x_faces=side(44, 40, -34, 6, 10),
        y_faces=side(44, 40, -34, 6, 10),
    ),
    dict(
        id="umc-03",
        name="Drive encoder housing",
        split="training",
        top_center_mm=[0, 0],
        recess=[48, 4, 36, 18],
        holes=[28, 14, 7],
        x_faces=side(50, 40, -33, 7),
        y_faces=side(50, 40, -33, 7),
    ),
    dict(
        id="umc-04",
        name="Valve feedback block",
        split="training",
        top_center_mm=[0, 0],
        recess=[46, 6, 38, 20],
        holes=[27, 14, 8],
        x_faces=side(46, 42, -33, 6),
        y_faces=side(46, 42, -33, 6),
    ),
    dict(
        id="umc-05",
        name="Wide service manifold",
        split="training",
        top_center_mm=[0, 0],
        recess=[54, 4, 42, 16],
        holes=[29, 14, 6],
        x_faces=side(52, 40, -34, 8),
        y_faces=side(52, 40, -34, 8),
    ),
    dict(
        id="umc-06",
        name="Offset monitoring block",
        split="training",
        top_center_mm=[-3, 2],
        recess=[44, 5, 34, 18],
        holes=[28, 14, 6],
        x_faces=side(44, 40, -32, 6, 12, 3),
        y_faces=side(48, 40, -34, 8, 12, -2),
    ),
    dict(
        id="umc-07",
        name="Cross-port service block",
        split="heldout",
        top_center_mm=[2, -2],
        recess=[50, 5, 40, 19],
        holes=[27, 14, 7],
        x_faces=side(48, 40, -33, 7, 12, -2),
        y_faces=side(46, 42, -32, 6, 12, 2),
    ),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def geometry(part):
    outer, outer_depth, inner, total = part["recess"]
    spacing, hole_diameter, hole_depth = part["holes"]
    return dict(
        units="mm",
        stock_min=[-40, -40, -70],
        stock_max=[40, 40, 0],
        top_recess=dict(
            center_xy_mm=part["top_center_mm"],
            outer_diameter_mm=outer,
            outer_depth_mm=outer_depth,
            inner_diameter_mm=inner,
            total_depth_mm=total,
        ),
        top_holes=dict(
            diameter_mm=hole_diameter,
            depth_mm=hole_depth,
            centers_xy_mm=[[x, y] for x in [-spacing, spacing] for y in [-spacing, spacing]],
        ),
        side_pockets=dict(
            x_positive_and_negative=part["x_faces"], y_positive_and_negative=part["y_faces"]
        ),
        side_coordinate_rule="For +/-X faces U=global Y; for +/-Y faces U=global X. Z is global Z. "
        "All pocket depths are inward normal to the exterior face. "
        "Each central circular island stays flush with that original face.",
        unchanged_surfaces="Stock exterior and bottom except the explicitly defined "
        "blind openings. "
        "No bottom machining, exterior facing, chamfers, fillets or threads.",
    )


def validate(part):
    outer, outer_depth, inner, total = part["recess"]
    spacing, hole_diameter, hole_depth = part["holes"]
    assert 12.7 < inner < outer and 0 < outer_depth < total <= 20 < 25.4
    assert hole_diameter > 12.7 and hole_depth <= 8
    assert spacing + hole_diameter / 2 < 40
    cx, cy = part["top_center_mm"]
    assert abs(cx) + outer / 2 < 40 and abs(cy) + outer / 2 < 40
    for x in [-spacing, spacing]:
        for y in [-spacing, spacing]:
            assert ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 > (outer + hole_diameter) / 2
    for s in [part["x_faces"], part["y_faces"]]:
        assert s["corner_radius_mm"] > 12.7 / 2
        assert (min(s["width_mm"], s["height_mm"]) - s["island_diameter_mm"]) / 2 > 12.7
        assert abs(s["center_u_mm"]) + s["width_mm"] / 2 < 40
        assert s["center_z_mm"] - s["height_mm"] / 2 >= -54
        assert s["center_z_mm"] + s["height_mm"] / 2 < -hole_depth
        assert 0 < s["depth_mm"] <= 8
    # Central recess and perpendicular side cuts remain geometrically separate.
    assert abs(cx) + outer / 2 < 40 - part["x_faces"]["depth_mm"]
    assert abs(cy) + outer / 2 < 40 - part["y_faces"]["depth_mm"]


def draw_pdf(part, path):
    width, height = landscape(A3)
    c = canvas.Canvas(str(path), pagesize=(width, height), invariant=1, pageCompression=1)
    c.setTitle(f"{part['id'].upper()} - {part['name']}")
    c.setAuthor("Silta - project-authored simulation benchmark")
    ink, teal, pale = (
        colors.HexColor("#122b39"),
        colors.HexColor("#116c74"),
        colors.HexColor("#e7f1f2"),
    )

    def text(x, y, value, size=11, bold=False, color=ink):
        c.setFillColor(color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, value)

    def dim_horizontal(x1, x2, y, label):
        c.setStrokeColor(colors.HexColor("#77888f"))
        c.setLineWidth(0.6)
        c.line(x1, y - 5, x1, y + 5)
        c.line(x2, y - 5, x2, y + 5)
        c.line(x1, y, x2, y)
        c.setFillColor(colors.white)
        c.rect((x1 + x2) / 2 - 18, y - 6, 36, 13, fill=1, stroke=0)
        text((x1 + x2) / 2 - 8, y - 3, label, 10)

    c.setFillColor(ink)
    c.rect(0, height - 100, width, 100, stroke=0, fill=1)
    text(40, height - 42, f"SILTA / {part['name'].upper()}", 22, True, colors.white)
    text(
        40,
        height - 70,
        f"DEMO-5X-{part['id'][-2:]} | REV A | AL6061 | ALL DIMENSIONS mm | GENERAL +/-0.127 mm",
        12,
        color=colors.white,
    )
    text(
        40,
        height - 125,
        "80 x 80 x 70 pre-sized blank. G54 origin = top-face center. Z up.",
        13,
        True,
    )
    text(
        40,
        height - 146,
        "Indexed 3+2 on UMC-750. One T1 flat end mill, diameter 12.7, "
        "flute length 25.4. NOT TO SCALE.",
        11,
    )

    scale, base_y = 2.7, 405
    top_x = 72
    text(top_x, 660, "TOP / +Z", 14, True)
    text(top_x, 640, "View coordinates: X right, Y up", 10)
    c.setLineWidth(1.4)
    c.setStrokeColor(ink)
    c.setFillColor(colors.white)
    c.rect(top_x, base_y, 80 * scale, 80 * scale, stroke=1, fill=0)
    center_x, center_y = top_x + 40 * scale, base_y + 40 * scale
    c.setDash(3, 3)
    c.setLineWidth(0.5)
    c.setStrokeColor(colors.HexColor("#9bafb5"))
    c.line(center_x, base_y - 8, center_x, base_y + 80 * scale + 8)
    c.line(top_x - 8, center_y, top_x + 80 * scale + 8, center_y)
    c.setDash()
    cx, cy = part["top_center_mm"]
    outer, _, inner, _ = part["recess"]
    c.setFillColor(pale)
    c.setStrokeColor(teal)
    c.setLineWidth(1.1)
    c.circle(center_x + cx * scale, center_y + cy * scale, outer / 2 * scale, fill=1)
    c.circle(center_x + cx * scale, center_y + cy * scale, inner / 2 * scale, fill=0)
    spacing, dia, _ = part["holes"]
    for x in [-spacing, spacing]:
        for y in [-spacing, spacing]:
            c.circle(center_x + x * scale, center_y + y * scale, dia / 2 * scale, fill=1)
    text(center_x + cx * scale - 5, center_y + cy * scale - 5, "A", 13, True, teal)
    text(top_x + 12, base_y + 183, "H", 11, True, teal)
    dim_horizontal(top_x, top_x + 80 * scale, base_y - 22, "80")

    for x0, side_key, title, axis in [
        (439, "x_faces", "SIDES / +X AND -X", "global Y"),
        (806, "y_faces", "SIDES / +Y AND -Y", "global X"),
    ]:
        s = part[side_key]
        text(x0, 660, title, 14, True)
        text(x0, 640, f"Coordinate diagram: U = {axis}, Z up", 10)
        c.setStrokeColor(ink)
        c.setLineWidth(1.4)
        # Align stock top with top-view top; side bottom sits 10 mm higher.
        y0 = base_y + 10 * scale
        c.rect(x0, y0, 80 * scale, 70 * scale, stroke=1, fill=0)
        px = x0 + (40 + s["center_u_mm"] - s["width_mm"] / 2) * scale
        py = y0 + (70 + s["center_z_mm"] - s["height_mm"] / 2) * scale
        c.setFillColor(pale)
        c.setStrokeColor(teal)
        c.setLineWidth(1.1)
        c.roundRect(
            px,
            py,
            s["width_mm"] * scale,
            s["height_mm"] * scale,
            s["corner_radius_mm"] * scale,
            stroke=1,
            fill=1,
        )
        c.setFillColor(colors.white)
        c.circle(
            x0 + (40 + s["center_u_mm"]) * scale,
            y0 + (70 + s["center_z_mm"]) * scale,
            s["island_diameter_mm"] / 2 * scale,
            stroke=1,
            fill=1,
        )
        text(x0 + 8, y0 + 70 * scale + 7, "Z=0", 10)
        text(x0 + 8, y0 - 16, "Z=-70; bottom untouched", 10)
        text(x0 + 80 * scale + 8, y0 + 35 * scale, "70", 10)
        dim_horizontal(x0, x0 + 80 * scale, base_y - 22, "80")

    # Exact dimensions, rather than scale-derived measurements, define the target.
    text(40, 344, "FEATURE SCHEDULE - CUT ONLY THESE BLIND FEATURES", 14, True)
    c.setFillColor(pale)
    c.rect(40, 190, width - 80, 137, fill=1, stroke=0)
    outer, od, inner, total = part["recess"]
    spacing, dia, hd = part["holes"]
    text(
        54,
        305,
        f"A / Top concentric stepped recess at (X,Y)=({cx},{cy}): diameter {outer} to depth {od};",
        12,
        True,
    )
    text(
        78,
        286,
        f"diameter {inner} to TOTAL depth {total} from Z=0. Flat floors; no island in this recess.",
        11,
    )
    text(
        54,
        262,
        f"H / 4 blind holes: diameter {dia}, depth {hd}; "
        f"centers (X,Y)=(+/-{spacing}, +/-{spacing}). Flat bottoms.",
        11,
    )
    for y, key, label in [(238, "x_faces", "+X and -X"), (217, "y_faces", "+Y and -Y")]:
        s = part[key]
        text(
            54,
            y,
            f"{label}: each pocket {s['width_mm']} wide x {s['height_mm']} high, "
            f"R{s['corner_radius_mm']} corners; "
            f"center (U,Z)=({s['center_u_mm']},{s['center_z_mm']}); depth {s['depth_mm']} inward; "
            f"central island diameter {s['island_diameter_mm']}.",
            11,
        )
    text(
        40,
        165,
        "Side pockets: planar floors. Islands share their pocket centers and "
        "stay flush with the original exterior face.",
        11,
    )
    text(
        40,
        145,
        "Side depths measured inward from X=+/-40 or Y=+/-40. U definitions "
        "above are global coordinates, not mirrored views.",
        11,
    )
    text(
        40,
        116,
        "UNSPECIFIED GEOMETRY IS PROHIBITED: no bottom cuts, exterior facing, "
        "edge fillets, chamfers, threads or through holes.",
        11,
        True,
    )
    text(
        40,
        96,
        "Precondition: the pre-sized blank is secured from below on the provided "
        "tall pedestal; mounting hardware is not a part feature.",
        11,
    )
    text(
        40,
        76,
        "Demo AL6061 input. Fixed exterior and bottom are already to size. Rigid "
        "fixture assumption; no physical load or cutting-force certification.",
        10,
    )
    c.setStrokeColor(colors.HexColor("#b8c8cb"))
    c.line(40, 55, width - 40, 55)
    text(
        40, 37, "PROJECT-AUTHORED BENCHMARK DRAWING - NOT A CUSTOMER OR INTERNET-SOURCED DESIGN", 9
    )
    text(width - 190, 37, f"{part['id'].upper()} / Rev A / 1 of 1", 9)
    c.showPage()
    c.save()


def build():
    base = json.loads(BASE.read_text())
    fixture = base["setup"]["fixture"]["artifact"]
    assert sha(fixture["path"]) == fixture["sha256"], "Current fixture artifact hash mismatch"
    assert base["setup"]["stock"]["dimensions_mm"] == [80, 80, 70]
    assert [tool["number"] for tool in base["tools"]["entries"] if tool.get("enabled")] == [1]
    PDF_ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "base_config": str(BASE),
        "fixture": fixture,
        "description": "Six NEW indexed target definitions; no machining outcomes included.",
        "parts": [],
    }
    seen = set()
    for part in PARTS:
        validate(part)
        spec = geometry(part)
        gh = canonical_hash(spec)
        assert gh not in seen
        seen.add(gh)
        pdf = PDF_ROOT / f"{part['id']}.pdf"
        draw_pdf(part, pdf)
        job = copy.deepcopy(base)
        job["drawings"] = [{"path": str(pdf), "sha256": sha(pdf)}]
        job["setup"]["material_source"] = f"DEMO-5X-{part['id'][-2:]} Rev A"
        job["setup"]["stock"]["precondition"] = (
            "Pre-sized AL6061 80x80x70 blank. Exterior and bottom remain unchanged "
            "except the specified top and four-side blind openings. Secured from below."
        )
        job["setup"]["simulation_assumptions"][0] = (
            f"Single T1 diameter12.7 flat end mill; flute25.4 and stickout33.02mm. "
            f"Top maximum depth{part['recess'][3]}mm; side maximum depth"
            f"{max(part['x_faces']['depth_mm'], part['y_faces']['depth_mm'])}mm."
        )
        job["tolerances"]["source"] = f"DEMO-5X-{part['id'][-2:]} Rev A general +/-0.127mm"
        job["sources"]["drawing_archive"] = (
            "Project-authored benchmark drawing; reproducible from "
            "scripts/demo/prepare_fusion_campaign.py"
        )
        job["readiness_scope"] = (
            "Drawing and unchanged machine/tool/fixture artifacts pinned; target "
            "CAD, CAM and completed simulation still to be generated and verified."
        )
        job["demo_part_spec"] = dict(
            part_id=part["id"],
            part_name=part["name"],
            split=part["split"],
            geometry=spec,
            geometry_sha256=gh,
            geometry_hash_scope="Canonical target specification, not a CAD-file hash",
            training_allowed=part["split"] == "training",
        )
        config = CONFIG_ROOT / f"{part['id']}-job.json"
        config.write_text(json.dumps(job, indent=2) + "\n")
        manifest["parts"].append(
            dict(
                id=part["id"],
                name=part["name"],
                split=part["split"],
                config_path=str(config),
                pdf_path=str(pdf),
                pdf_sha256=sha(pdf),
                geometry_sha256=gh,
                status="prepared_not_run",
            )
        )
    (CONFIG_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    build()
