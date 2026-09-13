"""114-second evidence film, actual Fusion frames plus explicitly labeled evidence graphics.

Run: uv run --with imageio-ffmpeg python scripts/demo/presentation_film.py
Replace only the tail after reviewing real captures:
  uv run --with imageio-ffmpeg python scripts/demo/presentation_film.py \
    --tail-receipts CAPTURE/capture-receipt.json --visually-reviewed
No source recording is modified. No simulated cutting frames are generated.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "output/presentation"
RAW = ROOT / "output/video"
FF = imageio_ffmpeg.get_ffmpeg_exe()
FONT = Path("/System/Library/Fonts/Supplemental")
BG = "#10151c"
ACCENT = "#a6dfc6"
WHITE = "#f3f5f1"
GRAY = "#bdc7ce"
OUT.mkdir(parents=True, exist_ok=True)


def run(args):
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def face(size, bold=False):
    return ImageFont.truetype(str(FONT / ("Arial Bold.ttf" if bold else "Arial.ttf")), size)


def write(draw, xy, value, size=34, color=WHITE, bold=False):
    draw.multiline_text(xy, value, font=face(size, bold), fill=color, spacing=16)


def panel(name, chapter, title, body, foot):
    image = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((1440, 0, 1920, 1080), fill=BG)
    write(draw, (1480, 58), "SILTA", 45, bold=True)
    write(draw, (1480, 182), chapter, 23, ACCENT, True)
    write(draw, (1480, 272), title, 45, bold=True)
    write(draw, (1480, 550), body, 30, GRAY)
    write(draw, (1480, 920), foot, 23, GRAY)
    path = OUT / f"film-{name}.png"
    image.save(path)
    return path


def card(name, picture, chapter, title, metric, lines, foot):
    image = Image.new("RGB", (1920, 1080), BG)
    fitted = ImageOps.contain(Image.open(picture).convert("RGB"), (960, 760))
    image.paste(fitted, ((1040 - fitted.width) // 2, (1080 - fitted.height) // 2))
    draw = ImageDraw.Draw(image)
    write(draw, (80, 62), "SILTA / RETAINED EVIDENCE", 26, GRAY)
    write(draw, (1080, 110), chapter, 24, ACCENT, True)
    write(draw, (1080, 220), title, 49, bold=True)
    write(draw, (1080, 406), metric, 76, ACCENT, True)
    write(draw, (1080, 560), lines, 32)
    write(draw, (80, 979), foot, 25, GRAY)
    path = OUT / f"film-{name}.png"
    image.save(path)
    return path


def video_crop(source):
    if source.name in {"umc08-finished-orbit.mp4", "umc09-stock-only-orbit.mp4"}:
        return "960:720:480:340"
    return "1280:960:340:160"


def fork_orbit_receipt():
    """Bind the stock-only presentation take to the retained completed candidate."""
    from silta.cnc.simulation_video import playback_position

    capture = ROOT / ".private/five-axis/umc09-capture"
    orbit_dir = ROOT / ".private/five-axis/umc09-stock-only-orbit"
    source = json.loads((capture / "source.json").read_text())
    binding = json.loads((capture / "binding.json").read_text())
    setting = json.loads((capture / "stock-only-setting.json").read_text())
    recorder = json.loads((orbit_dir / "recorder-result.json").read_text())
    camera = json.loads((orbit_dir / "camera-trajectory.json").read_text())
    manifest_path = ROOT / "runs/demo-umc-umc-09/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    best = manifest["best_verification"]
    document = source["reference"]["document_name"]
    assert manifest["status"] == "completed" and best["status"] == "passed"
    assert best["completed"] and best["candidate_digest"] == source["candidate_digest"]
    assert manifest["best_candidate"] == source["candidate"]
    assert binding["document"] == setting["document"] == recorder["document"] == document
    assert setting["target_root_body_light_bulb_on"] is False
    assert setting["simulation_end_requested"] is True
    assert recorder["status"] == "recorded" and camera["status"] == "completed"
    assert camera["document_identity"]["name"] == document
    poses = [
        playback_position(json.loads((orbit_dir / n).read_text()), document)["tool_position"]
        for n in ("simulation-before.json", "simulation-after.json")
    ]
    assert poses[0] == poses[1]
    operations = source["candidate"]["parameters"]["postprocessor"]["operations"]
    assert len(operations) == 7 and {o["tool_number"] for o in operations} == {1}
    video = RAW / "umc09-stock-only-orbit.mp4"
    video_hash = hashlib.sha256(video.read_bytes()).hexdigest()
    assert video_hash == hashlib.sha256((orbit_dir / "window-capture.mp4").read_bytes()).hexdigest()
    frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(video))
    assert frames == recorder["complete_frames"]
    raw_receipts = [capture / n for n in ("source.json", "binding.json", "stock-only-setting.json")]
    raw_receipts += [capture / "stock-only-ui/004-inspect.png"]
    raw_receipts += [
        orbit_dir / n
        for n in (
            "recorder-result.json",
            "camera-trajectory.json",
            "simulation-before.json",
            "simulation-after.json",
        )
    ]
    path = OUT / "film-umc09-source-receipt.json"
    path.write_text(
        json.dumps(
            {
                "document": document,
                "source_job": manifest["job_id"],
                "candidate_digest": source["candidate_digest"],
                "verified_seconds": best["machining_seconds"],
                "operation_count": 7,
                "tool_numbers": [1],
                "target_root_body_hidden": True,
                "tool_position_unchanged_during_orbit": True,
                "orbit_camera_updates": camera["actual_update_count"],
                "orbit_camera_update_hz": camera["observed_update_hz"],
                "media": [
                    {
                        "path": str(video.relative_to(ROOT)),
                        "sha256": video_hash,
                        "decoded_frames": frames,
                        "media_duration_seconds": seconds,
                        "capture_wall_seconds": recorder["duration_seconds"],
                        "source": recorder["source"],
                    }
                ],
                "scope": "Camera-only orbit of recorded simulation stock; not a new verification",
                "source_manifest": {
                    "path": str(manifest_path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                },
                "source_receipts": [
                    {
                        "path": str(p.relative_to(ROOT)),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    }
                    for p in raw_receipts
                ],
            },
            indent=2,
        )
        + "\n"
    )
    return video, path, manifest_path


def encode(name, source, seconds, overlay=None, start=0, still=False, fit_window=False):
    target = OUT / f"film-segment-{name}.mp4"
    inputs = ["-loop", "1", "-i", str(source)] if still else ["-ss", str(start), "-i", str(source)]
    if overlay:
        inputs += ["-loop", "1", "-i", str(overlay)]
        framing = (
            "scale=1440:1080:force_original_aspect_ratio=decrease,pad=1440:1080:(ow-iw)/2:(oh-ih)/2"
            if fit_window
            else f"crop={video_crop(source)},scale=1440:1080"
        )
        filtering = (
            f"[0:v]{framing},"
            "pad=1920:1080:0:0:color=0x10151c,setsar=1[base];"
            "[base][1:v]overlay=0:0,format=yuv420p[v]"
        )
        args = ["-filter_complex", filtering, "-map", "[v]"]
    else:
        args = ["-vf", "scale=1920:1080,setsar=1,format=yuv420p"]
    run(
        inputs
        + args
        + [
            "-t",
            str(seconds),
            "-r",
            "60",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    return target


def validated_tail_shots(receipts, *, visually_reviewed=False, source_loader=None):
    """Validate real capture receipts; visual review is an explicit operator attestation."""
    from scripts.demo.capture_verified_candidate import load_source

    if not visually_reviewed or not 1 <= len(receipts) <= 3:
        raise ValueError("Provide one to three captured orbits after visual review")
    durations = {1: [10], 2: [5, 5], 3: [4, 3, 3]}[len(receipts)]
    shots = []
    for path, duration in zip(receipts, durations, strict=True):
        path = Path(path).resolve()
        capture = json.loads(path.read_text())
        if not (
            capture.get("status") == "recorded_requires_visual_review"
            and not capture.get("errors")
            and capture.get("geometry_matches") is True
            and capture.get("source_manifest_unchanged") is True
        ):
            raise ValueError("Capture did not finish with unchanged verified source")
        refs = [
            capture["source_manifest"],
            *capture["media"],
            *capture["evidence"],
            *capture["implementation_sources"],
        ]
        for ref in refs:
            if hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError("Capture source hash changed")
        manifest, candidate, reference, _, _ = (source_loader or load_source)(
            capture["source_manifest"]["path"]
        )
        if not (
            capture["source_job"] == manifest["job_id"]
            and capture["candidate_id"] == candidate.id
            and capture["candidate_digest"] == candidate.digest
            and capture["reference"] == reference
            and capture["verified_seconds"] == manifest["best_verification"]["machining_seconds"]
        ):
            raise ValueError("Capture is not bound to the retained best candidate")
        orbit, playback = capture["orbit"], capture["machine_playback"]
        hidden = capture["target_display_hidden"]["states_after"]
        before = capture["target_display_before"]["states_before"]
        if not (
            orbit["recorder"]["status"] == "recorded"
            and orbit["recorder"].get("document") == reference["document_name"]
            and orbit["camera"]["status"] == "completed"
            and orbit["camera"].get("document_identity", {}).get("name")
            == reference["document_name"]
            and orbit["tool_position_unchanged"] is True
            and orbit["before"]["tool_position"] == orbit["after"]["tool_position"]
            and len(orbit["before"]["tool_position"]) == 3
            and playback.get("status") == "recorded"
            and not playback.get("errors")
            and playback["playback_end_observed"] is True
            and playback["tool_position_changed"] is True
            and hidden
            and all(value is False for value in hidden.values())
            and set(hidden) == set(before)
            and capture["target_display_restored"]["states_after"] == before
        ):
            raise ValueError("Finished-stock presentation evidence is incomplete")
        videos = [
            ref for ref in capture["media"] if Path(ref["path"]).name == "finished-stock-orbit.mp4"
        ]
        if len(videos) != 1:
            raise ValueError("Expected one recorded finished-stock orbit")
        shots.append(
            {
                "capture_receipt": str(path),
                "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source": videos[0]["path"],
                "source_sha256": videos[0]["sha256"],
                "duration_s": duration,
                "source_job": manifest["job_id"],
                "candidate_id": candidate.id,
                "candidate_digest": candidate.digest,
                "verified_seconds": capture["verified_seconds"],
            }
        )
    return shots


def replace_tail(receipts, *, visually_reviewed=False):
    """Replace only seconds104–114; preserve and verify all decoded prefix frames."""
    shots = validated_tail_shots(receipts, visually_reviewed=visually_reviewed)
    target, evidence_path = OUT / "silta-loop-demo.mp4", OUT / "film-evidence.json"
    previous = json.loads(evidence_path.read_text())
    old_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    if old_hash != previous["sha256"] or previous["expected_duration_seconds"] != 114:
        raise ValueError("Existing114-second film differs from frozen evidence")
    prefix_timeline = [row for row in previous["timeline"] if row["start_s"] < 104]
    if (
        not prefix_timeline
        or prefix_timeline[-1]["start_s"] + prefix_timeline[-1]["duration_s"] != 104
    ):
        raise ValueError("Frozen film does not have an exact104-second chapter boundary")
    for shot in shots:
        _, seconds = imageio_ffmpeg.count_frames_and_secs(shot["source"])
        if seconds < shot["duration_s"]:
            raise ValueError("Recorded orbit is shorter than requested excerpt")
    backup = OUT / f"film-before-tail-{old_hash[:16]}.mp4"
    backup_receipt = backup.with_suffix(".json")
    if not backup.exists():
        shutil.copy2(target, backup)
        shutil.copy2(evidence_path, backup_receipt)
    if hashlib.sha256(backup.read_bytes()).hexdigest() != old_hash:
        raise ValueError("Existing backup hash differs")
    prefix = OUT / "film-tail-prefix104.mp4"
    run(
        [
            "-i",
            str(backup),
            "-map",
            "0:v:0",
            "-frames:v",
            "6240",
            "-an",
            "-c:v",
            "copy",
            str(prefix),
        ]
    )
    segments, timeline, elapsed = [prefix], list(prefix_timeline), 104
    for index, shot in enumerate(shots):
        overlay = panel(
            f"captured-tail-{index}",
            "VERIFIED FINISHED STOCK",
            "New geometry.\nSame loop.",
            f"{shot['verified_seconds']:.1f}s CAM estimate\nFixed CAD / verified CAM",
            f"{shot['source_job']}\n{shot['candidate_id']}",
        )
        segments.append(
            encode(
                f"captured-tail-{index}",
                Path(shot["source"]),
                shot["duration_s"],
                overlay=overlay,
                fit_window=True,
            )
        )
        timeline.append(
            {
                **shot,
                "chapter": f"captured-tail-{index}",
                "start_s": elapsed,
                "source_start_s": 0,
                "type": "actual recorded finished-stock orbit",
            }
        )
        elapsed += shot["duration_s"]
    listing = OUT / "film-tail-concat.txt"
    listing.write_text("".join(f"file '{path.name}'\n" for path in segments))
    proposed = OUT / "film-tail-proposed.mp4"
    run(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(proposed),
        ]
    )
    frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(proposed))
    if frames != 6840 or abs(seconds - 114) >= 0.1:
        raise ValueError("Replacement film frame count/duration differs")

    def prefix_hash(path):
        return (
            subprocess.check_output(
                [
                    FF,
                    "-v",
                    "error",
                    "-i",
                    str(path),
                    "-map",
                    "0:v:0",
                    "-frames:v",
                    "6240",
                    "-an",
                    "-c:v",
                    "rawvideo",
                    "-pix_fmt",
                    "yuv420p",
                    "-f",
                    "hash",
                    "-hash",
                    "sha256",
                    "-",
                ]
            )
            .decode()
            .strip()
        )

    original_prefix_hash, proposed_prefix_hash = prefix_hash(backup), prefix_hash(proposed)
    if original_prefix_hash != proposed_prefix_hash:
        raise ValueError("Decoded first104seconds changed; original film retained")
    sources = list(previous["sources"])
    for shot in shots:
        sources += [
            {"path": shot["source"], "sha256": shot["source_sha256"]},
            {"path": shot["capture_receipt"], "sha256": shot["receipt_sha256"]},
        ]
    result = {
        **previous,
        "sha256": hashlib.sha256(proposed.read_bytes()).hexdigest(),
        "timeline": timeline,
        "sources": sources,
        "additional_source_receipts": [
            *previous.get("additional_source_receipts", []),
            *(s["capture_receipt"] for s in shots),
        ],
        "tail_replacement": {
            "previous_film": str(backup),
            "sha256": old_hash,
            "previous_evidence": str(backup_receipt),
            "previous_evidence_sha256": hashlib.sha256(backup_receipt.read_bytes()).hexdigest(),
            "frozen_prefix_seconds": 104,
            "decoded_prefix_equal": True,
            "decoded_prefix_hash": original_prefix_hash,
            "visual_review_operator_attested": True,
            "shots": shots,
        },
        "limitations": [
            *(
                line.replace(
                    "final fork orbit to UMC09 candidate4",
                    "final orbits bound by tail_replacement capture receipts",
                )
                for line in previous["limitations"]
                if not line.startswith("Final shots are camera-only orbits")
                and not line.startswith("Previous tail-specific limitations")
            ),
            "Final104–114second shots are camera-only orbits of actual captured stock; "
            "not new machining verification; see tail_replacement receipts",
        ],
    }
    proposed.replace(target)
    evidence_path.write_text(json.dumps(result, indent=2) + "\n")


def main():
    from silta.cnc.simulation_video import playback_position

    previous08 = OUT / "film-previous-umc08-114s.mp4"
    if not previous08.exists():
        shutil.copy2(OUT / "silta-loop-demo.mp4", previous08)
        shutil.copy2(OUT / "film-evidence.json", OUT / "film-previous-umc08-evidence.json")
    fork_video, fork_receipt, fork_manifest = fork_orbit_receipt()
    previous = OUT / "film-previous-v5-114s.mp4"
    if not previous.exists():
        shutil.copy2(OUT / "silta-loop-demo.mp4", previous)
        shutil.copy2(OUT / "film-evidence.json", OUT / "film-previous-v5-evidence.json")
    binding_path = ROOT / ".private/five-axis/umc08-capture1/binding.json"
    playback_path = ROOT / ".private/five-axis/umc08-machine-playback/result.json"
    orbit_path = ROOT / ".private/five-axis/umc08-orbit"
    binding = json.loads(binding_path.read_text())
    playback = json.loads(playback_path.read_text())
    orbit = json.loads((orbit_path / "camera-trajectory.json").read_text())
    orbit_recorder = json.loads((orbit_path / "recorder-result.json").read_text())
    source_manifest = ROOT / binding["source_manifest"]
    source_run = json.loads(source_manifest.read_text())
    document = binding["reference"]["document_name"]
    assert source_run["status"] == "completed"
    assert source_run["best_verification"]["completed"] is True
    assert source_run["best_verification"]["status"] == "passed"
    assert source_run["best_verification"]["candidate_digest"] == binding["candidate_digest"]
    assert source_run["best_verification"]["machining_seconds"] == binding["verified_seconds"]
    assert binding["geometry_matches"] is True
    assert playback["status"] == "recorded" and not playback["errors"]
    assert playback["playback_end_observed"] and playback["tool_position_changed"]
    assert playback["document"] == orbit_recorder["document"] == document
    assert orbit["status"] == "completed" and orbit_recorder["status"] == "recorded"
    assert orbit["document_identity"]["name"] == document
    poses = [
        playback_position(json.loads((orbit_path / n).read_text()), document)["tool_position"]
        for n in ("simulation-before.json", "simulation-after.json")
    ]
    assert poses[0] == poses[1]
    operations = binding["binding"]["operations"]
    tool_numbers = sorted({o["tool"]["post-process"]["number"] for o in operations})
    assert len(operations) == 18 and tool_numbers == [1]
    machine_video = RAW / "umc08-machine-playback.mp4"
    orbit_video = RAW / "umc08-finished-orbit.mp4"
    assert hashlib.sha256(machine_video.read_bytes()).hexdigest() == playback["video"]["sha256"]
    assert (
        hashlib.sha256(orbit_video.read_bytes()).hexdigest()
        == hashlib.sha256((orbit_path / "window-capture.mp4").read_bytes()).hexdigest()
    )
    media = []
    for video, receipt in ((machine_video, playback["recorder"]), (orbit_video, orbit_recorder)):
        frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(video))
        assert frames == receipt["complete_frames"]
        media.append(
            {
                "path": str(video.relative_to(ROOT)),
                "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "decoded_frames": frames,
                "media_duration_seconds": seconds,
                "capture_wall_seconds": receipt["duration_seconds"],
                "source": "ScreenCaptureKit Fusion window",
            }
        )
    receipt_path = OUT / "film-umc08-source-receipt.json"
    raw_receipts = [
        binding_path,
        playback_path,
        orbit_path / "camera-trajectory.json",
        orbit_path / "recorder-result.json",
        orbit_path / "simulation-before.json",
        orbit_path / "simulation-after.json",
    ]
    receipt_path.write_text(
        json.dumps(
            {
                "document": document,
                "source_job": source_run["job_id"],
                "candidate_digest": binding["candidate_digest"],
                "verified_seconds": binding["verified_seconds"],
                "geometry_matches": True,
                "operation_count": len(operations),
                "tool_numbers": tool_numbers,
                "playback_end_observed": True,
                "tool_position_changed_during_playback": True,
                "tool_position_unchanged_during_orbit": True,
                "orbit_camera_updates": orbit["actual_update_count"],
                "orbit_camera_update_hz": orbit["observed_update_hz"],
                "media": media,
                "scope": (
                    "Recorded playback and camera-only finished-stock orbit; not a new verification"
                ),
                "source_receipts": [
                    {
                        "path": str(p.relative_to(ROOT)),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    }
                    for p in raw_receipts
                ],
            },
            indent=2,
        )
        + "\n"
    )
    evaluation_path = ROOT / "output/evaluation/learning-evaluation.json"
    eval_data = json.loads(evaluation_path.read_text())
    assert eval_data["status"] == "published"
    variants = {v["name"]: v for v in eval_data["variants"]}
    c_path = ROOT / "runs/learning-part-c2/manifest.json"
    c = json.loads(c_path.read_text())
    rejection = next(
        e["result"] for e in c["events"] if e["event"] == "checks_completed" and e["attempt"] == 2
    )
    assert rejection["passed"] is False
    a_path = ROOT / "runs/learning-soft-jaw-a5/manifest.json"
    a = json.loads(a_path.read_text())
    first = next(
        e["verification"]
        for e in a["events"]
        if e["event"] == "verification_completed"
        and e["verification"]["status"] == "passed"
        and e["verification"]["completed"]
    )
    before, after = first["machining_seconds"], a["best_verification"]["machining_seconds"]
    assert a["best_verification"]["completed"]
    # Graphics show historical three-axis evidence, never pretend UMC footage is Part A/B/C.
    opt = card(
        "optimization",
        ROOT / "runs/learning-soft-jaw-a5/target/preview.png",
        "SAME PART / BETTER CAM",
        "Fixed geometry.\nShorter cycle.",
        f"{(before - after) / before * 100:.1f}% less time",
        f"{before:.1f}s  to  {after:.1f}s\nBoth candidates verified.\nRamp-feed change.",
        "Recorded Part A / same target / verified Fusion estimates",
    )
    b_path = ROOT / "runs/learning-part-b1/manifest.json"
    b = json.loads(b_path.read_text())
    proposal = next(
        e["proposal"]
        for e in b["events"]
        if e["event"] == "reusable_change_proposed" and e["proposal"]["kind"] == "checks"
    )
    check_path = Path(proposal["artifact_path"])
    check_lines = check_path.read_text().splitlines()
    line_index = next(
        i for i, line in enumerate(check_lines) if line.strip() == "if scope is not None:"
    )
    excerpt = "\n".join(line[16:] for line in check_lines[line_index : line_index + 3])
    # Exact consecutive source lines and exact substring of the recorded rejection.
    rejection_excerpt = "intersects finished X min side beyond the linear tolerance"
    assert rejection_excerpt in rejection["issues"][0]
    proof = Image.new("RGB", (1920, 1080), BG)
    pd = ImageDraw.Draw(proof)
    write(pd, (80, 68), "SILTA / PART B TO PART C", 26, ACCENT, True)
    write(pd, (80, 165), "A failure becomes a check.", 67, bold=True)
    write(
        pd,
        (84, 274),
        "B discovers the finished-side intrusion. C catches it before simulation.",
        31,
        GRAY,
    )
    pd.rounded_rectangle((78, 380, 1842, 620), 16, fill="#202a35")
    write(pd, (110, 405), "ACTUAL LEARNED CHECK", 22, ACCENT, True)
    pd.multiline_text(
        (112, 469),
        excerpt,
        font=ImageFont.truetype(str(FONT / "Courier New.ttf"), 32),
        fill=WHITE,
        spacing=17,
    )
    write(pd, (88, 710), "51 ms", 100, ACCENT, True)
    write(pd, (488, 729), "REJECTED BEFORE SIMULATION", 29, ACCENT, True)
    write(pd, (488, 788), "“intersects finished X min side\nbeyond the linear tolerance”", 38)
    write(
        pd,
        (80, 984),
        "Recorded three-axis experiment / source and returned-reason excerpts",
        25,
        GRAY,
    )
    transfer = OUT / "film-transfer.png"
    proof.save(transfer)
    # Minimal paired-results graphic, derived from published evidence.
    graph = Image.new("RGB", (920, 740), BG)
    gd = ImageDraw.Draw(graph)
    write(gd, (40, 32), "KNOWN INVALID PLANS CAUGHT", 25, GRAY)
    for y, key in ((170, "baseline"), (395, "learned")):
        value = variants[key]["caught_invalid"]
        write(gd, (40, y), key.upper(), 30, GRAY)
        gd.rounded_rectangle((40, y + 60, 840, y + 128), 10, fill="#27313b")
        if value:
            gd.rounded_rectangle((40, y + 60, 40 + 800 * value / 2, y + 128), 10, fill=ACCENT)
        write(gd, (680, y), f"{value} / 2", 39, WHITE, True)
    write(gd, (40, 610), "Both allow all four valid plans.", 30)
    graph_path = OUT / "film-eval-graph.png"
    graph.save(graph_path)
    eval_card = card(
        "evaluation",
        graph_path,
        "PUBLISHED / WEAVE",
        "Did the check\nactually improve?",
        "0/2  to  2/2",
        "6 retained cases.\nNo false rejections.\nExact code and results logged.",
        "Published retained-case replay / 2 invalid + 4 valid",
    )
    aria_path = ROOT / "output/sponsors/aria-review.json"
    aria = json.loads(aria_path.read_text())
    assert aria["status"] in {
        "recommendation_implemented_unit_verified",
        "recommendation_live_focus_recovery_observed",
    }
    aria_response = Path(aria["response_path"])
    assert hashlib.sha256(aria_response.read_bytes()).hexdigest() == aria["response_sha256"]
    quote = "The current bottleneck is Fusion session readiness and document binding"
    assert quote in aria_response.read_text()
    aria_image = Image.new("RGB", (1920, 1080), BG)
    ad = ImageDraw.Draw(aria_image)
    write(ad, (80, 70), "ARIA / IMPROVING THE AGENT SYSTEM", 26, ACCENT, True)
    write(ad, (80, 175), "It reviewed our failures.", 69, bold=True)
    write(
        ad,
        (80, 296),
        "“The current bottleneck is Fusion session\nreadiness and document binding”",
        45,
    )
    ad.rounded_rectangle((78, 479, 1842, 738), 16, fill="#202a35")
    write(ad, (112, 511), "silta/cnc/native_reader.py", 30, ACCENT, True)
    write(
        ad,
        (112, 585),
        "One bounded foreground-recovery attempt.\n"
        "Failure remains unknown; never an invented pass.",
        38,
    )
    write(ad, (82, 818), f"{aria['validation']['passed']} tests pass", 64, ACCENT, True)
    write(ad, (846, 844), "Live paired validation pending.", 34)
    write(ad, (80, 984), "Actual ARIA analysis / recommendation adapted and unit tested", 25, GRAY)
    aria_card = OUT / "film-aria.png"
    aria_image.save(aria_card)
    # One conditional lesson retained in both jobs, with each comparison on its own fixed target.
    indexed_paths = [
        ROOT / "runs/demo-umc-umc-03-recovery3/manifest.json",
        ROOT / "runs/demo-umc-umc-08/manifest.json",
    ]
    indexed_evidence = []
    lesson_sources = []
    for number, path in zip(("03", "08"), indexed_paths, strict=True):
        manifest = json.loads(path.read_text())
        verified = [
            e["verification"]
            for e in manifest["events"]
            if e["event"] == "verification_completed"
            and e["verification"]["status"] == "passed"
            and e["verification"]["completed"] is True
        ]
        first_time = verified[0]["machining_seconds"]
        best_time = manifest["best_verification"]["machining_seconds"]
        assert first_time > best_time and manifest["best_verification"]["completed"]
        learned = next(
            v
            for v in manifest["learning_sources"].values()
            if v["kind"] == "main_prompt"
            and "reducing ramp clearance from 1 mm to 0.2 mm" in Path(v["path"]).read_text()
        )
        lesson_path = Path(learned["path"])
        assert hashlib.sha256(lesson_path.read_bytes()).hexdigest() == learned["sha256"]
        lesson_sources.append(lesson_path)
        indexed_evidence.append(
            {
                "part": f"UMC{number}",
                "job_id": manifest["job_id"],
                "job_status": manifest["status"],
                "before_seconds": first_time,
                "after_seconds": best_time,
                "reduction_percent": 100 * (first_time - best_time) / first_time,
                "fixed_step_sha256": manifest["target"]["artifacts"]["step"]["sha256"],
                "lesson_sha256": learned["sha256"],
            }
        )
    assert indexed_evidence[0]["lesson_sha256"] == indexed_evidence[1]["lesson_sha256"]
    assert indexed_evidence[1]["job_status"] == "completed"
    lesson_image = Image.new("RGB", (1920, 1080), BG)
    ld = ImageDraw.Draw(lesson_image)
    write(ld, (78, 65), "LEARNING TRANSFERS / INDEXED 3+2", 25, ACCENT, True)
    write(ld, (78, 155), "One lesson. Two indexed parts.", 66, bold=True)
    write(ld, (82, 254), "Less air travel where a shallow ramp allows it.", 34, GRAY)
    ld.rounded_rectangle((78, 335, 1842, 430), 16, fill="#202a35")
    write(ld, (110, 351), "rampClearance:  1 mm  →  0.2 mm", 47, ACCENT, True)
    gallery = json.loads((OUT / "part-gallery.json").read_text())
    gallery = {"parts": [p for p in gallery["parts"] if p["short_id"] in {"UMC 03", "UMC 08"}]}
    gallery_path = OUT / "film-gallery-evidence.json"
    gallery_path.write_text(json.dumps(gallery, indent=2) + "\n")
    shape_sources = []
    for index, item in enumerate(indexed_evidence):
        left = 55 + 960 * index
        number = ("03", "08")[index]
        shape = next(p for p in gallery["parts"] if p["short_id"] == f"UMC {number}")
        image_path = ROOT / shape["render_path"]
        assert hashlib.sha256(image_path.read_bytes()).hexdigest() == shape["render_sha256"]
        assert shape["step_sha256"] == item["fixed_step_sha256"]
        snapshot = OUT / f"film-cad-umc{number}.png"
        shutil.copy2(image_path, snapshot)
        image_path = snapshot
        shape_sources.append(image_path)
        image = ImageOps.contain(Image.open(image_path).convert("RGB"), (435, 415))
        lesson_image.paste(image, (left, 500))
        write(ld, (left + 18, 465), f"UMC {number} / CAD TARGET", 24, GRAY)
        write(ld, (left + 450, 526), f"{item['reduction_percent']:.2f}%", 85, ACCENT, True)
        write(ld, (left + 450, 640), "less machining time", 27)
        write(
            ld,
            (left + 450, 704),
            f"{item['before_seconds']:.1f}s → {item['after_seconds']:.1f}s",
            32,
        )
        write(
            ld,
            (left + 450, 805),
            "Verified candidates\nJob incomplete"
            if index == 0
            else "Verified final plan\nJob completed",
            26,
            GRAY,
        )
    write(
        ld,
        (80, 979),
        "Verified CAM estimates, fixed part in each comparison. CAD previews shown.",
        27,
        GRAY,
    )
    indexed_card = OUT / "film-indexed-learning.png"
    lesson_image.save(indexed_card)
    cuts = [
        (
            "hook",
            machine_video,
            16,
            20,
            panel(
                "hook",
                "ACTUAL FUSION SIMULATION",
                "Your drawing.\nIts machining\nplan.",
                "Haas UMC-750\nIndexed 3+2\n18 operations / T1",
                "UMC08 / candidate 4\n12.7 mm flat end mill",
            ),
        ),
        (
            "loop",
            machine_video,
            14,
            36,
            panel(
                "loop",
                "THE LOOP",
                "Try. Verify.\nLearn.",
                "Fixed CAD\nCAM + cheap checks\nFusion + final stock\nJudge: improve or stop",
                "Failures return to repair.\nOnly passes reach judge.",
            ),
        ),
        ("optimization", opt, 12, 0, None),
        ("transfer", transfer, 14, 0, None),
        ("evaluation", eval_card, 14, 0, None),
        ("aria", aria_card, 10, 0, None),
        ("indexed-learning", indexed_card, 8, 0, None),
        (
            "motion",
            machine_video,
            16,
            56,
            panel(
                "motion",
                "BACK TO THE MACHINE",
                "One cutter.\nEight facets.",
                "18 operations\n1033.6s CAM estimate\nVerified final plan",
                "UMC08 / recorded 3+2\nHaas UMC-750",
            ),
        ),
        (
            "result",
            orbit_video,
            5,
            2,
            panel(
                "result",
                "THE RESULT",
                "A verified plan.\nA reusable\nlesson.",
                "CAD + CAM + NC\nChecks + guidance\nWeave evidence",
                "Simulated finished stock\nUMC08 / candidate 4",
            ),
        ),
        (
            "result-fork",
            fork_video,
            5,
            3,
            panel(
                "result-fork",
                "ANOTHER VERIFIED PART",
                "New geometry.\nSame loop.",
                "Forked actuator bracket\n7 operations / T1\n209.0s CAM estimate",
                "Actual finished-stock orbit\nUMC09 / candidate 4",
            ),
        ),
    ]
    segments = []
    timeline = []
    elapsed = 0
    for name, source, duration, start, overlay in cuts:
        print(f"Encoding {name}", flush=True)
        segments.append(encode(name, source, duration, overlay, start, still=overlay is None))
        timeline.append(
            {
                "chapter": name,
                "start_s": elapsed,
                "duration_s": duration,
                "source": str(source),
                "source_start_s": start,
                "crop": video_crop(source) if overlay else None,
                "type": "retained evidence graphic"
                if overlay is None
                else "actual recorded Fusion frames",
            }
        )
        elapsed += duration
    listing = OUT / "film-concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in segments))
    target = OUT / "silta-loop-demo.mp4"
    run(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    for at in (5, 22, 35, 48, 64, 75, 84, 97, 106, 111, 113):
        run(
            ["-ss", str(at), "-i", str(target), "-frames:v", "1", str(OUT / f"film-frame-{at}.png")]
        )
    source_paths = {source for _, source, _, _, _ in cuts} | {
        evaluation_path,
        c_path,
        a_path,
        b_path,
        check_path,
        aria_path,
        aria_response,
        receipt_path,
        fork_receipt,
        fork_manifest,
        gallery_path,
        *indexed_paths,
        *lesson_sources,
        *shape_sources,
    }
    (OUT / "film-evidence.json").write_text(
        json.dumps(
            {
                "output": str(target),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "timeline": timeline,
                "expected_duration_seconds": elapsed,
                "audio": "silent",
                "check_excerpt": excerpt,
                "indexed_learning": indexed_evidence,
                "machine_source_receipt": str(receipt_path),
                "additional_source_receipts": [str(fork_receipt)],
                "rejection_excerpt": rejection_excerpt,
                "sources": [
                    {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in source_paths
                ],
                "limitations": [
                    "No synthetic machining frames",
                    "Final shots are camera-only orbits of actual UMC08 and UMC09 simulation stock",
                    "Historical learning applied directly; Weave replay came later",
                    "Indexed 3+2, not simultaneous five-axis",
                    "Machining bound to UMC08 candidate4; final fork orbit to UMC09 candidate4; "
                    "earlier PartA/B/C graphics are separate experiments",
                    "UMC03 job incomplete with verified comparisons; UMC08 completed",
                    "No ten-completed-jobs claim",
                    "ARIA recommendation unit tested; live paired validation pending",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    actual_frames, actual_seconds = imageio_ffmpeg.count_frames_and_secs(str(target))
    assert actual_frames == elapsed * 60 and abs(actual_seconds - elapsed) < 0.1
    record_path = OUT / "film-evidence.json"
    record = json.loads(record_path.read_text())
    record["validation"] = {
        "full_video_decode": "passed",
        "expected_frames": elapsed * 60,
        "actual_frames": actual_frames,
        "actual_duration_seconds": actual_seconds,
        "resolution": [1920, 1080],
        "frame_rate": 60,
    }
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    print(target, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tail-receipts", nargs="+", type=Path)
    parser.add_argument("--visually-reviewed", action="store_true")
    args = parser.parse_args()
    if args.tail_receipts:
        replace_tail(args.tail_receipts, visually_reviewed=args.visually_reviewed)
    else:
        main()
