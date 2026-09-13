"""Opt-in real Astra preparation, then presenter release before first Fusion verification."""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def now():
    return datetime.now(UTC).isoformat()


def copy_learning(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    refs = {}
    for name in ("cad_cam.md", "checks.py"):
        shutil.copyfile(source / name, destination / name)
        refs[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    return refs


class PresentationPause:
    def __init__(self, receipt, release_file=None, timeout=3600, wait=None):
        self.receipt = receipt
        self.release_file = release_file
        self.timeout = timeout
        self.wait = wait
        self.released = False
        self.data = {
            "schema_version": 1,
            "status": "preparing",
            "preparation_started_at": now(),
            "scope": "Prepared CAD/CAM; live Fusion verification after explicit release",
        }
        self.save()

    def save(self):
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        self.receipt.write_text(json.dumps(self.data, indent=2))

    def before_verify(self, candidate, context):
        if self.released:
            return
        candidate.verify()
        self.data.update(
            status="awaiting_presenter",
            prepared_at=now(),
            candidate_id=candidate.id,
            candidate_digest=candidate.digest,
            input_digest=context.input_digest,
            versions=context.versions,
            presentation_pause_started_at=now(),
        )
        self.save()
        print(
            "CAD/CAM and checks prepared. Fusion verification has NOT run. "
            "Release starts live verification; preparation time is separate.",
            flush=True,
        )
        started = time.monotonic()
        if self.wait:
            self.wait()
        elif self.release_file:
            while not self.release_file.exists():
                if time.monotonic() - started > self.timeout:
                    raise TimeoutError("Presentation release timed out; verification not started")
                time.sleep(0.2)
            if self.release_file.read_text().strip() != candidate.digest:
                raise ValueError("Release file must contain the prepared candidate digest")
        else:
            input("Press Enter at presentation start to run actual Fusion verification: ")
        candidate.verify()
        self.released = True
        self.data.update(
            status="live_verification",
            released_at=now(),
            presentation_pause_seconds=time.monotonic() - started,
        )
        self.save()


def run(args):
    from silta.cnc import cli, fixed_verifier

    if not args.prepare:
        raise ValueError("Explicit --prepare is required; this runs real Astra CAD/CAM preparation")
    if args.release_file and args.release_file.exists():
        raise ValueError("Release file already exists; use a fresh path")
    if not args.release_file and not sys.stdin.isatty():
        raise ValueError("Unattended runs require --release-file")
    runs = args.runs.resolve()
    runs.mkdir(parents=True, exist_ok=True)
    # Same lock as campaign/resume, independent of custom output directory.
    with (ROOT / "runs/.fusion-campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (runs / args.job_id).exists():
            raise ValueError("Job identity already exists; do not overwrite held-out evidence")
        shadow = runs / f"{args.job_id}-shadow-learning"
        hashes = copy_learning(args.learning_source.resolve(), shadow)
        pause = PresentationPause(
            runs / f"{args.job_id}-presentation.json", args.release_file, args.release_timeout
        )
        pause.data.update(
            assessment="held_out_shadow_learning",
            learning_source=str(args.learning_source.resolve()),
            shadow_learning_directory=str(shadow),
            initial_learning_sha256=hashes,
            no_main_learning_promotion=True,
        )
        pause.save()
        original = fixed_verifier.FixedFusionVerifier

        class StageVerifier(original):
            def verify(self, candidate, context):
                pause.before_verify(candidate, context)
                started = time.monotonic()
                verdict = super().verify(candidate, context)
                pause.data.setdefault("verifications", []).append(
                    {
                        "candidate_id": candidate.id,
                        "status": verdict.status,
                        "completed": verdict.completed,
                        "verification_wall_seconds": time.monotonic() - started,
                        "estimated_machining_seconds": verdict.machining_seconds,
                    }
                )
                pause.save()
                if (
                    getattr(args, "show_playback", False)
                    and verdict.status == "passed"
                    and verdict.completed
                ):
                    try:
                        import runpy

                        show = runpy.run_path(str(ROOT / "scripts/demo/stage_playback.py"))["show"]
                        playback = show(
                            candidate,
                            self.bridge,
                            runs / f"{args.job_id}-playback" / candidate.id,
                            seconds=args.playback_seconds,
                        )
                        pause.data.setdefault("playbacks", []).append(playback)
                        pause.save()
                    except Exception as error:
                        print(f"Presentation failed after verdict: {error}", file=sys.stderr)
                return verdict

        fixed_verifier.FixedFusionVerifier = StageVerifier
        try:
            result = cli.run_job(
                SimpleNamespace(
                    config=args.config.resolve(),
                    project=args.project,
                    runs=runs,
                    learning_directory=shadow,
                    job_id=args.job_id,
                    max_attempts=args.max_attempts,
                    api_docs=args.api_docs,
                )
            )
            pause.data.update(
                status="job_finished",
                job_status=result["status"],
                finished_at=now(),
                weave_call_id=result.get("weave_call_id"),
                weave_recorded=result.get("weave_recorded"),
                ending_learning_sha256={
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in shadow.iterdir()
                    if p.name in hashes
                },
            )
            pause.save()
            print(json.dumps(result, default=str))
            return result
        except BaseException as error:
            pause.data.update(status="stopped", error_type=type(error).__name__, stopped_at=now())
            pause.save()
            raise
        finally:
            fixed_verifier.FixedFusionVerifier = original


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("--prepare", action="store_true")
    p.add_argument(
        "--show-playback",
        action="store_true",
        help=(
            "Presentation only, after a completed pass; "
            "manually establish machine/tool visibility first"
        ),
    )
    p.add_argument("--playback-seconds", type=float, choices=range(1, 31), default=15)
    p.add_argument("--job-id", required=True)
    p.add_argument("--release-file", type=Path)
    p.add_argument("--release-timeout", type=float, default=3600)
    p.add_argument("--runs", type=Path, default=ROOT / "runs")
    p.add_argument("--learning-source", type=Path, default=ROOT / "learning")
    p.add_argument("--project", default="silta/coreweave-hack-silta-squad")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--api-docs", nargs="*", default=[str(ROOT / "fusion/INDEXED_CAM_API.md")])
    return p


if __name__ == "__main__":
    run(parser().parse_args())
