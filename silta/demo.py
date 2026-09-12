"""Reproducible presenter fixture with real CAD, checks, simulation and disk memory."""

from __future__ import annotations

import tempfile
from pathlib import Path

from silta.controller import JobController, JobRequest
from silta.domain import Budget
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan, reach_repaired_plan, valid_plan
from silta.memory import LearningMemory
from silta.planner import PlanResult
from silta.policy import POLICY_V0
from silta.storage import LocalStorage
from silta.telemetry import Telemetry


async def prepare_demo():
    root = Path(tempfile.mkdtemp(prefix="silta-presenter-"))
    calls = 0

    async def fixture_planner(request, provider):
        nonlocal calls
        calls += 1
        plan = reach_repaired_plan() if calls == 1 else valid_plan()
        return PlanResult(plan, "repair", None, None, ())

    outcomes, rows = {}, []
    for name in ("cold", "warm"):
        memory = LearningMemory(LocalStorage(root / "memory"))
        controller = JobController(memory=memory, planner=fixture_planner, telemetry=Telemetry())
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
        events = [e async for e in controller.run(request)]
        outcome = controller.outcomes[request.job_id]
        if outcome.best_attempt is None:
            raise RuntimeError(f"The {name} fixture did not pass; inspect the current validators.")
        outcomes[name] = outcome
        rows.append(
            {
                "Run": name.title(),
                "Attempts": len(outcome.attempts),
                "Planner calls": calls - before,
                "Fresh simulations": sum(e.type == "simulation_started" for e in events),
            }
        )
    return {
        "outcomes": outcomes,
        "comparison": rows,
        "root": root,
        "memory": memory.inspect("warm", DEMO_SPEC, DEMO_SHOP, POLICY_V0),
    }
