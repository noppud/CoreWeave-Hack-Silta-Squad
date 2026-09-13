"""Create UMC09 drawing and frozen job input only; never generate CAD/CAM or run Fusion."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from prepare_showpiece import BLUE, INK, PALE, dimension, poly, text
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "output/pdf/demo-campaign/umc-09.pdf"
CONFIG = ROOT / "config/demo-campaign/umc-09-job.json"
DOC = ROOT / "docs/bracket-part.md"
GEOMETRY = {
    "units": "mm",
    "blank_min": [-40, -40, -70],
    "blank_max": [40, 40, 0],
    "base": {"x": [-40, 40], "y": [-40, 40], "z": [-70, -54]},
    "upper": {"shape": "square prism", "x": [-32, 32], "y": [-32, 32], "z": [-54, 0]},
    "top_channel": {
        "shape": "open-ended rectangular channel",
        "x": [-32, 32],
        "y": [-14, 14],
        "z": [-20, 0],
        "open_ends": "Both X ends; no end walls or added fillets",
        "ear_width_y": 18,
    },
    "side_pockets": {
        "count": 2,
        "entry_faces_y": [-32, 32],
        "center_x": 0,
        "center_z": -38,
        "overall_width_x": 40,
        "overall_height_z": 20,
        "end_radius": 10,
        "normal_depth": 6,
        "floor_y": [-26, 26],
        "definition": "Horizontal capsule: two R10 semicircles centered X=-10 and X=10, "
        "Z=-38, joined by straight top/bottom edges. Blind planar floor normal to Y.",
    },
    "tolerance_mm": 0.127,
    "tolerance_deg": 0.2,
    "excluded": "No optional ear holes, threads, chamfers or added fillets. "
    "No bottom, base exterior or attachment machining.",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate():
    checks = {
        "base_thickness_mm": -54 - -70,
        "ear_width_mm": 32 - 14,
        "channel_to_pocket_vertical_web_mm": -20 - (-38 + 10),
        "pocket_to_flange_vertical_web_mm": (-38 - 10) - -54,
        "pocket_end_to_tower_side_mm": 32 - 20,
        "opposing_pocket_floor_web_mm": 26 - -26,
        "top_depth_mm": 20,
        "side_pocket_depth_mm": 6,
        "exterior_normal_removal_mm": 40 - 32,
    }
    assert checks["base_thickness_mm"] == 16 and checks["ear_width_mm"] == 18
    assert min(checks[k] for k in checks if "web" in k) >= 6
    assert 28 > 12.7 and 20 > 12.7 and 10 > 12.7 / 2
    assert (
        max(
            checks["top_depth_mm"],
            checks["side_pocket_depth_mm"],
            checks["exterior_normal_removal_mm"],
        )
        < 25.4
    )
    return checks


def lines(c, x, y, values, size=10, step=18):
    for i, value in enumerate(values):
        text(c, x, y - i * step, value, size)


def drawing():
    PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=landscape(A3), invariant=1)
    c.setTitle("UMC-09 Rev A | Forked actuator bracket | Project-authored benchmark")
    c.setAuthor("Silta project team")
    w, h = landscape(A3)
    c.setFillColor(INK)
    c.rect(0, h - 83, w, 83, fill=1, stroke=0)
    text(c, 32, h - 35, "FORKED ACTUATOR BRACKET", 26, True, colors.white)
    text(
        c,
        33,
        h - 61,
        "UMC-09 / REV A     AL6061     PROJECT-AUTHORED INPUT - NO CAD/CAM SOLUTION",
        11,
        color=colors.white,
    )
    for x, label in [
        (33, "01  TOP / LOOKING -Z"),
        (416, "02  END / LOOKING -X"),
        (804, "03  SIDE / LOOKING -Y"),
    ]:
        text(c, x, 726, label, 12, True)
    s, ox, oy = 2.8, 183, 574

    def top(x, y):
        return ox + x * s, oy + y * s

    poly(c, [top(-40, -40), top(40, -40), top(40, 40), top(-40, 40)], PALE)
    poly(c, [top(-32, -32), top(32, -32), top(32, 32), top(-32, 32)], colors.white)
    poly(c, [top(-32, -14), top(32, -14), top(32, 14), top(-32, 14)], PALE)
    dimension(c, *top(-40, -49), *top(40, -49), "80")
    dimension(c, *top(-32, 44), *top(32, 44), "64")
    dimension(c, *top(47, -14), *top(47, 14), "28")
    text(c, 50, 414, "Channel runs THROUGH both X ends.", 10, True)
    lines(
        c,
        50,
        395,
        [
            "X=-32..32; Y=-14..14; floor Z=-20.",
            "Two ears: Y=-32..-14 and Y=14..32.",
            "Each ear is 18 wide; ends stay open.",
        ],
    )
    # End projection: U channel is visible directly.
    ox, oy = 560, 683

    def end(y, z):
        return ox + y * s, oy + z * s

    poly(c, [end(-40, -70), end(40, -70), end(40, -54), end(-40, -54)], PALE)
    poly(
        c,
        [
            end(-32, -54),
            end(32, -54),
            end(32, 0),
            end(14, 0),
            end(14, -20),
            end(-14, -20),
            end(-14, 0),
            end(-32, 0),
        ],
        colors.white,
    )
    dimension(c, *end(-32, 7), *end(32, 7), "64")
    dimension(c, *end(-14, -9), *end(14, -9), "28")
    dimension(c, *end(43, 0), *end(43, -20), "20")
    dimension(c, *end(-44, 0), *end(-44, -54), "54")
    dimension(c, *end(43, -54), *end(43, -70), "16")
    dimension(c, *end(-40, -78), *end(40, -78), "80")
    lines(
        c,
        425,
        414,
        [
            "Overall height 70; tower height 54.",
            "Tower centered: 64 x 64 on 80 x 80 base.",
            "Top Z0; flange top Z=-54; bottom Z=-70.",
            "No optional holes in the 18 mm ears.",
        ],
    )
    # Side projection: both symmetric pockets are completely specified by this view.
    ox, oy = 948, 683

    def side(x, z):
        return ox + x * s, oy + z * s

    poly(c, [side(-40, -70), side(40, -70), side(40, -54), side(-40, -54)], PALE)
    poly(c, [side(-32, -54), side(32, -54), side(32, 0), side(-32, 0)], colors.white)
    c.setStrokeColor(INK)
    c.setFillColor(PALE)
    c.roundRect(*side(-20, -48), 40 * s, 20 * s, 10 * s, fill=1, stroke=1)
    c.setDash(3, 3)
    c.line(*side(-32, -20), *side(32, -20))
    c.setDash()
    dimension(c, *side(-20, -57), *side(20, -57), "40")
    dimension(c, *side(26, -28), *side(26, -48), "20")
    text(c, 1033, 626, "Z=-20", 9, color=BLUE)
    text(c, 1033, 573, "Z=-38", 9, color=BLUE)
    text(c, 878, 570, "R10", 10, color=BLUE)
    lines(
        c,
        810,
        414,
        [
            "2X horizontal obround, 40 x 20, R10.",
            "Centered X0, Z=-38 on Y=-32 and Y=32.",
            "Depth 6 inward; floors at Y=-26 and Y=26.",
            "Extents X=-20..20; Z=-48..-28.",
        ],
    )
    c.setStrokeColor(BLUE)
    c.line(33, 326, w - 33, 326)
    text(c, 33, 302, "GEOMETRY AND DATUMS", 12, True)
    lines(
        c,
        33,
        281,
        [
            "All dimensions in millimeters. General linear tolerance +/-0.127; angular +/-0.2 deg.",
            "G54 = center of original blank top. X,Y along blank edges; Z upward. Do "
            "not move this datum.",
            "Preserve 80 x 80 x 16 base: X,Y=-40..40; Z=-70..-54. Upper tower: X,Y=-32..32.",
            "Remove the top channel to planar Z=-20. Channel boundaries are sharp, "
            "open at both X ends.",
            "Side-pocket semicircle centers: (X,Z)=(-10,-38) and (10,-38). No island; "
            "flat pocket floors.",
            "No unshown holes, chamfers, added fillets or bottom features. Optional "
            "ear holes are omitted.",
        ],
        10,
        20,
    )
    text(c, 725, 302, "MACHINE / TOOL / ANALYTICAL SCREEN", 12, True)
    lines(
        c,
        725,
        281,
        [
            "Haas UMC-750 Reboot; indexed 3+2; existing tall pedestal.",
            "T1 only: DIA 12.7 flat end mill; flute 25.4; stickout 33.02.",
            "Blank 80 x 80 x 70 AL6061, attached from below. No bottom cuts.",
            "Top depth 20; side depth 6; exterior normal removal 8.",
            "Channel-to-pocket web 8; pocket-to-flange web 6.",
            "R10 > tool radius 6.35; channel 28 > tool diameter 12.7.",
            "These checks do not establish CAM/holder/machine clearance.",
        ],
        10,
        20,
    )
    c.setFillColor(PALE)
    c.rect(33, 49, w - 66, 68, fill=1, stroke=0)
    text(c, 48, 94, "INPUT ONLY - UNRUN", 13, True)
    text(
        c,
        48,
        74,
        "Dimensions define the target. Astra must generate CAD and CAM; actual Fusion "
        "verification is still required.",
        10,
    )
    text(c, w - 175, 22, "UMC-09 REV A  |  1 / 1", 9)
    c.save()


def main():
    screen = validate()
    drawing()
    original = json.loads((ROOT / "config/umc-actuator-tall-job.json").read_text())
    job = copy.deepcopy(original)
    job["drawings"] = [{"path": str(PDF), "sha256": sha(PDF)}]
    job["setup"]["material_source"] = "UMC-09 Rev A project-authored benchmark"
    job["setup"]["stock"]["precondition"] = (
        "Pre-sized AL6061 80x80x70 blank attached from below to existing tall pedestal. "
        "Machine centered64x64 upper tower, open top channel and two blind side obrounds. "
        "Preserve full80x80x16 square base Z=-70..-54; no bottom/base exterior machining."
    )
    job["setup"]["simulation_assumptions"] = [
        "Only T1 DIA12.7, flute25.4mm, stickout33.02mm. Top channel depth20mm; "
        "side pockets normal depth6mm; upper exterior normal stock removal8mm.",
        "Indexed 3+2 access to top and horizontal side normals. Full upper height54mm "
        "exceeds flute length: tool reach and holder clearance require actual CAM "
        "planning/verification.",
        "Maintain6mm web above flange and8mm web between channel floor and side pockets. "
        "No optional ear holes or added geometry.",
        "Analytical feature screening only; no generated CAD/CAM or completed simulation yet.",
        "Rigid bolted pedestal assumption inherited; physical cutting loads not certified.",
    ]
    job["tolerances"]["source"] = "UMC-09 Rev A"
    job["tolerances"]["angular_plus_minus_deg"] = 0.2
    job["sources"]["drawing_archive"] = "Project-authored UMC-09 Rev A; no customer provenance"
    job["readiness_scope"] = "Drawing/resource hashes pinned; no CAD/CAM/simulator run supplied."
    canonical = json.dumps(GEOMETRY, sort_keys=True, separators=(",", ":")).encode()
    job["demo_part_spec"] = {
        "part_id": "umc-09",
        "part_name": "Forked actuator bracket",
        "split": "training",
        "geometry": GEOMETRY,
        "geometry_sha256": hashlib.sha256(canonical).hexdigest(),
        "training_allowed": True,
    }
    for field in ["machine", "tools", "cost_assumptions", "objective", "checks"]:
        assert job[field] == original[field]
    assert job["setup"]["fixture"] == original["setup"]["fixture"]
    assert job["setup"]["machine_position"] == original["setup"]["machine_position"]
    CONFIG.write_text(json.dumps(job, indent=2) + "\n")
    DOC.write_text(
        "# UMC09: forked actuator bracket\n\n"
        "Project-authored input only, not queued or run. No CAD/CAM solution is supplied.\n\n"
        "The 80x80x70 AL6061 blank retains its bottom80x80x16 flange. A centered64x64 tower "
        "has a28mm-wide channel through both X ends,20mm deep, leaving two18mm ears. "
        "Two40x20 R10 blind obrounds enter opposite Y faces6mm, centered at X0,Z=-38.\n\n"
        "Optional ear holes are omitted: DIA16 in an18mm ear would leave only1mm "
        "lateral wall; they add no necessary visual distinction or learning target.\n\n"
        "## Analytical screen\n\n"
        + "\n".join(f"- {k}: {v} mm" for k, v in screen.items())
        + "\n\nT1 diameter12.7mm fits channel28 and pocketheight20; R10 exceeds toolradius6.35. "
        "Top depth20, side depth6, and exterior normal removal8 are below25.4mm flute length. "
        "Tower height54 exceeds flute length, so it cannot be assumed machinable by one full-depth "
        "top contour. Actual indexed tool access, holder links and finished-stock "
        "conformity remain unverified.\n\n"
        "## Frozen input\n\n"
        f"- PDF: `output/pdf/demo-campaign/umc-09.pdf` SHA256 `{sha(PDF)}`\n"
        f"- Config: `config/demo-campaign/umc-09-job.json` SHA256 `{sha(CONFIG)}`\n"
        f"- Geometry specification SHA256: `{job['demo_part_spec']['geometry_sha256']}`\n\n"
        "Machine, tools, fixture, placement, objective, baseline checks and cost assumptions "
        "are identical to `config/umc-actuator-tall-job.json`. Rebuild with "
        "`uv run --with reportlab python scripts/demo/prepare_bracket.py`. "
        "No edits to UMC02-08 or campaign queue.\n"
    )
    print(
        json.dumps(
            {
                "pdf": str(PDF),
                "pdf_sha256": sha(PDF),
                "config": str(CONFIG),
                "config_sha256": sha(CONFIG),
                "status": "input_only_unrun",
            }
        )
    )


if __name__ == "__main__":
    main()
