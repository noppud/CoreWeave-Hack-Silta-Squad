"""Relocate checkout-local artifact paths without changing pinned hashes or account IDs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


def relocate(config, old_root, new_root):
    old_root, new_root = Path(old_root).resolve(), Path(new_root).resolve()
    result = copy.deepcopy(config)
    changes, errors, verified = [], [], []

    def walk(value, location="$"):
        if isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{location}[{i}]")
        elif isinstance(value, dict):
            if isinstance(value.get("path"), str):
                path = Path(value["path"])
                if path.is_absolute():
                    try:
                        relative = path.relative_to(old_root)
                    except ValueError:
                        errors.append(f"{location}: path outside old root: {path}")
                    else:
                        if ".." in relative.parts:
                            errors.append(f"{location}: path traversal refused")
                        else:
                            new = new_root / relative
                            if not new.resolve().is_relative_to(new_root):
                                errors.append(f"{location}: destination symlink escapes new root")
                            else:
                                value["path"] = str(new)
                                if str(path) != str(new):
                                    changes.append(
                                        dict(location=location, before=str(path), after=str(new))
                                    )
                else:
                    errors.append(f"{location}: relative path is ambiguous")
                if "sha256" in value:
                    destination = Path(value["path"])
                    if not destination.is_file():
                        errors.append(f"{location}: missing pinned artifact: {destination}")
                    elif hashlib.sha256(destination.read_bytes()).hexdigest() != value["sha256"]:
                        errors.append(f"{location}: pinned SHA256 mismatch: {destination}")
                    else:
                        verified.append(str(destination))
            for key, child in value.items():
                walk(child, f"{location}.{key}")

    walk(result)
    return result, dict(
        status="verified" if not errors else "failed",
        changes=changes,
        verified_artifacts=verified,
        errors=errors,
        scope=(
            "Local path and pinned-byte verification only; Fusion account/machine access not tested"
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--old-root", required=True, type=Path)
    parser.add_argument("--new-root", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-only", action="store_true")
    group.add_argument("--output", type=Path)
    args = parser.parse_args()
    config, report = relocate(json.loads(args.config.read_text()), args.old_root, args.new_root)
    print(json.dumps(report, indent=2))
    if report["errors"]:
        return 1
    if args.output:
        with args.output.open("x") as stream:
            stream.write(json.dumps(config, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
