"""Durable evidence memory. Exact-context recipes always undergo fresh verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from silta.domain import Attempt, Disposition, PartSpec, ProcessPlan, ShopProfile, stable_hash
from silta.fixtures import DEMO_SHOP, DEMO_SPEC
from silta.policy import Policy
from silta.storage import Storage

MEMORY_VERSION = "memory-1"
# Only trusted diagnostic codes become advice; free-text model output is not policy.
LESSON_TEXT = {
    "tool_cutting_reach": (
        "Choose an inventory tool whose cutting length reaches the feature depth."
    ),
    "simulation_collision": (
        "Put non-cutting traverses above fixtures plus the shop clearance margin."
    ),
    "simulation_residual_stock": (
        "Cover the full target feature depth and area; verify residual stock."
    ),
    "simulation_gouge": "Keep cutting inside the target removal volume; verify remaining geometry.",
}


@lru_cache(maxsize=1)
def validator_fingerprint() -> str:
    root = Path(__file__).parent
    return stable_hash(
        {
            name: (root / name).read_text()
            for name in (
                "cad.py",
                "checks.py",
                "domain.py",
                "policy.py",
                "simulation.py",
                "toolpaths.py",
            )
        }
    )


@dataclass(frozen=True)
class MemoryRecall:
    context: str
    scope: str
    episode_ids: tuple[str, ...] = ()
    lesson_ids: tuple[str, ...] = ()
    instructions: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    recipe: ProcessPlan | None = None
    recipe_episode_id: str | None = None


class LearningMemory:
    def __init__(self, storage: Storage):
        self.storage = storage
        # Keys that could not be read or validated, for diagnosis. Never fatal.
        self.skipped: list[str] = []

    def namespace(self, session_id: str, spec: PartSpec, shop: ShopProfile, policy: Policy):
        # Only the exact public synthetic fixture shares memory across browser sessions.
        public_demo = (
            spec.spec_id == DEMO_SPEC.spec_id
            and not spec.source_asset_ids
            and spec.design_hash == DEMO_SPEC.design_hash
            and shop.shop_hash == DEMO_SHOP.shop_hash
        )
        scope = "public-demo" if public_demo else "session-" + stable_hash(session_id)[:24]
        context = stable_hash(
            {
                "version": MEMORY_VERSION,
                "design": spec.design_hash,
                "shop": shop.shop_hash,
                "policy": {
                    "version": policy.version,
                    "rules": policy.planner_rules,
                    "checks": sorted(policy.promoted_checks),
                },
                "validator": validator_fingerprint(),
            }
        )
        return scope, context, f"memory/{scope}/{context}"

    def _read_collection(self, prefix: str, collection: str) -> list[dict]:
        # Immutable objects avoid a shared append/overwrite race across Cloud Run workers.
        # A single unreadable object must not take the namespace down with it: the
        # public demo shares one namespace across every visitor, so one truncated or
        # half-written blob would otherwise crash every later job. Skip what cannot be
        # read and carry on with the rest.
        keys = self.storage.list_prefix(f"{prefix}/{collection}/")
        entries: list[dict] = []
        for key in sorted(keys):
            if not key.endswith(".json"):
                continue
            try:
                entry = json.loads(self.storage.get_bytes(key))
            except (json.JSONDecodeError, UnicodeDecodeError, OSError, ValueError):
                self.skipped.append(key)
                continue
            if isinstance(entry, dict):
                entries.append(entry)
            else:
                self.skipped.append(key)
        return entries

    def recall(self, session_id, spec, shop, policy) -> MemoryRecall:
        scope, context, prefix = self.namespace(session_id, spec, shop, policy)
        episodes = [
            e
            for e in self._read_collection(prefix, "episodes")
            if {"finished_at", "episode_id", "disposition", "attempt"} <= e.keys()
        ]
        episodes.sort(key=lambda e: (str(e["finished_at"]), str(e["episode_id"])))
        usable = []
        for e in episodes:
            if e["disposition"] != Disposition.PASSED.value:
                continue
            try:
                attempt = Attempt.model_validate(e["attempt"])
            except ValidationError:
                # An episode written by an older contract version is not usable now.
                self.skipped.append(e["episode_id"])
                continue
            if (
                attempt.plan
                and attempt.simulation
                and attempt.simulation.passed
                and not attempt.blocking_failures
            ):
                if (
                    attempt.plan.spec_design_hash == spec.design_hash
                    and attempt.plan.shop_hash == shop.shop_hash
                ):
                    usable.append((e, attempt.plan))
        recipe = usable[-1] if usable else None
        validations = self._read_collection(prefix, "validations")
        active = {v["lesson_id"] for v in validations if v.get("status") == "passed"}
        lessons = self._read_collection(prefix, "lessons")
        selected = list(
            {
                lesson["lesson_id"]: lesson for lesson in lessons if lesson["lesson_id"] in active
            }.values()
        )[-5:]
        return MemoryRecall(
            context=context,
            scope=scope,
            episode_ids=tuple(e["episode_id"] for e in episodes[-12:]),
            lesson_ids=tuple(lesson["lesson_id"] for lesson in selected),
            instructions=tuple(lesson["instruction"] for lesson in selected),
            observations=tuple(
                json.dumps(
                    {
                        "episode_id": e["episode_id"],
                        "check_id": check["check_id"],
                        "actual": check.get("actual"),
                        "required": check.get("required"),
                        "units": check.get("units"),
                    }
                )
                for e in episodes[-6:]
                for check in e["attempt"]["checks"]
                if check["status"] == "fail"
            )[-12:],
            recipe=recipe[1] if recipe else None,
            recipe_episode_id=recipe[0]["episode_id"] if recipe else None,
        )

    def record(self, session_id, spec, shop, policy, attempt: Attempt) -> dict:
        scope, context, prefix = self.namespace(session_id, spec, shop, policy)
        episode = {
            "episode_id": attempt.attempt_id,
            "context": context,
            "scope": scope,
            "finished_at": attempt.finished_at.isoformat(),
            "disposition": attempt.disposition.value,
            "attempt": attempt.model_dump(mode="json"),
        }
        self._put(f"{prefix}/episodes/{attempt.attempt_id}.json", episode)
        lessons = []
        for failure in attempt.blocking_failures:
            instruction = LESSON_TEXT.get(failure.check_id)
            if not instruction:
                continue
            lesson_id = (
                "lesson-" + stable_hash({"context": context, "check": failure.check_id})[:20]
            )
            lesson = {
                "lesson_id": lesson_id,
                "status": "proposed",
                "instruction": instruction,
                "check_id": failure.check_id,
                "source_episode_id": attempt.attempt_id,
                "context": context,
                "scope": scope,
            }
            # One immutable proposal per observed failure; no lost shared update.
            self._put(f"{prefix}/lessons/{lesson_id}-{attempt.attempt_id}.json", lesson)
            lessons.append(lesson_id)
        return {
            "episode_id": attempt.attempt_id,
            "context": context,
            "scope": scope,
            "lesson_ids": lessons,
            "recipe_eligible": attempt.disposition is Disposition.PASSED,
        }

    def inspect(self, session_id, spec, shop, policy) -> dict:
        scope, context, prefix = self.namespace(session_id, spec, shop, policy)
        episodes = self._read_collection(prefix, "episodes")
        # Collapse repeated observations to a bounded instruction, retaining episode provenance.
        lessons = {entry["lesson_id"]: entry for entry in self._read_collection(prefix, "lessons")}
        validations = self._read_collection(prefix, "validations")
        return {
            "scope": scope,
            "context": context,
            "episode_count": len(episodes),
            "episodes": [
                {k: e[k] for k in ("episode_id", "finished_at", "disposition")}
                for e in sorted(episodes, key=lambda e: e["finished_at"])[-20:]
            ],
            "lessons": list(lessons.values()),
            "validations": validations,
            "storage": type(self.storage).__name__,
        }

    def validate(self, session_id, spec, shop, policy, runner) -> list[dict]:
        _, _, prefix = self.namespace(session_id, spec, shop, policy)
        snapshot = self.inspect(session_id, spec, shop, policy)
        passed = {v["lesson_id"] for v in snapshot["validations"] if v["status"] == "passed"}
        reports = []
        for lesson in snapshot["lessons"][:5]:
            if lesson["lesson_id"] in passed:
                continue
            # Current sandbox validator supports one bounded, trusted clearance rule.
            if lesson["check_id"] != "simulation_collision":
                continue
            report = runner.validate(lesson)
            self._put(f"{prefix}/validations/{report['report_id']}.json", report)
            reports.append(report)
        return reports

    def _put(self, key: str, value: dict):
        return self.storage.put_bytes(
            key, json.dumps(value, sort_keys=True).encode(), "application/json"
        )
