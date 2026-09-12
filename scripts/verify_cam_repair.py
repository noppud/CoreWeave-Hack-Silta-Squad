"""Exercise measured CAM repair on the synthetic part; --live uses configured inference."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from silta.controller import JobController, JobRequest
from silta.domain import Budget, JobState
from silta.fixtures import DEMO_SHOP, DEMO_SPEC, naive_plan
from silta.providers import WandbInferenceProvider, load_provider_from_env
from silta.telemetry import Telemetry


async def run(live):
    config = load_provider_from_env("planner") if live else None
    if live and config is None:
        raise SystemExit("No planner inference provider configured.")
    provider = WandbInferenceProvider(config) if config else None
    request = JobRequest(
        session_id="cam-repair-verification",
        spec=DEMO_SPEC,
        shop=DEMO_SHOP,
        seed_plan=naive_plan(),
        memory_enabled=False,
        origin="fixture",
        budget=Budget(max_attempts=3, max_model_calls=3, job_deadline_s=120),
    )
    controller = JobController(provider=provider, telemetry=Telemetry())
    events = []
    try:
        async for event in controller.run(request):
            events.append(event.model_dump(mode="json"))
            if event.type == "attempt_completed":
                print(
                    json.dumps(
                        {
                            "attempt": event.payload.get("attempt"),
                            "disposition": event.payload.get("disposition"),
                            "blocking": event.payload.get("blocking"),
                        }
                    ),
                    flush=True,
                )
    finally:
        if provider:
            await provider.close()
    outcome = controller.outcomes[request.job_id]
    evidence_dir = Path("artifacts") / request.job_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "repair-events.json").write_text(json.dumps(events, indent=2) + "\n")
    summary = {
        "job_id": request.job_id,
        "state": outcome.state.value,
        "message": outcome.message,
        "attempts": len(outcome.attempts),
        "planner_sources": [a.plan_source for a in outcome.attempts],
        "model_calls": sum(a.usage.calls for a in outcome.attempts if a.usage),
        "model": config.model if config else None,
        "fallbacks": [e["payload"] for e in events if e["type"] == "planner_fallback"],
        "evidence": str(evidence_dir / "repair-events.json"),
    }
    (evidence_dir / "repair-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if outcome.state is JobState.PASSED and not summary["fallbacks"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    raise SystemExit(asyncio.run(run(parser.parse_args().live)))
