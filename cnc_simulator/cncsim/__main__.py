import argparse
import json
import sys
from pathlib import Path

from . import InputError, simulate


def main():
    parser = argparse.ArgumentParser(
        description="Conservative structured-movement CNC simulation (mm)"
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, default=Path("simulation-output"))
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text())
        result = simulate(plan, base_dir=args.plan.parent, output_dir=args.output)
    except (InputError, ValueError, OSError, TypeError, KeyError) as exc:
        result = dict(
            validity="invalid", passed=False, verification="input_error",
            issues=[
                dict(code="input_error", certainty="uncertain", moves=[], description=str(exc))
            ],
            estimated_time_seconds=None,
            time_breakdown=dict(cutting=None, rapid=None, dwell=None, tool_changes=None),
        )
        print(json.dumps(result, allow_nan=False))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return {"valid": 0, "invalid": 1, "unknown": 2}[result["validity"]]


if __name__ == "__main__":
    sys.exit(main())
