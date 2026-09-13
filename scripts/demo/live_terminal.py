"""Read-only live terminal view of actual Fusion campaign artifacts.

No source execution, model calls, Fusion operations, or desktop changes.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import math
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def clean(value) -> str:
    return "".join(
        character for character in str(value).replace("\t", "    ") if character.isprintable()
    )


def clip(value, width):
    value = clean(value)
    return value if len(value) <= width else value[: max(0, width - 3)] + "..."


def read_json(path):
    try:
        path = Path(path)
        if path.stat().st_size > 32_000_000:
            raise ValueError("JSON record exceeds32MB")
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("Expected JSON object")
        return value, None
    except (OSError, ValueError) as error:
        return {}, clean(error)


def source_text(path, expected_sha=None):
    try:
        path = Path(path)
        if path.stat().st_size > 1_000_000:
            return None, "Source exceeds1MB preview limit"
        data = path.read_bytes()
        if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
            return None, "Recorded source hash mismatch"
        return data.decode("utf-8"), None
    except (OSError, UnicodeError) as error:
        return None, clean(error)


def short(ref):
    return ref[:12] if isinstance(ref, str) and ref else "unavailable"


def finite_metric(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def recorded_pass(verdict):
    return bool(
        isinstance(verdict, dict)
        and verdict.get("status") == "passed"
        and verdict.get("completed") is True
        and verdict.get("evidence")
        and not verdict.get("issues")
        and verdict.get("coverage")
    )


def choose_job(campaign, campaign_path, job=None):
    parts = campaign.get("parts", [])
    if job:
        candidate = Path(job).expanduser()
        if candidate.is_file():
            return candidate.resolve(), None
        for part in parts:
            if job in {part.get("part_id"), part.get("job_id"), part.get("label")}:
                return Path(part["manifest_path"]), part
        path = campaign_path.parent / job / "manifest.json"
        return path, None
    current = campaign.get("current_part_id")
    part = next((item for item in parts if item.get("part_id") == current), None)
    part = part or (parts[-1] if parts else None)
    return (Path(part["manifest_path"]), part) if part else (None, None)


def snippet(before, after, height=6, code=False):
    if after is None:
        return ["Source not yet available"]
    if before is not None and before != after:
        lines = list(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile="initial",
                tofile="current",
                lineterm="",
                n=1,
            )
        )
        return [line for line in lines if not line.startswith(("---", "+++"))][:height]
    # Actual source, with source line numbers; never generated summaries.
    rows = [(i + 1, line) for i, line in enumerate(after.splitlines()) if line.strip()]
    if code:
        start = next((i for i, (_, line) in enumerate(rows) if line.startswith("def check(")), None)
        if start is None:
            start = next((i for i, (_, line) in enumerate(rows) if line.startswith("def ")), 0)
        rows = rows[start:]
    return [f"{number:>3} {line}" for number, line in rows[:height]] or ["(empty source)"]


def machining_excerpt(source, height=6):
    """Select retained code only; parse literal wrappers without executing them."""
    label = "CAM SOURCE EXCERPT / file lines"
    if source is None:
        return ["Source not yet available"], label
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "compile"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "<silta-machining-plan>"
            ):
                source = node.args[0].value
                label = f"CAM EXCERPT / embedded plan lines (file L{node.lineno})"
                break
    except (SyntaxError, ValueError):
        pass
    rows = [(i + 1, line) for i, line in enumerate(source.splitlines()) if line.strip()]

    def score(line):
        if line.lstrip().startswith(("#", "import ", "from ", "def ")):
            return 0
        if re.search(r"\.expression\s*=\s*['\"][-+.\d]", line):
            return 10
        if re.search(r"\.operations\.(?:createInput|add)\(", line):
            return 8
        if re.search(
            r"rampClearanceHeight|maximumStepdown|maximumStepover|feedHeight_offset|"
            r"tool_feedCutting|tool_spindleSpeed|rampAngle|keepToolDown|safeDistance",
            line,
        ):
            return 6
        return 0

    scores = [score(line) for _, line in rows]
    best = max(range(len(rows)), key=lambda i: scores[i], default=0)
    start = max(0, best - 1) if scores and scores[best] else 0
    return (
        [f"{number:>3} {line}" for number, line in rows[start : start + height]]
        or ["(empty source)"]
    ), label


def event_text(event):
    label = event.get("event", "event").replace("_", " ")
    attempt = f" #{event['attempt']}" if "attempt" in event else ""
    detail = event.get("reason") or event.get("candidate_id") or ""
    if event.get("event") == "checks_completed":
        result = event.get("result", {})
        detail = "passed" if result.get("passed") is True else "failed"
        detail += ": " + "; ".join(result.get("issues", [])) if result.get("issues") else ""
    elif event.get("event") == "verification_completed":
        result = event.get("verification", {})
        detail = f"{result.get('status', 'unknown')}, completed={result.get('completed') is True}"
        if result.get("issues"):
            detail += ": " + "; ".join(result["issues"])
    elif event.get("event") == "supervisor_decision":
        result = event.get("decision", {})
        detail = f"{result.get('action', '?')}: {result.get('instructions', '')}"
    elif event.get("event") == "learning_change_saved":
        detail = f"{event.get('change_kind')}; eval={event.get('evaluation_performed')}"
    elif event.get("event") == "cam_generation_failed":
        detail = json.dumps(event.get("feedback", {}), ensure_ascii=True)
    timestamp = str(event.get("at", "")).split("T")[-1][:8]
    return f"{timestamp} {label}{attempt}" + (f" | {detail}" if detail else "")


def load_snapshot(campaign_path: Path, job=None):
    campaign, error = read_json(campaign_path)
    if error:
        return {
            "error": f"Campaign unavailable: {error}",
            "campaign": {},
            "manifest": {},
            "events": [],
        }
    manifest_path, part = choose_job(campaign, campaign_path, job)
    manifest, error = read_json(manifest_path) if manifest_path else ({}, None)
    events = manifest.get("events", [])
    all_sources = dict(manifest.get("learning_sources", {}))
    # Initial sources can live in an earlier recovery or earlier campaign job.
    for row in campaign.get("parts", []):
        for path in [row.get("manifest_path"), *row.get("recovery_sources", [])]:
            if path and Path(path) != manifest_path:
                historic, _ = read_json(path)
                for ref, source in historic.get("learning_sources", {}).items():
                    all_sources.setdefault(ref, source)
    initial = (
        manifest.get("versions", {})
        if job
        else campaign.get("initial_versions") or manifest.get("versions", {})
    )
    current = manifest.get("current_versions") or manifest.get("versions", {})
    learning = Path(campaign.get("learning_directory") or ROOT / "learning")
    if manifest_path:
        presentation_path = manifest_path.parent.parent / (
            manifest_path.parent.name + "-presentation.json"
        )
        presentation, _ = read_json(presentation_path)
        shadow = presentation.get("shadow_learning_directory")
        if isinstance(shadow, str) and shadow:
            learning = Path(shadow)
    sources = {}
    for kind, filename in [("checks", "checks.py"), ("main_prompt", "cad_cam.md")]:
        pair = []
        warnings = []
        for ref in [initial.get(kind), current.get(kind)]:
            source = all_sources.get(ref, {})
            if source:
                text, warning = source_text(source["path"], source.get("sha256"))
            else:
                text, warning = None, "Versioned source not retained in available manifests"
            pair.append(text)
            if warning:
                warnings.append(warning)
        live, live_error = source_text(learning / filename)
        live_ref = (
            hashlib.sha256((kind + "\0" + live).encode()).hexdigest() if live is not None else None
        )
        # A source file differing from this job's pin is shown separately as on-disk state.
        if pair[1] is None and live_ref == current.get(kind):
            pair[1] = live
        if pair[0] is None and live_ref == initial.get(kind):
            pair[0] = live
        sources[kind] = {
            "initial": initial.get(kind),
            "current": current.get(kind),
            "live_ref": live_ref,
            "path": str(learning / filename),
            "before": pair[0],
            "after": pair[1],
            "warnings": warnings,
            "live_error": live_error,
        }
    candidate = next(
        (
            event.get("candidate", {})
            for event in reversed(events)
            if event.get("event") == "candidate_created"
        ),
        {},
    )
    artifacts = candidate.get("artifacts", {})
    nc = next(
        (
            value
            for key, value in artifacts.items()
            if key.startswith("nc")
            or Path(value.get("path", "")).suffix.lower() in {".nc", ".gcode"}
        ),
        {},
    )
    nc_text, _ = source_text(nc["path"], nc.get("sha256")) if nc else (None, None)
    nc_lines = []
    if nc_text:
        # Skip controller/header comments, start at actual machine instructions.
        instructions = [
            (i + 1, line)
            for i, line in enumerate(nc_text.splitlines())
            if line.strip() and not line.lstrip().startswith(("(", "%", "O"))
        ]
        nc_lines = [f"{i:>3} {line}" for i, line in instructions[:6]]
    cam_files = list(manifest_path.parent.glob("workspace/**/*.py")) if manifest_path else []
    cam_files = [path for path in cam_files if path.name.startswith(("cam", "cad"))]
    cam_file = max(cam_files, key=lambda path: path.stat().st_mtime) if cam_files else None
    cam_text, _ = source_text(cam_file) if cam_file else (None, None)
    cam_lines, cam_label = machining_excerpt(cam_text)
    best = manifest.get("best_verification") or {}
    estimate = candidate.get("parameters", {}).get("estimated_metrics", {}).get("machining_seconds")
    return {
        "campaign": campaign,
        "manifest": manifest,
        "manifest_path": str(manifest_path or ""),
        "part": part or {},
        "events": events,
        "sources": sources,
        "candidate": candidate,
        "best": best,
        "estimate": estimate,
        "nc_lines": nc_lines,
        "nc_path": nc.get("path", ""),
        "cam_lines": cam_lines,
        "cam_excerpt_label": cam_label,
        "cam_path": str(cam_file or ""),
        "error": f"Manifest unavailable: {error}" if error else None,
    }


def render(snapshot, width=120, height=40, color=False):
    width, height = max(60, min(width, 120)), max(20, min(height, 40))
    lines = []
    headings = set()

    def add(text="", heading=False):
        if heading:
            headings.add(len(lines))
        lines.append(clip(text, width))

    def pair(left, right):
        cell = (width - 3) // 2
        add(clip(left, cell).ljust(cell) + " | " + clip(right, width - cell - 3))

    campaign, manifest, events = snapshot["campaign"], snapshot["manifest"], snapshot["events"]
    add("SILTA / LIVE FUSION CAMPAIGN  [recorded artifacts]", True)
    add(
        f"Campaign {campaign.get('campaign_id', 'unavailable')}"
        f"  |  status {campaign.get('status', 'unknown')}"
        f"  |  listed parts {len(campaign.get('parts', []))}"
    )
    add(
        f"Job {manifest.get('job_id', snapshot.get('part', {}).get('job_id', 'not started'))}"
        f"  |  status {manifest.get('status', 'unavailable')}"
    )
    last = events[-1] if events else {}
    add("Stage: " + last.get("event", "waiting for recorded events").replace("_", " "))
    best = snapshot.get("best", {})
    accepted = bool(manifest.get("best_candidate")) and recorded_pass(best)
    metric = best.get("machining_seconds")
    verified = f"{metric:.2f}s" if accepted and finite_metric(metric) else "none yet"
    latest = snapshot.get("estimate")
    estimate = f"{latest:.2f}s [UNVERIFIED estimate]" if finite_metric(latest) else "unavailable"
    add(f"Best verified time (recorded): {verified}  |  Latest CAM: {estimate}")
    latest_check = next(
        (e.get("result", {}) for e in reversed(events) if e.get("event") == "checks_completed"),
        None,
    )
    latest_sim = next(
        (
            e.get("verification", {})
            for e in reversed(events)
            if e.get("event") == "verification_completed"
        ),
        None,
    )
    check_status = (
        "not run"
        if latest_check is None
        else ("passed" if latest_check.get("passed") is True else "failed")
    )
    sim_status = (
        "not completed"
        if latest_sim is None
        else f"{latest_sim.get('status', 'unknown')} / "
        f"completed={latest_sim.get('completed') is True}"
    )
    add(f"Checks: {check_status}  |  Last simulation verdict: {sim_status}")
    for kind, label in [("checks", "CHECKS"), ("main_prompt", "PROMPT")]:
        source = snapshot.get("sources", {}).get(kind, {})
        suffix = (
            " SAME"
            if source.get("initial") and source.get("initial") == source.get("current")
            else " CHANGED"
            if source.get("current")
            else ""
        )
        if source.get("live_ref") and source.get("live_ref") != source.get("current"):
            suffix += f" | on disk {short(source['live_ref'])} [not this job's current pin]"
        add(
            f"{label:6} initial {short(source.get('initial'))} -> "
            f"current {short(source.get('current'))}{suffix}"
        )
    add("-" * width)
    pair("CHECK SOURCE / EXACT DIFF (+ added, - removed)", "CAD/CAM SYSTEM PROMPT / EXACT DIFF")
    block = 6 if height >= 36 else 3
    source_panels = []
    for kind in ["checks", "main_prompt"]:
        source = snapshot.get("sources", {}).get(kind, {})
        source_panels.append(
            snippet(source.get("before"), source.get("after"), block, code=kind == "checks")
        )
    for i in range(block):
        pair(*(panel[i] if i < len(panel) else "" for panel in source_panels))
    add("-" * width)
    pair(
        snapshot.get("cam_excerpt_label", "CAM SOURCE EXCERPT / file lines"),
        "LATEST POSTED NC / G-CODE [not NC verification]",
    )
    for i in range(block):
        pair(
            snapshot.get("cam_lines", [])[i] if i < len(snapshot.get("cam_lines", [])) else "",
            snapshot.get("nc_lines", [])[i] if i < len(snapshot.get("nc_lines", [])) else "",
        )
    add("RECENT ACTUAL EVENTS", True)
    for event in events[-6:]:
        add(event_text(event))
    if not events:
        add("No job events have been recorded.")
    add("Manifest: " + snapshot.get("manifest_path", ""), True)
    add("CAM source: " + (snapshot.get("cam_path") or "not saved in this recovery job"))
    add("NC source: " + (snapshot.get("nc_path") or "not yet exported"))
    if snapshot.get("error"):
        add("READ ERROR: " + snapshot["error"])
    add(
        "Read-only. No generated summaries or inferred passes. "
        "Ctrl-C exits; --once gives a plain capture."
    )
    # Keep the decisive verdict and source columns within the requested viewport.
    lines = lines[:height]
    if color:
        lines = [
            (f"\033[1;36m{line}\033[0m" if i in headings else line) for i, line in enumerate(lines)
        ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=ROOT / "runs/demo-campaign.json")
    parser.add_argument("--job", help="Campaign part/job ID or direct manifest path")
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--plain", action="store_true", help="Disable ANSI color and cursor controls"
    )
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--width", type=int, default=120)
    parser.add_argument("--height", type=int, default=40)
    args = parser.parse_args(argv)
    if args.interval < 0.25:
        parser.error("--interval must be at least0.25 seconds")
    ansi = sys.stdout.isatty() and not args.plain and not args.once
    previous, last_good = None, None
    try:
        if ansi:
            print("\033[?25l", end="", flush=True)
        while True:
            snapshot = load_snapshot(args.campaign.resolve(), args.job)
            if snapshot.get("error") and last_good is not None:
                snapshot = {
                    **last_good,
                    "error": snapshot["error"] + " [last readable snapshot retained]",
                }
            elif not snapshot.get("error"):
                last_good = snapshot
            size = shutil.get_terminal_size((args.width, args.height))
            view = render(
                snapshot, min(args.width, size.columns), min(args.height, size.lines), ansi
            )
            if ansi:
                print("\033[H\033[2J" + view, end="", flush=True)
            elif view != previous:
                print(view, flush=True)
            previous = view
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        if ansi:
            print("\033[0m\033[?25h", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
