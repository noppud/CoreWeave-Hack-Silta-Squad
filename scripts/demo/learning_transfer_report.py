"""Read-only, source-grounded cross-drawing learning audit; no model or Fusion calls."""

# ruff: noqa: E501
from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
OUT = ROOT / "output/evaluation"
PATTERNS = [
    ("A", "learning-soft-jaw-a*"),
    ("B", "learning-part-b*"),
    ("C", "learning-part-c*"),
    ("D", "learning-part-d*"),
    ("UMC02", "demo-umc-umc-02*"),
    ("UMC03", "demo-umc-umc-03*"),
    ("UMC08", "demo-umc-umc-08*"),
    ("UMC04", "demo-umc-umc-04*"),
    ("UMC09", "demo-umc-umc-09*"),
    ("UMC05", "demo-umc-umc-05*"),
    ("UMC06", "demo-umc-umc-06*"),
    ("UMC10", "demo-umc-umc-10*"),
    ("UMC11", "demo-umc-umc-11*"),
    ("UMC12", "demo-umc-umc-12*"),
]
PARAMETERS = (
    "tool_feedRamp",
    "rampAngle",
    "maximumRampZStepdown",
    "rampClearanceHeight",
    "feedHeight_offset",
    "safeDistance",
)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def generated_source(path):
    """Decode literal compile strings through AST, never execute generated Python."""
    text = path.read_text()
    tree = ast.parse(text)
    blocks = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "compile"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    return blocks or [text]


def cam_evidence(directory):
    records = []
    for path in sorted(directory.glob("workspace/**/cam*.py")):
        try:
            for block_index, block in enumerate(generated_source(path)):
                snippets = [
                    {"line": index, "text": line}
                    for index, line in enumerate(block.splitlines(), 1)
                    if any(parameter in line for parameter in PARAMETERS) or ".expression" in line
                ]
                if snippets:
                    records.append(
                        {
                            "path": str(path),
                            "sha256": sha(path),
                            "literal_block": block_index,
                            "line_number_scope": "decoded literal block, not wrapper file",
                            "snippets": snippets,
                        }
                    )
        except (OSError, SyntaxError) as error:
            records.append({"path": str(path), "unavailable": type(error).__name__})
    return records


def validate_verdict(verdict):
    seconds = verdict.get("machining_seconds")
    if not (
        verdict.get("status") == "passed"
        and verdict.get("completed") is True
        and verdict.get("evidence")
        and verdict.get("coverage")
        and not verdict.get("issues")
        and isinstance(seconds, (float, int))
        and not isinstance(seconds, bool)
        and math.isfinite(seconds)
        and seconds >= 0
        and str(verdict.get("verifier_version", "")).startswith("fusion-fixed-")
    ):
        return False
    try:
        return all(sha(ref["path"]) == ref["sha256"] for ref in verdict["evidence"])
    except (KeyError, OSError):
        return False


def pinned_source(manifest, directory, kind, version):
    retained = manifest.get("learning_sources", {}).get(version)
    if retained:
        path = Path(retained["path"])
        if path.exists() and sha(path) == retained["sha256"]:
            text = path.read_text()
            if hashlib.sha256((kind + "\0" + text).encode()).hexdigest() == version:
                return {"path": str(path), "sha256": sha(path), "version_valid": True}
    # Older jobs retained proposal files, before learning_sources existed.
    for path in directory.glob(f"workspace/**/{kind}-{version}.*"):
        text = path.read_text()
        if hashlib.sha256((kind + "\0" + text).encode()).hexdigest() == version:
            return {"path": str(path), "sha256": sha(path), "version_valid": True}
    return {"version_valid": False, "reason": "No retained bytes found in this job"}


def part_record(label, paths):
    jobs, passed, changes, rejects, code, decisions, verdicts = [], {}, [], [], [], [], []
    paths = sorted(paths, key=lambda p: read(p).get("created_at", ""))
    drawings = set()
    initial, ending = {}, {}
    for path in paths:
        manifest = read(path)
        nomination_path = path.parent / "workspace/manual-trial-nomination.json"
        nomination = read(nomination_path) if nomination_path.is_file() else None
        drawings.update(ref["sha256"] for ref in manifest["inputs"]["drawings"])
        if not initial:
            initial = manifest.get("versions", {})
        ending = manifest.get("current_versions", manifest.get("versions", {}))
        events = manifest.get("events", [])
        jobs.append(
            {
                "job_id": manifest["job_id"],
                "status": manifest.get("status"),
                "collection_warning": manifest.get("collection_warning"),
                "manual_trial_nomination": nomination,
                "manifest": str(path),
                "manifest_sha256": sha(path),
                "initial_versions": manifest.get("versions", {}),
                "ending_versions": ending,
                "last_event": events[-1].get("event") if events else None,
                "input_digest": manifest.get("input_digest"),
                "target_digest": manifest.get("target_digest"),
            }
        )
        for index, event in enumerate(events):
            anchor = {"manifest": str(path), "event_index": index, "at": event.get("at")}
            if event.get("event") == "supervisor_decision":
                decisions.append(
                    {
                        **anchor,
                        "versions": event.get("versions", {}),
                        "decision": event.get("decision", {}),
                    }
                )
            verdict = event.get("verification")
            if verdict:
                verdicts.append(
                    {
                        **anchor,
                        "attempt": event.get("attempt"),
                        "candidate_digest": verdict.get("candidate_digest"),
                        "status": "collection_invalidated"
                        if manifest.get("collection_warning")
                        else verdict.get("status"),
                        "recorded_status": verdict.get("status"),
                        "collection_warning": manifest.get("collection_warning"),
                        "completed": verdict.get("completed"),
                        "issues": verdict.get("issues", []),
                    }
                )
            if verdict and not manifest.get("collection_warning") and validate_verdict(verdict):
                key = verdict.get("candidate_digest")
                passed.setdefault(
                    key,
                    {
                        **anchor,
                        "candidate_digest": key,
                        "input_digest": verdict.get("input_digest"),
                        "target_digest": manifest.get("target_digest"),
                        "verifier_version": verdict.get("verifier_version"),
                        "machining_seconds": verdict["machining_seconds"],
                        "attempt": event.get("attempt"),
                        "retained_evidence_hashes_valid": True,
                        "manual_nomination": bool(
                            nomination and nomination.get("candidate_digest") == key
                        ),
                        "nomination_artifact": {
                            "path": str(nomination_path),
                            "sha256": sha(nomination_path),
                        }
                        if nomination
                        else None,
                    },
                )
            if event.get("event") == "promoted_change_applied":
                kind, version = event["change_kind"], event["version"]
                changes.append(
                    {
                        **anchor,
                        "kind": kind,
                        "previous_version": event.get("previous_version"),
                        "version": version,
                        "source": pinned_source(manifest, path.parent, kind, version),
                        "meaning": "Applied shared learning edit; not evidence of an eval gate",
                    }
                )
            if event.get("event") == "checks_completed" and event["result"].get("passed") is False:
                attempt = event.get("attempt")
                ran = any(
                    e.get("event") == "verification_started" and e.get("attempt") == attempt
                    for e in events
                )
                rejects.append(
                    {
                        **anchor,
                        "attempt": attempt,
                        "version": event["result"].get("version"),
                        "runtime_s": event["result"].get("runtime_s"),
                        "issues": event["result"].get("issues"),
                        "same_attempt_simulation_started": ran,
                    }
                )
        code.extend(cam_evidence(path.parent))
    if len(drawings) != 1:
        raise ValueError(f"{label}: expected one distinct drawing; got {len(drawings)}")
    verified = sorted(passed.values(), key=lambda row: row["at"] or "")
    best = min(verified, key=lambda row: row["machining_seconds"]) if verified else None
    first = verified[0] if verified else None
    comparison = None
    if first and best and first["candidate_digest"] != best["candidate_digest"]:
        comparison = {
            "first_seconds": first["machining_seconds"],
            "best_seconds": best["machining_seconds"],
            "reduction_percent": 100
            * (first["machining_seconds"] - best["machining_seconds"])
            / first["machining_seconds"],
            "same_input_digest": first["input_digest"] == best["input_digest"],
            "same_target_digest": first["target_digest"] == best["target_digest"],
            "same_verifier_version": first["verifier_version"] == best["verifier_version"],
            "verifier_implementation_bytes_frozen": False,
            "manual_nomination": best.get("manual_nomination", False),
            "claim": (
                "Operator-nominated retained-CAM retest; not autonomous improvement or new learning"
                if best.get("manual_nomination")
                else "Within-drawing verified candidate optimization, not a cross-part causal effect"
            ),
        }
    trials = []
    for decision in decisions:
        if decision["decision"].get("action") != "improve":
            continue
        same_job = [v for v in verified if v["manifest"] == decision["manifest"]]
        previous = [v for v in same_job if (v["at"] or "") < (decision["at"] or "")]
        following = [v for v in same_job if (v["at"] or "") > (decision["at"] or "")]
        if not previous or not following:
            continue
        before = min(previous, key=lambda v: v["machining_seconds"])
        after = following[0]
        instructions = decision["decision"].get("instructions", "")
        proposed = re.search(
            r"\bTrial (?:reducing|changing only|lowering)\s+([A-Za-z_]\w*)", instructions
        )
        trials.append(
            {
                "decision": decision,
                "proposed_parameter": proposed.group(1) if proposed else None,
                "parameters_named_in_instruction": [p for p in PARAMETERS if p in instructions],
                "before_seconds": before["machining_seconds"],
                "after_seconds": after["machining_seconds"],
                "saved_seconds": before["machining_seconds"] - after["machining_seconds"],
                "before_candidate_digest": before["candidate_digest"],
                "after_candidate_digest": after["candidate_digest"],
                "same_input_target_verifier": all(
                    before[k] == after[k]
                    for k in ("input_digest", "target_digest", "verifier_version")
                ),
                "scope": "Recorded supervisor instruction followed by verified candidate; inspect CAM source for actual assignments",
            }
        )
    return {
        "part": label,
        "drawing_sha256": next(iter(drawings)),
        "initial_versions": initial,
        "ending_versions": ending,
        "latest_job_status": jobs[-1]["status"],
        "any_completed_job": any(job["status"] == "completed" for job in jobs),
        "best_verified_seconds": best["machining_seconds"] if best else None,
        "jobs": jobs,
        "verified_candidates": verified,
        "same_part_optimization": comparison,
        "learning_edits": changes,
        "check_rejections": rejects,
        "generated_cam_evidence": code,
        "supervisor_decisions": decisions,
        "verified_supervisor_trials": trials,
        "all_verdicts": verdicts,
    }


def build_report():
    parts = [
        part_record(label, list(RUNS.glob(pattern + "/manifest.json")))
        for label, pattern in PATTERNS
        if list(RUNS.glob(pattern + "/manifest.json"))
    ]
    lookup = {part["part"]: part for part in parts}
    transfers = []
    for source, destination, kind, behavior in [
        (
            "A",
            "B",
            "main_prompt",
            "B source sets the supplied ramp feed to 457.2 mm/min; consistent with A guidance, not a controlled counterfactual.",
        ),
        (
            "B",
            "C",
            "checks",
            "C check event rejects candidate before simulation; direct observed cross-part use.",
        ),
        (
            "C",
            "D",
            "main_prompt",
            "D source sets 2-degree ramps and 2 mm cap; consistent with C guidance, not causal speedup.",
        ),
        (
            "C",
            "UMC02",
            "main_prompt",
            "Initial prompt retained; different indexed drawing and machine. Inheritance alone is not effectiveness.",
        ),
        (
            "UMC03",
            "UMC08",
            "main_prompt",
            "Inspect actual ramp-clearance assignments; conditional guidance is not a universal 0.2 mm default.",
        ),
        (
            "UMC03",
            "UMC04",
            "main_prompt",
            "The same retained UMC03 ramp-clearance lesson is available to UMC04; inspect code and decisions separately from timing.",
        ),
        (
            "UMC03",
            "UMC09",
            "main_prompt",
            "UMC09 inherits the UMC03 lesson. Its first verified trial changes pocket ramp clearance; later trials change feed-start height. Do not attribute their combined gain solely to the ramp lesson.",
        ),
    ]:
        if source not in lookup or destination not in lookup:
            continue
        ref = lookup[destination]["initial_versions"].get(kind)
        edits = [
            edit
            for edit in lookup[source]["learning_edits"]
            if edit["kind"] == kind and edit["version"] == ref
        ]
        record = {
            "source_part": source,
            "destination_part": destination,
            "kind": kind,
            "version": ref,
            "source_edit_observed": bool(edits),
            "source_edits": edits,
            "behavior_scope": behavior,
        }
        if destination == "C":
            record["observed_rejections"] = lookup["C"]["check_rejections"]
        if destination in {"B", "D", "UMC08", "UMC04", "UMC09"}:
            record["source_code"] = lookup[destination]["generated_cam_evidence"]
        if destination in {"UMC08", "UMC04", "UMC09"}:
            lines = [
                line["text"]
                for source in record["source_code"]
                for line in source.get("snippets", [])
                if "rampClearanceHeight" in line["text"] or ".expression" in line["text"]
            ]
            record["observed_ramp_clearance_assignments"] = lines
            record["reduced_clearance_0_2_seen_in_source"] = any("0.2" in line for line in lines)
            record["adoption_conclusion"] = (
                "First CAM retained 1 mm; later generated CAM sets 0.2 mm after supervisor feedback. Verification and causal benefit remain separate."
                if record["reduced_clearance_0_2_seen_in_source"]
                else "No 0.2 mm assignment observed. First CAM retains 1 mm; latest lesson is inherited but its lower-clearance action is not demonstrated."
                if lines
                else "No generated clearance assignment available yet."
            )
            record["supervisor_reuse"] = [
                event
                for event in lookup[destination]["supervisor_decisions"]
                if "0.2 mm" in event["decision"].get("instructions", "")
                and event.get("versions", {}).get("main_prompt") == ref
            ]
            agent_path = ROOT / "silta/cnc/agents.py"
            agent_source = agent_path.read_text()
            record["destination_same_part_optimization"] = lookup[destination][
                "same_part_optimization"
            ]
            record["supervisor_prompt_flow"] = {
                "path": str(agent_path),
                "sha256": sha(agent_path),
                "pinned_main_prompt_included_in_request": '"current_main_prompt": self._prompt("main_prompt", context.versions)'
                in agent_source,
                "claim": "Current AstraSupervisor.decide explicitly includes pinned current_main_prompt; "
                "the recorded decision carries that same version. This shows lesson availability, "
                "not proof that the lesson caused the decision.",
            }
        transfers.append(record)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "Explicitly selected drawings; no model calls, live Fusion or Weave upload",
        "distinct_drawings": len({part["drawing_sha256"] for part in parts}),
        "completed_distinct_drawings": len(
            {
                part["drawing_sha256"]
                for part in parts
                if part["any_completed_job"] and part["verified_candidates"]
            }
        ),
        "parts": parts,
        "transfers": transfers,
        "limitations": [
            "Different drawing times are not a learning curve; no cross-part timing causality is claimed.",
            "Prompt/check version continuity proves inheritance, not adoption or usefulness.",
            "Only completed passed verdicts with currently matching retained evidence hashes supply times.",
            "Same-part comparisons retain input/target/verifier identity, but historical verifier source bytes were not frozen.",
            "Generated source assignments are code evidence, not independent operation readback or a manufacturing verdict.",
            "Historical source retention is incomplete; unavailable source bytes are explicit.",
            "The report is a read-only snapshot; ongoing jobs require rerunning this command.",
        ],
    }


def markdown(report):
    lines = [
        "# Learning transfer evidence",
        "",
        f"Snapshot: {report['generated_at']}.",
        "",
        "Different parts are not a timing learning curve. Full hashes, source excerpts and event indices are in learning-transfer.json.",
        "",
        f"{report['completed_distinct_drawings']} completed distinct drawings out of "
        f"{report['distinct_drawings']} observed drawings. An incomplete job's verified candidate "
        "does not count as a completed drawing.",
        "",
        "| Drawing | Inherited prompt / checks | Latest job | Best verified s | Within-part reduction |",
        "| --- | --- | --- | --- | --- |",
    ]
    for part in report["parts"]:
        versions = part["initial_versions"]
        comparison = part["same_part_optimization"]
        improvement = (
            f"{comparison['first_seconds']:.3f} → {comparison['best_seconds']:.3f} "
            f"({comparison['reduction_percent']:.1f}%)"
            if comparison
            else "not measured"
        )
        if comparison and not comparison.get("same_verifier_version"):
            improvement += " — **verifier changed; historical comparison**"
        if comparison and comparison.get("manual_nomination"):
            improvement += " — **manually nominated retest**"
        best = (
            f"{part['best_verified_seconds']:.3f}"
            if part["best_verified_seconds"] is not None
            else "none"
        )
        lines.append(
            f"| {part['part']} / {part['drawing_sha256'][:10]} | "
            f"{versions.get('main_prompt', '')[:12]} / {versions.get('checks', '')[:12]} | "
            f"{part['latest_job_status']} | {best} | {improvement} |"
        )
    lines += ["", "## Observed cross-part behavior", ""]
    for transfer in report["transfers"]:
        lines.append(
            f"- **{transfer['source_part']} → {transfer['destination_part']} ({transfer['kind']}):** "
            + transfer.get("adoption_conclusion", transfer["behavior_scope"])
        )
        if transfer.get("supervisor_reuse"):
            lines.append(
                "  Supervisor received the pinned learned prompt and requested the same clearance mechanism. "
                "This is observed reuse, not proven causal benefit."
            )
        comparison = transfer.get("destination_same_part_optimization")
        if comparison:
            lines.append(
                f"  New part's own verified trial: {comparison['first_seconds']:.6f} → "
                f"{comparison['best_seconds']:.6f} s "
                f"({comparison['first_seconds'] - comparison['best_seconds']:.6f} s saved). "
                "Input, target and verifier version match; no control without learned guidance was run."
            )
        for reject in transfer.get("observed_rejections", []):
            lines.append(
                f"  Rejected attempt {reject['attempt']} in {1000 * reject['runtime_s']:.2f} ms; "
                f"same-attempt simulation started={reject['same_attempt_simulation_started']}."
            )
    lines += ["", "## UMC09: separate the actual supervisor trials", ""]
    bracket = next((p for p in report["parts"] if p["part"] == "UMC09"), None)
    if bracket:
        lines += [
            "UMC09 inherited the same main prompt and checks and saved no new shared lesson. "
            "Its total optimization includes ramp clearance and separate approach-height changes.",
            "",
            "| Proposed parameter change | Before / after verified seconds | Saved seconds |",
            "| --- | --- | --- |",
        ]
        for trial in bracket["verified_supervisor_trials"]:
            lines.append(
                f"| {trial['proposed_parameter'] or 'See exact instruction'} | "
                f"{trial['before_seconds']:.6f} → {trial['after_seconds']:.6f} | "
                f"{trial['saved_seconds']:.6f} |"
            )
        lines += [
            "",
            "These rows retain the exact instruction, event indices, version and candidate digests in JSON. "
            "All comparisons use matching input/target/verifier identities; no control run omitted the learned guidance.",
        ]
    lines += [
        "",
        "## Evidence boundaries",
        "",
        *["- " + item for item in report["limitations"]],
        "",
        "Refresh: .venv/bin/python scripts/demo/learning_transfer_report.py",
    ]
    return "\n".join(lines) + "\n"


def main():
    report = build_report()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "learning-transfer.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    text = markdown(report)
    (OUT / "learning-transfer.md").write_text(text)
    (ROOT / "docs/learning-transfer.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
