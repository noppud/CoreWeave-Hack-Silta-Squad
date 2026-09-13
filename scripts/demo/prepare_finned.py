"""Prepare held-out UMC10 drawing and resource-pinned input; no CAD, CAM or runtime job."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from prepare_bracket import lines, sha
from prepare_showpiece import BLUE, INK, PALE, dimension, poly, text
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "output/pdf/demo-campaign/umc-10.pdf"
CONFIG = ROOT / "config/demo-campaign/umc-10-job.json"
DOC = ROOT / "docs/finned-part.md"
CHANNELS = [(-30, -14), (-8, 8), (14, 30)]
FINS = [(-36, -30), (-14, -8), (8, 14), (30, 36)]
GEOMETRY = {
    "units": "mm",
    "blank_min": [-40, -40, -70],
    "blank_max": [40, 40, 0],
    "base": {"x": [-40, 40], "y": [-40, 40], "z": [-70, -54]},
    "upper": {
        "shape": "rectangular prism before channel removal",
        "x": [-32, 32],
        "y": [-36, 36],
        "z": [-54, 0],
    },
    "top_channels": {
        "count": 3,
        "shape": "open-ended rectangular channels",
        "x": [-32, 32],
        "y_intervals": CHANNELS,
        "z": [-18, 0],
        "width_y": 16,
        "depth_z": 18,
        "open_ends": "Every channel is open through both X=-32 and X=32 ends",
        "remaining_fins": {"count": 4, "y_intervals": FINS, "thickness_y": 6, "height_z": 18},
    },
    "side_pockets": {
        "count": 2,
        "entry_faces_y": [-36, 36],
        "center_x": 0,
        "center_z": -37,
        "overall_width_x": 40,
        "overall_height_z": 20,
        "end_radius": 10,
        "normal_depth": 6,
        "floor_y": [-30, 30],
        "definition": "Horizontal capsule: R10 semicircle centers (X,Z)=(-10,-37),(10,-37), "
        "joined by straight top/bottom edges. Blind planar floor normal to Y; no island.",
    },
    "tolerance_mm": 0.127,
    "tolerance_deg": 0.2,
    "excluded": "No bottom/base exterior or mounting-feature machining; "
    "no holes, undercuts, threads, chamfers or added fillets.",
}


def validate():
    assert [b - a for a, b in CHANNELS] == [16] * 3
    assert [b - a for a, b in FINS] == [6] * 4
    assert 3 * 16 + 4 * 6 == 72
    intervals = sorted(CHANNELS + FINS)
    assert intervals[0][0] == -36 and intervals[-1][1] == 36
    assert all(a[1] == b[0] for a, b in zip(intervals, intervals[1:], strict=False))
    assert 16 > 12.7 and 20 > 12.7 and 10 > 12.7 / 2
    screen = {
        "channel_width_mm": 16,
        "fin_thickness_mm": 6,
        "channel_depth_mm": 18,
        "channel_to_pocket_vertical_web_mm": -18 - (-37 + 10),
        "pocket_to_flange_vertical_web_mm": (-37 - 10) - -54,
        "pocket_end_to_tower_side_mm": 32 - 20,
        "opposing_pocket_floor_web_mm": 30 - (-30),
        "base_thickness_mm": -54 - (-70),
        "side_pocket_depth_mm": 6,
        "exterior_normal_removal_x_mm": 40 - 32,
        "exterior_normal_removal_y_mm": 40 - 36,
    }
    assert screen["channel_to_pocket_vertical_web_mm"] == 9
    assert screen["pocket_to_flange_vertical_web_mm"] == 7
    assert screen["base_thickness_mm"] == 16
    assert max(18, 6, 8, 4) < 25.4
    return screen


def drawing():
    PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=landscape(A3), invariant=1)
    c.setTitle("UMC-10 Rev A | Finned instrument support | Project-authored benchmark")
    c.setAuthor("Silta project team")
    w, h = landscape(A3)
    c.setFillColor(INK)
    c.rect(0, h - 83, w, 83, fill=1, stroke=0)
    text(c, 32, h - 35, "FINNED INSTRUMENT SUPPORT", 26, True, colors.white)
    text(
        c,
        33,
        h - 61,
        "UMC-10 / REV A     AL6061     PROJECT-AUTHORED BENCHMARK INPUT",
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
    poly(c, [top(-32, -36), top(32, -36), top(32, 36), top(-32, 36)], colors.white)
    for a, b in CHANNELS:
        poly(c, [top(-32, a), top(32, a), top(32, b), top(-32, b)], PALE)
    dimension(c, *top(-40, -49), *top(40, -49), "80")
    dimension(c, *top(-32, 44), *top(32, 44), "64")
    dimension(c, *top(47, -36), *top(47, 36), "72")
    lines(
        c,
        40,
        414,
        [
            "3X open-ended channels: 16 wide x 18 deep.",
            "X=-32..32; every channel floor Z=-18.",
            "Y intervals: -30..-14, -8..8, 14..30.",
            "Each passes both X ends. No end walls.",
        ],
        10,
    )
    ox, oy = 560, 683

    def end(y, z):
        return ox + y * s, oy + z * s

    poly(c, [end(-40, -70), end(40, -70), end(40, -54), end(-40, -54)], PALE)
    contour = [(-36, -54), (36, -54), (36, 0)]
    for a, b in reversed(CHANNELS):
        contour.extend([(b, 0), (b, -18), (a, -18), (a, 0)])
    contour.append((-36, 0))
    poly(c, [end(y, z) for y, z in contour], colors.white)
    dimension(c, *end(-36, 7), *end(36, 7), "72")
    dimension(c, *end(-8, -9), *end(8, -9), "16")
    dimension(c, *end(43, 0), *end(43, -18), "18")
    dimension(c, *end(-44, 0), *end(-44, -54), "54")
    dimension(c, *end(43, -54), *end(43, -70), "16")
    dimension(c, *end(-40, -78), *end(40, -78), "80")
    lines(
        c,
        420,
        414,
        [
            "4X fins, each 6 thick, 18 high, 64 long.",
            "Fin Y: -36..-30, -14..-8, 8..14, 30..36.",
            "Overall height 70; upper prism 64 x 72 x 54.",
            "Flange top Z=-54; bottom Z=-70.",
        ],
        10,
    )
    ox, oy = 948, 683

    def side(x, z):
        return ox + x * s, oy + z * s

    poly(c, [side(-40, -70), side(40, -70), side(40, -54), side(-40, -54)], PALE)
    poly(c, [side(-32, -54), side(32, -54), side(32, 0), side(-32, 0)], colors.white)
    c.setStrokeColor(INK)
    c.setFillColor(PALE)
    c.roundRect(*side(-20, -47), 40 * s, 20 * s, 10 * s, fill=1, stroke=1)
    c.setDash(3, 3)
    c.line(*side(-32, -18), *side(32, -18))
    c.setDash()
    dimension(c, *side(-20, -57), *side(20, -57), "40")
    dimension(c, *side(26, -27), *side(26, -47), "20")
    text(c, 1033, 632, "Z=-18", 9, color=BLUE)
    text(c, 1033, 576, "Z=-37", 9, color=BLUE)
    text(c, 878, 573, "R10", 10, color=BLUE)
    lines(
        c,
        810,
        414,
        [
            "2X blind horizontal obround: 40 x 20, R10.",
            "Center X0,Z=-37; enter Y=-36 and Y=36.",
            "Depth 6 inward; floors Y=-30 and Y=30.",
            "Bounds X=-20..20; Z=-47..-27.",
        ],
        10,
    )
    c.setStrokeColor(BLUE)
    c.line(33, 326, w - 33, 326)
    text(c, 33, 302, "GEOMETRY / DATUMS", 12, True)
    lines(
        c,
        33,
        281,
        [
            "All dimensions in mm. General linear tolerance +/-0.127; angular +/-0.2 deg.",
            "G54 = original blank top center. X,Y along blank edges; Z upward. Keep "
            "this datum fixed.",
            "Blank: X,Y=-40..40; Z=-70..0. Preserve the full 80 x 80 x 16 bottom flange.",
            "Upper prism: X=-32..32; Y=-36..36; Z=-54..0. All three channels remove Z=-18..0.",
            "Channel floor/wall junctions are square; channels open through both X "
            "ends, no corner fillets.",
            "Side-pocket R10 semicircle centers: (X,Z)=(-10,-37),(10,-37). No central island.",
            "No unshown holes, undercuts, threads, chamfers, fillets or mounting features.",
        ],
        10,
        20,
    )
    text(c, 725, 302, "TOOL / ACCESS / ANALYTICAL SCREEN", 12, True)
    lines(
        c,
        725,
        281,
        [
            "Haas UMC-750 Reboot, indexed 3+2; same tall pedestal.",
            "T1 only: DIA 12.7 flat; flute 25.4; stickout 33.02.",
            "Top channels 18 deep; side pockets 6 deep.",
            "Upper exterior normal removal: X sides 8; Y sides 4.",
            "Channel/pocket web 9; pocket/flange web 7; fin thickness 6.",
            "Channel 16 > tool DIA 12.7; pocket R10 > tool R6.35.",
            "Fixture clearance, fin rigidity and CAM remain unverified.",
        ],
        10,
        20,
    )
    c.setFillColor(PALE)
    c.rect(33, 49, w - 66, 68, fill=1, stroke=0)
    text(c, 48, 94, "FRESH INPUT ONLY - NOT QUEUED OR RUN", 13, True)
    text(
        c,
        48,
        74,
        "Authored for a benchmark; no thermal or manufacturing qualification. Astra "
        "must generate CAD/CAM and verify it.",
        10,
    )
    text(c, w - 175, 22, "UMC-10 REV A  |  1 / 1", 9)
    c.save()


def resource_count(value):
    count = 0
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            assert sha(Path(value["path"])) == value["sha256"], value["path"]
            count += 1
        count += sum(resource_count(v) for v in value.values())
    elif isinstance(value, list):
        count += sum(resource_count(v) for v in value)
    return count


def main():
    screen = validate()
    drawing()
    original = json.loads((ROOT / "config/umc-actuator-tall-job.json").read_text())
    job = copy.deepcopy(original)
    job["drawings"] = [{"path": str(PDF), "sha256": sha(PDF)}]
    job["setup"]["material_source"] = "UMC-10 Rev A project-authored benchmark"
    job["setup"]["stock"]["precondition"] = (
        "Pre-sized AL6061 80 x 80 x 70 blank attached from below to existing tall pedestal. "
        "Machine centered 64 x 72 upper support, three open top channels and two blind side "
        "obrounds. Preserve full 80 x 80 x 16 base at Z=-70..-54; no bottom/base exterior cuts."
    )
    job["setup"]["simulation_assumptions"] = [
        "Only T1 DIA12.7, flute25.4mm, stickout33.02mm. Channel width16mm, depth18mm; "
        "four6mm fins. Side pocket normal depth6mm; upper exterior normal removal8mm X/4mm Y.",
        "Indexed 3+2 access to top and horizontal side normals. Upper height54mm exceeds "
        "flute length; do not assume a single full-depth top contour reaches the flange.",
        "Analytical nonintersection and cutter-size screen only. Actual fin rigidity, engagement, "
        "holder/machine/fixture clearances and stock conformity require verification.",
        "Rigid bolted pedestal assumption inherited; no thermal or physical cutting qualification.",
    ]
    job["tolerances"]["source"] = "UMC-10 Rev A"
    job["tolerances"]["angular_plus_minus_deg"] = 0.2
    job["sources"]["drawing_archive"] = (
        "Project-authored UMC-10 Rev A; no customer/internet-part provenance"
    )
    job["readiness_scope"] = (
        "Drawing and resource hashes pinned; no CAD/CAM or simulator run supplied."
    )
    canonical = json.dumps(GEOMETRY, sort_keys=True, separators=(",", ":")).encode()
    job["demo_part_spec"] = {
        "part_id": "umc-10",
        "part_name": "Finned instrument support",
        "split": "heldout",
        "geometry": GEOMETRY,
        "geometry_sha256": hashlib.sha256(canonical).hexdigest(),
        "training_allowed": False,
    }
    for field in ["machine", "tools", "cost_assumptions", "objective", "checks"]:
        assert job[field] == original[field]
    for field in ["fixture", "machine_position", "work_coordinate_system"]:
        assert job["setup"][field] == original["setup"][field]
    count = resource_count(job)
    CONFIG.write_text(json.dumps(job, indent=2) + "\n")
    DOC.write_text(
        "# UMC10: finned instrument support\n\n"
        "Project-authored benchmark drawing only. Held out as a fresh live-demo alternative; "
        "not queued or run. No CAD/CAM solution is included, and no internet part or thermal/"
        "manufacturing qualification is claimed.\n\n"
        "The 80 x 80 x 70 AL6061 blank retains its 16 mm bottom flange. A centered "
        "64 x 72 x 54 upper support has three 16 mm channels, open along the full X span "
        "and 18 mm deep. Four 6 mm fins remain. Two opposite Y-face obrounds are 40 x 20, "
        "R10, 6 mm deep and centered at X0, Z=-37.\n\n"
        "## Analytical screen\n\n"
        + "\n".join(f"- {k}: {v} mm" for k, v in screen.items())
        + "\n\nThe seven alternating channel/fin intervals exactly fill the 72 mm width. "
        "Channel width 16 exceeds T1 diameter 12.7, pocket radius 10 exceeds tool radius 6.35, "
        "and all normal removal depths are below the 25.4 mm flute length. Channels and side "
        "pockets do not intersect. No inaccessible undercut or tiny internal planar "
        "corner is required. "
        "The 54 mm upper height still needs indexed access; fin stiffness, holder clearance and "
        "actual machining performance are not established by this drawing.\n\n"
        "## Frozen resources\n\n"
        f"- PDF SHA256: `{sha(PDF)}`\n- Config SHA256: `{sha(CONFIG)}`\n"
        f"- Geometry specification SHA256: `{job['demo_part_spec']['geometry_sha256']}`\n"
        f"- {count} drawing/machine/tool/fixture/check resource references verified "
        "against their SHA256.\n\n"
        "Machine, tool library, fixture, placement, objective, costs and baseline checks remain "
        "identical to `config/umc-actuator-tall-job.json`. Training is disabled in the input spec "
        "to reserve freshness; this is not an assertion that every caller enforces the flag.\n\n"
        "Rebuild this input only: `uv run --with reportlab python scripts/demo/prepare_finned.py`. "
        "Outputs: `output/pdf/demo-campaign/umc-10.pdf` and "
        "`config/demo-campaign/umc-10-job.json`. "
        "Existing parts, campaign queue, film and Fusion are untouched.\n"
    )
    print(
        json.dumps(
            {
                "pdf": str(PDF),
                "config": str(CONFIG),
                "pdf_sha256": sha(PDF),
                "config_sha256": sha(CONFIG),
                "verified_resource_count": count,
                "status": "input_only_heldout_unrun",
            }
        )
    )


if __name__ == "__main__":
    main()
