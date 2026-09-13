# Portable slide PDF

Regenerate the two-page 16:9 PDF from the retained slide PNGs with:

```sh
uv run --with reportlab python scripts/demo/export_slide_pdf.py
```

The exporter writes `output/pdf/silta-demo-slides.pdf` and its JSON source-hash receipt. It embeds the exact raster slides; it does not rerun experiments or update their historical claims. Packaging checks the PDF and both slide hashes before inclusion. ReportLab is a one-off export dependency, not required by the CNC runtime.
