"""Refresh the presentation's offline policy evaluation evidence. No model calls."""

import asyncio
import hashlib
import html
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from silta.domain import Disposition  # noqa: E402
from silta.evaluation import load_fixtures, run_batch  # noqa: E402
from silta.policy import POLICY_V0, POLICY_V1  # noqa: E402


async def build():
    batches = []
    for split in ("development", "holdout"):
        fixtures = load_fixtures(split)
        for policy in (POLICY_V0, POLICY_V1):
            outcomes = await run_batch(fixtures, policy, max_attempts=1)
            batches.append(
                {
                    "split": split,
                    "display_split": "Development" if split == "development" else "Regression",
                    "policy": policy.version,
                    "cases": len(outcomes),
                    "matched": sum(o.matched_expectation for o in outcomes),
                    "simulations": sum(o.simulations_run for o in outcomes),
                    "false_accepts": sum(
                        o.disposition == Disposition.PASSED
                        and Disposition.PASSED
                        not in (f.expectation.accepted_dispositions or (f.expectation.disposition,))
                        for f, o in zip(fixtures, outcomes, strict=True)
                    ),
                    "false_rejects": sum(
                        o.disposition != Disposition.PASSED
                        and f.expectation.disposition == Disposition.PASSED
                        for f, o in zip(fixtures, outcomes, strict=True)
                    ),
                    "outcomes": [asdict(o) for o in outcomes],
                }
            )
    paths = (
        sorted((ROOT / "fixtures/development").glob("*.json"))
        + sorted((ROOT / "fixtures/holdout").glob("*.json"))
        + sorted((ROOT / "silta").glob("*.py"))
    )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": (
            "Offline replay: 8 development and 4 regression fixtures (former holdout). "
            "An earlier fix used a holdout failure; this is not a blind test. "
            "Fixed seed plans; no model calls."
        ),
        "sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "batches": batches,
    }
    dest = ROOT / "demo/evals.json"
    dest.write_text(json.dumps(report, indent=2, default=str) + "\n")
    rows = "".join(
        f"<tr><td>{b['display_split']}</td><td>{b['policy']}</td>"
        f"<td>{b['matched']} / {b['cases']}</td><td>{b['simulations']}</td>"
        f"<td>{b['false_accepts']}</td><td>{b['false_rejects']}</td></tr>"
        for b in batches
    )
    cases = "".join(
        f"<h2>{b['display_split']} · {b['policy']}</h2><table>"
        "<tr><th>Fixture</th><th>Observed outcome</th><th>Matched oracle</th></tr>"
        + "".join(
            f"<tr><td>{html.escape(o['fixture_id'])}</td>"
            f"<td>{html.escape(o['disposition'])}</td>"
            "<td>"
            + ("Yes" if o["matched_expectation"] else html.escape(o["mismatch_reason"] or "No"))
            + "</td></tr>"
            for o in b["outcomes"]
        )
        + "</table>"
        for b in batches
    )
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Silta CNC · Evaluation evidence</title><style>
body{font:18px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;
background:#f6f9fb;color:#163449}a{color:#075e9b}table{border-collapse:collapse;
display:block;overflow:auto}td,th{padding:12px;border:1px solid #ccd9e2;text-align:left}
nav{display:flex;gap:24px;flex-wrap:wrap}code{background:#e5edf3}
</style><nav><a href="slides.html#3">Back to eval slide</a>
<a href="http://localhost:2733/">Interactive eval notebook</a>
<a href="evals.json">Raw results and source hashes</a></nav>
<h1>Policy evaluation evidence</h1><p>SCOPE</p><p>Measured: TIMESTAMP</p>
<table><tr><th>Split</th><th>Policy</th><th>Expected outcomes matched</th>
<th>Simulations</th><th>False accepts</th><th>False rejects</th></tr>ROWS</table>
<p>Policy v1 checks the swept tool envelope against fixtures before simulation.
Expected rejections count as correct results. This evaluates the validator on
12 existing synthetic fixtures, not general model planning quality or real-machine safety.</p>
<p>Reproduce: <code>.venv/bin/python scripts/build_demo_evals.py</code></p>CASES</html>"""
    for key, value in {
        "SCOPE": report["scope"],
        "TIMESTAMP": report["generated_at"],
        "ROWS": rows,
        "CASES": cases,
    }.items():
        page = page.replace(key, value)
    (ROOT / "demo/evals.html").write_text(page)
    for batch in batches:
        print({k: v for k, v in batch.items() if k != "outcomes"})
    print(dest)


if __name__ == "__main__":
    asyncio.run(build())
