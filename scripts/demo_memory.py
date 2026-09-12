"""Reproducible three-attempt cold run versus one-attempt durable-memory run.

Run with: python scripts/demo_memory.py
Uses a new local directory, deterministic fixture repairs, and real checks/simulation.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from silta.controller import JobController, JobRequest
from silta.domain import Budget
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan, reach_repaired_plan, valid_plan
from silta.memory import LearningMemory
from silta.planner import PlanResult
from silta.storage import LocalStorage


async def main():
    root = Path(tempfile.mkdtemp(prefix="silta-memory-demo-"))
    calls = 0

    async def planner(request, provider):
        nonlocal calls
        calls += 1
        plan = reach_repaired_plan() if calls == 1 else valid_plan()
        return PlanResult(plan, "repair", None, None, ())

    report = {"backend": "LocalStorage", "inference": "deterministic fixture repairs", "runs": []}
    for name in ("cold", "warm"):
        # Deliberately construct new instances: warm run must read disk, not Python state.
        memory = LearningMemory(LocalStorage(root / "memory"))
        controller = JobController(memory=memory, planner=planner)
        request = JobRequest(
            session_id=name,
            spec=DEMO_SPEC,
            shop=DEMO_SHOP,
            seed_plan=naive_plan(),
            budget=Budget(max_attempts=3),
            origin="fixture",
            artifact_dir=root / name,
        )
        before = calls
        events = [event async for event in controller.run(request)]
        outcome = controller.outcomes[request.job_id]
        report["runs"].append(
            {
                "name": name,
                "job_id": request.job_id,
                "attempts": len(outcome.attempts),
                "planner_calls": calls - before,
                "fresh_simulations": sum(e.type == "simulation_started" for e in events),
                "state": outcome.state.value,
                "source": outcome.attempts[0].plan_source,
            }
        )
    report["evidence_directory"] = str(root)
    assert [r["attempts"] for r in report["runs"]] == [3, 1]
    assert report["runs"][1]["fresh_simulations"] == 1
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
