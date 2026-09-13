"""Export the two retained presentation slides as a portable 16:9 PDF."""

import hashlib
import json
from pathlib import Path

from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]


def main():
    sources = [ROOT / f"output/presentation/slide-{i}.png" for i in (1, 2)]
    output = ROOT / "output/pdf/silta-demo-slides.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output), pagesize=(960, 540))
    pdf.setTitle("Silta - The part stays fixed. The process improves.")
    for source in sources:
        pdf.drawImage(str(source), 0, 0, width=960, height=540)
        pdf.showPage()
    pdf.save()
    receipt = {
        "pdf": str(output.relative_to(ROOT)),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "pages": 2,
        "page_points": [960, 540],
        "sources": [
            {"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sources
        ],
        "scope": "Exact raster slides in PDF; no new performance claims or experiment runs",
    }
    output.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
