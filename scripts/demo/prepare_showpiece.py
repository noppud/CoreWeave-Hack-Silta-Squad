"""Reproduce UMC08: an analytical drawing, not a CAD/CAM solution."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "output/pdf/demo-campaign/umc-08.pdf"
CONFIG = ROOT / "config/demo-campaign/umc-08-job.json"
INK = colors.HexColor("#183644")
BLUE = colors.HexColor("#087F9B")
PALE = colors.HexColor("#E6F1F4")
GEOMETRY = {
    "units": "mm",
    "blank_min": [-40, -40, -70],
    "blank_max": [40, 40, 0],
    "base": {"x": [-40, 40], "y": [-40, 40], "z": [-70, -54]},
    "upper": {
        "shape": "regular octagonal prism",
        "across_flats": 74,
        "z": [-54, 0],
        "face_normal_angles_deg": list(range(0, 360, 45)),
        "halfspace_definition": "x*cos(theta)+y*sin(theta)<=37 for every listed theta",
    },
    "top_cavity": {
        "center_xy": [0, 0],
        "outer_diameter": 46,
        "outer_depth": 5,
        "inner_diameter": 32,
        "total_depth": 18,
    },
    "side_slots": {
        "count": 8,
        "width_u": 16,
        "height_z": 30,
        "radius": 8,
        "center_u": 0,
        "center_z": -28,
        "normal_depth": 5,
        "definition": "Blind vertical obround on each octagonal face; "
        "tangent U=(-sin(theta),cos(theta),0).",
    },
    "tolerance_mm": 0.127,
    "tolerance_deg": 0.2,
    "excluded": "No bottom or flange exterior machining, holes, threads, "
    "chamfers or added fillets.",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate():
    assert GEOMETRY["base"]["z"][1] - GEOMETRY["base"]["z"][0] == 16
    assert 40 * math.sqrt(2) - 37 < 20 < 25.4
    assert 16 > 12.7 and 8 > 12.7 / 2
    assert 18 <= 20 and 5 <= 20
    assert 74 * math.tan(math.pi / 8) > 16
    assert -28 - 30 / 2 > -54
    assert 37 - 5 - 46 / 2 >= 9


def text(c, x, y, value, size=10, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, value)


def poly(c, points, fill=None, width=0.8):
    c.setStrokeColor(INK)
    c.setLineWidth(width)
    p = c.beginPath()
    p.moveTo(*points[0])
    for point in points[1:]:
        p.lineTo(*point)
    p.close()
    if fill:
        c.setFillColor(fill)
    c.drawPath(p, fill=int(fill is not None), stroke=1)


def dimension(c, x1, y1, x2, y2, label):
    c.setStrokeColor(BLUE)
    c.setLineWidth(0.55)
    c.line(x1, y1, x2, y2)
    angle = math.atan2(y2 - y1, x2 - x1)
    for x, y, direction in [(x1, y1, angle), (x2, y2, angle + math.pi)]:
        for spread in [-0.4, 0.4]:
            c.line(x, y, x + 5 * math.cos(direction + spread), y + 5 * math.sin(direction + spread))
    text(c, (x1 + x2) / 2 + (6 if x1 == x2 else -10), (y1 + y2) / 2 + 5, label, 9, color=BLUE)


def octagon():
    t = 37 * math.tan(math.pi / 8)
    return [(37, t), (t, 37), (-t, 37), (-37, t), (-37, -t), (-t, -37), (t, -37), (37, -t)]


def obround():
    return [
        (8 * math.cos(a), 7 + 8 * math.sin(a)) for a in [math.pi * i / 24 for i in range(25)]
    ] + [
        (8 * math.cos(a), -7 + 8 * math.sin(a))
        for a in [math.pi + math.pi * i / 24 for i in range(25)]
    ]


def drawing():
    PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=landscape(A3), invariant=1)
    c.setTitle("UMC-08 Rev A | Octagonal instrument housing | Project benchmark")
    c.setAuthor("Silta project team - project-authored demonstration drawing")
    w, h = landscape(A3)
    c.setFillColor(INK)
    c.rect(0, h - 86, w, 86, fill=1, stroke=0)
    text(c, 32, h - 36, "OCTAGONAL INSTRUMENT HOUSING", 25, True, colors.white)
    text(
        c,
        33,
        h - 62,
        "UMC-08 / REV A     PROJECT-AUTHORED BENCHMARK - NOT A CUSTOMER DRAWING",
        11,
        color=colors.white,
    )
    for x, label in [
        (34, "01  TOP VIEW"),
        (347, "02  TYPICAL FACET / ELEVATION"),
        (725, "03  ANALYTICAL ISOMETRIC"),
    ]:
        text(c, x, 723, label, 12, True)

    s, ox, oy = 2.65, 163, 575

    def top(x, y):
        return ox + s * x, oy + s * y

    poly(c, [top(x, y) for x, y in [(-40, -40), (40, -40), (40, 40), (-40, 40)]], PALE)
    poly(c, [top(x, y) for x, y in octagon()], colors.white)
    for radius in [23, 16]:
        c.circle(ox, oy, radius * s)
    c.setDash(3, 3)
    c.setStrokeColor(BLUE)
    c.line(ox - 120, oy, ox + 120, oy)
    c.line(ox, oy - 120, ox, oy + 120)
    c.setDash()
    dimension(c, ox - 40 * s, 452, ox + 40 * s, 452, "80")
    dimension(c, ox - 37 * s, 693, ox + 37 * s, 693, "74 A/F")
    for i, line in enumerate(
        [
            "Cavity: DIA 46 x 5; DIA 32 x 18 TOTAL",
            "Concentric at X0 Y0; depths from Z0.",
            "8 equal facets; normals at 0,45,...315 deg.",
            "Flange outer boundary remains 80 x 80.",
        ]
    ):
        text(c, 46, 420 - i * 19, line, 10, i == 0)

    ox, oy, s = 462, 663, 2.55

    def side(x, z):
        return ox + s * x, oy + s * z

    poly(c, [side(-40, -70), side(40, -70), side(40, -54), side(-40, -54)], PALE)
    poly(c, [side(-37, -54), side(37, -54), side(37, 0), side(-37, 0)], colors.white)
    t = 37 * math.tan(math.pi / 8)
    for x in [-t, t]:
        c.line(*side(x, 0), *side(x, -54))
    poly(c, [side(u, -28 + v) for u, v in obround()], PALE)
    dimension(c, 581, oy, 581, oy - 54 * s, "54")
    dimension(c, 581, oy - 54 * s, 581, oy - 70 * s, "16")
    dimension(c, 339, oy, 339, oy - 70 * s, "70")
    text(c, 602, oy - 28 * s, "Z=-28", 9, color=BLUE)
    c.setDash(3, 3)
    c.line(*side(-20, -28), *side(20, -28))
    c.setDash()
    text(c, 357, 452, "8X BLIND VERTICAL OBROUND", 10, True)
    for i, line in enumerate(
        [
            "Width 16, height 30, end radius R8.",
            "Centered on facet: U0, Z=-28.",
            "Depth 5 normal inward from finished facet.",
            "Slot spans Z=-43 to -13; floor is planar.",
            "No slot intersects top cavity or flange.",
        ]
    ):
        text(c, 357, 432 - i * 19, line, 10)

    # Mathematical projection of drawing primitives, never represented as CAD.
    def iso(x, y, z):
        return 920 + 2.2 * (math.sqrt(3) / 2) * (x - y), 650 + 2.2 * (0.5 * x + 0.5 * y + z)

    base = [(-40, -40), (40, -40), (40, 40), (-40, 40)]
    for a, b in [(base[0], base[1]), (base[3], base[0])]:
        poly(
            c, [iso(*a, -54), iso(*b, -54), iso(*b, -70), iso(*a, -70)], colors.HexColor("#B5CCD3")
        )
    poly(c, [iso(x, y, -54) for x, y in base], colors.HexColor("#DBE8EC"))
    points = octagon()
    for index, a in enumerate(points):
        b = points[(index + 1) % 8]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if mx + my >= -1e-8:
            continue
        poly(
            c,
            [iso(*a, 0), iso(*b, 0), iso(*b, -54), iso(*a, -54)],
            colors.HexColor("#A5CBD6" if mx > 0 else "#C6DEE5"),
        )
        theta = math.atan2(my, mx)
        normal = (math.cos(theta), math.sin(theta))
        tangent = (-normal[1], normal[0])
        poly(
            c,
            [
                iso(37 * normal[0] + u * tangent[0], 37 * normal[1] + u * tangent[1], -28 + v)
                for u, v in obround()
            ],
            colors.HexColor("#4E8496"),
        )
    poly(c, [iso(x, y, 0) for x, y in points], colors.HexColor("#EEF5F7"))
    for radius, depth, fill in [(23, 0, "#4E8496"), (23, -5, "#A5CBD6"), (16, -5, "#2F6476")]:
        pts = [
            iso(radius * math.cos(a), radius * math.sin(a), depth)
            for a in [i * 2 * math.pi / 96 for i in range(96)]
        ]
        poly(c, pts, colors.HexColor(fill), 0.5)
    text(c, 740, 385, "Illustrative projection of the specified geometry.", 9)
    text(c, 740, 369, "Not CAD output, a simulation, or a completed part.", 9)

    c.setStrokeColor(BLUE)
    c.line(34, 330, w - 34, 330)
    text(c, 34, 306, "COMPLETE GEOMETRY / DATUM CONTRACT", 12, True)
    left = [
        "All dimensions mm. Origin X0 Y0 Z0 = original blank top center; +Z up.",
        "Base: X and Y in [-40,+40], Z in [-70,-54]. Base stays entirely solid.",
        "Upper: Z in [-54,0], regular octagon across flats 74, centered X0 Y0.",
        "Exact facet planes: X cos(theta) + Y sin(theta) = 37;",
        "theta = 0,45,90,135,180,225,270,315 deg. Solid lies <=37 for all planes.",
        "Facet length = 74 tan(22.5 deg) = 30.6518 REF. No facet-edge chamfers.",
        "For each slot: U=(-sin(theta),cos(theta),0), origin on face at Z=-28.",
        "Subtract its 16 x 30 obround profile inward 5 along the face normal.",
        "Top cavity: circular DIA46 to Z=-5; concentric DIA32 to Z=-18.",
        "All pocket floors flat. Sharp theoretical exterior edges; no added fillets.",
    ]
    right = [
        "Material: AL6061. Start: pre-sized 80 x 80 x 70 blank.",
        "General linear tolerance +/-0.127; angles +/-0.2 deg.",
        "Machine: Haas UMC-750; indexed 3+2 access to eight facets.",
        "Only T1 DIA12.7 flat endmill; flute 25.4, stickout 33.02.",
        "Upper exterior machining IS required. Retain square lower base.",
        "No bottom machining, threads, through holes or extra features.",
        "Blank is attached from below to the existing tall pedestal.",
        "Rigid mounting assumed. Tool/holder/fixture clearance must pass",
        "the actual simulator. Drawing is NOT a manufacturing approval.",
        "Edges deburred manually after machining; no modeled edge breaks.",
    ]
    text(c, 674, 306, "MATERIAL / MANUFACTURING BOUNDARY", 12, True)
    for x, lines in [(34, left), (674, right)]:
        for i, line in enumerate(lines):
            text(c, x, 285 - i * 18, line, 10)
    c.setFillColor(PALE)
    c.rect(34, 35, w - 68, 39, fill=1, stroke=0)
    text(c, 45, 50, "UMC-08  |  REV A  |  AL6061  |  ALL DIMENSIONS mm  |  DO NOT SCALE", 10, True)
    text(c, w - 205, 50, "PROJECT BENCHMARK / 1 OF 1", 9, True)
    c.showPage()
    c.save()


def main():
    validate()
    drawing()
    original = json.loads((ROOT / "config/umc-actuator-tall-job.json").read_text())
    job = copy.deepcopy(original)
    job["drawings"] = [{"path": str(PDF), "sha256": sha(PDF)}]
    job["setup"]["material_source"] = "UMC-08 Rev A project-authored benchmark"
    job["setup"]["stock"]["precondition"] = (
        "Pre-sized AL6061 80x80x70 blank attached from below to the existing tall pedestal. "
        "Machine upper octagonal exterior and drawing-defined blind features. Preserve full square "
        "base Z=-70..-54, bottom and base exterior. No bottom machining."
    )
    job["setup"]["simulation_assumptions"] = [
        "Only T1; 25.4mm flute, 33.02mm stickout. Max top depth18mm; side slots5mm. "
        "Maximum stock-to-diagonal-facet normal removal19.568542mm.",
        "Indexed 3+2 access: eight horizontal face normals at 45-degree azimuth "
        "increments plus top. "
        "Use collision-safe links and respect installed B/C limits.",
        "Upper exterior IS machined to drawing. Keep full 80x80x16mm square lower base "
        "attached to pedestal.",
        "Drawing geometry is analytically screened only; actual CAM and "
        "machine/holder/stock simulation are unverified.",
        "Rigid bolted pedestal assumed; no physical cutting-force certification.",
    ]
    job["tolerances"]["source"] = "UMC-08 Rev A"
    job["tolerances"]["angular_plus_minus_deg"] = 0.2
    job["sources"]["drawing_archive"] = (
        "Project-authored benchmark UMC-08 Rev A; analytical illustration, no customer provenance"
    )
    job["readiness_scope"] = (
        "Drawing and resource hashes pinned; no CAD, CAM or simulator run supplied."
    )
    canonical = json.dumps(GEOMETRY, sort_keys=True, separators=(",", ":")).encode()
    job["demo_part_spec"] = {
        "part_id": "umc-08",
        "part_name": "Octagonal instrument housing",
        "split": "training",
        "geometry": GEOMETRY,
        "geometry_sha256": hashlib.sha256(canonical).hexdigest(),
        "training_allowed": True,
    }
    for field in ["machine", "tools", "cost_assumptions", "objective", "checks"]:
        assert job[field] == original[field]
    assert job["setup"]["fixture"] == original["setup"]["fixture"]
    assert job["setup"]["machine_position"] == original["setup"]["machine_position"]
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(job, indent=2) + "\n")
    print(
        json.dumps(
            {
                "pdf": str(PDF),
                "sha256": sha(PDF),
                "config": str(CONFIG),
                "geometry_sha256": job["demo_part_spec"]["geometry_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
