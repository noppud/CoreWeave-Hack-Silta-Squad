"""Local Fusion control center, backed by actual manifests and retained media.

Run with .venv/bin/python -m silta.cnc.control_center. The browser receives no
credentials. Only an explicit Start request launches the existing CNC runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from .presentation import complete_pass, current_stage, run_summary

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "applications/control-center"


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {} if default is None else default


def now():
    return datetime.now(UTC).isoformat()


class Catalog:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.allowed: set[Path] = set()
        self.cache = {}
        self.lock = threading.RLock()

    def path(self, value):
        p = Path(value)
        p = (self.root / p).resolve() if not p.is_absolute() else p.resolve()
        if not p.is_relative_to(self.root) or any(
            x.startswith(".") for x in p.relative_to(self.root).parts
        ):
            raise ValueError("Artifact is outside the evidence workspace")
        return p

    def asset(self, value):
        if not value:
            return None
        try:
            p = self.path(value)
        except ValueError:
            return None
        if not p.is_file() or p.suffix.lower() not in {
            ".json",
            ".py",
            ".md",
            ".png",
            ".jpg",
            ".mp4",
            ".pdf",
            ".nc",
            ".stl",
            ".step",
            ".f3d",
        }:
            return None
        self.allowed.add(p)
        return "/artifact/" + quote(str(p.relative_to(self.root)), safe="/")

    def text(self, value):
        try:
            p = self.path(value)
            return p.read_text()[:200000] if p.is_file() else ""
        except (ValueError, OSError):
            return ""

    def manifests(self):
        result = {}
        for p in (self.root / "runs").glob("*/manifest.json"):
            stamp = p.stat().st_mtime_ns
            old = self.cache.get(p)
            if old is None or old[0] != stamp:
                self.cache[p] = (stamp, read_json(p))
            d = self.cache[p][1]
            if d.get("job_id"):
                result[p.parent.name] = d
        return result

    def media(self):
        result = {}
        receipts = [
            "output/presentation/film-umc08-source-receipt.json",
            "output/presentation/film-umc09-source-receipt.json",
            "output/video/umc11-close-capture-r3/capture-receipt-portable.json",
            "output/video/umc12-close-capture/capture-receipt-portable-v2.json",
        ]
        for name in receipts:
            d = read_json(self.root / name)
            for item in d.get("media", []):
                path = item.get("path", "")
                url = self.asset(path)
                if not url or not path.endswith(".mp4"):
                    continue
                orbit = "orbit" in path
                result.setdefault(d.get("source_job"), []).append(
                    dict(
                        url=url,
                        label="Finished stock · orbit" if orbit else "Fusion · machining",
                        kind="orbit" if orbit else "machining",
                        scope="Recorded camera orbit of simulated stock"
                        if orbit
                        else "Recorded Fusion machine simulation",
                        candidate=d.get("candidate_id"),
                        digest=d.get("candidate_digest"),
                        receipt=self.asset(name),
                        duration=item.get("media_duration_seconds"),
                    )
                )
        return result

    def parts(self, manifests):
        gallery = read_json(self.root / "output/presentation/part-gallery.json")
        media = self.media()
        parts = []
        for row in gallery.get("parts", []):
            job = row["job_id"]
            d = manifests.get(job, {})
            if not d:
                continue
            parts.append(
                dict(
                    id=job,
                    label=row["label"],
                    number=row["short_id"],
                    preview=self.asset(row.get("render_path") or row.get("preview_path")),
                    mesh=self.asset(row.get("tessellation_path")),
                    media=media.get(job, []),
                    status=d.get("status"),
                    verified=complete_pass(d.get("best_verification") or {}),
                    summary=run_summary(d),
                    stage=current_stage(d),
                    created_at=d.get("created_at"),
                    at=(d.get("events") or [{}])[-1].get("at"),
                    image_scope="CAD preview",
                    machine=d.get("inputs", {}).get("machine", {}).get("name"),
                    drawings=[
                        self.asset(a.get("path")) for a in d.get("inputs", {}).get("drawings", [])
                    ],
                )
            )
        # User-submitted jobs become library entries as soon as their manifest exists.
        for intake_path in (self.root / "runs/control-center-inputs").glob("*/intake.json"):
            intake = read_json(intake_path)
            job = intake.get("job")
            if not job or job not in manifests or any(p["id"] == job for p in parts):
                continue
            d = manifests[job]
            verdict = d.get("best_verification") or {}
            artifacts = (
                verdict.get("feedback", {}).get("target_stock_comparison", {}).get("artifacts", {})
            )
            parts.append(
                dict(
                    id=job,
                    label=intake.get("filename", job),
                    number="NEW",
                    preview=None,
                    mesh=self.asset(artifacts.get("target_mesh")),
                    media=media.get(job, []),
                    status=d.get("status"),
                    verified=complete_pass(verdict),
                    summary=run_summary(d),
                    stage=current_stage(d),
                    created_at=d.get("created_at"),
                    at=(d.get("events") or [{}])[-1].get("at"),
                    image_scope="CAD preview",
                    machine=d.get("inputs", {}).get("machine", {}).get("name"),
                    drawings=[
                        self.asset(a.get("path")) for a in d.get("inputs", {}).get("drawings", [])
                    ],
                )
            )
        priority = {"UMC 11": 0, "UMC 12": 1, "UMC 08": 2, "UMC 09": 3}
        return sorted(parts, key=lambda p: priority.get(p["number"], 10))

    def event(self, e, job, label):
        kind = e.get("event", "")
        titles = {
            "target_generation_started": "Reading drawing & building CAD",
            "target_accepted": "CAD target accepted",
            "candidate_generation_started": "Writing machining plan",
            "candidate_created": "CAM candidate generated",
            "checks_completed": "Checks passed"
            if e.get("result", {}).get("passed")
            else "Check caught an issue",
            "verification_started": "Fusion verification started",
            "verification_completed": {
                "passed": "Fusion verification passed",
                "failed": "Fusion found a failure",
            }.get(e.get("verification", {}).get("status"), "Verification incomplete"),
            "supervisor_decision": "Judge selected best plan"
            if e.get("decision", {}).get("action") == "stop"
            else "Judge requested an improvement",
            "learning_change_saved": "New check saved"
            if e.get("change_kind") == "checks"
            else "Machining guidance updated",
            "promoted_change_applied": "Learning applied to next attempt",
            "cam_generation_failed": "CAM generation needs repair",
            "execution_interrupted": "Run interrupted",
            "incumbent_updated": "New best verified plan",
        }
        group = (
            "learning"
            if kind in {"learning_change_saved", "promoted_change_applied"}
            else "checks"
            if kind == "checks_completed"
            else "judge"
            if kind == "supervisor_decision"
            else "work"
        )
        detail = e.get("decision", {}).get("instructions") or e.get("reason")
        if kind == "checks_completed":
            detail = (
                "\n".join(e.get("result", {}).get("issues", []))
                or "The recorded check set returned a pass."
            )
        if kind == "verification_completed":
            detail = "\n".join(e.get("verification", {}).get("issues", [])) or e.get(
                "verification", {}
            ).get("coverage")
        return dict(
            job=job,
            part=label,
            at=e.get("at"),
            event=kind,
            title=titles.get(kind, kind.replace("_", " ").capitalize()),
            group=group,
            detail=detail,
            attempt=e.get("attempt"),
            seconds=e.get("verification", {}).get("machining_seconds"),
            runtime=e.get("result", {}).get("runtime_s"),
            raw=e,
        )

    def learning(self, manifests):
        changes = []
        for job, d in manifests.items():
            proposals = {
                e["proposal"]["id"]: e["proposal"] for e in d.get("events", []) if e.get("proposal")
            }
            for e in d.get("events", []):
                if e.get("event") != "learning_change_saved":
                    continue
                p = proposals.get(e.get("proposal_id"), {})
                content = self.text(p.get("artifact_path", ""))
                changes.append(
                    dict(
                        id=p.get("id", job + str(e.get("at"))),
                        job=job,
                        at=e.get("at"),
                        kind=p.get("kind", e.get("change_kind")),
                        reason=p.get("reason", ""),
                        version=p.get("proposed_version"),
                        source=self.asset(p.get("artifact_path")),
                        content=content,
                        evaluation_performed=e.get("evaluation_performed", False),
                    )
                )
        transfer = read_json(self.root / "output/evaluation/learning-transfer.json")
        bc = next((t for t in transfer.get("transfers", []) if t.get("kind") == "checks"), {})
        checks = []
        fixture = next(
            (self.root / "runs/learning-check-retry-a3/workspace").glob(
                "check-proposal-*/checks-*.py"
            ),
            None,
        )
        if fixture:
            checks.append(
                dict(
                    id="fixture",
                    title="Keep the cutter clear of fixture parallels",
                    label="LEARNED CHECK 01",
                    learned_on="Part A",
                    scope="Cutter endpoint check for the configured fixture envelopes.",
                    description=(
                        "A collision led to a reusable check before the next Fusion simulation."
                    ),
                    source=self.asset(fixture),
                    content=self.text(fixture),
                    job="learning-soft-jaw-a3",
                    evidence=self.asset("docs/learning-results.md"),
                    status="Retained learned check",
                )
            )
        change = next(
            (c for c in changes if c["kind"] == "checks" and c["job"] == "learning-part-b1"), None
        )
        if change:
            checks.append(
                dict(
                    id="sides",
                    title="Protect the finished outside faces",
                    label="LEARNED CHECK 02",
                    learned_on="Part B → used on Part C",
                    scope=(
                        "Endpoint-only check for pre-sized blanks and internal features. "
                        "Not full swept-volume verification."
                    ),
                    description=(
                        "A stock-conformity failure on B became a check that rejected "
                        "C’s candidate before simulation."
                    ),
                    source=change["source"],
                    content=change["content"],
                    job=change["job"],
                    reason=change["reason"],
                    status="Observed cross-part reuse",
                    transfer=bc,
                    at=change["at"],
                )
            )
        return dict(
            checks=checks,
            changes=sorted(changes, key=lambda x: x["at"], reverse=True),
            evaluation=read_json(self.root / "output/evaluation/learning-evaluation.json"),
            evaluation_source=self.asset("output/evaluation/learning-evaluation.json"),
            active_checks=self.asset("learning/checks.py"),
            active_guidance=self.asset("learning/cad_cam.md"),
            guidance=self.text("learning/cad_cam.md"),
            baseline=self.asset("checks/baseline.py"),
            aria=self.text("output/sponsors/aria-response.md"),
            aria_source=self.asset("output/sponsors/aria-response.md"),
            aria_review={
                key: value
                for key, value in read_json(self.root / "output/sponsors/aria-review.json").items()
                if key
                in {"status", "recommendation", "validation", "implemented_change", "live_outcome"}
            },
        )

    def detail(self, job):
        manifests = self.manifests()
        if job not in manifests:
            raise ValueError("Job not found")
        d = manifests[job]
        parts = self.parts(manifests)
        p = next(
            (p for p in parts if p["id"] == job), dict(id=job, label=job, media=[], preview=None)
        )
        if p["label"] == job:
            drawing_hashes = {x.get("sha256") for x in d.get("inputs", {}).get("drawings", [])}
            parent = next(
                (
                    part
                    for part in parts
                    if drawing_hashes
                    & {
                        x.get("sha256")
                        for x in manifests[part["id"]].get("inputs", {}).get("drawings", [])
                    }
                ),
                None,
            )
            if parent:
                p = {**p, "label": parent["label"], "number": parent["number"]}
        events = [self.event(e, job, p["label"]) for e in d.get("events", [])]
        sources = []
        work = self.root / "runs" / job / "workspace"
        # Only emitted source/response artifacts, never auth files or raw process logs.
        for path in sorted(work.glob("cam-*/*")):
            if path.name.endswith(".py") or path.name == "cam-source.json":
                content = self.text(path)
                if path.name.endswith(".json"):
                    content = read_json(path).get("source", "")
                if content:
                    sources.append(
                        dict(
                            name=str(path.relative_to(work)), content=content, url=self.asset(path)
                        )
                    )
        cad_sources = list(work.glob("cad-attempt-*.py"))
        cad_sources += list(work.glob("*/cad-attempt-*.py"))
        for path in sorted(cad_sources):
            sources.insert(
                0,
                dict(
                    name=str(path.relative_to(work)), content=self.text(path), url=self.asset(path)
                ),
            )
        best = d.get("best_candidate") or next(
            (
                e["candidate"]
                for e in reversed(d.get("events", []))
                if e.get("event") == "candidate_created"
            ),
            {},
        )
        files = [
            dict(name=name, url=self.asset(ref.get("path")))
            for name, ref in best.get("artifacts", {}).items()
        ]
        for name, ref in best.get("artifacts", {}).items():
            if name.startswith("nc-"):
                sources.insert(
                    0,
                    dict(
                        name=f"Selected plan / {name}.nc",
                        content=self.text(ref["path"]),
                        url=self.asset(ref["path"]),
                    ),
                )
        verdict = d.get("best_verification") or {}
        stock_artifacts = (
            verdict.get("feedback", {}).get("target_stock_comparison", {}).get("artifacts", {})
        )
        evidence = [
            dict(name=Path(ref["path"]).name, url=self.asset(ref["path"]))
            for ref in verdict.get("evidence", [])
            if ref.get("path")
        ]
        preview = p.get("preview") or self.asset(
            d.get("target", {}).get("artifacts", {}).get("preview", {}).get("path")
        )
        receipt = read_json(self.root / "runs" / job / "run-receipt.json")
        weave = (
            ("https://wandb.ai/" + receipt["weave_project"] + "/r/call/" + receipt["weave_call_id"])
            if receipt.get("weave_call_id") and receipt.get("weave_project")
            else None
        )
        return dict(
            p,
            preview=preview,
            mesh=p.get("mesh") or self.asset(stock_artifacts.get("target_mesh", {}).get("path")),
            stock_mesh=self.asset(stock_artifacts.get("stock", {}).get("path")),
            events=events,
            sources=sources,
            files=files,
            evidence=evidence,
            verdict=verdict,
            summary=run_summary(d),
            status=d.get("status"),
            stage=current_stage(d),
            reason=d.get("reason"),
            versions=d.get("current_versions", d.get("versions")),
            weave=weave,
            drawings=[self.asset(a.get("path")) for a in d.get("inputs", {}).get("drawings", [])],
            manifest=self.asset(self.root / "runs" / job / "manifest.json"),
        )


class Center:
    def __init__(self, root=ROOT, enable_runs=True):
        self.root = Path(root).resolve()
        self.catalog = Catalog(root)
        self.enable_runs = enable_runs
        self.lock = threading.Lock()
        self.process = None
        self.active_id = None
        self.worker = dict(status="unchecked", label="Fusion connection not checked")
        self.inputs = self.root / "runs/control-center-inputs"
        self.frame_lock = threading.Lock()
        self.pdf_lock = threading.Lock()
        from .demo_replay import DemoReplay

        self.demo = DemoReplay(self.root, self.catalog)

    def profiles(self):
        configs = list((self.root / "config/demo-campaign").glob("*-job.json"))
        configs += list((self.root / "config").glob("learning-part-*-job.json"))
        configs += [self.root / "config/soft-jaw-job.json"]
        result = []
        for p in configs:
            d = read_json(p)
            if d.get("status") == "ready" and not d.get("unresolved"):
                result.append((p, d))
        return result

    def intake(self, name, data):
        if not data.startswith(b"%PDF-") or len(data) > 25_000_000:
            raise ValueError("Choose a PDF drawing smaller than 25 MB")
        key = "drawing-" + uuid.uuid4().hex[:12]
        folder = self.inputs / key
        folder.mkdir(parents=True)
        path = folder / "drawing.pdf"
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        matches = [
            (p, d)
            for p, d in self.profiles()
            if any(a.get("sha256") == digest for a in d.get("drawings", []))
        ]
        item = dict(
            id=key,
            filename=Path(name).name[:160],
            at=now(),
            sha256=digest,
            status="ready",
            job=None,
            drawing=str(path),
            profile=None,
        )
        from .demo_replay import demo_match

        item["demo"] = demo_match(digest)
        if item["demo"]:
            profile = self.root / "config/demo-campaign/umc-12-job.json"
            config = read_json(profile)
        elif matches:
            profile, config = matches[0]
        else:
            profile = self.root / "config/control-center-umc-profile.json"
            config = read_json(profile)
            if not config:
                raise ValueError("The local shop profile is missing")
        config = json.loads(json.dumps(config))
        config["drawings"] = [dict(path=str(path), sha256=digest)]
        (folder / "job.json").write_text(json.dumps(config, indent=2))
        item["profile"] = dict(
            name=profile.stem,
            machine=config.get("machine", {}).get("name"),
            source=str(profile.relative_to(self.root)),
            material=config.get("setup", {}).get("material"),
            stock=config.get("setup", {}).get("stock", {}).get("dimensions_mm"),
            known_drawing=bool(matches or item.get("demo")),
            assumptions=config.get("setup", {}).get("simulation_assumptions", []),
        )
        (folder / "intake.json").write_text(json.dumps(item, indent=2))
        return self.public_intake(item)

    def public_intake(self, item):
        return {**item, "drawing": self.catalog.asset(item.get("drawing"))}

    def detail(self, job):
        try:
            detail = self.catalog.detail(job)
        except ValueError:
            item = next(
                (
                    read_json(p)
                    for p in self.inputs.glob("*/intake.json")
                    if read_json(p).get("job") == job
                ),
                None,
            )
            if not item:
                raise
            running = self.active_id == job and self.process and self.process.poll() is None
            return dict(
                id=job,
                label=item["filename"],
                number="NEW PDF",
                status="starting" if running else "stopped",
                stage="Starting Fusion runner" if running else "Worker stopped",
                reason="Waiting for the first runner event."
                if running
                else "The worker stopped before creating a run manifest. Check runner access.",
                preview=None,
                mesh=None,
                stock_mesh=None,
                media=[],
                sources=[],
                files=[],
                events=[],
                verdict={},
                summary=run_summary({}),
                evidence=[],
                versions={},
                drawings=[self.catalog.asset(item["drawing"])],
                manifest=None,
                weave=None,
            )
        return detail

    def start(self, key):
        if not self.enable_runs:
            raise ValueError("This server is in review-only mode")
        if not re.fullmatch(r"drawing-[a-f0-9]{12}", key):
            raise ValueError("Unknown drawing")
        with self.lock:
            if self.demo.busy:
                raise ValueError("Reset the staged demo before starting a fresh Fusion job")
            if self.process and self.process.poll() is None:
                raise ValueError("Fusion is already working on a job")
            folder = self.inputs / key
            item = read_json(folder / "intake.json")
            if item.get("demo"):
                raise ValueError("Use Start demo replay for the prepared drawing")
            if item.get("status") != "ready" or item.get("job"):
                raise ValueError("Drawing needs a matching shop setup, or has already been started")
            # Validate every configured artifact and drawing digest before launching.
            from .cli import read_inputs

            read_inputs(folder / "job.json")
            self.ping()
            if self.worker["status"] != "ready":
                raise ValueError(
                    "Fusion add-in is not responding. Open Fusion and start SiltaBridge."
                )
            job = "control-" + uuid.uuid4().hex[:12]
            learning = folder / "learning"
            learning.mkdir()
            for name in ("checks.py", "cad_cam.md"):
                shutil.copyfile(self.root / "learning" / name, learning / name)
            hsec = Path.home() / ".local/bin/hsec"
            command = [
                str(hsec),
                "exec",
                "--only",
                "COREWEAVE_WANDB_API_KEY",
                "--",
                sys.executable,
                "-m",
                "silta.cnc.cli",
                "run",
                str(folder / "job.json"),
                "--runs",
                str(self.root / "runs"),
                "--job-id",
                job,
                "--learning-directory",
                str(learning),
                "--max-attempts",
                "3",
            ]
            with (folder / "worker.log").open("w") as log:
                self.process = subprocess.Popen(
                    command, cwd=self.root, stdout=log, stderr=log, start_new_session=True
                )
            self.active_id = job
            item.update(status="started", job=job, started_at=now())
            (folder / "intake.json").write_text(json.dumps(item, indent=2))
            return dict(job=job, status="starting")

    def start_demo(self, key):
        if not self.enable_runs:
            raise ValueError("This server is in review-only mode")
        if not re.fullmatch(r"drawing-[a-f0-9]{12}", key):
            raise ValueError("Unknown drawing")
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ValueError("Fusion is already working on a job")
            return self.demo.start(read_json(self.inputs / key / "intake.json"))

    def ping(self):
        from .fusion import FusionBridge

        try:
            reply = FusionBridge().request("ping", timeout=4)
            ok = reply.get("status") == "ok"
            self.worker = dict(
                status="ready" if ok else "unavailable",
                label="Fusion add-in connected" if ok else "Fusion add-in unavailable",
                checked_at=now(),
            )
        except (RuntimeError, TimeoutError, ValueError, OSError):
            self.worker = dict(
                status="unavailable", label="Fusion add-in not responding", checked_at=now()
            )
        return self.worker

    def capture_frame(self):
        """Read native capture only; bridge scripts can exit machining simulation."""
        with self.frame_lock:
            folder = self.root / "output/control-center"
            folder.mkdir(parents=True, exist_ok=True)
            # Reuse the read-only window capture when the companion gateway is running.
            # Only the image is copied; pairing data stays private.
            capture_dir = self.root / ".private/fusion-live-gateway"
            capture = read_json(capture_dir / "status.json")
            frame = capture_dir / "frame.jpg"
            if (
                capture.get("status") == "live"
                and frame.is_file()
                and 0 <= time.time() - capture.get("heartbeat", 0) < 5
                and 0 <= time.time() - capture.get("captured_at", 0) < 5
            ):
                temporary = folder / "fusion-window-next.jpg"
                temporary.write_bytes(frame.read_bytes())
                path = folder / "fusion-window.jpg"
                temporary.replace(path)
                return dict(
                    url=self.catalog.asset(path),
                    at=datetime.fromtimestamp(capture["captured_at"], UTC).isoformat(),
                    document=capture.get("window_title", "Fusion window"),
                    refresh_ms=250,
                    scope="Live Fusion window; not a verification verdict",
                )
            raise ValueError(
                "Fusion viewport unavailable. Start the companion live window capture."
            )

    def drawing_page(self, url, page=1):
        if not url.startswith("/artifact/"):
            raise ValueError("Choose a registered drawing")
        source = self.catalog.path(unquote(url[len("/artifact/") :]))
        if source not in self.catalog.allowed or source.suffix.lower() != ".pdf":
            raise ValueError("Choose a registered PDF drawing")
        if not shutil.which("pdftoppm") or not shutil.which("pdfinfo"):
            raise ValueError("PDF preview needs Poppler. The original PDF is still available.")
        with self.pdf_lock:
            info = subprocess.run(
                ["pdfinfo", str(source)], capture_output=True, text=True, timeout=10, check=True
            )
            found = re.search(r"^Pages:\s+(\d+)", info.stdout, re.MULTILINE)
            count = int(found[1]) if found else 1
            if page < 1 or page > count:
                raise ValueError("Page is outside this PDF")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:24]
            folder = self.root / "output/control-center/pdf-previews"
            folder.mkdir(parents=True, exist_ok=True)
            prefix = folder / f"{digest}-{page}"
            image = prefix.with_suffix(".png")
            if not image.is_file():
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(page),
                        "-singlefile",
                        "-scale-to",
                        "1800",
                        "-png",
                        str(source),
                        str(prefix),
                    ],
                    capture_output=True,
                    timeout=25,
                    check=True,
                )
            return dict(image=self.catalog.asset(image), page=page, pages=count, pdf=url)

    def state(self):
        with self.catalog.lock:
            manifests = self.catalog.manifests()
            parts = self.catalog.parts(manifests)
            names = {p["id"]: p["label"] for p in parts}
            drawing_names = {
                a.get("sha256"): part["label"]
                for part in parts
                for a in manifests[part["id"]].get("inputs", {}).get("drawings", [])
            }
            for job, manifest in manifests.items():
                if job not in names:
                    hashes = [
                        a.get("sha256") for a in manifest.get("inputs", {}).get("drawings", [])
                    ]
                    label = next((drawing_names[h] for h in hashes if h in drawing_names), None)
                    if label:
                        names[job] = label + " · retained run"
            timeline = []
            for job, d in manifests.items():
                for e in d.get("events", []):
                    if e.get("event") in {
                        "target_accepted",
                        "verification_completed",
                        "learning_change_saved",
                        "supervisor_decision",
                        "checks_completed",
                        "execution_interrupted",
                    }:
                        timeline.append(self.catalog.event(e, job, names.get(job, job)))
            learning = self.catalog.learning(manifests)
            running = bool(self.process and self.process.poll() is None)
            intakes = []
            for p in self.inputs.glob("*/intake.json"):
                item = read_json(p)
                if item:
                    if (
                        item.get("job") == self.active_id
                        and not running
                        and item.get("status") == "started"
                    ):
                        item["worker_exit_code"] = self.process.returncode if self.process else None
                        item["status"] = manifests.get(self.active_id, {}).get("status", "stopped")
                    intakes.append(self.public_intake(item))
            return dict(
                parts=parts,
                timeline=sorted(timeline, key=lambda e: e.get("at") or "", reverse=True),
                learning=learning,
                worker={**self.worker, "running": running, "job": self.active_id},
                intakes=sorted(intakes, key=lambda x: x["at"], reverse=True),
                generated_at=now(),
                enable_runs=self.enable_runs,
                demo=dict(
                    drawing=self.catalog.asset("output/pdf/silta-clevis-demo.pdf"),
                    label="Clevis demo",
                    mode="replay",
                ),
                stats=dict(
                    parts=len(parts),
                    verified=sum(p["verified"] for p in parts),
                    checks=len(learning["checks"]),
                    runs=len(manifests),
                ),
                slides=[
                    self.catalog.asset("output/presentation/slide-1.png"),
                    self.catalog.asset("output/presentation/slide-2.png"),
                ],
            )


def make_handler(center):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def payload(self, data, status=200):
            body = json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_file(self, p):
            size = p.stat().st_size
            start, end, status = 0, size - 1, 200
            requested = self.headers.get("Range")
            if requested:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
                if not match or not any(match.groups()):
                    self.send_error(416)
                    return
                a, b = match.groups()
                start = int(a) if a else max(0, size - int(b))
                end = min(int(b), size - 1) if a and b else size - 1
                if start > end or start >= size:
                    self.send_error(416)
                    return
                status = 206
            self.send_response(status)
            kind = mimetypes.guess_type(p)[0] or "application/octet-stream"
            if p.suffix in {".py", ".md", ".nc"}:
                kind = "text/plain; charset=utf-8"
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-cache")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            try:
                with p.open("rb") as source:
                    source.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = source.read(min(262144, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/api/state":
                self.payload(center.state())
                return
            if path == "/api/drawing":
                try:
                    query = parse_qs(urlsplit(self.path).query)
                    self.payload(
                        center.drawing_page(query["path"][0], int(query.get("page", ["1"])[0]))
                    )
                except (ValueError, KeyError, OSError, subprocess.SubprocessError):
                    self.payload(
                        dict(error="Drawing preview unavailable. Open the original PDF."), 400
                    )
                return
            if path.startswith("/api/demo/"):
                try:
                    self.payload(center.demo.public(path.rsplit("/", 1)[1]))
                except ValueError as e:
                    self.payload(dict(error=str(e)), 404)
                return
            if path.startswith("/api/jobs/"):
                try:
                    self.payload(center.detail(path.rsplit("/", 1)[1]))
                except ValueError as e:
                    self.payload(dict(error=str(e)), 404)
                return
            if path.startswith("/artifact/"):
                try:
                    p = center.catalog.path(path[len("/artifact/") :])
                except ValueError:
                    self.send_error(404)
                    return
                if p not in center.catalog.allowed or not p.is_file():
                    self.send_error(404)
                    return
                self.send_file(p)
                return
            vendor = {
                "three.module.js": "build/three.module.js",
                "three.core.js": "build/three.core.js",
                "OrbitControls.js": "examples/jsm/controls/OrbitControls.js",
                "STLLoader.js": "examples/jsm/loaders/STLLoader.js",
            }
            if path.startswith("/vendor/") and path[8:] in vendor:
                p = center.root / "cnc_simulator/viewer/node_modules/three" / vendor[path[8:]]
            elif path == "/reference":
                p = center.root / "cnc_simulator/references/joel-demo/index.html"
            elif path in {
                "/",
                "/index.html",
                "/app.js",
                "/style.css",
                "/model.js",
                "/replay.mjs",
                "/aria.mjs",
                "/history.mjs",
                "/walkthrough.mjs",
                "/staged-replay.mjs",
            }:
                p = center.root / "applications/control-center" / (path.lstrip("/") or "index.html")
            else:
                self.send_error(404)
                return
            if not p.is_file():
                self.send_error(404)
                return
            self.send_file(p)

        def do_POST(self):
            expected = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Origin") != expected or self.headers.get("Host") != expected[7:]:
                self.payload(dict(error="Only same-origin local requests are accepted"), 403)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 25_000_000:
                    raise ValueError("Request is too large")
                body = self.rfile.read(size)
                path = urlsplit(self.path).path
                if path == "/api/upload":
                    result = center.intake(
                        unquote(self.headers.get("X-Filename", "drawing.pdf")), body
                    )
                elif path == "/api/demo/start":
                    result = center.start_demo(json.loads(body)["id"])
                elif path == "/api/demo/play":
                    result = center.demo.play(json.loads(body)["id"])
                elif path == "/api/demo/reset":
                    result = center.demo.reset(json.loads(body)["id"])
                elif path == "/api/start":
                    result = center.start(json.loads(body)["id"])
                elif path == "/api/worker/check":
                    result = center.ping()
                elif path == "/api/worker/frame":
                    result = center.capture_frame()
                else:
                    self.send_error(404)
                    return
                self.payload(result)
            except (ValueError, KeyError, OSError, RuntimeError) as e:
                self.payload(dict(error=str(e)), 400)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args()
    center = Center(enable_runs=not args.review_only)
    center.state()  # Register only curated evidence assets before serving.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(center))
    print(f"SILTA control center: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
