"""Sequential real Fusion jobs with shared learning and presentation-readable progress.

Run through hsec exec --only COREWEAVE_WANDB_API_KEY. Existing run directories are
never overwritten; a failed/incomplete job stops the batch for diagnosis.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from silta.cnc.learning import SharedLearning  # noqa: E402


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configs", type=Path, nargs="+")
    parser.add_argument("--manifest", type=Path, default=ROOT / "runs/demo-campaign.json")
    parser.add_argument("--prefix", default="demo-umc")
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--learning-directory", type=Path, default=ROOT / "learning")
    parser.add_argument("--api-docs", type=Path, nargs="*", default=[])
    args = parser.parse_args()
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    lock = (ROOT / "runs/.fusion-campaign.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    learning = SharedLearning(args.learning_directory)
    if args.manifest.exists():
        campaign = json.loads(args.manifest.read_text())
    else:
        campaign = dict(
            campaign_id=args.prefix,
            status="ready",
            current_part_id=None,
            initial_versions=learning.active(),
            learning_directory=str(learning.root),
            parts=[],
            events=[],
        )
    for config in args.configs:
        config = config.resolve(strict=True)
        data = json.loads(config.read_text())
        job_id = args.prefix + "-" + config.stem.removesuffix("-job")
        path = ROOT / "runs" / job_id / "manifest.json"
        rows = [p for p in campaign["parts"] if p["part_id"] == job_id]
        row = (
            rows[0]
            if rows
            else dict(
                part_id=job_id,
                job_id=job_id,
                label=data.get("demo_part_spec", {}).get("name", config.stem),
                config=str(config),
                manifest_path=str(path),
                status="queued",
            )
        )
        if not rows:
            campaign["parts"].append(row)
        path = Path(row["manifest_path"])
        if path.exists():
            existing = json.loads(path.read_text())
            if existing.get("status") == "completed":
                row["status"] = "completed"
                continue
            raise RuntimeError(f"{job_id} exists but is not completed; inspect before retry")
        row.update(status="running", starting_versions=learning.active(), started_at=time.time())
        campaign.update(status="running", current_part_id=job_id)
        save(args.manifest, campaign)
        log = args.manifest.parent / (job_id + ".log")
        command = [
            sys.executable,
            "-m",
            "silta",
            "run",
            str(config),
            "--job-id",
            job_id,
            "--runs",
            str(ROOT / "runs"),
            "--learning-directory",
            str(learning.root),
            "--max-attempts",
            str(args.max_attempts),
        ]
        if args.api_docs:
            command += ["--api-docs", *(str(p.resolve()) for p in args.api_docs)]
        print(f"Starting {job_id}; log: {log}", flush=True)
        with log.open("w") as output:
            result = subprocess.run(
                command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, env=os.environ.copy()
            )
        actual = json.loads(path.read_text()) if path.exists() else {}
        row.update(
            status=actual.get("status", "failed"),
            exit_code=result.returncode,
            ending_versions=learning.active(),
            finished_at=time.time(),
            reason=actual.get("reason", "See process log"),
        )
        campaign["events"].append(dict(part_id=job_id, status=row["status"], at=time.time()))
        if result.returncode or row["status"] != "completed":
            campaign.update(status="needs_attention", current_part_id=job_id)
            save(args.manifest, campaign)
            raise SystemExit(f"{job_id} requires attention: {row['reason']}")
        save(args.manifest, campaign)
    pending = [row for row in campaign["parts"] if row.get("status") != "completed"]
    campaign.update(status="needs_attention" if pending else "completed", current_part_id=None)
    save(args.manifest, campaign)
    print(f"Campaign {campaign['status']}: {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
