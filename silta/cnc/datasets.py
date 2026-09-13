"""Capture and register real benchmark cases without starting agents or cloud work.

Usage: python -m silta.cnc.datasets --help
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .benchmarks import capture_case, register_dataset, verifier_hash
from .evaluation import VersionStore
from .models import Artifact


def _json(path: str) -> dict:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _new_json(path: str, value: dict) -> None:
    """Do not replace an earlier identity or captured case accidentally."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as output:
        json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    identity = commands.add_parser(
        "identity", help="Pin verifier code and configuration before a run"
    )
    identity.add_argument("--version", required=True)
    identity.add_argument("--coverage", required=True)
    identity.add_argument(
        "--artifact",
        action="append",
        required=True,
        help="Verifier implementation dependency; repeat for every relevant file",
    )
    identity.add_argument("--configuration", help="JSON object containing verifier configuration")
    identity.add_argument("--output", required=True)

    capture = commands.add_parser("capture", help="Capture an actual completed simulation attempt")
    capture.add_argument("--manifest", required=True)
    capture.add_argument("--attempt", type=int, required=True)
    capture.add_argument("--identity", required=True)
    capture.add_argument("--kind", choices=("checks", "loop"), required=True)
    capture.add_argument("--case-id")
    capture.add_argument("--output", required=True)

    register = commands.add_parser("register", help="Validate cases and store an immutable dataset")
    register.add_argument("--store", required=True)
    register.add_argument("--case", action="append", required=True)

    inspect = commands.add_parser(
        "inspect", help="Revalidate a dataset and show its immutable reference"
    )
    inspect.add_argument("--store", required=True)
    inspect.add_argument("--dataset", required=True)
    return cli


def execute(args: argparse.Namespace) -> dict:
    if args.command == "identity":
        value = {
            "version": args.version,
            "coverage": args.coverage,
            "artifacts": [asdict(Artifact.from_path(path)) for path in args.artifact],
            "configuration": _json(args.configuration) if args.configuration else {},
        }
        if not value["version"].strip() or not value["coverage"].strip():
            raise ValueError("Version and coverage must not be blank")
        ref = verifier_hash(value)
        _new_json(args.output, value)
        return {
            "status": "identity_pinned",
            "verifier_hash": ref,
            "path": str(Path(args.output).resolve()),
        }
    if args.command == "capture":
        if args.attempt < 1:
            raise ValueError("Attempt must be positive")
        case = capture_case(
            args.manifest, args.attempt, _json(args.identity), kind=args.kind, case_id=args.case_id
        )
        _new_json(args.output, case)
        return {
            "status": "captured",
            "case_id": case["case_id"],
            "kind": case["kind"],
            "label": case["label"],
            "path": str(Path(args.output).resolve()),
        }
    if args.command == "register":
        store = VersionStore(args.store)
        cases = [_json(path) for path in args.case]
        ref = register_dataset(store, cases)
    else:
        store = VersionStore(args.store)
        obj = store.get(args.dataset)
        if obj["kind"] != "dataset":
            raise ValueError("Reference is not an evaluation dataset")
        cases, ref = obj["content"], args.dataset
        if not cases:
            raise ValueError("Dataset is empty")
        # Reuse the complete dataset validation; the content-addressed object
        # already exists, so this does not replace it or create a new version.
        if register_dataset(store, cases) != ref:
            raise ValueError("Dataset reference changed during validation")
    return {
        "status": "registered" if args.command == "register" else "validated",
        "dataset_ref": ref,
        "kind": cases[0]["kind"],
        "case_count": len(cases),
        "labels": {
            label: sum(case["label"] == label for case in cases) for label in ("valid", "invalid")
        },
        "object_path": str(store.root.resolve() / "objects" / f"{ref}.json"),
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = execute(args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "error", "reason": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
