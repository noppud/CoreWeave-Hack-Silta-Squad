"""Deterministic Weave evaluation gates, with immutable local version references.

Scoring is offline; publication is explicit and must succeed before promotion.
Simulator labels belong to frozen candidates plus their complete setup/verifier hash.
This module never invokes a judge model or changes the running job's pinned versions.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

KINDS = frozenset({"checks", "main_prompt", "supervisor_prompt"})


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return float(value)


def _indexed(rows: list[dict]) -> dict[str, dict]:
    if not rows:
        raise ValueError("Evaluation requires examples")
    indexed = {}
    for row in rows:
        key = row.get("case_id")
        if not isinstance(key, str) or not key or key in indexed:
            raise ValueError("Every example needs a unique nonempty case_id")
        indexed[key] = row
    return indexed


def _same_inputs(left: dict, right: dict) -> None:
    for key in ("input_hash", "verifier_hash"):
        if not isinstance(left.get(key), str) or not left[key] or left[key] != right.get(key):
            raise ValueError(f"Stale or mismatched {key} for {left.get('case_id')}")


@dataclass(frozen=True)
class EvaluationResult:
    kind: str
    eligible: bool
    reasons: tuple[str, ...]
    summary: dict
    rows: tuple[dict, ...]

    @property
    def digest(self) -> str:
        return digest(asdict(self))


def evaluate_loop_change(baseline: list[dict], proposed: list[dict]) -> EvaluationResult:
    """Strict paired gate: no lost success; metrics compare matched successes only.

    `input_hash` must cover drawing, fixed target, machine, tools, fixtures and
    costing assumptions. Timings are estimates from the same immutable verifier.
    A failed case never acquires a zero-valued cost or speed score.
    """
    old, new = _indexed(baseline), _indexed(proposed)
    if old.keys() != new.keys():
        raise ValueError("Baseline and proposed must run exactly the same examples")
    reasons, rows = [], []
    totals = {name: [0.0, 0.0] for name in ("machining_seconds", "cost", "simulation_attempts")}
    successes = [0, 0]
    matched = 0
    for key in sorted(old):
        pair = old[key], new[key]
        _same_inputs(*pair)
        for row in pair:
            if type(row.get("verified")) is not bool:
                raise ValueError("verified must be an explicit bool; unknown is not pass")
            if row["verified"]:
                if not row.get("verification_evidence"):
                    raise ValueError("Verified results require verification evidence")
                for metric in totals:
                    _number(row.get(metric), metric)
        success = [row["verified"] for row in pair]
        successes = [successes[i] + int(success[i]) for i in (0, 1)]
        if success[0] and not success[1]:
            reasons.append(f"Lost verified completion on {key}")
        scores: dict[str, Any] = {"baseline_verified": success[0], "proposed_verified": success[1]}
        if all(success):
            matched += 1
            for metric in totals:
                values = [_number(row[metric], metric) for row in pair]
                totals[metric] = [totals[metric][i] + values[i] for i in (0, 1)]
                scores[f"{metric}_delta"] = values[1] - values[0]
        rows.append({"case_id": key, "baseline": pair[0], "proposed": pair[1], "scores": scores})
    improved = successes[1] > successes[0]
    summary: dict[str, Any] = {
        "baseline_completed": successes[0],
        "proposed_completed": successes[1],
        "examples": len(old),
        "matched_successes": matched,
    }
    for metric, values in totals.items():
        summary[metric] = {
            "baseline": values[0] / matched if matched else None,
            "proposed": values[1] / matched if matched else None,
        }
        if matched and values[1] > values[0] + 1e-9:
            reasons.append(f"Matched successful plans regress on {metric}")
        if matched and values[1] < values[0] - 1e-9:
            improved = True
    if not improved:
        reasons.append("No demonstrated improvement")
    return EvaluationResult("loop", not reasons, tuple(reasons), summary, tuple(rows))


def evaluate_check_change(
    cases: list[dict], baseline: list[dict], proposed: list[dict]
) -> EvaluationResult:
    """Replay cached labels only against byte-identical candidate/setup/verifier inputs."""
    frozen, old, new = _indexed(cases), _indexed(baseline), _indexed(proposed)
    if frozen.keys() != old.keys() or old.keys() != new.keys():
        raise ValueError("Every frozen case must have both check results")
    if {case.get("label") for case in cases} != {"valid", "invalid"}:
        raise ValueError("Check evaluation needs both simulator-labeled valid and invalid examples")
    reasons, rows = [], []
    totals = [{"caught": 0, "false_rejections": 0, "runtime_ms": 0.0} for _ in (0, 1)]
    for key, case in sorted(frozen.items()):
        if not case.get("verification_evidence"):
            raise ValueError("Frozen simulator labels require evidence")
        for i, row in enumerate((old[key], new[key])):
            _same_inputs(case, row)
            if type(row.get("passed")) is not bool:
                raise ValueError("Check result must be explicit passed bool")
            totals[i]["runtime_ms"] += _number(row.get("runtime_ms"), "runtime_ms")
            totals[i]["caught"] += int(case["label"] == "invalid" and not row["passed"])
            totals[i]["false_rejections"] += int(case["label"] == "valid" and not row["passed"])
        if case["label"] == "valid" and not new[key]["passed"]:
            reasons.append(f"Proposed checks reject a simulator-valid plan: {key}")
        if case["label"] == "invalid" and not old[key]["passed"] and new[key]["passed"]:
            reasons.append(f"Previously caught failure escapes on {key}")
        rows.append(
            {
                "case_id": key,
                "case": case,
                "baseline": old[key],
                "proposed": new[key],
                "scores": {
                    "baseline_caught": case["label"] == "invalid" and not old[key]["passed"],
                    "proposed_caught": case["label"] == "invalid" and not new[key]["passed"],
                    "proposed_false_rejection": case["label"] == "valid" and not new[key]["passed"],
                },
            }
        )
    improved = (
        totals[1]["caught"] > totals[0]["caught"]
        or totals[1]["false_rejections"] < totals[0]["false_rejections"]
        or totals[1]["runtime_ms"] < totals[0]["runtime_ms"] - 1e-9
    )
    if totals[1]["runtime_ms"] > totals[0]["runtime_ms"] + 1e-9:
        reasons.append("Check runtime regressed")
    if not improved:
        reasons.append("No demonstrated improvement")
    return EvaluationResult(
        "checks",
        not reasons,
        tuple(reasons),
        {"baseline": totals[0], "proposed": totals[1], "examples": len(cases)},
        tuple(rows),
    )


class VersionStore:
    """Content-addressed artifacts and an atomically replaced production pointer.

    The controller owns this directory; generated code must never receive write access.
    Promotion uses compare-and-swap under a process lock, preserving prior versions.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        (self.root / "objects").mkdir(parents=True, exist_ok=True)

    def put(self, kind: str, content: Any) -> str:
        if kind not in KINDS | {"dataset", "evaluation", "publication"}:
            raise ValueError("Unsupported version kind")
        value = {"kind": kind, "content": content}
        ref = digest(value)
        path = self.root / "objects" / f"{ref}.json"
        if not path.exists():
            self._write(path, value)
        self.get(ref)  # Detect corruption even when the object already existed.
        return ref

    def get(self, ref: str) -> dict:
        if len(ref) != 64 or any(c not in "0123456789abcdef" for c in ref):
            raise ValueError("Expected immutable SHA-256 reference")
        value = json.loads((self.root / "objects" / f"{ref}.json").read_text())
        if digest(value) != ref:
            raise ValueError("Version content changed after freezing")
        return value

    @staticmethod
    def _write(path: Path, value: Any) -> None:
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".version-")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def active(self) -> dict[str, str]:
        path = self.root / "production.json"
        return json.loads(path.read_text()).get("versions", {}) if path.exists() else {}

    def initialize(self, kind: str, ref: str) -> None:
        """One-time trusted baseline registration, never a candidate promotion shortcut."""
        self._activate(kind, ref, expected=None, reason="initial baseline")

    def _activate(self, kind: str, ref: str, expected: str | None, reason: str) -> None:
        import fcntl

        if kind not in KINDS or self.get(ref)["kind"] != kind:
            raise ValueError("Version kind does not match pointer")
        with (self.root / ".promotion.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            versions = self.active()
            if versions.get(kind) != expected:
                raise ValueError(
                    "Production version changed; evaluate against the current baseline"
                )
            versions[kind] = ref
            path = self.root / "production.json"
            history = json.loads(path.read_text()).get("history", []) if path.exists() else []
            history.append({"kind": kind, "previous": expected, "version": ref, "reason": reason})
            self._write(path, {"versions": versions, "history": history})

    def promote(
        self,
        kind: str,
        baseline_ref: str,
        proposed_ref: str,
        result: EvaluationResult,
        publication: dict,
    ) -> None:
        self.get(baseline_ref)
        if not result.eligible:
            raise ValueError("Evaluation rejected promotion: " + "; ".join(result.reasons))
        if (
            publication.get("status") != "published"
            or publication.get("result_digest") != result.digest
            or publication.get("baseline_ref") != baseline_ref
            or publication.get("proposed_ref") != proposed_ref
            or not publication.get("weave_refs")
        ):
            raise ValueError("Promotion needs matching, successfully published Weave evaluation")
        if (kind == "checks") != (result.kind == "checks"):
            raise ValueError("Evaluation kind does not match change")
        self._activate(kind, proposed_ref, baseline_ref, reason=f"Weave evaluation {result.digest}")

    def rollback(self, kind: str, expected: str, previous: str) -> None:
        path = self.root / "production.json"
        history = json.loads(path.read_text()).get("history", []) if path.exists() else []
        if not any(row["kind"] == kind and row["version"] == previous for row in history):
            raise ValueError("Rollback target must have been previously active")
        self._activate(kind, previous, expected, reason="rollback")


def publish_evaluation(
    project: str,
    result: EvaluationResult,
    *,
    baseline_ref: str,
    proposed_ref: str,
    dataset_ref: str,
    frozen_cases: list[dict] | None = None,
    version_artifacts: dict[str, Any] | None = None,
) -> dict:
    """Publish real paired Weave evaluations; read both server calls before success.

    Needs configured W&B credentials. Exceptions propagate; no local-mode success or
    synthetic URL is ever substituted for successful publication. This function does
    not activate a version. Invoke from the trusted controller, never agent code.
    """
    if not project or len(project.split("/")) != 2:
        raise ValueError("Use explicit Weave entity/project")
    import weave

    client = weave.init(project)
    dataset = weave.Dataset(
        name=f"cnc-cases-{dataset_ref[:12]}",
        rows=frozen_cases
        or [
            {
                "case_id": row["case_id"],
                "input_hash": row["baseline"]["input_hash"],
                "verifier_hash": row["baseline"]["verifier_hash"],
            }
            for row in result.rows
        ],
    )
    dataset_uri = weave.publish(dataset).uri()
    refs = []
    for variant, version in (("baseline", baseline_ref), ("proposed", proposed_ref)):
        logger = weave.EvaluationLogger(
            name=f"cnc-{result.kind}-{variant}-{version[:12]}",
            model={
                "version": version,
                "variant": variant,
                "artifact": (version_artifacts or {}).get(version),
            },
            dataset=dataset,
            eval_attributes={"result_digest": result.digest, "frozen_dataset_ref": dataset_ref},
        )
        for row in result.rows:
            with logger.log_prediction(
                inputs={
                    "case_id": row["case_id"],
                    "input_hash": row[variant]["input_hash"],
                    "verifier_hash": row[variant]["verifier_hash"],
                },
                output=row[variant],
                example_id=row["case_id"],
            ) as prediction:
                if result.kind == "loop":
                    prediction.log_score("verified", row[variant]["verified"])
                    if row[variant]["verified"]:
                        for name in ("machining_seconds", "cost", "simulation_attempts"):
                            prediction.log_score(name, row[variant][name])
                else:
                    prediction.log_score("caught", row["scores"][f"{variant}_caught"])
                    prediction.log_score(
                        "false_rejection",
                        row["case"]["label"] == "valid" and not row[variant]["passed"],
                    )
                    prediction.log_score("runtime_ms", row[variant]["runtime_ms"])
        logger.log_summary(
            {
                "promotion_eligible": result.eligible,
                "reasons": list(result.reasons),
                "paired_summary": result.summary,
            },
            auto_summarize=False,
        )
        # EvaluationLogger currently exposes its evaluation call via this field.
        # Read-back fails closed if SDK compatibility changes or the upload failed.
        call = logger._evaluate_call
        if call is None:
            raise RuntimeError("Weave did not create an evaluation call")
        client.flush()
        remote = client.get_call(call.id)
        if remote.ended_at is None or remote.exception:
            raise RuntimeError("Weave evaluation is not successfully finalized on the server")
        refs.append(f"weave:///{project}/call/{call.id}")
    return {
        "status": "published",
        "result_digest": result.digest,
        "baseline_ref": baseline_ref,
        "proposed_ref": proposed_ref,
        "dataset_ref": dataset_ref,
        "dataset_uri": dataset_uri,
        "weave_refs": refs,
    }


class WeaveEvaluationGate:
    """Controller adapter; `runner` executes real baseline/proposed benchmark cases.

    runner(kind, version_ref, frozen_cases, job_context) returns records consumed by
    the scoring functions. No synthetic examples or invented scores are supplied.
    """

    def __init__(
        self,
        store: VersionStore,
        project: str,
        dataset_ref: str,
        runner: Any,
        publisher: Any = publish_evaluation,
    ):
        self.store, self.project, self.dataset_ref = store, project, dataset_ref
        self.runner, self.publisher = runner, publisher

    def evaluate(self, proposal: Any, context: Any) -> Any:
        from .models import PromotionResult

        try:
            if proposal.kind not in KINDS:
                raise ValueError("Unsupported reusable change")
            for ref in (proposal.base_version, proposal.proposed_version):
                if self.store.get(ref)["kind"] != proposal.kind:
                    raise ValueError("Proposal version kind mismatch")
            if self.store.active().get(proposal.kind) != proposal.base_version:
                raise ValueError("Proposal is not based on current production version")
            dataset = self.store.get(self.dataset_ref)
            if dataset["kind"] != "dataset":
                raise ValueError("Expected frozen evaluation dataset")
            cases = dataset["content"]
            indexed = _indexed(cases)
            runs = []
            for version in (proposal.base_version, proposal.proposed_version):
                records = self.runner(
                    proposal.kind, version, json.loads(json.dumps(cases)), context
                )
                if _indexed(records).keys() != indexed.keys():
                    raise ValueError("Runner did not evaluate every frozen example")
                for record in records:
                    _same_inputs(indexed[record["case_id"]], record)
                    if record.get("version_ref") != version:
                        raise ValueError("Runner result does not identify the evaluated version")
                runs.append(records)
            result = (
                evaluate_check_change(cases, *runs)
                if proposal.kind == "checks"
                else evaluate_loop_change(*runs)
            )
            result_ref = self.store.put("evaluation", asdict(result))
            publication = self.publisher(
                self.project,
                result,
                baseline_ref=proposal.base_version,
                proposed_ref=proposal.proposed_version,
                dataset_ref=self.dataset_ref,
                frozen_cases=cases,
                version_artifacts={
                    ref: self.store.get(ref)
                    for ref in (proposal.base_version, proposal.proposed_version)
                },
            )
            receipt_ref = self.store.put("publication", publication)
            evidence = (
                str(self.store.root / "objects" / f"{result_ref}.json"),
                str(self.store.root / "objects" / f"{receipt_ref}.json"),
                *publication["weave_refs"],
            )
            if not result.eligible:
                return PromotionResult(proposal.id, False, "; ".join(result.reasons), evidence)
            self.store.promote(
                proposal.kind, proposal.base_version, proposal.proposed_version, result, publication
            )
            return PromotionResult(proposal.id, True, "Passed paired Weave evaluation", evidence)
        except Exception as exc:
            return PromotionResult(proposal.id, False, f"Evaluation not promoted: {exc}", ())
