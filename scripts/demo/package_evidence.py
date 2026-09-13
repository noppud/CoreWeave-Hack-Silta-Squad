"""Portable judge evidence; build locally, publish only by explicit --publish invocation.

uv run python scripts/demo/package_evidence.py
hsec exec --only COREWEAVE_WANDB_API_KEY -- uv run python scripts/demo/package_evidence.py \
  --bundle output/submission/<bundle> --publish
"""

import argparse
import hashlib
import html
import json
import os
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {".pdf", ".step", ".stp", ".nc", ".json", ".py", ".md", ".png", ".stl"}
SECRET = re.compile(r"wandb_v1_[A-Za-z0-9_-]{30,}|sk-proj-[A-Za-z0-9_-]{20,}")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def normalized(value):
    """Retain source references without requiring this host or private workspace."""
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if isinstance(value, str):
        value = value.replace(str(ROOT) + "/", "")
        value = re.sub(r"(?:/[^\s\"']*)?\.private/[^\s\"']*", "[private-source-omitted]", value)
        value = re.sub(
            r"/(?:Users|private/var|var/folders|Applications|Library)/[^\s\"']*",
            "[host-path-omitted]",
            value,
        )
        if SECRET.search(value):
            raise ValueError("Credential-like text detected; refusing package")
    return value


class Bundle:
    def __init__(self, directory):
        self.directory = directory
        self.files = []
        self.omitted = []
        self.by_source = {}

    def add(self, source, relative, job=None, expected=None):
        source = Path(source).resolve()
        try:
            ref = source.relative_to(ROOT)
        except ValueError:
            self.omitted.append({"source_ref": "external-host-file", "source_job_id": job})
            return None
        if ".private" in ref.parts or not source.is_file():
            self.omitted.append(
                {
                    "source_ref": normalized(str(ref)),
                    "source_job_id": job,
                    "reason": "private or unavailable",
                }
            )
            return None
        raw = source.read_bytes()
        original_hash = digest(raw)
        if expected and original_hash != expected:
            raise ValueError(f"Artifact changed: {ref}")
        if str(ref) in self.by_source:
            return self.by_source[str(ref)]
        target = self.directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        rewritten = source.suffix in {".json", ".md", ".py", ".txt", ".html"}
        if source.suffix == ".json":
            raw = (json.dumps(normalized(json.loads(raw)), indent=2) + "\n").encode()
        elif rewritten:
            raw = normalized(raw.decode()).encode()
        target.write_bytes(raw)
        item = {
            "path": str(relative),
            "sha256": digest(raw),
            "bytes": len(raw),
            "source_ref": str(ref),
            "source_sha256": original_hash,
            "source_job_id": job,
            "normalized_host_paths": rewritten,
        }
        self.files.append(item)
        self.by_source[str(ref)] = item
        return item

    def refs(self, value, job, counter):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                source = Path(value["path"])
                if not source.is_absolute():
                    source = ROOT / source
                if source.suffix.lower() in ALLOWED:
                    counter[0] += 1
                    self.add(
                        source,
                        Path("jobs") / job / "artifacts" / f"{counter[0]:04d}-{source.name}",
                        job,
                        value["sha256"],
                    )
                else:
                    self.omitted.append(
                        {
                            "source_ref": normalized(str(source)),
                            "source_sha256": value["sha256"],
                            "source_job_id": job,
                            "reason": "Binary project/archive not in compact judge bundle",
                        }
                    )
            for child in value.values():
                self.refs(child, job, counter)
        elif isinstance(value, list):
            for child in value:
                self.refs(child, job, counter)


def add_collection_capture_proofs(bundle):
    """Retain exact probe implementation and honestly assisted capture provenance."""
    probe = ROOT / "output/evaluation/umc11-v6-comparison-budget-probe.json"
    if probe.is_file():
        bundle.add(probe, Path("proofs/collection-audit") / probe.name)
        bundle.refs(read(probe).get("sources", []), "collection-audit", [21000])
    captures = [
        ROOT / "output/video/umc12-close-capture/capture-receipt-portable-v2.json",
        ROOT / "output/video/umc11-close-capture-r3/capture-receipt-portable.json",
    ]
    for index, capture in enumerate(captures):
        if not capture.is_file():
            continue
        record = read(capture)
        bundle.add(capture, Path("proofs") / capture.parent.name / capture.name)
        selected = {key: record.get(key) for key in (
            "original_capture_receipt", "operator_assistance", "visual_review",
            "implementation_sources", "finished_stock_artifact", "portable_v2_derivation",
        )}
        bundle.refs(selected, record["source_job"], [22000 + index * 2000])
        review = record.get("visual_review")
        if review:
            bundle.refs(read(review["path"]), record["source_job"], [23000 + index * 2000])



def add_stage_rehearsals(bundle):
    """Receipt-selected rehearsals remain separate from shared-learning campaign counts."""
    records = []
    for presentation in sorted((ROOT / "runs").glob("stage-*-presentation.json")):
        receipt = read(presentation)
        job = presentation.name.removesuffix("-presentation.json")
        manifest_path = ROOT / "runs" / job / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = read(manifest_path)
        if receipt.get("no_main_learning_promotion") is not True:
            raise ValueError(f"Stage receipt does not declare isolated learning: {job}")
        if receipt.get("input_digest") != manifest.get("input_digest"):
            raise ValueError(f"Stage receipt input differs: {job}")
        main = Path(receipt["learning_source"]).resolve()
        shadow = Path(receipt["shadow_learning_directory"]).resolve()
        if shadow == main or not shadow.is_relative_to(ROOT / "runs"):
            raise ValueError(f"Stage learning directory is not separate: {job}")
        base = Path("stage-rehearsals") / job
        bundle.add(presentation, base / "presentation.json")
        bundle.add(manifest_path, base / "run-record.json")
        bundle.add(manifest_path.parent / "run-receipt.json", base / "weave-receipt.json")
        for recovery in sorted(manifest_path.parent.glob("operator-recovery-*.json")):
            bundle.add(recovery, base / recovery.name, expected=digest(recovery.read_bytes()))
        for name, expected in receipt.get("ending_learning_sha256", {}).items():
            source = shadow / name
            if source.is_symlink() or (main / name).is_file() and source.samefile(main / name):
                raise ValueError(f"Stage learning aliases main learning: {job}/{name}")
            bundle.add(source, base / "shadow-learning" / name, expected=expected)
        bundle.refs(
            {
                "inputs": manifest["inputs"],
                "target": manifest.get("target"),
                "best_candidate": manifest.get("best_candidate"),
                "verifications": [
                    e["verification"] for e in manifest.get("events", []) if e.get("verification")
                ],
                "learning_sources": manifest.get("learning_sources", {}),
            },
            job,
            [20000],
        )
        for source in sorted((ROOT / "runs" / f"{job}-playback").rglob("*")):
            if source.is_file() and source.suffix in {".json", ".png", ".txt"}:
                bundle.add(
                    source,
                    base / "playback" / source.relative_to(ROOT / "runs" / f"{job}-playback"),
                )
        preparation = None
        if receipt.get("prepared_at"):
            preparation = (
                datetime.fromisoformat(receipt["prepared_at"])
                - datetime.fromisoformat(receipt["preparation_started_at"])
            ).total_seconds()
        records.append(
            {
                "job_id": job,
                "status": manifest["status"],
                "collection_warning": manifest.get("collection_warning"),
                "category": "stage_rehearsal_shadow_learning",
                "record_path": str(base / "run-record.json"),
                "presentation_receipt": str(base / "presentation.json"),
                "counted_in_campaign_completed_drawings": False,
                "preparation_wall_seconds": preparation,
                "presenter_pause_seconds": receipt.get("presentation_pause_seconds"),
                "verifications": receipt.get("verifications", []),
                "best_estimated_machining_seconds": None if manifest.get("collection_warning")
                else (manifest.get("best_verification") or {}).get("machining_seconds"),
                "observed_motion_playbacks": sum(
                    p.get("tool_motion_observed") is True for p in receipt.get("playbacks", [])
                ),
                "shadow_learning_files_separate": True,
                "initial_learning_sha256": receipt.get("initial_learning_sha256"),
                "ending_learning_sha256": receipt.get("ending_learning_sha256"),
                "scope": "Prepared CAD/CAM, released live verification, then playback; "
                "timings are separate; no shared-learning promotion",
            }
        )
    return records


def add_stage_recoveries(bundle):
    """Retain resumed shadow-learning jobs without calling them fresh rehearsals."""
    rows = []
    for provenance_path in sorted((ROOT / "runs").glob("stage-*/workspace/resume-provenance.json")):
        run = provenance_path.parent.parent
        manifest_path = run / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest, provenance = read(manifest_path), read(provenance_path)
        learning = provenance.get("learning_provenance") or {}
        if learning.get("uses_main_learning_directory") is not False:
            raise ValueError(f"Stage recovery does not declare shadow learning: {run.name}")
        shadow = Path(learning["learning_directory"]).resolve()
        if shadow == (ROOT / "learning").resolve() or not shadow.is_relative_to(ROOT / "runs"):
            raise ValueError(f"Stage recovery learning directory is not separate: {run.name}")
        chain, visited, current = [], {manifest_path.resolve()}, provenance
        while True:
            source = Path(current["source_manifest"]).resolve()
            if source in visited or not source.is_relative_to(ROOT / "runs"):
                raise ValueError("Stage recovery source chain is cyclic or external")
            visited.add(source)
            raw = source.read_bytes()
            if digest(raw) != current["source_manifest_sha256"]:
                raise ValueError(f"Stage recovery source changed: {source}")
            prior = json.loads(raw)
            if (prior.get("input_digest") != manifest.get("input_digest")
                    or prior.get("target_digest") != manifest.get("target_digest")):
                raise ValueError("Stage recovery source input or target differs")
            chain.append({"path": str(source), "sha256": digest(raw),
                          "job_id": prior["job_id"]})
            presentation = ROOT / "runs" / f"{prior['job_id']}-presentation.json"
            if presentation.is_file():
                origin = read(presentation)
                if (origin.get("no_main_learning_promotion") is not True
                        or origin.get("input_digest") != manifest.get("input_digest")
                        or Path(origin["shadow_learning_directory"]).resolve() != shadow):
                    raise ValueError("Stage recovery origin does not match isolated rehearsal")
                break
            prior_provenance = source.parent / "workspace/resume-provenance.json"
            current = read(prior_provenance)
            bundle.add(prior_provenance, Path("stage-recoveries") / run.name
                       / f"source-{len(chain)}-resume-provenance.json")
        base = Path("stage-recoveries") / run.name
        bundle.add(provenance_path, base / "resume-provenance.json")
        bundle.add(manifest_path, base / "run-record.json")
        bundle.add(presentation, base / "original-presentation.json")
        if (run / "run-receipt.json").is_file():
            bundle.add(run / "run-receipt.json", base / "weave-receipt.json")
        bundle.refs(chain, run.name, [30000])
        initial = learning["initial_file_sha256"]
        for name, kind in (("checks.py", "checks"), ("cad_cam.md", "main_prompt")):
            ref = manifest.get("learning_sources", {}).get(manifest.get("versions", {}).get(kind))
            if not ref or ref["sha256"] != initial.get(name):
                raise ValueError("Stage recovery initial learning source differs")
            live = shadow / name
            main = ROOT / "learning" / name
            if live.is_symlink() or main.is_file() and live.samefile(main):
                raise ValueError("Stage recovery learning aliases main learning")
            bundle.add(Path(ref["path"]), base / "initial-learning" / name,
                       expected=initial[name])
        bundle.refs({"inputs": manifest["inputs"], "target": manifest.get("target"),
                     "best_candidate": manifest.get("best_candidate"),
                     "best_verification": manifest.get("best_verification"),
                     "events": manifest.get("events", []),
                     "learning_sources": manifest.get("learning_sources", {})}, run.name, [31000])
        best = manifest.get("best_verification") or {}
        valid = not manifest.get("collection_warning") and best.get("completed") is True \
            and best.get("status") == "passed"
        rows.append({"job_id": run.name, "status": manifest["status"],
                     "category": "stage_recovery_shadow_learning",
                     "counted_in_campaign_completed_drawings": False,
                     "fresh_preparation_or_presentation": False,
                     "record_path": str(base / "run-record.json"),
                     "resume_provenance": str(base / "resume-provenance.json"),
                     "source_chain": chain, "initial_learning_sha256": initial,
                     "current_learning_versions": manifest.get("current_versions"),
                     "current_learning_sha256": {
                         name: manifest.get("learning_sources", {}).get(
                             manifest.get("current_versions", {}).get(kind), {}
                         ).get("sha256")
                         for name, kind in (("checks.py", "checks"),
                                            ("cad_cam.md", "main_prompt"))
                     },
                     "collection_warning": manifest.get("collection_warning"),
                     "best_estimated_machining_seconds": (
                         best.get("machining_seconds") if valid else None),
                     "scope": "Recovery of prepared rehearsal using separate shadow learning; "
                              "no fresh live-presentation or playback claim"})
    return rows


def build(include_media):
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    directory = ROOT / "output/submission" / f"silta-fusion-evidence-{stamp}"
    directory.mkdir(parents=True, exist_ok=False)
    bundle = Bundle(directory)
    history_path = ROOT / "runs/four-part-learning-summary.json"
    history = read(history_path)
    campaign_path = ROOT / "runs/demo-campaign.json"
    campaign = read(campaign_path) if campaign_path.is_file() else {}
    paths = [ROOT / "runs" / p["final_run"] / "manifest.json" for p in history["parts"]]
    paths += [Path(p["manifest_path"]) for p in campaign.get("parts", []) if p.get("manifest_path")]
    jobs, pending, seen = [], [], set()
    for path in paths:
        if not path.is_file():
            pending.append({"manifest_ref": normalized(str(path)), "status": "not_available"})
            continue
        m = read(path)
        job = m["job_id"]
        if ((ROOT / "runs" / f"{job}-presentation.json").is_file()
                or (job.startswith("stage-")
                    and (path.parent / "workspace/resume-provenance.json").is_file())):
            # A stage receipt is categorized below even if a campaign row links it.
            continue
        operator_recoveries = []
        for recovery in sorted(list(path.parent.glob("operator-recovery-*.json"))
                               + list(path.parent.glob("operator-collection-*.json"))
                               + list((path.parent / "workspace").glob("manual-trial-*.json"))):
            item = bundle.add(
                recovery,
                Path("jobs") / job / recovery.name,
                job,
                expected=digest(recovery.read_bytes()),
            )
            if item:
                operator_recoveries.append(item["path"])
        best = m.get("best_verification") or {}
        if (
            m.get("collection_warning")
            or m.get("status") != "completed"
            or best.get("status") != "passed"
            or best.get("completed") is not True
        ):
            pending.append(
                {
                    "job_id": job,
                    "status": m.get("status"),
                    "collection_warning": m.get("collection_warning"),
                    "verified_best": (not m.get("collection_warning")
                                      and best.get("status") == "passed"
                                      and best.get("completed") is True),
                    "operator_recovery_receipts": operator_recoveries,
                }
            )
            if (not m.get("collection_warning") and best.get("status") == "passed"
                    and best.get("completed") is True):
                bundle.add(path, Path("proofs") / job / "incomplete-run-record.json", job)
                bundle.refs(
                    {
                        "inputs": m["inputs"],
                        "target": m["target"],
                        "best_candidate": m["best_candidate"],
                        "best_verification": best,
                        "learning_sources": m.get("learning_sources", {}),
                    },
                    job,
                    [0],
                )
            continue
        identity = tuple(sorted(item["sha256"] for item in m["inputs"]["drawings"]))
        if identity in seen:
            continue
        seen.add(identity)
        record = bundle.add(path, Path("jobs") / job / "run-record.json", job)
        bundle.refs(
            {
                "inputs": m["inputs"],
                "target": m["target"],
                "best_candidate": m["best_candidate"],
                "best_verification": best,
                "learning_sources": m.get("learning_sources", {}),
            },
            job,
            [0],
        )
        # Include any retained learning proposal bytes explicitly referenced by this job.
        for index, event in enumerate(m.get("events", [])):
            proposal = event.get("proposal") or {}
            if proposal.get("artifact_path"):
                source = Path(proposal["artifact_path"])
                bundle.add(source, Path("jobs") / job / "learning" / f"{index}-{source.name}", job)
        receipt = path.parent / "run-receipt.json"
        if receipt.is_file():
            bundle.add(receipt, Path("jobs") / job / "weave-receipt.json", job)
        jobs.append(
            {
                "job_id": job,
                "drawing_sha256": list(identity),
                "status": m["status"],
                "candidate_id": m["best_candidate"]["id"],
                "machining_seconds": best["machining_seconds"],
                "estimated_cost": best.get("estimated_cost"),
                "coverage": best.get("coverage"),
                "record_path": record["path"],
                "operator_recovery_receipts": operator_recoveries,
            }
        )
    # Retain the exact failure/transfer records supporting the learning story.
    for proof_job in ("learning-soft-jaw-a3", "learning-part-b1", "learning-part-c2"):
        proof_path = ROOT / "runs" / proof_job / "manifest.json"
        if not proof_path.is_file():
            continue
        proof = read(proof_path)
        bundle.add(proof_path, Path("proofs") / proof_job / "run-record.json", proof_job)
        for index, event in enumerate(proof.get("events", [])):
            proposal = event.get("proposal") or {}
            if proposal.get("artifact_path"):
                source = Path(proposal["artifact_path"])
                bundle.add(
                    source,
                    Path("proofs") / proof_job / "learning" / f"{index}-{source.name}",
                    proof_job,
                )
    fixed = [
        history_path,
        campaign_path,
        ROOT / "learning/checks.py",
        ROOT / "learning/cad_cam.md",
        ROOT / "output/evaluation/learning-evaluation.json",
        ROOT / "output/evaluation/replay-evidence.json",
        ROOT / "output/evaluation/learning-transfer.json",
        ROOT / "output/evaluation/fusion-campaign.json",
        ROOT / "output/sponsors/aria-review.json",
        ROOT / "output/sponsors/aria-response.md",
        ROOT / "output/sponsors/weave-demo-links.md",
        ROOT / "output/sponsors/fusion-native-scores.json",
        ROOT / "docs/submission.md",
        ROOT / "docs/learning-results.md",
        ROOT / "docs/learning-transfer.md",
        ROOT / "docs/demo-evaluation.md",
        ROOT / "docs/stock-regeneration-audit.md",
        ROOT / "output/evaluation/collection-invalidations.json",
        ROOT / "runs/demo-umc-umc-11-recovery4/manifest-before-incumbent-summary-fix.json",
        ROOT / "runs/demo-umc-umc-11-recovery4/manifest-summary-repair.json",
        ROOT / "docs/weave-evaluation-dashboard.md",
        ROOT / "docs/demo-runbook.md",
        ROOT / "docs/reviews/finned-rehearsal-collection.md",
        ROOT / "docs/verified-improvements.md",
        ROOT / "docs/slide-pdf.md",
        ROOT / "scripts/demo/plot_verified_improvements.py",
        ROOT / "scripts/demo/export_slide_pdf.py",
        ROOT / "output/presentation/evidence.json",
        ROOT / "output/presentation/film-evidence.json",
        ROOT / "output/presentation/film-umc08-source-receipt.json",
        ROOT / "output/presentation/film-umc09-source-receipt.json",
        ROOT / "output/presentation/film-gallery-evidence.json",
        ROOT / "output/presentation/part-gallery.json",
    ]
    fixed += sorted((ROOT / "output/evaluation").glob("checks-*.py"))
    slide_pdf_receipt = ROOT / "output/pdf/silta-demo-slides.json"
    if slide_pdf_receipt.is_file():
        slides = read(slide_pdf_receipt)
        source = ROOT / slides["pdf"]
        bundle.add(source, Path("presentation") / source.name, expected=slides["sha256"])
        for reference in slides["sources"]:
            source = ROOT / reference["path"]
            bundle.add(source, Path("presentation") / source.name, expected=reference["sha256"])
        fixed.append(slide_pdf_receipt)
    # Validate the chart against its generation receipt before packaging; the
    # normalized bundle records both original and portable-copy hashes.
    for chart_receipt in (
        ROOT / "output/evaluation/verified-improvements.json",
        ROOT / "output/evaluation/cage-manual-retest.json",
    ):
        if not chart_receipt.is_file():
            continue
        chart = read(chart_receipt)
        references = [
            chart["source_report"],
            *chart["artifacts"],
            {
                "path": str(ROOT / "scripts/demo/plot_verified_improvements.py"),
                "sha256": chart["generator_sha256"],
            },
        ]
        for reference in references:
            source = Path(reference["path"])
            if not source.is_absolute():
                source = ROOT / source
            bundle.add(
                source, Path("context") / source.relative_to(ROOT), expected=reference["sha256"]
            )
        chart_counter = [10000]
        for pair in chart["pairs"]:
            for key in ("first_valid", "best_valid"):
                candidate = pair[key]
                source = Path(candidate["manifest"])
                bundle.add(
                    source,
                    Path("proofs") / source.parent.name / "chart-run-record.json",
                    expected=candidate["manifest_sha256"],
                )
                bundle.refs(candidate["evidence"], source.parent.name, chart_counter)
        fixed.append(chart_receipt)
    dashboard_receipts = []
    for source in sorted((ROOT / "output/evaluation").glob("native-summary-*/publication.json")):
        receipt = read(source)
        publication = receipt.get("publication", {})
        if not (
            publication.get("readback_finalized")
            and publication.get("native_score_aggregates_verified")
        ):
            continue
        fixed.append(source)
        for key in ("source_replay", "source_receipt"):
            reference = receipt[key]
            original = Path(reference["path"])
            if not original.is_absolute():
                original = ROOT / original
            bundle.add(
                original, Path("context") / original.relative_to(ROOT), expected=reference["sha256"]
            )
        dashboard_receipts.append(
            {
                "path": str(Path("context") / source.relative_to(ROOT)),
                "source_sha256": digest(source.read_bytes()),
                "weave_urls": receipt.get("weave_urls", []),
                "scope": receipt.get("scope"),
            }
        )
    for source in fixed:
        if source.is_file():
            bundle.add(source, Path("context") / source.relative_to(ROOT))
    collection_audit = ROOT / "output/evaluation/collection-invalidations.json"
    if collection_audit.is_file():
        bundle.refs(read(collection_audit), "collection-audit", [20000])
    add_collection_capture_proofs(bundle)
    rehearsals = add_stage_rehearsals(bundle)
    stage_recoveries = add_stage_recoveries(bundle)
    # The film is frozen. Retain its exact small sources and explicitly inventory
    # omitted raw recordings; never silently substitute a newer source revision.
    film_path = ROOT / "output/presentation/film-evidence.json"
    if film_path.is_file():
        film = read(film_path)
        capture_receipts = [
            film["machine_source_receipt"],
            *film.get("additional_source_receipts", []),
        ]
        media_jobs = {}
        for capture in capture_receipts:
            receipt = read(ROOT / capture)
            for media in receipt["media"]:
                media_jobs[(ROOT / media["path"]).resolve()] = receipt["source_job"]
        for reference in film.get("sources", []):
            source = Path(reference["path"])
            if not source.is_absolute():
                source = ROOT / source
            if source.suffix.lower() == ".mp4":
                if digest(source.read_bytes()) != reference["sha256"]:
                    raise ValueError(f"Frozen film source changed: {source.name}")
                bundle.omitted.append(
                    {
                        "source_ref": str(source.relative_to(ROOT)),
                        "source_sha256": reference["sha256"],
                        "source_job_id": media_jobs[source.resolve()],
                        "reason": "Raw recording omitted; capture receipt retained",
                    }
                )
            else:
                bundle.add(
                    source, Path("context") / source.relative_to(ROOT), expected=reference["sha256"]
                )
    if include_media:
        for name in (
            "silta-loop-demo.mp4",
            "slide-1.png",
            "slide-2.png",
            "slides.html",
            "part-gallery.png",
            "part-gallery.html",
            "part-gallery.variety.png",
        ):
            source = ROOT / "output/presentation" / name
            if source.is_file():
                expected = (
                    film["sha256"]
                    if name == "silta-loop-demo.mp4" and film_path.is_file()
                    else None
                )
                bundle.add(source, Path("presentation") / name, expected=expected)
    manifest = {
        "schema_version": 1,
        "bundle_id": directory.name,
        "generated_at": stamp,
        "scope": "Fusion evidence snapshot; completed jobs on distinct drawings only",
        "completed_distinct_drawings": len(jobs),
        "target_count": 10,
        "campaign_status_snapshot": campaign.get("status"),
        "pending_jobs": pending,
        "evaluation_dashboard_receipts": dashboard_receipts,
        "jobs": jobs,
        "stage_rehearsals": rehearsals,
        "stage_recoveries": stage_recoveries,
        "files": bundle.files,
        "omitted_source_references": bundle.omitted,
        "notes": [
            "JSON/source references normalized; source and packaged hashes are separate",
            "No credentials, private workspaces or host dependencies included",
            "F3D/project archives omitted from compact bundle; original source references retained",
            "Retrospective replay; not held-out generalization or historical promotion gate",
            "Indexed UMC video and earlier three-axis learning are separate examples",
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = "".join(
        f'<tr><td><a href="{html.escape(j["record_path"])}">{html.escape(j["job_id"])}</a></td>'
        f"<td>{j['machining_seconds']:.3f}s</td><td>completed / verified</td></tr>"
        for j in jobs
    )
    files = "".join(
        f'<li><a href="{html.escape(f["path"])}">{html.escape(f["path"])}</a></li>'
        for f in bundle.files
    )
    media_links = (
        '<p><a href="presentation/silta-loop-demo.mp4">Demo film</a> · '
        '<a href="presentation/slides.html">Two slides</a></p>'
        if include_media
        else "<p>Media omitted from this compact snapshot.</p>"
    )
    dashboard_links = "".join(
        f'<p><a href="{html.escape(receipt["path"])}">Corrected native Weave dashboard receipt</a> '
        + " · ".join(
            f'<a href="{html.escape(url)}">Evaluation {i + 1}</a>'
            for i, url in enumerate(receipt["weave_urls"])
        )
        + "</p>"
        for receipt in dashboard_receipts
    )
    rehearsal_links = "".join(
        f'<li><a href="{html.escape(r["presentation_receipt"])}">'
        f"{html.escape(r['job_id'])}</a>: {html.escape(r['status'])}; "
        f"{r['observed_motion_playbacks']} observed-motion playbacks. "
        "Preparation, live verification and machining estimates "
        "are separate in the receipt.</li>"
        for r in rehearsals
    )
    recovery_links = "".join(
        f'<li><a href="{html.escape(r["resume_provenance"])}">'
        f'{html.escape(r["job_id"])}</a>: {html.escape(r["status"])}; '
        'resumed shadow-learning job, not a fresh presentation.</li>'
        for r in stage_recoveries
    )
    page = f"""<!doctype html><meta charset="utf-8"><title>Silta Fusion evidence</title>
<style>
body{{font:17px system-ui;max-width:1080px;margin:60px auto;padding:0 24px;color:#172021}}
td,th{{padding:10px;text-align:left}}a{{color:#146858}}li{{margin:8px 0}}
</style>
<h1>Silta / Fusion evidence</h1><p>Snapshot {stamp}.
<b>{len(jobs)} distinct drawings have packaged completed jobs.</b> Original goal: 10.</p>
<p>Fixed CAD → CAM → cheap checks → Fusion and finished-stock verification → judge.
Learning carries checks and planning guidance into later jobs.</p>
<table><tr><th>Job</th><th>Estimated machining</th><th>Result</th></tr>{rows}</table>
<p>Different parts have different machining work.
Their final times are not a controlled learning curve.</p>
<p><a href="manifest.json">Manifest, source references and SHA256 hashes</a> ·
<a href="context/output/evaluation/learning-evaluation.json">Published Weave evaluations</a> ·
<a href="context/output/sponsors/aria-response.md">Actual ARIA response</a></p>
{media_links}
{dashboard_links}
<h2>Stage rehearsals / isolated learning</h2>
<p>Separate evidence; not added to the shared-learning campaign count.</p>
<ul>{rehearsal_links}</ul>
<h2>Stage recoveries / isolated learning</h2><ul>{recovery_links}</ul>
<p><a href="context/output/presentation/film-umc08-source-receipt.json">
UMC08 film capture provenance</a></p>
<details><summary>All packaged files</summary><ul>{files}</ul></details>"""
    (directory / "index.html").write_text(page)
    archive = directory.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for source in sorted(directory.rglob("*")):
            if source.is_file():
                output.write(source, str(source.relative_to(directory)))
    print(
        json.dumps(
            {
                "bundle": str(directory),
                "archive": str(archive),
                "completed_drawings": len(jobs),
                "files": len(bundle.files),
                "bytes": archive.stat().st_size,
            }
        )
    )
    return directory


def publish(directory):
    import wandb

    key = os.environ.get("COREWEAVE_WANDB_API_KEY")
    if not key:
        raise RuntimeError("Use narrowly scoped hsec injection of COREWEAVE_WANDB_API_KEY")
    manifest = read(directory / "manifest.json")
    with wandb.init(
        entity="silta",
        project="coreweave-hack-silta-squad",
        job_type="evidence-package",
        name=manifest["bundle_id"],
        settings=wandb.Settings(api_key=key),
    ) as run_handle:
        artifact = wandb.Artifact(
            "silta-fusion-judge-evidence",
            type="evidence",
            metadata={
                "bundle_id": manifest["bundle_id"],
                "completed_drawings": manifest["completed_distinct_drawings"],
                "partial": manifest["completed_distinct_drawings"] < 10,
            },
        )
        artifact.add_dir(str(directory))
        logged = run_handle.log_artifact(artifact, aliases=[manifest["bundle_id"]])
        logged.wait()
        print(json.dumps({"artifact": logged.qualified_name, "run_url": run_handle.url}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="Existing reviewed bundle for optional upload")
    parser.add_argument("--publish", action="store_true", help="Explicit opt-in upload to W&B")
    parser.add_argument("--no-media", action="store_true")
    args = parser.parse_args()
    directory = args.bundle.resolve() if args.bundle else build(not args.no_media)
    if args.publish:
        publish(directory)


if __name__ == "__main__":
    main()
