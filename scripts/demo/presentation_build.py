"""Build a two-slide local Fusion pitch from retained evidence; no runtime jobs."""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/presentation"
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path("/System/Library/Fonts/Supplemental")
INK = "#172021"
MUTED = "#576462"
RED = "#c43d34"
BG = "#f6f3eb"


def font(size, bold=False, serif=False):
    name = "Georgia.ttf" if serif else "Arial Bold.ttf" if bold else "Arial.ttf"
    return ImageFont.truetype(str(FONT / name), size)


def slide(number, eyebrow):
    image = Image.new("RGB", (1920, 1080), BG)
    draw = ImageDraw.Draw(image)
    draw.text((94, 70), "SILTA", font=font(34, True), fill=INK)
    draw.text((282, 78), eyebrow, font=font(24), fill=MUTED)
    draw.line((94, 130, 1826, 130), fill="#d4d7ce", width=2)
    draw.text((1770, 1007), f"0{number}", font=font(24), fill=MUTED)
    return image, draw


def text(draw, xy, content, size=30, fill=INK, bold=False, serif=False, spacing=12):
    draw.multiline_text(xy, content, font=font(size, bold, serif), fill=fill, spacing=spacing)


def arrow(draw, start, end, fill=INK):
    draw.line((*start, *end), fill=fill, width=4)
    x, y = end
    draw.polygon([(x, y), (x - 14, y - 9), (x - 14, y + 9)], fill=fill)


inputs = {
    "eval": ROOT / "output/evaluation/learning-evaluation.json",
    "transfer": ROOT / "runs/learning-part-c2/manifest.json",
    "optimization": ROOT / "runs/learning-soft-jaw-a5/manifest.json",
}
data = {key: json.loads(path.read_text()) for key, path in inputs.items()}
assert data["eval"]["status"] == "published"
variants = {item["name"]: item for item in data["eval"]["variants"]}
transfer = next(
    e["result"]
    for e in data["transfer"]["events"]
    if e["event"] == "checks_completed" and e["attempt"] == 2
)
assert transfer["passed"] is False
passes = [
    e["verification"]
    for e in data["optimization"]["events"]
    if e["event"] == "verification_completed"
    and e["verification"]["status"] == "passed"
    and e["verification"]["completed"]
]
before = passes[0]["machining_seconds"]
after = data["optimization"]["best_verification"]["machining_seconds"]
saving = (before - after) / before * 100

im, d = slide(1, "A MACHINING AGENT THAT LEARNS FROM CONSEQUENCES")
text(d, (94, 185), "The part stays fixed.\nThe machining learns.", 81, serif=True, spacing=8)
text(d, (100, 412), "Drawing + machine + tools → fixed CAD", 30, fill=MUTED)
xs = [100, 538, 976, 1414]
for x, title, subtitle in zip(
    xs,
    ["ASTRA", "CODE CHECKS", "FUSION", "JUDGE"],
    ["Create / repair CAM", "Catch known mistakes", "Machine + final stock", "Improve or finish"],
    strict=True,
):
    d.rounded_rectangle((x, 520, x + 400, 676), radius=18, fill="white", outline="#d4d7ce", width=2)
    text(d, (x + 27, 550), title, 29, bold=True)
    text(d, (x + 27, 600), subtitle, 26, fill=MUTED)
for x in xs[:-1]:
    arrow(d, (x + 403, 598), (x + 430, 598))
d.line((1180, 684, 1180, 755, 730, 755, 730, 684), fill=RED, width=4)
d.polygon([(730, 684), (721, 698), (739, 698)], fill=RED)
text(d, (716, 780), "A new failure becomes a new check.", 32, RED, True)
d.line((1616, 684, 1616, 897, 300, 897, 300, 684), fill=INK, width=3)
d.polygon([(300, 684), (291, 698), (309, 698)], fill=INK)
text(d, (625, 917), "A verified result becomes better planning guidance.", 29)
text(
    d,
    (100, 1010),
    "LIVE PROOF: Astra SDK · real Fusion simulation · inspectable source and traces",
    23,
    MUTED,
)
im.save(OUT / "slide-1.png")

im, d = slide(2, "ONE FAILURE. A LESSON THE NEXT PART CAN USE.")
text(d, (94, 185), "The learning is visible.", 81, serif=True)
for x in (667, 1253):
    d.line((x, 390, x, 825), fill="#d4d7ce", width=2)
text(d, (100, 337), "01 / REAL FAILURE", 24, RED, True)
text(d, (100, 401), "Part B", 65, serif=True)
text(d, (100, 510), "Simulation catches a\nfinished-side intrusion.", 34)
text(d, (100, 634), "The agent writes an\napplicable code check.", 31, MUTED)
text(d, (710, 337), "02 / NEXT-PART TRANSFER", 24, RED, True)
text(d, (710, 401), f"{transfer['runtime_s'] * 1000:.0f} ms", 81, serif=True)
text(d, (710, 510), "Part C is rejected\nbefore simulation.", 34)
text(d, (710, 634), "The actual learned check\ncatches the repeated mistake.", 29, MUTED)
text(d, (1298, 337), "03 / WEAVE REPLAY", 24, RED, True)
text(
    d,
    (1298, 401),
    f"{variants['baseline']['caught_invalid']}/2 to {variants['learned']['caught_invalid']}/2",
    71,
    serif=True,
)
text(d, (1298, 510), "Known failures caught.", 34)
text(d, (1298, 582), "0 / 4 valid plans rejected\nby either version.", 30, MUTED)
text(d, (1298, 693), "Retained-case replay;\nnot a held-out test.", 26, MUTED)
d.rounded_rectangle((96, 851, 1824, 976), radius=14, fill=INK)
text(d, (128, 878), f"Same-part CAM optimization: {before:.1f}s → {after:.1f}s", 34, "white", True)
text(d, (1250, 878), f"{saving:.1f}% less time", 38, "#b9dfce", True)
text(
    d,
    (128, 929),
    "Verified candidate estimates. Historical learning was saved directly; "
    "replay evaluation came later.",
    22,
    "#dbe5df",
)
text(
    d,
    (100, 1010),
    "NEXT: raw generated code → learned checks / guidance → Fusion → judge",
    23,
    MUTED,
)
im.save(OUT / "slide-2.png")

links = "".join(
    f'<a href="{v["weave_url"]}">{name} evaluation</a> ' for name, v in variants.items()
)
(OUT / "slides.html").write_text(
    """<!doctype html><html><meta charset="utf-8"><title>Silta · Fusion loop</title>
<style>
html,body{margin:0;background:#111;height:100%;overflow:hidden}
img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
img[hidden]{display:none}
nav{position:fixed;bottom:8px;right:14px;opacity:0;transition:opacity .2s;font:14px Arial}
nav:hover{opacity:1}
a,button{color:white;background:#222;border:0;padding:8px;cursor:pointer}
</style>
<img id="s1" src="slide-1.png" alt="Fixed CAD and the learning loop">
<img id="s2" src="slide-2.png" alt="Real cross-part learning and published Weave replay" hidden>
<nav><button onclick="show(1)">1</button><button onclick="show(2)">2</button>"""
    + links
    + """</nav>
<script>
let n=1;
function show(v){n=v;document.getElementById('s1').hidden=n!==1;
document.getElementById('s2').hidden=n!==2}
addEventListener('keydown',e=>{
if(['ArrowRight',' ','PageDown'].includes(e.key))show(2);
if(['ArrowLeft','PageUp','Home'].includes(e.key))show(1)});
</script></html>"""
)
(OUT / "evidence.json").write_text(
    json.dumps(
        {
            "sources": {
                key: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for key, path in inputs.items()
            },
            "cross_part_rejection_ms": transfer["runtime_s"] * 1000,
            "same_part_before_seconds": before,
            "same_part_after_seconds": after,
            "same_part_improvement_percent": saving,
            "weave_variants": variants,
            "branch_inspiration": [
                "origin/hack-slide-deck:docs/pitch-3min.md",
                "origin/konsta-demo-hackathon:docs/demo-3min.md",
            ],
            "aria": "No completed ARIA analysis used in this deck",
        },
        indent=2,
    )
    + "\n"
)
print(OUT / "slides.html")
