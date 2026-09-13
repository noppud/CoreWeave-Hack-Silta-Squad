"""Read standalone diagnostic post evidence; deliberately not connected to checks.

Run operation_frames.cps as a separate diagnostic NC program only. Its callbacks
use the default engine mapping, while Section.getWCSPosition samples expose the
independent local-to-WCS affine frame. Live calibration remains required before
consumer checks may rely on either representation. This module never posts NC.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


def read_diagnostic(path: str | Path) -> dict:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows or rows[0].get("type") != "header" or rows[-1].get("type") != "footer":
        raise ValueError("Incomplete diagnostic: header/footer required")
    header, footer = rows[0], rows[-1]
    if (
        header.get("schema_version") != 1
        or header.get("units") != "mm"
        or footer.get("completed") is not True
    ):
        raise ValueError("Unsupported or incomplete diagnostic")
    sections = set()
    motions = []

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nonfinite diagnostic coordinate")
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        if isinstance(value, list):
            for item in value:
                finite(item)

    for row in rows:
        finite(row)
        kind = row.get("type")
        if kind == "section":
            if row["id"] in sections:
                raise ValueError("Duplicate section")
            sections.add(row["id"])
        elif kind in {"linear", "rapid", "circular"}:
            if row.get("section") not in sections:
                raise ValueError("Motion without preceding section")
            if kind == "circular" and not all(
                k in row
                for k in (
                    "center",
                    "normal",
                    "sweep_radians",
                    "full_circle",
                    "helical",
                    "clockwise",
                )
            ):
                raise ValueError("Incomplete analytic arc")
            motions.append(row)
        elif kind not in {"header", "footer"}:
            raise ValueError("Unsupported motion/record")
    if len(motions) != footer.get("motion_count"):
        raise ValueError("Motion count mismatch")
    return {
        "rows": rows,
        "motion_count": len(motions),
        "section_count": len(sections),
        "usable_for_checks": False,
        "reason": (
            "Requires live coordinate calibration; no cutter swept-volume coverage implemented"
        ),
    }
