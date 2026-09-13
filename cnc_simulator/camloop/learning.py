"""Versioned, evidence-gated checks and planner guidance shared across runs."""

import copy
import fcntl
import json
import time
import uuid
from pathlib import Path

from cncsim import simulate

from .common import candidate, cheap_checks, digest, file_hash, save, verify_frozen
from .demo import verifier_digest


def context_for(job, previous, feedback, guidance, rules, instruction=""):
    return dict(
        task="Produce a valid CAM plan, then minimize estimated machining seconds.",
        fixed_job=copy.deepcopy(job),
        previous=copy.deepcopy(previous),
        feedback=copy.deepcopy(feedback),
        active_guidance=guidance,
        active_checks=rules,
        supervisor_instructions=instruction,
        semantics=(
            "Fixed +Z cylinder cutter; absolute XYZ linear moves. Cut retracts are "
            "permitted. "
            "Rapid touching freshly cut stock may be numerically unknown. Feeds must "
            "stay within the job limits. "
            "Dwell and tool changes are optional unless required by the supplied moves. "
            "If final_position is specified, return exactly there; include approach, "
            "retract and return travel. "
            "No part of the target or manufacturing constraints may be changed."
        ),
    )


CHECK_VERSION = "feature-floor-v2"


class Knowledge:
    def __init__(self, root, mode, corpus):
        self.root = Path(root) / mode
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "active.json"
        self.mode, self.corpus = mode, Path(corpus)
        self.state = self.load()

    def load(self):
        if not self.path.exists():
            return dict(version=0, mode=self.mode, rules=[], guidance="", promotions=[])
        state = json.loads(self.path.read_text())
        if state["mode"] != self.mode:
            raise ValueError("Cannot mix rehearsal learning and live Astra learning")
        expected_rules, expected_guidance, expected_version = [], "", 0
        for item in state["promotions"]:
            if file_hash(item["evidence"]) != item["sha256"]:
                raise ValueError("Learning evidence changed")
            evidence = json.loads(Path(item["evidence"]).read_text())
            if (
                not evidence["promoted"]
                or evidence["verifier"] != verifier_digest()
                or evidence.get("check_version") != CHECK_VERSION
            ):
                raise ValueError("Learning requires reevaluation against this verifier")
            if evidence["base_version"] != expected_version or evidence["mode"] != self.mode:
                raise ValueError("Learning history is out of order")
            if evidence["kind"] == "check":
                expected_rules.append(evidence["proposal"])
            elif evidence["kind"] == "guidance":
                expected_guidance = evidence["proposal"]
            else:
                raise ValueError("Unknown learning promotion")
            expected_version += 1
        if (state["version"], state["rules"], state["guidance"]) != (
            expected_version,
            expected_rules,
            expected_guidance,
        ):
            raise ValueError("Active learning does not match evaluated promotions")
        if state["promotions"]:
            self.cases()
        if any(
            rule != {"name": "feature_floor", "family": "capsule_pocket"} for rule in state["rules"]
        ):
            raise ValueError("Unsupported learned rule")
        return state

    def cases(self):
        index = json.loads(self.corpus.read_text())
        if index["verifier"] != verifier_digest():
            raise ValueError("Corpus verifier changed; rebuild the labels")
        cases = []
        for entry in index["cases"]:
            if file_hash(entry["path"]) != entry["sha256"]:
                raise ValueError("Corpus case changed")
            case = json.loads(Path(entry["path"]).read_text())
            verify_frozen(case["job"], case["fingerprint"])
            if digest(case["plan"]) != case["plan_hash"] or case["verifier"] != verifier_digest():
                raise ValueError("Untrusted simulation label")
            cases.append(case)
        return cases

    def finish(self, record, changes):
        record.update(
            mode=self.mode,
            verifier=verifier_digest(),
            base_version=self.state["version"],
            check_version=CHECK_VERSION,
        )
        path = self.root / f"evaluation-{uuid.uuid4().hex[:12]}.json"
        with (self.root / "promotion.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            latest = self.load()
            if latest != self.state:
                record.update(
                    promoted=False, reason="Knowledge changed during evaluation; reevaluate"
                )
            save(path, record)
            if record["promoted"]:
                self.state = {
                    **self.state,
                    **changes,
                    "version": self.state["version"] + 1,
                    "promotions": [
                        *self.state["promotions"],
                        dict(evidence=str(path.resolve()), sha256=file_hash(path)),
                    ],
                }
                save(self.path, self.state)
        return {**record, "evidence": str(path.resolve())}

    def evaluate_check(self, name):
        if name != "feature_floor":
            raise ValueError("Unsupported check proposal")
        proposed = dict(name=name, family="capsule_pocket")
        if proposed in self.state["rules"]:
            return dict(promoted=False, reason="Rule already active")
        rules = [*self.state["rules"], proposed]
        rows = []
        for case in self.cases():
            old = cheap_checks(case["job"], case["plan"], self.state["rules"])
            started = time.perf_counter()
            new = cheap_checks(case["job"], case["plan"], rules)
            rows.append(
                dict(
                    case=case["id"],
                    validity=case["result"]["validity"],
                    baseline_rejected=bool(old),
                    proposed_rejected=bool(new),
                    runtime_seconds=time.perf_counter() - started,
                )
            )
        positives = [r for r in rows if r["validity"] == "valid"]
        improvements = sum(
            r["validity"] == "invalid" and r["proposed_rejected"] and not r["baseline_rejected"]
            for r in rows
        )
        false_rejections = sum(r["proposed_rejected"] for r in positives)
        promoted = len(positives) >= 2 and improvements > 0 and false_rejections == 0
        return self.finish(
            dict(
                kind="check",
                proposal=proposed,
                rows=rows,
                promoted=promoted,
                newly_caught_failures=improvements,
                false_rejections=false_rejections,
                reason=(
                    "Requires two valid controls, zero false rejections and at least one "
                    "newly caught failure"
                ),
            ),
            dict(rules=rules),
        )

    def evaluate_guidance(self, guidance, roles, event=lambda *a, **k: None):
        if not isinstance(guidance, str) or not guidance.strip() or len(guidance) > 2000:
            raise ValueError("Guidance must be a nonempty string of at most 2000 characters")
        cases = [c for c in self.cases() if c["id"].endswith("-valid")][:2]
        rows = []
        for case in cases:
            job = case["job"]
            row = dict(case=case["id"])
            for label, text in [("baseline", self.state["guidance"]), ("proposed", guidance)]:
                event("guidance_evaluation_started", case=case["id"], variant=label)
                response, evidence = roles.ask(
                    "planner", context_for(job, job["plan"], {}, text, self.state["rules"])
                )
                try:
                    plan = candidate(job, response)
                    verify_frozen(job, case["fingerprint"])
                    check = cheap_checks(job, plan, self.state["rules"])
                    result = (
                        simulate(plan)
                        if not check
                        else dict(validity="invalid", estimated_time_seconds=None, issues=check)
                    )
                except (ValueError, TypeError, KeyError) as error:
                    plan = None
                    result = dict(
                        validity="unknown", estimated_time_seconds=None, issues=[str(error)]
                    )
                row[label] = dict(result=result, evidence=evidence, proposal=response, plan=plan)
            rows.append(row)
        old = [r["baseline"]["result"] for r in rows]
        new = [r["proposed"]["result"] for r in rows]

        def valid(r):
            return r["validity"] == "valid"

        no_regression = all(
            not valid(a)
            or (valid(b) and b["estimated_time_seconds"] <= a["estimated_time_seconds"] + 1e-9)
            for a, b in zip(old, new, strict=True)
        )
        improved = any(
            valid(b)
            and (not valid(a) or b["estimated_time_seconds"] < a["estimated_time_seconds"] - 1e-9)
            for a, b in zip(old, new, strict=True)
        )
        promoted = len(rows) >= 2 and no_regression and improved and all(valid(r) for r in new)
        return self.finish(
            dict(
                kind="guidance",
                proposal=guidance,
                rows=rows,
                promoted=promoted,
                reason=(
                    "Paired same-part Astra + simulator evaluation; no valid-case regression "
                    "and measurable improvement required. Small development set, not general "
                    "proof."
                ),
            ),
            dict(guidance=guidance),
        )
