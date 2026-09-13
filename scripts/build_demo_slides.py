"""Build the standalone SILTA CAD pitch and presenter guide."""

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    import markdown

    target = ROOT / "demo/slides.html"
    photo = base64.b64encode((ROOT / "demo/assets/team.jpeg").read_bytes()).decode()
    target.write_text(
        (ROOT / "scripts/pitch_template.html").read_text(encoding="utf-8").replace(
            "__TEAM_IMAGE__", "data:image/jpeg;base64," + photo
        ),
        encoding="utf-8",
    )
    notes = markdown.markdown(
        (ROOT / "docs/demo-3min.md").read_text(encoding="utf-8"),
        extensions=["markdown.extensions.tables"],
    )
    guide = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SILTA CAD · Pitch guide</title><style>
body{margin:48px auto;padding:0 28px;max-width:920px;background:#f3f2ee;
color:#191919;font:18px/1.65 Arial,sans-serif}h1,h2,h3{line-height:1.2;
font-weight:500;letter-spacing:-.025em}h2{margin-top:48px}a{color:inherit}
table{border-collapse:collapse;width:100%;font-size:15px}th,td{border-bottom:1px solid #ccc;
padding:12px;text-align:left;vertical-align:top}code{font-size:.85em}pre{overflow:auto}
</style><a href="slides.html">← SILTA CAD pitch</a><main>CONTENT</main></html>'''
    (ROOT / "demo/guide.html").write_text(
        guide.replace("CONTENT", notes), encoding="utf-8"
    )
    print(target)


if __name__ == "__main__":
    main()
