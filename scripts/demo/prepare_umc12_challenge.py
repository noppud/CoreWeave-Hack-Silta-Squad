"""Author only the UMC12 drawing/config; no CAD, CAM or Fusion actions."""

import copy
import hashlib
import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = {
    "units": "mm",
    "blank_min": [-40, -40, -70],
    "blank_max": [40, 40, 0],
    "base": {"x": [-40, 40], "y": [-40, 40], "z": [-70, -54], "preserve": True},
    "upper": {"x": [-36, 36], "y": [-34, 34], "z": [-54, 0]},
    "top_channel": {
        "x": [-14, 14],
        "y": [-34, 34],
        "z": [-24, 0],
        "definition": "Open at both Y ends; rectangular section, flat floor; no end walls",
    },
    "pin_bores": {
        "axis": "X",
        "center_y": 0,
        "center_z": -14,
        "diameter": 16,
        "intervals_x": [[-36, -14], [14, 36]],
        "through_each_ear": True,
    },
    "left_counterbore": {
        "entry_x": -36,
        "floor_x": -33,
        "center_y": 0,
        "center_z": -14,
        "diameter": 22,
    },
    "side_lightening_pockets": {
        "entry_x": [-36, 36],
        "floor_x": [-28, 28],
        "center_y": [-22, 22],
        "center_z": -30,
        "width_y": 16,
        "height_z": 28,
        "radius": 8,
        "definition": (
            "Four vertical capsules: semicircle centers Z=-36 and -24, same Y; "
            "flat blind floors; depth8"
        ),
    },
    "end_ports": {
        "entry_y": [-34, 34],
        "floor_y": [-18, 18],
        "center_x": 0,
        "center_z": -40,
        "diameter": 16,
        "definition": "Two blind cylindrical ports, planar floors; depth16",
    },
    "tolerance_mm": 0.127,
    "tolerance_deg": 0.2,
    "excluded": (
        "No threads, added fillets/chamfers, undercuts or base machining. "
        "Sharp convex edges; capsule concave R8 only."
    ),
}


def apply_part_setup(config):
    config["setup"]["material_source"] = "UMC-12 Rev A project-authored benchmark"
    config["setup"]["stock"]["precondition"] = (
        "Pre-sized AL6061 80 x 80 x 70 blank attached from below to the existing tall "
        "pedestal. Target features are defined by the pinned UMC12 drawing. Preserve "
        "the full 80 x 80 x 16 base at Z=-70..-54; no bottom/base exterior cuts."
    )
    config["setup"]["simulation_assumptions"] = [
        "Only T1 DIA12.7, flute25.4mm, stickout33.02mm. Feature geometry and depths "
        "are defined by the pinned UMC12 drawing.",
        "Indexed 3+2 access to top and horizontal side normals. Upper height54mm "
        "exceeds flute length; do not assume a single full-depth top contour reaches the flange.",
        "Nominal cutter reach is not proof of holder clearance, acceptable cutting loads "
        "or a feasible strategy. Actual machine/fixture clearances and stock conformity "
        "require verification.",
        "Rigid bolted pedestal assumption inherited; no physical cutting qualification.",
    ]


def main():
    pdf = ROOT / "output/pdf/demo-campaign/umc-12.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pdf), pagesize=landscape(A4))
    w, h = landscape(A4)

    def text(x, y, value, size=10):
        c.setFont("Helvetica", size)
        c.drawString(x, y, value)

    def header(page):
        c.setFillColor(HexColor("#18313d"))
        c.rect(0, h - 72, w, 72, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        text(32, h - 31, "UMC12 / RIBBED CLEVIS", 23)
        text(
            32, h - 53, "Aerospace-style geometry challenge | AL6061 | INDEXED 3+2 | UNVERIFIED", 10
        )
        c.setFillColor(HexColor("#18313d"))
        text(w - 100, 20, f"{page} / 2", 9)

    header(1)
    scale = 2.65

    def view(ox, oy, title, kind):
        text(ox - 106, oy + (145 if kind == "top" else 30), title, 12)
        c.saveState()
        c.translate(ox, oy)
        c.scale(scale, scale)
        c.setLineWidth(0.35)
        if kind == "front":
            c.rect(-40, -70, 80, 16)
            c.rect(-36, -54, 72, 54)
            c.setFillColor(HexColor("#ffffff"))
            c.rect(-14, -24, 28, 24, fill=1, stroke=1)
            c.circle(0, -40, 8)
            c.setDash(1, 1)
            c.line(-36, -14, 36, -14)
            c.setDash()
        elif kind == "side":
            c.rect(-40, -70, 80, 16)
            c.rect(-34, -54, 68, 54)
            for yy in (-22, 22):
                c.roundRect(yy - 8, -44, 16, 28, 8)
            c.circle(0, -14, 8)
            c.circle(0, -14, 11)
        else:
            c.rect(-40, -40, 80, 80)
            c.rect(-36, -34, 72, 68)
            c.line(-14, -34, -14, 34)
            c.line(14, -34, 14, 34)
        c.restoreState()

    view(145, 440, "FRONT / LOOK FROM -Y", "front")
    view(420, 440, "LEFT / LOOK FROM -X", "side")
    view(685, 325, "TOP / LOOK FROM +Z", "top")
    notes = [
        "Views are orthographic diagrams. Exact coordinate dimensions on sheet 2 govern.",
        "G54: stock top center (0,0,0). X/Y horizontal; +Z upward. Stock 80 x 80 x 70.",
        "Preserve complete base X,Y +/-40; Z -70 to -54. Upper envelope 72 x 68 x 54.",
        "Clevis ears: X [-36,-14] and [14,36], joined below channel floor Z=-24.",
        (
            "Four side capsules leave outer webs 4 mm, central rib 28 mm "
            "and pocket floors 14 mm thick."
        ),
        "Asymmetry: left pin bore has DIA22 x3 counterbore; right bore is DIA16 plain.",
        (
            "No physical machining approval. All geometry, toolpath and collision "
            "checks remain required."
        ),
    ]
    for i, line in enumerate(notes):
        text(32, 151 - i * 17, line, 10)
    c.showPage()
    header(2)
    rows = [
        ("01 / Envelope", "Upper: X[-36,36], Y[-34,34], Z[-54,0]. Base: X/Y[-40,40], Z[-70,-54]."),
        (
            "02 / Open clevis channel",
            "Remove X[-14,14], Y[-34,34], Z[-24,0]. Width28, depth24; open at both Y ends.",
        ),
        (
            "03 / Coaxial pin bores",
            "DIA16, axis X, center(Y,Z)=(0,-14). Through each22-thick ear into channel.",
        ),
        (
            "04 / Left counterbore only",
            "DIA22 on -X face, same center as pin. Depth3: entryX=-36, floorX=-33.",
        ),
        (
            "05 / Four side pockets",
            "On each X=+/-36 face: capsule centers(Y,Z)=(-22,-30),(22,-30). Depth8.",
        ),
        (
            "Pocket definition",
            "Overall16(Y) x28(Z), R8 ends. Arc centersZ=-36,-24. FloorsX=-28,+28.",
        ),
        (
            "06 / Two end ports",
            "DIA16 blind from Y=+/-34. Center(X,Z)=(0,-40). Depth16; floorsY=-18,+18.",
        ),
        (
            "Intersection rules",
            "Pin/counterbore share axes; pin exits into top channel. No other voids intersect.",
        ),
        (
            "Remaining material",
            "Side pocket to Y edge4; pocket floor to inner ear14; ports to base top6.",
        ),
        (
            "Critical webs",
            "Pin bottomZ=-22 is2 above channel floor; left counterbore topZ=-3 leaves3.",
        ),
        (
            "Tool envelope",
            "Only existing T1: DIA12.7 flat, flute25.4, stickout33.02, assembly gauge96.52mm.",
        ),
        (
            "Reach analysis",
            "Largest intended inward cut24; ear bore22; pockets8; ports16; counterbore3.",
        ),
        (
            "Entry orientations",
            "Top +Z; side features +/-X; ports +/-Y. No tilted planes or hidden undercuts.",
        ),
        (
            "Tolerance / finish",
            "All linear +/-0.127mm; angular +/-0.2deg. No unspecified fillets or chamfers.",
        ),
    ]
    for i, (label, desc) in enumerate(rows):
        y = h - 101 - i * 29
        c.setFillColor(HexColor("#eaf0f2"))
        c.rect(28, y - 10, w - 56, 27, fill=1, stroke=0)
        c.setFillColor(HexColor("#18313d"))
        text(36, y, label, 10)
        text(186, y, desc, 9)
    text(
        32,
        42,
        (
            "Tool reach is a nominal dimension check, not proof of holder clearance, "
            "acceptable cutting loads or a feasible strategy."
        ),
        9,
    )
    c.save()
    config = copy.deepcopy(json.loads((ROOT / "config/demo-campaign/umc-10-job.json").read_text()))
    config["drawings"] = [
        {"path": str(pdf), "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}
    ]
    config["demo_part_spec"] = {
        "part_id": "umc-12",
        "part_name": "Ribbed asymmetric clevis",
        "split": "challenge",
        "training_allowed": True,
        "geometry": GEOMETRY,
        "geometry_sha256": hashlib.sha256(
            json.dumps(GEOMETRY, sort_keys=True).encode()
        ).hexdigest(),
    }
    config["readiness_scope"] = (
        "Challenge drawing/resource pins only; CAD, CAM and Fusion verification not attempted."
    )
    apply_part_setup(config)
    (ROOT / "config/demo-campaign/umc-12-job.json").write_text(json.dumps(config, indent=2) + "\n")
    print(pdf)


if __name__ == "__main__":
    main()
