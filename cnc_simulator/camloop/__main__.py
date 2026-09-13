import argparse
import json
import time
from pathlib import Path

from .astra import Astra
from .controller import run_job
from .demo import build_corpus
from .rehearsal import Rehearsal


def main():
    parser = argparse.ArgumentParser(description="Silta programmatic CAM loops")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser(
        "prepare", help="Create accepted pocket jobs and simulator-labelled gate corpus"
    )
    setup.add_argument("--workspace", type=Path, default=Path("workspace"))
    run = sub.add_parser("run", help="Run Astra or explicitly scripted rehearsal")
    run.add_argument("job", type=Path)
    run.add_argument("--workspace", type=Path, default=Path("workspace"))
    run.add_argument("--mode", choices=["astra", "rehearsal"], default="astra")
    run.add_argument("--id")
    run.add_argument("--attempts", type=int, default=5)
    run.add_argument("--guidance-evaluations", type=int, default=1)
    serve = sub.add_parser("serve", help="Local viewer and run launcher")
    serve.add_argument("--workspace", type=Path, default=Path("workspace"))
    serve.add_argument("--port", type=int, default=2731)
    benchmark = sub.add_parser("benchmark", help="Run ten different frozen parts through live Astra")
    benchmark.add_argument("--workspace", type=Path, default=Path("workspace-ten-parts"))
    benchmark.add_argument("--attempts", type=int, default=6)
    benchmark.add_argument("--report-only", action="store_true")
    benchmark.add_argument("--transfer-audit", action="store_true")
    args = parser.parse_args()
    if args.command == "benchmark":
        from .benchmark import evaluate_transfer, report, run_benchmark
        result = report(args.workspace) if args.report_only else run_benchmark(args.workspace, args.attempts)
        if args.transfer_audit:
            evaluate_transfer(args.workspace)
        print(json.dumps(result, indent=2))
        return 0 if result["parts_with_valid_plan"] == 10 else 1
    elif args.command == "prepare":
        print(build_corpus(args.workspace))
    elif args.command == "run":
        run_id = args.id or f"{args.mode}-{args.job.parent.name}-{int(time.time())}"
        if not run_id or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for c in run_id
        ):
            parser.error("Run ID must use letters, digits, hyphens or underscores")
        result = run_job(
            args.job,
            args.workspace,
            run_id,
            Astra if args.mode == "astra" else Rehearsal,
            max_attempts=args.attempts,
            guidance_evaluations=args.guidance_evaluations,
        )
        print(
            json.dumps(
                dict(
                    id=result["id"],
                    status=result["status"],
                    best=result["best"],
                    reason=result["reason"],
                ),
                indent=2,
            )
        )
        return 0 if result["status"] == "completed" else 1
    else:
        from .server import serve as start_server

        start_server(args.workspace, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
