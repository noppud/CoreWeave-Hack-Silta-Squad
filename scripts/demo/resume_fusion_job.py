"""Resume accepted CAD or reverify retained CAM through the normal Astra loop.

Requires the same drawing and manufacturing inputs. Historical evidence stays
unchanged; fresh verification and decisions are written to a new job directory.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from silta.cnc.agents import AstraCheckLearner, AstraMainAgent, AstraSupervisor  # noqa: E402
from silta.cnc.astra import AstraClient  # noqa: E402
from silta.cnc.benchmarks import decode_candidate, decode_target, decode_verification  # noqa: E402
from silta.cnc.cli import read_inputs  # noqa: E402
from silta.cnc.controller import Controller  # noqa: E402
from silta.cnc.fixed_verifier import VERIFIER_VERSION, FixedFusionVerifier  # noqa: E402
from silta.cnc.fusion import FusionBridge  # noqa: E402
from silta.cnc.learning import SharedLearning  # noqa: E402
from silta.cnc.tracing import trace_controller  # noqa: E402


def retained_plan(source):
    result = source.get("result") or source
    candidate = result.get("best_candidate") or next(
        (e["candidate"] for e in reversed(source["events"]) if e["event"] == "candidate_created"),
        None,
    )
    verification = result.get("best_verification")
    if verification and candidate is None:
        raise ValueError("Source verdict has no retained candidate")
    return candidate, verification


def selected_trial(path, candidate_id, input_digest, target):
    """Nominate exact retained CAM bytes; never inherit this source's verdict."""
    path = Path(path).resolve()
    raw = path.read_bytes()
    source = json.loads(raw)
    if source.get("input_digest") != input_digest:
        raise ValueError("Trial requires unchanged drawing and manufacturing inputs")
    source_target = decode_target(source["target"])
    source_target.verify()
    if source.get("target_digest") != target.digest or source_target.digest != target.digest:
        raise ValueError("Trial requires the same accepted target")
    matches = [
        (index, event["candidate"])
        for index, event in enumerate(source.get("events", []))
        if event.get("event") == "candidate_created"
        and event.get("candidate", {}).get("id") == candidate_id
    ]
    if len(matches) != 1:
        raise ValueError("Trial candidate ID must select exactly one candidate_created event")
    index, retained = matches[0]
    candidate = decode_candidate(retained)
    if candidate.target_digest != target.digest:
        raise ValueError("Trial candidate does not match the accepted target")
    candidate.verify()
    return candidate, {
        "event": "manual_trial_nomination",
        "manual_nomination": True,
        "source_manifest": str(path),
        "source_manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "source_job_id": source.get("job_id"),
        "source_event_index": index,
        "candidate_id": candidate.id,
        "candidate_digest": candidate.digest,
        "input_digest": input_digest,
        "target_digest": target.digest,
        "collection_warning": source.get("collection_warning"),
        "old_verdict_inherited": False,
        "scope": "Manual retained-candidate hypothesis; not learned or supervisor-selected. "
        "requires current checks and fresh simulation before comparison.",
    }


def recovery_learning(directory):
    """Reuse existing state explicitly; never silently seed a missing shadow copy."""
    directory = Path(directory).resolve()
    files = {name: directory / name for name in ("checks.py", "cad_cam.md")}
    if not all(path.is_file() for path in files.values()):
        raise ValueError("Recovery learning directory requires existing checks.py and cad_cam.md")
    provenance = {
        "learning_directory": str(directory),
        "recovery_not_fresh_preparation": True,
        "uses_main_learning_directory": directory == (ROOT / "learning").resolve(),
        "initial_file_sha256": {
            name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()
        },
    }
    return SharedLearning(directory), provenance


class PlaybackVerifier:
    """Optional presentation after verification; return the original verdict unchanged."""

    def __init__(self, verifier, show, bridge, directory, receipts, seconds=15):
        self.verifier, self.show, self.bridge = verifier, show, bridge
        self.directory, self.receipts, self.seconds = directory, receipts, seconds

    def verify(self, candidate, context):
        verdict = self.verifier.verify(candidate, context)
        if verdict.status == "passed" and verdict.completed:
            try:
                receipt = self.show(
                    candidate, self.bridge, self.directory / candidate.id, seconds=self.seconds
                )
            except Exception as error:
                receipt = {
                    "candidate_id": candidate.id,
                    "status": "presentation_failed",
                    "error": str(error),
                    "meaning": "Presentation only; verdict unchanged",
                }
            self.receipts.append(receipt)
        return verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--learning-directory", type=Path, default=ROOT / "learning")
    parser.add_argument("--api-docs", nargs="*", default=[])
    parser.add_argument("--show-playback", action="store_true")
    parser.add_argument("--playback-seconds", type=int, choices=range(1, 31), default=15)
    parser.add_argument("--trial-source", type=Path)
    parser.add_argument("--trial-candidate-id")
    args = parser.parse_args()
    if bool(args.trial_source) != bool(args.trial_candidate_id):
        parser.error("--trial-source and --trial-candidate-id must be provided together")
    lock = (ROOT / "runs/.fusion-campaign.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    source_bytes = args.source.read_bytes()
    source = json.loads(source_bytes)
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    inputs = read_inputs(args.config.resolve())
    if inputs.digest != source["input_digest"]:
        raise ValueError("A resumed job requires unchanged drawing and manufacturing inputs")
    target = decode_target(source["target"])
    retained, prior_verdict = retained_plan(source)
    candidate = decode_candidate(retained) if retained else None
    verification = decode_verification(prior_verdict) if prior_verdict else None
    target.verify()
    if candidate:
        candidate.verify()
    if verification and (verification.status != "passed" or not verification.completed):
        raise ValueError("Source does not contain a completed verified incumbent")
    # A backend/version change requires a new baseline, not comparison against
    # an older verdict. Keep the source evidence, but reverify its CAM first.
    compatible_incumbent = bool(
        verification
        and verification.verifier_version == VERIFIER_VERSION
        and not source.get("collection_warning")
    )
    trial, nomination = None, None
    if args.trial_source:
        if not compatible_incumbent:
            raise ValueError("Manual trial requires an incumbent verified by the current verifier")
        trial, nomination = selected_trial(
            args.trial_source, args.trial_candidate_id, inputs.digest, target
        )
    learning, learning_provenance = recovery_learning(args.learning_directory)
    key = os.environ.get("WANDB_API_KEY") or os.environ.pop("COREWEAVE_WANDB_API_KEY", "")
    if not key:
        raise RuntimeError("Inject COREWEAVE_WANDB_API_KEY with hsec")
    os.environ["WANDB_API_KEY"] = key
    import weave

    client = weave.init("silta/coreweave-hack-silta-squad")
    pins = {**learning.active(), "verifier": VERIFIER_VERSION}
    astra, bridge = AstraClient(), FusionBridge()

    class ResumeMain(AstraMainAgent):
        def establish_target(self, inputs, workspace):
            (Path(workspace) / "resume-provenance.json").write_text(
                json.dumps(
                    {
                        "source_manifest": str(args.source.resolve()),
                        "source_manifest_sha256": source_sha256,
                        "manual_trial": nomination,
                        "learning_provenance": learning_provenance,
                        "candidate_digest": candidate.digest if candidate else None,
                        "reason": (
                            "Same fixed target; fresh verification of retained candidate first"
                            if candidate
                            else "Same accepted CAD; regenerate CAM after prior failure"
                        ),
                        "source_verifier_version": verification.verifier_version
                        if verification
                        else None,
                        "current_verifier_version": VERIFIER_VERSION,
                        "source_verdict_eligible_as_incumbent": compatible_incumbent,
                    },
                    indent=2,
                )
            )
            if nomination:
                raw = args.trial_source.read_bytes()
                if hashlib.sha256(raw).hexdigest() != nomination["source_manifest_sha256"]:
                    raise ValueError("Nominated source changed before the trial began")
                (Path(workspace) / "manual-trial-source.json").write_bytes(raw)
                (Path(workspace) / "manual-trial-nomination.json").write_text(
                    json.dumps(nomination, indent=2)
                )
            return target

        def propose(self, context, previous, feedback, instructions, attempt):
            if attempt == 1 and trial is not None:
                return trial
            if attempt == 1 and candidate is not None:
                return candidate
            if nomination:
                feedback = {**(feedback or {}), "manual_trial_nomination": nomination}
            if attempt == 1:
                feedback = {
                    **(feedback or {}),
                    "historical_cam_failure": {
                        "reason": source.get("reason"),
                        "source_manifest": str(args.source.resolve()),
                    },
                }
            return super().propose(context, previous, feedback, instructions, attempt)

    class ResumeJudge(AstraSupervisor):
        def decide(self, context, candidate, verification, history):
            return super().decide(
                context,
                candidate,
                verification,
                [
                    {
                        "event": "historical_source",
                        "manifest": str(args.source.resolve()),
                        "collection_warning": source.get("collection_warning"),
                        "events": [] if source.get("collection_warning") else source["events"],
                    },
                    *([nomination] if nomination else []),
                    *history,
                ],
            )

    playback_receipts = []
    verifier = FixedFusionVerifier(bridge)
    if args.show_playback:
        import runpy

        show = runpy.run_path(str(ROOT / "scripts/demo/stage_playback.py"))["show"]
        verifier = PlaybackVerifier(
            verifier,
            show,
            bridge,
            ROOT / "runs" / (args.job_id + "-playback"),
            playback_receipts,
            args.playback_seconds,
        )
    common = dict(version_store=learning, default_versions=pins)
    controller = trace_controller(
        Controller(
            ResumeMain(astra, bridge, api_docs=args.api_docs, **common),
            learning.make_checks(pins["checks"]),
            verifier,
            ResumeJudge(astra, **common),
            learner=AstraCheckLearner(astra, **common),
            learning=learning,
            check_runner_factory=learning.make_checks,
        ),
        weave.op,
    )

    @weave.op(enable_code_capture=False)
    def resumed_job():
        return asdict(
            controller.run(
                inputs,
                ROOT / "runs",
                args.job_id,
                pins,
                args.max_attempts,
                verified_incumbent=(candidate, verification) if compatible_incumbent else None,
            )
        )

    result, call = resumed_job.call()
    client.flush()
    receipt = dict(
        job_id=args.job_id,
        weave_project="silta/coreweave-hack-silta-squad",
        weave_call_id=call.id,
        learning_provenance=learning_provenance,
        presentation_playbacks=playback_receipts,
        presentation_scope="Known retained CAD/CAM; fresh verification, separate playback",
        ending_learning_sha256={
            name: hashlib.sha256((learning.root / name).read_bytes()).hexdigest()
            for name in ("checks.py", "cad_cam.md")
        },
        weave_recorded=client.get_call(call.id).ended_at is not None,
    )
    (ROOT / "runs" / args.job_id / "run-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    print(json.dumps({k: result[k] for k in ["job_id", "status", "reason", "attempts"]}, indent=2))
    if result["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
