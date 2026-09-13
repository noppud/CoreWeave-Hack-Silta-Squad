"""Replay checks against retained Fusion verdicts; never run models or promote learning."""

# ruff: noqa: E402, E501
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from silta.cnc.benchmarks import (
    case_input_hash,
    decode_candidate,
    decode_inputs,
    decode_target,
    decode_verification,
    verification_timing,
)
from silta.cnc.checks import IntegrityChecks
from silta.cnc.evaluation import digest, evaluate_check_change
from silta.cnc.learning import EMPTY_CHECKS
from silta.cnc.local_checks import LocalCheckRunner
from silta.cnc.models import JobContext

SELECTION = [
    ("learning-soft-jaw-a3", 1),
    ("learning-part-b1", 2),
    ("learning-soft-jaw-a5", 2),
    ("learning-part-b2", 1),
    ("learning-part-c5", 1),
    ("learning-part-d1", 2),
]
LIMITATIONS = [
    "Offline replay on six selected historical cases, not a held-out generalization test.",
    "Labels come from retained completed Fusion verdicts and hashed evidence; historical verifier implementation bytes were not retained, so this is not a frozen-verifier benchmark or promotion gate.",
    "Replay does not rerun Fusion. Timing includes isolated check execution and artifact preparation; it is not CNC machining time or measured end-to-end speedup.",
    "Prompt evidence is historical within-part candidate improvement, not a controlled prompt-policy comparison.",
    "Checks cover narrow three-axis fixture and finished-side conditions; they do not certify manufacturing or cover the indexed demo machine.",
]
SCORE_NAMES = ["caught_invalid", "false_rejection", "accepted_valid", "runtime_ms"]


def row_scores(label, record):
    """Exclude inapplicable labels from rate denominators, rather than scoring False."""
    if label not in {"valid", "invalid"} or not isinstance(record.get("passed"), bool):
        raise ValueError("Expected an exact valid/invalid label and boolean check verdict")
    runtime = record["runtime_ms"]
    if (
        isinstance(runtime, bool)
        or not isinstance(runtime, (int, float))
        or not math.isfinite(runtime)
        or runtime < 0
    ):
        raise ValueError("Expected finite nonnegative retained runtime")
    return {
        "caught_invalid": not record["passed"] if label == "invalid" else None,
        "false_rejection": not record["passed"] if label == "valid" else None,
        "accepted_valid": record["passed"] if label == "valid" else None,
        "runtime_ms": runtime,
    }


def expected_summary(rows, key):
    scores = [row_scores(row["case"]["label"], row[key]) for row in rows]
    result = {}
    for name in SCORE_NAMES:
        values = [row[name] for row in scores if row[name] is not None]
        if not values:
            raise ValueError(f"No applicable cases for {name}")
        if name == "runtime_ms":
            result[name] = {"mean": sum(values) / len(values)}
        else:
            count = sum(values)
            result[name] = {"true_count": count, "true_fraction": count / len(values)}
    return result


def validate_server_summary(output, expected):
    """Finalization alone is insufficient: the UI needs native aggregate score keys."""
    for name, fields in expected.items():
        for key, value in fields.items():
            actual = output.get(name, {}).get(key)
            if not isinstance(actual, (int, float)) or not math.isclose(
                actual, value, rel_tol=1e-10, abs_tol=1e-10
            ):
                raise RuntimeError(f"Missing or incorrect native aggregate: {name}.{key}")


def retained_case(run, attempt):
    path = ROOT / "runs" / run / "manifest.json"
    m = json.loads(path.read_text())

    def event(name):
        found = [e for e in m["events"] if e["event"] == name and e.get("attempt") == attempt]
        if len(found) != 1:
            raise ValueError(f"{run}: expected one {name}")
        return found[0]

    inputs, target = decode_inputs(m["inputs"]), decode_target(m["target"])
    candidate = decode_candidate(event("candidate_created")["candidate"])
    verdict = decode_verification(event("verification_completed")["verification"])
    context = JobContext(inputs, target, inputs.digest, m["versions"], str(path.parent))
    inputs.verify()
    target.verify()
    candidate.verify()
    verdict.validate(candidate, context)
    if m["input_digest"] != inputs.digest or m["target_digest"] != target.digest:
        raise ValueError("Historical input or target mismatch")
    if (
        verdict.completed is not True
        or verdict.status not in ("passed", "failed")
        or not verdict.evidence
    ):
        raise ValueError("No completed labeled verification")
    for artifact in verdict.evidence:
        artifact.verify()
    # This is an evidence identity, explicitly NOT an implementation identity.
    evidence_identity = {
        "kind": "retained-verdict-evidence-not-verifier-source",
        "version": verdict.verifier_version,
        "coverage": verdict.coverage,
        "evidence": [asdict(x) for x in verdict.evidence],
    }
    row = {
        "case_id": f"{run}-attempt-{attempt}",
        "input_hash": case_input_hash("checks", inputs, target, candidate),
        "verifier_hash": digest(evidence_identity),
        "identity_scope": evidence_identity["kind"],
        "label": "valid" if verdict.status == "passed" else "invalid",
        "verification_evidence": [asdict(x) for x in verdict.evidence],
        "verification_timing": verification_timing(m, attempt),
        "source_manifest": str(path),
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "candidate": asdict(candidate),
        "verdict": asdict(verdict),
    }
    return row, candidate, context


def publish_evaluation(
    project,
    result,
    *,
    baseline_ref,
    proposed_ref,
    dataset_ref,
    frozen_cases,
    version_artifacts,
    name_suffix="",
    publication_scope="historical-label-replay-no-promotion",
):
    """Observational evaluations using the installed SDK; no promotion verdict."""
    import weave

    client = weave.init(project)
    dataset = weave.Dataset(name=f"retained-fusion-checks-{dataset_ref[:12]}", rows=frozen_cases)
    uri = weave.publish(dataset).uri()
    refs = []
    summaries = []
    for name, ref, key in [
        ("baseline", baseline_ref, "baseline"),
        ("learned", proposed_ref, "proposed"),
    ]:
        logger = weave.EvaluationLogger(
            name=f"retained-checks-{name}-{ref[:12]}{name_suffix}",
            model={"name": f"checks-{name}", "version": ref, "artifact": version_artifacts[ref]},
            dataset=dataset,
            scorers=SCORE_NAMES,
            eval_attributes={
                "scope": publication_scope,
                "dataset_ref": dataset_ref,
                "limitations": LIMITATIONS,
            },
        )
        for row in result.rows:
            record = row[key]
            with logger.log_prediction(
                inputs={"case_id": row["case_id"]}, output=record, example_id=row["case_id"]
            ) as prediction:
                for score_name, value in row_scores(row["case"]["label"], record).items():
                    prediction.log_score(score_name, value)
        logger.log_summary(
            {
                "variant": name,
                **result.summary[key],
                "case_count": len(frozen_cases),
                "invalid_case_count": sum(c["label"] == "invalid" for c in frozen_cases),
                "valid_case_count": sum(c["label"] == "valid" for c in frozen_cases),
                "scope": publication_scope,
                "limitations": LIMITATIONS,
            },
            auto_summarize=True,
        )
        client.flush()
        call = client.get_call(logger._evaluate_call.id)
        if call.ended_at is None or call.exception:
            raise RuntimeError("Evaluation server readback did not confirm successful finalization")
        validate_server_summary(call.output, expected_summary(result.rows, key))
        summaries.append({"variant": name, "output": json.loads(json.dumps(call.output))})
        refs.append(f"weave:///{project}/call/{call.id}")
    return {
        "status": "published",
        "dataset_uri": uri,
        "dataset_ref": dataset_ref,
        "result_digest": result.digest,
        "weave_refs": refs,
        "baseline_ref": baseline_ref,
        "proposed_ref": proposed_ref,
        "readback_finalized": True,
        "native_score_aggregates_verified": True,
        "server_summaries": summaries,
    }


def run(publish=False, project="silta/coreweave-hack-silta-squad"):
    out = ROOT / "output/evaluation"
    out.mkdir(parents=True, exist_ok=True)
    captured = [retained_case(*item) for item in SELECTION]
    cases = [item[0] for item in captured]
    sources = {"baseline": EMPTY_CHECKS, "learned": (ROOT / "learning/checks.py").read_text()}
    refs, records = {}, {}
    for name, source in sources.items():
        ref = hashlib.sha256(source.encode()).hexdigest()
        refs[name] = ref
        frozen = out / f"checks-{ref}.py"
        frozen.write_text(source)
        runner = IntegrityChecks(LocalCheckRunner(frozen, version=ref, sha256=ref))
        records[name] = []
        for case, candidate, original in captured:
            context = JobContext(
                original.inputs,
                original.target,
                original.input_digest,
                {**original.versions, "checks": ref},
                original.job_directory,
            )
            samples = [runner.run(candidate, context) for _ in range(5)]
            if len({(s.passed, s.issues) for s in samples}) != 1:
                raise ValueError("Unstable replay verdict")
            if any(
                any(
                    "unavailable:" in issue
                    or issue in ("check_execution_failed", "check_timeout", "invalid_check_output")
                    for issue in s.issues
                )
                for s in samples
            ):
                raise ValueError("Check execution error cannot count as a caught failure")
            timings = [s.runtime_s * 1000 for s in samples]
            records[name].append(
                {k: case[k] for k in ("case_id", "input_hash", "verifier_hash")}
                | {
                    "version_ref": ref,
                    "passed": samples[0].passed,
                    "issues": list(samples[0].issues),
                    "runtime_samples_ms": timings,
                    "runtime_ms": median(timings),
                }
            )
    result = evaluate_check_change(cases, records["baseline"], records["learned"])
    dataset_ref = digest(cases)
    payload = {
        "schema_version": 1,
        "status": "local_only",
        "title": "Learned checks: retained-case replay",
        "scope": "Historical Fusion labels, current isolated check replay, no promotion gate",
        "dataset": {
            "case_count": len(cases),
            "valid_count": sum(c["label"] == "valid" for c in cases),
            "invalid_count": sum(c["label"] == "invalid" for c in cases),
            "ref": dataset_ref,
        },
        "variants": [],
        "rows": [],
        "limitations": LIMITATIONS,
        "publication": {},
        "check_source": sources,
        "prompt_source": (ROOT / "learning/cad_cam.md").read_text(),
        "prompt_evidence": [
            {
                "part": "A",
                "before_seconds": 384.860,
                "after_seconds": 211.037,
                "scope": "Historical verified ramp-feed candidate change",
                "weave_url": f"https://wandb.ai/{project}/r/call/01a098a9-7350-7b4b-adb4-e5d9c997f8c4",
            },
            {
                "part": "C",
                "before_seconds": 228.182,
                "after_seconds": 211.850,
                "scope": "Historical verified ramp-stepdown candidate change",
                "weave_url": f"https://wandb.ai/{project}/r/call/01a098c9-7ed1-7b60-81e5-6f877aebfda8",
            },
        ],
    }
    for name, summary_name in [("baseline", "baseline"), ("learned", "proposed")]:
        totals = result.summary[summary_name]
        payload["variants"].append(
            {
                "name": name,
                "version": refs[name],
                "caught_invalid": totals["caught"],
                "false_rejections": totals["false_rejections"],
                "median_runtime_ms": median(r["runtime_ms"] for r in records[name]),
                "weave_url": None,
            }
        )
    for c, old, new in zip(cases, records["baseline"], records["learned"], strict=True):
        payload["rows"].append(
            {
                "case_id": c["case_id"],
                "label": c["label"],
                "baseline_passed": old["passed"],
                "learned_passed": new["passed"],
                "baseline_runtime_ms": old["runtime_ms"],
                "learned_runtime_ms": new["runtime_ms"],
                "issues": new["issues"],
            }
        )
    (out / "replay-evidence.json").write_text(
        json.dumps({"cases": cases, "records": records, "result": asdict(result)}, indent=2)
    )
    target = out / "learning-evaluation.json"
    target.write_text(json.dumps(payload, indent=2))
    if publish:
        if "COREWEAVE_WANDB_API_KEY" in os.environ:
            os.environ["WANDB_API_KEY"] = os.environ.pop("COREWEAVE_WANDB_API_KEY")
        try:
            publication = publish_evaluation(
                project,
                result,
                baseline_ref=refs["baseline"],
                proposed_ref=refs["learned"],
                dataset_ref=dataset_ref,
                frozen_cases=cases,
                version_artifacts={
                    refs[n]: {"source": s, "scope": payload["scope"], "limitations": LIMITATIONS}
                    for n, s in sources.items()
                },
            )
            payload["publication"] = publication
            payload["status"] = "published"
            for variant, ref in zip(payload["variants"], publication["weave_refs"], strict=True):
                variant["weave_url"] = f"https://wandb.ai/{project}/r/call/{ref.rsplit('/', 1)[-1]}"
        except Exception as exc:
            payload["status"] = "failed"
            payload["publication"] = {"error_type": type(exc).__name__}
            target.write_text(json.dumps(payload, indent=2))
            raise
        target.write_text(json.dumps(payload, indent=2))
    print(
        json.dumps(
            {"status": payload["status"], "artifact": str(target), "variants": payload["variants"]}
        )
    )


def republish_retained(evidence_path, receipt_path, output_directory, project):
    """Publish existing observations; never call a checker, model or Fusion."""
    evidence_raw, receipt_raw = evidence_path.read_bytes(), receipt_path.read_bytes()
    evidence, receipt = json.loads(evidence_raw), json.loads(receipt_raw)
    result = evaluate_check_change(
        evidence["cases"], evidence["records"]["baseline"], evidence["records"]["learned"]
    )
    old = receipt["publication"]
    if result.digest != old["result_digest"] or digest(evidence["cases"]) != old["dataset_ref"]:
        raise ValueError("Retained data does not reproduce the original evaluation identity")

    def verify_pins(value):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                if hashlib.sha256(Path(value["path"]).read_bytes()).hexdigest() != value["sha256"]:
                    raise ValueError("Retained evidence artifact changed")
            for child in value.values():
                verify_pins(child)
        elif isinstance(value, list):
            for child in value:
                verify_pins(child)

    verify_pins(evidence["cases"])
    artifacts = {}
    for name, key in [("baseline", "baseline_ref"), ("learned", "proposed_ref")]:
        source = receipt["check_source"][name]
        ref = hashlib.sha256(source.encode()).hexdigest()
        frozen = evidence_path.parent / f"checks-{ref}.py"
        if ref != old[key] or frozen.read_text() != source:
            raise ValueError("Frozen check source does not match original version")
        if any(row["version_ref"] != ref for row in evidence["records"][name]):
            raise ValueError("Retained row version differs from frozen check source")
        artifacts[ref] = {"source": source, "scope": "retained-data-republication-no-new-execution"}
    if "COREWEAVE_WANDB_API_KEY" not in os.environ:
        raise RuntimeError("Use hsec exec --only COREWEAVE_WANDB_API_KEY")
    os.environ["WANDB_API_KEY"] = os.environ.pop("COREWEAVE_WANDB_API_KEY")
    output_directory.mkdir(parents=True, exist_ok=False)
    target = output_directory / "publication.json"
    payload = {
        "schema_version": 1,
        "status": "publishing",
        "scope": "Native UI summary repair: retained-data republication, no new checks/Fusion/model execution",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_replay": {
            "path": str(evidence_path),
            "sha256": hashlib.sha256(evidence_raw).hexdigest(),
        },
        "source_receipt": {
            "path": str(receipt_path),
            "sha256": hashlib.sha256(receipt_raw).hexdigest(),
        },
        "original_weave_refs": old["weave_refs"],
        "original_result_digest": result.digest,
        "dataset": receipt["dataset"],
        "metric_definitions": {
            "caught_invalid": "Fraction/count among the two invalid cases; valid rows are null",
            "false_rejection": "Fraction/count among the four valid cases; invalid rows are null",
            "accepted_valid": "Fraction/count among the four valid cases; invalid rows are null",
            "runtime_ms": "Mean of six retained per-case median check runtimes; each original median used five repetitions",
        },
        "limitations": LIMITATIONS,
    }
    target.write_text(json.dumps(payload, indent=2) + "\n")
    try:
        payload["publication"] = publish_evaluation(
            project,
            result,
            baseline_ref=old["baseline_ref"],
            proposed_ref=old["proposed_ref"],
            dataset_ref=old["dataset_ref"],
            frozen_cases=evidence["cases"],
            version_artifacts=artifacts,
            name_suffix="-native-summary-v2",
            publication_scope="retained-data-republication-no-new-execution",
        )
        payload["status"] = "published_and_score_aggregates_read_back"
        payload["weave_urls"] = [
            f"https://wandb.ai/{project}/r/call/{ref.rsplit('/', 1)[-1]}"
            for ref in payload["publication"]["weave_refs"]
        ]
    except Exception as error:
        payload.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        target.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    if evidence_path.read_bytes() != evidence_raw or receipt_path.read_bytes() != receipt_raw:
        raise RuntimeError("Original evidence changed during publication")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "receipt": str(target),
                "weave_urls": payload["weave_urls"],
            }
        )
    )
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--project", default="silta/coreweave-hack-silta-squad")
    parser.add_argument("--republish-retained", action="store_true")
    parser.add_argument(
        "--evidence", type=Path, default=ROOT / "output/evaluation/replay-evidence.json"
    )
    parser.add_argument(
        "--original-receipt", type=Path, default=ROOT / "output/evaluation/learning-evaluation.json"
    )
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    if args.republish_retained:
        if not args.publish:
            parser.error("--republish-retained requires --publish")
        output = args.output_directory or ROOT / "output/evaluation" / (
            "native-summary-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        )
        republish_retained(args.evidence, args.original_receipt, output, args.project)
    else:
        run(args.publish, args.project)
