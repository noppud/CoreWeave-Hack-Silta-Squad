"""Author UMC11 ambitious drawing input only; no CAD/CAM solution or Fusion calls."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from prepare_bracket import lines
from prepare_finned import resource_count
from prepare_showpiece import BLUE, INK, PALE, dimension, poly, sha, text
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "output/pdf/demo-campaign/umc-11.pdf"
CONFIG = ROOT / "config/demo-campaign/umc-11-job.json"
DOC = ROOT / "docs/cage-part.md"
ANGLES = list(range(0, 360, 45))
GEOMETRY = {
    "units": "mm",
    "blank_min": [-40, -40, -70],
    "blank_max": [40, 40, 0],
    "base": {"x": [-40, 40], "y": [-40, 40], "z": [-70, -54]},
    "collar": {"shape": "regular octagonal prism", "across_flats": 78, "z": [-54, -48]},
    "upper": {"shape": "regular octagonal prism", "across_flats": 74, "z": [-48, 0]},
    "octagon_definition": "For each listed theta: X*cos(theta)+Y*sin(theta)<=across_flats/2",
    "face_normal_angles_deg": ANGLES,
    "top_cavity": {
        "center_xy": [0, 0],
        "counterbore_diameter": 58,
        "counterbore_depth": 4,
        "inner_diameter": 54,
        "total_depth": 24,
        "floor_z": -24,
        "definition": "Open from top; concentric circular flat-bottom cavities; no island.",
    },
    "upper_windows": {
        "count": 8,
        "face_normal_angles_deg": ANGLES,
        "shape": "circular through-wall window",
        "diameter": 16,
        "center_u": 0,
        "center_z": -13,
        "removal_n_interval": [23, 37],
        "normal_depth": 14,
        "definition": "At each face, remove circular profile U^2+(Z+13)^2<=8^2, "
        "extruded along N=23..37. It intentionally breaks into the top cavity. "
        "N=X*cos(theta)+Y*sin(theta), U=-X*sin(theta)+Y*cos(theta). "
        "Only the near wall is removed; do not cut the opposite wall.",
    },
    "lower_reliefs": {
        "count": 8,
        "face_normal_angles_deg": ANGLES,
        "shape": "blind vertical capsule",
        "width_u": 16,
        "height_z": 18,
        "end_radius": 8,
        "center_u": 0,
        "center_z": -36,
        "normal_depth": 6,
        "floor_n": 31,
        "removal_n_interval": [31, 37],
        "definition": "R8 semicircle centers (U,Z)=(0,-35),(0,-37), joined by vertical "
        "sides U=+-8. Z limits -45..-27. Flat blind floor N=31. "
        "These are weight-relief pockets, not openings into another hidden chamber.",
    },
    "tolerance_mm": 0.127,
    "tolerance_deg": 0.2,
    "excluded": (
        "Preserve base sides/bottom; no mounting holes, threads, chamfers, extra fillets, "
        "undercuts, hidden lower chamber or unshown features."
    ),
}


def validate():
    original = json.loads((ROOT / "config/umc-actuator-tall-job.json").read_text())
    tool = next(t for t in original["tools"]["entries"] if t["number"] == 1)
    assert tool["unit"] == "inches"
    flute = tool["geometry"]["LCF"] * 25.4
    stickout = tool["stickout_below_holder_mm"]
    diameter = tool["geometry"]["DC"] * 25.4
    assert math.isclose(flute, 25.4) and math.isclose(stickout, 33.02)
    assert math.isclose(diameter, 12.7)
    inner_radius, window_half = 27, 8
    inner_wall_n = math.sqrt(inner_radius**2 - window_half**2)
    # At the widest cross-section, an adjacent face's window cannot meet this one
    # in the retained wall: the next window's U is still beyond its half-width.
    adjacent_u = (inner_wall_n - window_half) / math.sqrt(2)
    arc_rib = inner_radius * (math.pi / 4 - 2 * math.asin(window_half / inner_radius))
    screen = {
        "tool_diameter_mm": diameter,
        "flute_length_mm": flute,
        "stickout_below_holder_mm": stickout,
        "top_cavity_depth_mm": 24,
        "flute_margin_at_cavity_floor_mm": flute - 24,
        "holder_axial_standoff_at_cavity_floor_mm": stickout - 24,
        "upper_through_window_normal_depth_mm": 14,
        "breakthrough_margin_at_max_window_u_mm": inner_wall_n - 23,
        "nominal_upper_wall_thickness_mm": 37 - inner_radius,
        "counterbore_rim_thickness_mm": 37 - 29,
        "facet_width_mm": 74 * math.tan(math.pi / 8),
        "window_edge_to_facet_corner_mm": 37 * math.tan(math.pi / 8) - 8,
        "inner_cavity_circumferential_rib_arc_mm": arc_rib,
        "adjacent_window_nonintersection_u_margin_mm": adjacent_u - window_half,
        "top_to_upper_window_mm": 5,
        "upper_window_to_cavity_floor_mm": 3,
        "window_levels_vertical_web_mm": 6,
        "cavity_floor_to_lower_relief_top_mm": 3,
        "lower_relief_to_collar_vertical_web_mm": 3,
        "lower_relief_normal_depth_mm": 6,
        "collar_height_mm": 6,
        "collar_radial_step_mm": 2,
        "max_diagonal_exterior_normal_removal_mm": 40 * math.sqrt(2) - 37,
        "base_thickness_mm": 16,
    }
    assert max(24, 14, 6, screen["max_diagonal_exterior_normal_removal_mm"]) < flute
    assert 16 > diameter and 8 > diameter / 2
    assert inner_wall_n > 23 and adjacent_u > window_half and arc_rib > 4
    assert 37 * math.tan(math.pi / 8) > 8
    assert 39 <= 40 and 37 <= 40
    assert -21 > -24 > -27 > -45 > -48 > -54 > -70
    return screen


def octagon(apothem):
    t = apothem * math.tan(math.pi / 8)
    return [
        (apothem, t),
        (t, apothem),
        (-t, apothem),
        (-apothem, t),
        (-apothem, -t),
        (-t, -apothem),
        (t, -apothem),
        (apothem, -t),
    ]


def header(c, subtitle, page):
    w, h = landscape(A3)
    c.setFillColor(INK)
    c.rect(0, h - 82, w, 82, fill=1, stroke=0)
    text(c, 32, h - 34, "WINDOWED OCTAGONAL CAGE", 25, True, colors.white)
    text(
        c,
        33,
        h - 60,
        "UMC-11 / REV A    AL6061    AMBITIOUS PROJECT-AUTHORED CHALLENGE",
        11,
        color=colors.white,
    )
    text(c, 33, 727, subtitle, 12, True)
    text(c, 33, 23, "INPUT DRAWING ONLY - NOT YET MACHINED OR VERIFIED", 9, True)
    text(c, w - 145, 23, f"UMC-11 REV A | {page} / 2", 9)


def drawing():
    PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=landscape(A3), invariant=1)
    c.setTitle("UMC-11 Rev A | Windowed octagonal cage | Ambitious challenge input")
    c.setAuthor("Silta project team")
    header(c, "01  ORTHOGRAPHIC DEFINITION - ALL DIMENSIONS IN MM", 1)
    text(c, 45, 692, "TOP / LOOKING -Z", 11, True)
    text(c, 426, 692, "TYPICAL FACET / LOOKING ALONG -N", 11, True)
    text(c, 838, 692, "SECTION A-A / THROUGH X AXIS", 11, True)
    s = 3
    ox, oy = 192, 535

    def top(x, y):
        return ox + x * s, oy + y * s

    poly(c, [top(-40, -40), top(40, -40), top(40, 40), top(-40, 40)], PALE)
    poly(c, [top(x, y) for x, y in octagon(39)], colors.HexColor("#D0E2E8"))
    poly(c, [top(x, y) for x, y in octagon(37)], colors.white)
    c.setStrokeColor(INK)
    c.circle(ox, oy, 29 * s)
    c.circle(ox, oy, 27 * s)
    c.setDash(3, 3)
    c.setStrokeColor(BLUE)
    c.line(*top(-47, 0), *top(47, 0))
    c.setDash()
    text(c, 43, 531, "A", 9, True)
    text(c, 332, 531, "A", 9, True)
    dimension(c, *top(-40, -47), *top(40, -47), "80")
    dimension(c, *top(-37, 45), *top(37, 45), "74 A/F")
    lines(
        c,
        45,
        359,
        [
            "Main body 74 A/F, Z=-48..0.",
            "Collar 78 A/F, Z=-54..-48.",
            "Square base 80 x 80, Z=-70..-54.",
            "Top: DIA58 x 4; DIA54 x 24 total depth.",
        ],
        10,
    )
    ox, oy = 590, 647

    def face(u, z):
        return ox + u * s, oy + z * s

    poly(c, [face(-40, -70), face(40, -70), face(40, -54), face(-40, -54)], PALE)
    poly(
        c,
        [face(-39, -54), face(39, -54), face(39, -48), face(-39, -48)],
        colors.HexColor("#D0E2E8"),
    )
    poly(c, [face(-37, -48), face(37, -48), face(37, 0), face(-37, 0)], colors.white)
    # Only central facet boundaries solid; other silhouette facets are projected edges.
    half = 37 * math.tan(math.pi / 8)
    c.setStrokeColor(INK)
    c.line(*face(-half, -48), *face(-half, 0))
    c.line(*face(half, -48), *face(half, 0))
    c.setFillColor(PALE)
    c.circle(*face(0, -13), 8 * s, fill=1, stroke=1)
    c.roundRect(*face(-8, -45), 16 * s, 18 * s, 8 * s, fill=1, stroke=1)
    c.setStrokeColor(BLUE)
    c.setDash(2, 3)
    c.line(*face(-23, -13), *face(23, -13))
    c.line(*face(-23, -36), *face(23, -36))
    c.setDash()
    dimension(c, *face(-48, 0), *face(-48, -70), "70")
    dimension(c, *face(44, 0), *face(44, -13), "13")
    dimension(c, *face(44, -13), *face(44, -36), "23")
    dimension(c, *face(-8, 5), *face(8, 5), "16")
    lines(
        c,
        429,
        359,
        [
            "8X upper: DIA16 through near wall only.",
            "Centers U=0, Z=-13; normal removal 14.",
            "8X lower: 16 wide x 18 high, R8.",
            "Centers U=0, Z=-36; blind depth 6.",
        ],
        10,
    )
    ox, oy = 993, 647

    def sec(x, z):
        return ox + x * 2.7, oy + z * 2.7

    outline = [
        (-40, -70),
        (40, -70),
        (40, -54),
        (39, -54),
        (39, -48),
        (37, -48),
        (37, 0),
        (29, 0),
        (29, -4),
        (27, -4),
        (27, -24),
        (-27, -24),
        (-27, -4),
        (-29, -4),
        (-29, 0),
        (-37, 0),
        (-37, -48),
        (-39, -48),
        (-39, -54),
        (-40, -54),
    ]
    poly(c, [sec(x, z) for x, z in outline], PALE)
    # Section intersects theta=0/180 window centerlines; omit only defined removals.
    for a, b in [(27, 37), (-37, -27)]:
        poly(c, [sec(a, -21), sec(b, -21), sec(b, -5), sec(a, -5)], colors.white)
    for a, b in [(31, 37), (-37, -31)]:
        poly(c, [sec(a, -45), sec(b, -45), sec(b, -27), sec(a, -27)], colors.white)
    dimension(c, *sec(-29, 7), *sec(29, 7), "DIA58")
    dimension(c, *sec(46, 0), *sec(46, -24), "24")
    dimension(c, *sec(31, -51), *sec(37, -51), "6")
    dimension(c, *sec(45, -54), *sec(45, -70), "16")
    lines(
        c,
        843,
        359,
        [
            "Section cuts two opposing upper windows.",
            "Top cavity floor Z=-24; no hidden chamber.",
            "Upper window Z=-21..-5, opens into cavity.",
            "Lower relief Z=-45..-27; floor N=31.",
        ],
        9.5,
    )
    c.setFillColor(PALE)
    c.rect(33, 151, 1124, 128, fill=1, stroke=0)
    text(c, 49, 254, "DATUMS / INTERPRETATION", 12, True)
    lines(
        c,
        49,
        233,
        [
            "Origin: stock top center (X,Y,Z)=(0,0,0). Stock bottom Z=-70.",
            (
                "All octagonal facet outward normals "
                "theta=0,45,90,135,180,225,270,315 degrees from +X toward "
                "+Y."
            ),
            (
                "N=X cos(theta)+Y sin(theta); U=-X sin(theta)+Y cos(theta). The "
                "typical facet drawing applies to all eight "
                "faces."
            ),
            (
                "Upper windows intentionally meet the top cavity. Lower relief "
                "pockets are blind; their lower core remains "
                "solid."
            ),
            (
                "General tolerance +/-0.127 mm; angular +/-0.2 deg. Sharp convex "
                "edges; no extra chamfers, fillets or "
                "features."
            ),
        ],
        10,
        step=19,
    )
    lines(
        c,
        45,
        116,
        [
            (
                "FIXTURE: preserve full 80 x 80 x 16 bottom flange. No base "
                "side/bottom machining or mounting-hole "
                "creation."
            ),
            (
                "Machine: existing Haas UMC-750, indexed 3+2; T1 only, DIA12.7 "
                "flat, flute 25.4, stickout "
                "33.02."
            ),
            "See sheet 2 for authoritative feature coordinates and analytical access limits.",
        ],
        10,
        step=18,
    )
    c.showPage()
    header(c, "02  FEATURE COORDINATES / ACCESS SCREEN", 2)
    y = 684
    for title, body in [
        (
            "SOLID ENVELOPE",
            [
                (
                    "Keep base: X,Y=-40..40; Z=-70..-54. Add regular octagonal collar "
                    "78 A/F at Z=-54..-48."
                ),
                (
                    "Above collar: regular octagon 74 A/F at Z=-48..0. Octagon = "
                    "intersection of eight N<=A/F/2 "
                    "halfspaces."
                ),
                (
                    "Collar has 2 mm radial step beyond main faces. No decorative "
                    "radius or corner blend is implied."
                ),
            ],
        ),
        (
            "OPEN TOP CAVITY",
            [
                (
                    "Concentric with origin: DIA58 circular counterbore from Z=0 to "
                    "-4; DIA54 cavity from Z=0 to "
                    "-24."
                ),
                (
                    "Both floors planar normal to Z. Resulting DIA54 floor is Z=-24; "
                    "the annular shoulder is Z=-4."
                ),
                "No inner island, taper, undercut, thread or lower internal cavity.",
            ],
        ),
        (
            "8X UPPER THROUGH-WALL WINDOWS",
            [
                "One on every theta facet: circle U^2+(Z+13)^2<=64. Center U=0, Z=-13; DIA16.",
                (
                    "Remove along N=23..37 (14mm normal depth from outer face). This "
                    "deliberately intersects DIA54 "
                    "cavity."
                ),
                (
                    "At U=8, cavity near wall N=sqrt(27^2-8^2)=25.7876; N=23 endpoint "
                    "gives 2.7876 mm breakthrough "
                    "margin."
                ),
                (
                    "Do not extend the window cut through the opposite cage wall. "
                    "Circular window is visible at "
                    "N37."
                ),
            ],
        ),
        (
            "8X LOWER BLIND RELIEF WINDOWS",
            [
                (
                    "One on every theta facet: vertical capsule 16 wide, 18 high, R8; "
                    "center U=0, Z=-36."
                ),
                (
                    "Semicircle centers U=0,Z=-35 and U=0,Z=-37. Straight sides "
                    "U=+/-8; total Z=-45..-27."
                ),
                (
                    "Remove along N=31..37 only (6mm normal depth); retain flat floor "
                    "N=31. No internal island."
                ),
                (
                    "These do not connect into the cavity or into adjacent pockets; "
                    "they are not a second hollow "
                    "chamber."
                ),
            ],
        ),
        (
            "RIBS / TOOL ACCESS - ANALYTICAL SCREEN, NOT VERIFICATION",
            [
                (
                    "DIA16 apertures exceed T1 DIA12.7; all internal planar profile "
                    "radii R8 exceed tool R6.35."
                ),
                (
                    "Top depth 24 < flute 25.4 and stickout 33.02; cavity bottom "
                    "leaves 9.02 mm axial holder standoff from "
                    "top."
                ),
                (
                    "Facet width 30.652 mm; 16 mm window leaves 7.326 mm on each "
                    "facet edge. Internal rib arc approximately 4.962 "
                    "mm."
                ),
                (
                    "Upper window bottom -21 is 3 mm above cavity floor. Lower relief "
                    "top -27 is 3 mm below that "
                    "floor."
                ),
                (
                    "Vertical gap between window levels 6 mm; lower relief ends 3 mm "
                    "above collar. Counterbore rim 8 "
                    "mm."
                ),
                (
                    "Worst diagonal outside-stock removal 19.569 mm < flute 25.4. "
                    "Upper body height 48 requires indexed "
                    "access."
                ),
                (
                    "No blind depth beyond tool reach is specified. Workholding, "
                    "engagement, holder/fixture "
                    "clearances,"
                ),
                (
                    "stock conformity and actual manufacturability still require the "
                    "agent and full Fusion verification."
                ),
            ],
        ),
    ]:
        text(c, 43, y, title, 12, True)
        y -= 23
        lines(c, 43, y, body, 10, step=18)
        y -= len(body) * 18 + 25
    c.save()


def main():
    screen = validate()
    drawing()
    original = json.loads((ROOT / "config/umc-actuator-tall-job.json").read_text())
    job = copy.deepcopy(original)
    job["drawings"] = [{"path": str(PDF), "sha256": sha(PDF)}]
    job["setup"]["material_source"] = "UMC-11 Rev A project-authored ambitious challenge"
    job["setup"]["stock"]["precondition"] = (
        "Pre-sized AL6061 80x80x70 blank on existing tall pedestal. "
        "Preserve80x80x16baseZ-70..-54. "
        "Produce78AF6mmcollar,74AF48mmoctagon,steppedopentopcavity,eightth"
        "roughupperwindows andeightblindlowerreliefs "
        "asdrawing."
    )
    job["setup"]["simulation_assumptions"] = [
        (
            "Actual enabledT1 DIA12.7,flute25.4,stickout33.02. "
            "Topcavity24deep;upperwindow14normal;lowerrelief6normal;maxdiagona"
            "lexterior19.569normal."
        ),
        (
            "Indexed3+2topandeightsidenormals. Upperbody48mmheight cannot be "
            "assumed reachable by one full-depth top "
            "contour."
        ),
        (
            "Topcavityandupperwindows intentionally connect. "
            "Lowerreliefsremainblind. No hidden deepchamber or "
            "undercut."
        ),
        (
            "Analyticalaccessscreen only; "
            "wallstiffness/holder/fixture/stockcompliance require "
            "actualverification. No physicalqualification."
        ),
    ]
    job["tolerances"]["source"] = "UMC-11 Rev A"
    job["tolerances"]["angular_plus_minus_deg"] = 0.2
    job["sources"]["drawing_archive"] = (
        "Project-authored UMC-11 Rev A; ambitiouschallenge, no customer or internetpart provenance"
    )
    job["readiness_scope"] = (
        "Drawing/resourcehashes only; noCAD/CAMsolution or simulation supplied."
    )
    canonical = json.dumps(GEOMETRY, sort_keys=True, separators=(",", ":")).encode()
    job["demo_part_spec"] = {
        "part_id": "umc-11",
        "part_name": "Windowed octagonal cage",
        "split": "challenge",
        "geometry": GEOMETRY,
        "geometry_sha256": hashlib.sha256(canonical).hexdigest(),
        "training_allowed": True,
        "status": "unverified_ambitious_challenge",
    }
    for field in ["machine", "tools", "cost_assumptions", "objective", "checks"]:
        assert job[field] == original[field]
    for field in ["fixture", "machine_position", "work_coordinate_system"]:
        assert job["setup"][field] == original["setup"][field]
    count = resource_count(job)
    CONFIG.write_text(json.dumps(job, indent=2) + "\n")
    DOC.write_text(
        (
            "# UMC11: windowed octagonal cage\n\nAmbitious project-authored "
            "challenge input, not a verified part. No CAD/CAM solution is "
            "supplied and no Fusion run was performed during preparation.\n\nA "
            "stepped octagonal body has an open stepped circular cavity, "
            "eight through-wall upper windows and eight blind lower relief "
            "windows. The lower core remains solid: this avoids inventing an "
            "inaccessible deep interior under the existing short cutter. The "
            "eight facet access directions and two feature levels challenge "
            "toolpath planning while preserving connecting ribs and a rigid "
            "bottom flange.\n\n## Analytical dimensions and access "
            "screen\n\n"
        )
        + "\n".join(f"- {k}: {v:.6f}" for k, v in screen.items())
        + (
            "\n\nThe normal cuts intentionally meet only where the upper "
            "windows open into the top cavity. Adjacent upper windows retain "
            "positive circumferential ribs; lower reliefs remain separate. "
            "Each indexed pocket profile is reachable from its outward face "
            "with R8>=tool R6.35. Top cut 24 leaves 1.4 mm flute margin and "
            "9.02 mm nominal holder standoff. These checks do not establish "
            "holder collision safety, cutting load or rib rigidity. Full "
            "target/CAM/stock verification remains necessary.\n\n## Frozen "
            "input\n\n"
        )
        + f"- PDF SHA256: `{sha(PDF)}`\n- Config SHA256: `{sha(CONFIG)}`\n"
        + f"- Geometry SHA256: `{job['demo_part_spec']['geometry_sha256']}`\n"
        + f"- {count} drawing/machine/tool/fixture/check resource references checked.\n\n"
        + (
            "Drawing: `output/pdf/demo-campaign/umc-11.pdf`. Config: "
            "`config/demo-campaign/umc-11-job.json`. Rebuild only this input: "
            "`uv run --with reportlab python scripts/demo/prepare_cage.py`. "
            "Machine/tool/fixture/setup placement/objective/check resources "
            "match the existing tall-pedestal job. Existing drawings, "
            "campaign queue, film and Fusion are "
            "untouched.\n\nThis is a shared-learning challenge: split=challenge and "
            "training_allowed=true. No run has been performed during preparation.\n"
        )
    )
    print(
        json.dumps(
            {
                "pdf": str(PDF),
                "config": str(CONFIG),
                "pdf_sha256": sha(PDF),
                "config_sha256": sha(CONFIG),
                "verified_resource_count": count,
                "screen": screen,
                "status": "unverified_challenge_input_only",
            }
        )
    )


if __name__ == "__main__":
    main()
