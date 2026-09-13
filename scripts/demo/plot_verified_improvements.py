"""Plot retained, matched within-part Fusion timing improvements; no new simulation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.demo.learning_transfer_report import validate_verdict  # noqa: E402

DEFAULT_PARTS = ("UMC04", "UMC05", "UMC06", "UMC08", "UMC09", "UMC12")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_pairs(report, labels):
    """Reject stale evidence and cross-version comparisons, including recovery runs."""
    lookup = {part["part"]: part for part in report["parts"]}
    pairs = []
    for label in labels:
        part = lookup[label]
        if not part["any_completed_job"]:
            raise ValueError(f"{label}: no completed job")
        verified = []
        for row in part["verified_candidates"]:
            path = Path(row["manifest"])
            manifest_hash = digest(path)
            manifest = json.loads(path.read_text())
            if manifest.get("collection_warning"):
                raise ValueError(f"{label}: collection-invalidated source")
            verdict = manifest["events"][row["event_index"]]["verification"]
            nomination_path = path.parent / "workspace/manual-trial-nomination.json"
            nomination = (
                json.loads(nomination_path.read_text()) if nomination_path.is_file() else {}
            )
            manually_selected = nomination.get("candidate_digest") == verdict["candidate_digest"]
            if bool(row.get("manual_nomination")) != manually_selected:
                raise ValueError(f"{label}: manual nomination attribution differs from source")
            if not validate_verdict(verdict):
                raise ValueError(f"{label}: retained verification no longer valid")
            expected = {
                "candidate_digest": verdict["candidate_digest"],
                "input_digest": verdict["input_digest"],
                "target_digest": manifest["target_digest"],
                "verifier_version": verdict["verifier_version"],
                "machining_seconds": verdict["machining_seconds"],
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ValueError(f"{label}: report disagrees with manifest")
            if part["drawing_sha256"] not in {
                item["sha256"] for item in manifest["inputs"]["drawings"]
            }:
                raise ValueError(f"{label}: drawing identity differs")
            if digest(path) != manifest_hash:
                raise ValueError(f"{label}: manifest changed while reading")
            verified.append(
                {**row, "manifest_sha256": manifest_hash, "evidence": verdict["evidence"]}
            )
        verified.sort(key=lambda row: row["at"])
        if not verified:
            raise ValueError(f"{label}: no valid candidates")
        first = verified[0]
        keys = ("input_digest", "target_digest", "verifier_version")
        matched = [row for row in verified if all(row[k] == first[k] for k in keys)]
        best = min(matched, key=lambda row: row["machining_seconds"])
        if first["machining_seconds"] <= 0:
            raise ValueError(f"{label}: zero baseline cannot define an improvement")
        pairs.append(
            {
                "part": label,
                "drawing_sha256": part["drawing_sha256"],
                "first_valid": first,
                "best_valid": best,
                "reduction_percent": 100
                * (1 - best["machining_seconds"] / first["machining_seconds"]),
                "manual_nomination": best.get("manual_nomination", False),
                "attribution": "Operator-nominated retained CAM retest; not autonomous improvement"
                if best.get("manual_nomination")
                else "Observed within-part CAM optimization",
                "matched_valid_candidate_count": len(matched),
                "excluded_other_identity_candidates": len(verified) - len(matched),
            }
        )
    return pairs


def render(pairs, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12})
    fig, ax = plt.subplots(figsize=(12, 6.4), facecolor="#f7f9fc")
    ax.set_facecolor("#f7f9fc")
    manually_nominated = any(pair.get("manual_nomination") for pair in pairs)
    maximum = max(pair["first_valid"]["machining_seconds"] for pair in pairs)
    for index, pair in enumerate(pairs):
        first = pair["first_valid"]["machining_seconds"]
        best = pair["best_valid"]["machining_seconds"]
        ax.barh(
            index - 0.17,
            first,
            height=0.28,
            color="#a6b4c7",
            label="First valid CAM" if index == 0 else None,
        )
        ax.barh(
            index + 0.17,
            best,
            height=0.28,
            color="#087f8c",
            label=("Retested CAM" if manually_nominated else "Best valid CAM")
            if index == 0
            else None,
        )
        for y, value in ((index - 0.17, first), (index + 0.17, best)):
            ax.text(value + maximum * 0.015, y, f"{value:,.1f}s", va="center", fontsize=11)
        ax.text(
            maximum * 1.29,
            index,
            f"−{pair['reduction_percent']:.2f}%",
            va="center",
            ha="right",
            weight="bold",
            color="#087f8c",
            fontsize=15,
        )
    ax.set_yticks(range(len(pairs)), [p["part"].replace("UMC", "UMC ") for p in pairs])
    ax.invert_yaxis()
    ax.set_xlim(0, maximum * 1.33)
    ax.set_xlabel("Estimated machining time (seconds)", loc="left", labelpad=14)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#d7dfe8")
    ax.tick_params(axis="y", length=0, pad=14)
    ax.grid(axis="x", alpha=0.12)
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.015), ncol=2, frameon=False)
    title = "Manually nominated CAM retest" if manually_nominated else "Verified CAM improvements"
    fig.text(0.08, 0.945, title, fontsize=25, weight="bold", color="#182c44")
    fig.text(
        0.08,
        0.892,
        "Same drawing, inputs, target and recorded verifier version in each pair.",
        color="#526176",
        fontsize=12,
    )
    fig.text(
        0.08,
        0.035,
        (
            "Operator selected retained CAM • Not autonomous improvement or new learning\n"
            if manually_nominated
            else "Within-part optimization • Not evidence of cross-part learning causality\n"
        )
        + "Fusion estimates, not measured physical cycle times. Invalid candidates excluded.",
        color="#526176",
        fontsize=10,
        linespacing=1.6,
    )
    fig.subplots_adjust(left=0.12, right=0.96, top=0.77, bottom=0.2)
    files = []
    for suffix in (".png", ".svg"):
        path = output.with_suffix(suffix)
        fig.savefig(path, dpi=180, facecolor=fig.get_facecolor())
        files.append({"path": str(path.resolve()), "sha256": digest(path)})
    plt.close(fig)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "output/evaluation/learning-transfer.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/evaluation/verified-improvements"
    )
    parser.add_argument("--parts", nargs="+", default=DEFAULT_PARTS)
    args = parser.parse_args()
    report_hash = digest(args.report)
    pairs = select_pairs(json.loads(args.report.read_text()), args.parts)
    if digest(args.report) != report_hash:
        raise ValueError("Source report changed during selection")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_report": {"path": str(args.report.resolve()), "sha256": report_hash},
        "generator_sha256": digest(__file__),
        "pairs": pairs,
        "scope": "Retained completed verification; within-part estimates, no fresh simulation",
        "verifier_implementation_bytes_frozen": False,
        "artifacts": render(pairs, args.output),
    }
    args.output.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"parts": [p["part"] for p in pairs], "artifacts": receipt["artifacts"]}))


if __name__ == "__main__":
    main()
