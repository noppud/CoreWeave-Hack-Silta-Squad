"""The authoritative repair / simulation / optimization / evaluated-learning loops."""

import copy
import time
from pathlib import Path

from cncsim import simulate

from .common import candidate, cheap_checks, digest, freeze_job, load_job, save, verify_frozen
from .learning import Knowledge, context_for
from .playback import export_playback


def run_job(job_path, workspace, run_id, roles_factory, *, max_attempts=5, guidance_evaluations=1):
    if not 1 <= max_attempts <= 20 or not 0 <= guidance_evaluations <= 2:
        raise ValueError("Attempt/evaluation budget out of range")
    root = Path(workspace).resolve()
    directory = root / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    roles = roles_factory(directory / "evidence")
    manifest = dict(
        id=run_id,
        status="running",
        stage="initializing",
        mode=roles.mode,
        started_at=time.time(),
        attempts=[],
        events=[],
        best=None,
        learning=[],
        job_id=None,
        objective="estimated_time_seconds",
        reason="",
        model="gpt-6-astra" if roles.mode == "astra" else None,
    )

    def event(kind, **data):
        manifest["events"].append(dict(type=kind, time=time.time(), **data))
        manifest["stage"] = kind
        save(directory / "manifest.json", manifest)
        print(f"{run_id}: {kind}", flush=True)

    try:
        job, fingerprint = freeze_job(load_job(job_path), directory / "frozen")
        knowledge = Knowledge(root / "knowledge", roles.mode, root / "corpus/index.json")
        manifest.update(
            job_id=job["id"],
            target_hash=fingerprint["meshes"][job["plan"]["target"]["path"]],
            loaded_knowledge=copy.deepcopy(knowledge.state),
            feature=job["feature"],
        )
        event(
            "target_frozen",
            knowledge_version=knowledge.state["version"],
            rules=knowledge.state["rules"],
        )
        previous = job["plan"]
        feedback, instructions = {}, ""
        check_attempted, guidance_attempted = False, 0
        for attempt in range(max_attempts):
            verify_frozen(job, fingerprint)
            path = directory / f"attempt-{attempt:03d}"
            path.mkdir()
            row = dict(
                index=attempt,
                summary="",
                stage="planning",
                result=None,
                playback=None,
                source="supplied_seed" if attempt == 0 else roles.mode,
                knowledge_version=knowledge.state["version"],
            )
            manifest["attempts"].append(row)
            if attempt == 0:
                plan = copy.deepcopy(previous)
                row["summary"] = (
                    "Supplied starting plan"
                    if job["family"] == "capsule_pocket"
                    else "Supplied starting plan"
                )
            else:
                event("planning_started", attempt=attempt)
                response, evidence = roles.ask(
                    "planner",
                    context_for(
                        job,
                        previous,
                        feedback,
                        knowledge.state["guidance"],
                        knowledge.state["rules"],
                        instructions,
                    ),
                )
                save(path / "proposal.json", dict(value=response, evidence=evidence))
                try:
                    plan = candidate(job, response)
                    row["summary"] = response["summary"]
                except (ValueError, TypeError, KeyError, AttributeError) as error:
                    feedback = dict(stage="checks", issues=[str(error)])
                    row.update(
                        stage="check_failed",
                        result=dict(
                            validity="invalid", passed=False, issues=[dict(description=str(error), moves=[])]
                        ),
                    )
                    event("checks_failed", attempt=attempt, feedback=feedback)
                    continue
            verify_frozen(job, fingerprint)
            save(path / "plan.json", plan)
            fixed_candidate = digest(plan)
            checks = cheap_checks(job, plan, knowledge.state["rules"])
            previous = plan
            if checks:
                row.update(
                    stage="check_failed",
                    result=dict(validity="invalid", passed=False, issues=checks, estimated_time_seconds=None),
                )
                feedback = dict(stage="checks", issues=checks)
                event("checks_failed", attempt=attempt, issues=checks)
                continue
            event("simulation_started", attempt=attempt)
            result = simulate(plan, output_dir=path / "simulation")
            if digest(plan) != fixed_candidate:
                raise ValueError("Simulation altered candidate")
            verify_frozen(job, fingerprint)
            row.update(stage="simulated", result=result)
            if "artifacts" in result:
                try:
                    export_playback(plan, path / "simulation")
                    row["playback"] = f"attempt-{attempt:03d}/simulation/playback.json"
                except ValueError as error:
                    row["visualization_error"] = str(error)
                    event("visualization_failed", attempt=attempt, reason=str(error))
            event(
                "simulation_completed",
                attempt=attempt,
                validity=result["validity"],
                seconds=result["estimated_time_seconds"],
            )
            if result["validity"] != "valid":
                feedback = dict(stage="simulation", result=result)
                if result.get("verification") == "unresolved" or result["validity"] == "unknown":
                    # Never relax resolution/tolerance to manufacture a pass.
                    event("simulation_failed", attempt=attempt, reason="Numerical clearance could not be verified")
                elif not check_attempted:
                    check_attempted = True
                    event("check_learning_started", attempt=attempt)
                    proposal, evidence = roles.ask(
                        "check_learner",
                        dict(
                            job=job,
                            plan=plan,
                            result=result,
                            active_checks=knowledge.state["rules"],
                        ),
                    )
                    if proposal["rule"] != "none":
                        evaluation = knowledge.evaluate_check(proposal["rule"])
                        manifest["learning"].append(
                            dict(
                                proposal=proposal, proposal_evidence=evidence, evaluation=evaluation
                            )
                        )
                        event(
                            "check_evaluated",
                            promoted=evaluation["promoted"],
                            knowledge_version=knowledge.state["version"],
                        )
                continue
            seconds = result["estimated_time_seconds"]
            if manifest["best"] is None or seconds < manifest["best"]["seconds"]:
                manifest["best"] = dict(
                    attempt=attempt,
                    seconds=seconds,
                    plan=f"attempt-{attempt:03d}/plan.json",
                    playback=row["playback"],
                )
                save(directory / "best-plan.json", plan)
                event("best_updated", attempt=attempt, seconds=seconds)
            event("supervisor_started", attempt=attempt)
            decision, evidence = roles.ask(
                "supervisor",
                dict(
                    objective="Minimize estimated machining seconds among passing plans",
                    current_seconds=seconds,
                    time_breakdown=result["time_breakdown"],
                    best_seconds=manifest["best"]["seconds"],
                    verified_time_history=[a["result"]["estimated_time_seconds"] for a in manifest["attempts"]
                        if a.get("result") and a["result"]["validity"] == "valid"],
                    active_guidance=knowledge.state["guidance"],
                    guidance_evaluation_available=guidance_attempted < guidance_evaluations,
                    attempts_remaining=max_attempts - attempt - 1,
                ),
            )
            if decision["action"] not in ("improve", "stop"):
                raise ValueError("Unsupported supervisor action")
            row["supervisor"] = dict(value=decision, evidence=evidence)
            proposal = decision.get("guidance_proposal")
            if proposal and guidance_attempted < guidance_evaluations:
                guidance_attempted += 1
                event("guidance_learning_started")
                evaluation = knowledge.evaluate_guidance(proposal, roles, event)
                manifest["learning"].append(
                    dict(proposal=proposal, proposal_evidence=evidence, evaluation=evaluation)
                )
                event(
                    "guidance_evaluated",
                    promoted=evaluation["promoted"],
                    knowledge_version=knowledge.state["version"],
                )
            if decision["action"] == "stop":
                manifest.update(
                    status="completed", reason="Supervisor selected the fastest verified valid plan"
                )
                event("completed", best=manifest["best"])
                break
            instructions = "The timing judge requests another faster candidate. Independently plan it, keeping all fixed constraints; it must pass checks and simulation again."
            import json

            previous = json.loads((directory / manifest["best"]["plan"]).read_text())
            feedback = dict(stage="supervisor", best=manifest["best"], last_result=result)
        else:
            manifest.update(
                status="incomplete",
                reason="Operational attempt limit reached; retained best is not a supervisor stop",
            )
            event("attempt_limit")
        manifest["final_knowledge"] = copy.deepcopy(knowledge.state)
    except Exception as error:
        manifest.update(status="incomplete", reason=f"{type(error).__name__}: {error}")
        event("interrupted", reason=manifest["reason"])
    manifest["finished_at"] = time.time()
    save(directory / "manifest.json", manifest)
    return manifest
