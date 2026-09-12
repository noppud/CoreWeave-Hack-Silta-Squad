"""The real CNC application. Missing access is an error, never a demo fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

from .astra import AstraClient
from .evaluation import VersionStore, WeaveEvaluationGate
from .fusion import FusionBridge
from .models import Artifact, JobInputs, PromotionResult

ROOT = Path(__file__).resolve().parents[1]


def read_inputs(path: Path) -> JobInputs:
    data = json.loads(path.read_text())
    if data.get("status") != "ready" or data.get("unresolved"):
        raise ValueError("Job configuration is not ready: " + "; ".join(data.get("unresolved", [])))
    fields = data.get("inputs", data)
    drawings = []
    for item in fields["drawings"]:
        name = item["path"] if isinstance(item, dict) else item
        file = Path(name)
        file = file if file.is_absolute() else path.parent / file
        artifact = Artifact.from_path(file)
        if isinstance(item, dict) and item.get("sha256") != artifact.sha256:
            raise ValueError("Drawing content differs from the selected configuration")
        drawings.append(artifact)
    result = JobInputs(
        drawings=tuple(drawings),
        machine=fields["machine"],
        tools=fields["tools"],
        setup=fields["setup"],
        tolerances=fields["tolerances"],
        cost_assumptions=fields.get("cost_assumptions", {}),
        objective=fields.get("objective", "machining_seconds"),
    )
    result.verify()
    return result


def initialize(store: VersionStore) -> dict[str, str]:
    paths = {
        "main_prompt": ROOT.parent / "prompts/main_prompt.md",
        "supervisor_prompt": ROOT.parent / "prompts/supervisor_prompt.md",
        "checks": ROOT.parent / "checks/baseline.py",
    }
    for kind, path in paths.items():
        if kind not in store.active():
            store.initialize(kind, store.put(kind, path.read_text()))
    return store.active()


def make_checks(store: VersionStore, ref: str):
    from .local_checks import LocalCheckRunner

    obj = store.get(ref)
    if obj["kind"] != "checks" or not isinstance(obj["content"], str):
        raise ValueError("Expected check source version")
    contents = obj["content"].encode()
    directory = store.root / "check-code"
    directory.mkdir(exist_ok=True)
    path = directory / f"{ref}.py"
    path.write_bytes(contents)
    return LocalCheckRunner(
        path,
        version=ref,
        sha256=hashlib.sha256(contents).hexdigest(),
    )


def run_job(args) -> dict:
    from .agents import AstraCheckLearner, AstraMainAgent, AstraSupervisor
    from .controller import Controller
    from .tracing import trace_adapter, trace_call, trace_controller
    from .ui_verifier import VERIFIER_VERSION, FusionUIVerifier

    inputs = read_inputs(args.config.resolve())
    api_key = os.environ.get("WANDB_API_KEY") or os.environ.pop("COREWEAVE_WANDB_API_KEY", "")
    if not api_key:
        raise RuntimeError("W&B credential missing; inject it with hsec exec")
    # Weave reads this variable. Astra launches with an explicit clean environment.
    os.environ["WANDB_API_KEY"] = api_key
    import weave

    client = weave.init(args.project)
    store = VersionStore(args.versions)
    versions = initialize(store)
    versions["verifier"] = VERIFIER_VERSION
    astra = AstraClient()
    astra.check_access(args.config.parent.resolve())
    bridge = FusionBridge()
    ping = bridge.request("ping", timeout=5)
    if ping.get("status") == "error":
        raise RuntimeError("Fusion add-in is not ready")
    ui_astra = AstraClient(computer_use=True)

    def factory(pins, evaluation_enabled=False):
        return trace_controller(Controller(
            main=AstraMainAgent(
                astra, bridge, version_store=store, default_versions=pins, api_docs=args.api_docs
            ),
            checks=make_checks(store, pins["checks"]),
            fusion=FusionUIVerifier(ui_astra, bridge),
            supervisor=AstraSupervisor(astra, version_store=store, default_versions=pins),
            learner=AstraCheckLearner(astra, version_store=store, default_versions=pins),
            check_runner_factory=lambda ref: make_checks(store, ref),
        ), weave.op)

    controller = factory(versions)
    from .benchmarks import BenchmarkRunner

    runner = BenchmarkRunner(
        store=store,
        root=args.runs / "benchmarks",
        make_controller=factory,
        check_runner_factory=lambda ref: trace_adapter(
            make_checks(store, ref), {"run": "candidate_checks"}, weave.op
        ),
        max_attempts=args.max_attempts,
    )

    class DatasetGate:
        def evaluate(self, proposal, context):
            dataset = args.check_dataset if proposal.kind == "checks" else args.loop_dataset
            if not dataset:
                return PromotionResult(
                    proposal.id,
                    False,
                    "Awaiting real simulator cases; no change promoted without a Weave evaluation",
                )
            gate = WeaveEvaluationGate(
                store=store,
                project=args.project,
                dataset_ref=dataset,
                runner=trace_call(runner, "paired_benchmark_run", weave.op),
            )
            return gate.evaluate(proposal, context)

    controller.evaluation = trace_adapter(
        DatasetGate(), {"evaluate": "reusable_change_evaluation"}, weave.op
    )

    # Fusion computes verification; the UI adapter requires actual native observations.
    @weave.op(enable_code_capture=False)
    def machining_job(job_inputs: dict, version_refs: dict, job_id: str) -> dict:
        return asdict(controller.run(inputs, args.runs, job_id, versions, args.max_attempts))

    result, call = machining_job.call(asdict(inputs), versions, args.job_id or uuid.uuid4().hex)
    client.flush()
    receipt = client.get_call(call.id)
    result["weave_call_id"] = call.id
    result["weave_recorded"] = receipt.ended_at is not None
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Silta: drawing to verified CNC plan")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check local subscription and Fusion bridge")
    doctor.add_argument("--fusion", action="store_true", help="Send a live read-only bridge ping")
    doctor.add_argument(
        "--fusion-ui",
        action="store_true",
        help="Ask Astra to read Fusion once, requesting native app consent if needed",
    )
    commands.add_parser("init", help="Register initial local check and prompt versions")
    run = commands.add_parser("run", help="Run a real configured CNC job")
    run.add_argument("config", type=Path)
    run.add_argument("--project", default="silta/coreweave-hack-silta-squad")
    run.add_argument("--runs", type=Path, default=Path("runs"))
    run.add_argument("--versions", type=Path, default=Path("versions"))
    run.add_argument("--job-id")
    run.add_argument("--max-attempts", type=int, default=20)
    run.add_argument("--api-docs", nargs="*", default=[])
    run.add_argument("--check-dataset", help="Immutable dataset ref of simulator-labeled plans")
    run.add_argument("--loop-dataset", help="Immutable dataset ref of fixed-target part cases")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            result = {"astra": AstraClient().check_access(Path.cwd())}
            if args.fusion:
                result["fusion"] = FusionBridge().request("ping", timeout=5)
            if args.fusion_ui:
                evidence_dir = Path(".private/access/fusion-ui")
                evidence_dir.mkdir(parents=True, exist_ok=True)
                result["fusion_ui"] = AstraClient(computer_use=True).ask_with_evidence(
                    "Read Autodesk Fusion with computer use once and report the current screen. "
                    "Do not click, change anything, or retry after a denial or lock error.",
                    workspace=evidence_dir.resolve(),
                    schema={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["read", "unavailable"]},
                            "screen": {"type": "string"},
                        },
                        "required": ["status", "screen"],
                        "additionalProperties": False,
                    },
                )
                if result["fusion_ui"]["value"]["status"] != "read":
                    result["status"] = "incomplete"
        elif args.command == "init":
            result = initialize(VersionStore("versions"))
        else:
            result = run_job(args)
        print(json.dumps(result, indent=2))
        if result.get("status") == "incomplete":
            sys.exit(2)
    except (ValueError, RuntimeError, OSError, TimeoutError) as error:
        parser.exit(1, f"{type(error).__name__}: {error}\n")
