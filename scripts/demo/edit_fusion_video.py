"""Cut actual Fusion footage into a short, labeled demo. No generated machining frames.
Run with: uv run --with imageio-ffmpeg python scripts/demo/edit_fusion_video.py
"""

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/video"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def label(text, x, y, size=28, color="white"):
    # Fixed authored text only, no shell interpolation.
    return f"drawtext=fontfile='{FONT}':text='{text}':x={x}:y={y}:fontsize={size}:fontcolor={color}"


def main():
    # Honest final still: a saved viewport of finished simulated stock, not a CAD render.
    subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            str(OUT / "finished-stock.png"),
            "-t",
            "14",
            "-vf",
            "scale=1920:1080,pad=1920:1204:0:124:white",
            "-r",
            "60",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(OUT / "umc750-finished-stock-still.mp4"),
        ],
        check=True,
    )
    cuts = [
        ("umc750-machine-playback.mp4", 3, 47, 2, "01 / MACHINE", "Haas UMC-750", "B + C indexing"),
        ("umc750-stock-removal.mp4", 3, 47, 2, "02 / MACHINING", "One cutter.", "Five faces."),
        ("umc750-finished-stock-still.mp4", 1, 13, 1, "03 / RESULT", "Verified", "finished stock"),
    ]
    segments = []
    for i, (name, start, end, speed, chapter, title, subtitle) in enumerate(cuts):
        source = OUT / name
        target = OUT / f"demo-segment-{i}.mp4"
        filters = [
            f"trim=start={start}:end={end}",
            f"setpts=(PTS-STARTPTS)/{speed}",
            "crop=1280:960:340:160",
            "scale=1440:1080",
            "pad=1920:1080:0:0:color=0x10151c",
            "setsar=1",
            "fps=60",
            label("SILTA", 1480, 55, 46),
            label(chapter, 1480, 165, 22, "0x73dfb8"),
            label(title, 1480, 225, 36),
            label(subtitle, 1480, 276, 32),
            label("1 TOOL", 1480, 395, 38),
            label("12.7 mm flat end mill", 1480, 448, 22, "0xbac6d4"),
            label("7 OPERATIONS", 1480, 530, 32),
            label("Indexed 3+2 machining", 1480, 578, 22, "0xbac6d4"),
            label("0 ERRORS", 1480, 668, 38, "0x73dfb8"),
            label("Machine verification", 1480, 720, 22, "0xbac6d4"),
            label("0.127 mm", 1480, 810, 36),
            label("Stock comparison tolerance", 1480, 860, 22, "0xbac6d4"),
            label("Actual Fusion simulation", 1480, 975, 21, "0xbac6d4"),
            label(
                "Finished-stock still" if i == 2 else "Edited / accelerated playback",
                1480,
                1010,
                20,
                "0xbac6d4",
            ),
        ]
        subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-vf",
                ",".join(filters),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "19",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(target),
            ],
            check=True,
        )
        segments.append(target)
    manifest = OUT / "demo-concat.txt"
    manifest.write_text("".join(f"file '{path.name}'\n" for path in segments))
    result = OUT / "silta-five-axis-demo.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(result),
        ],
        check=True,
    )
    (OUT / "demo-edit.json").write_text(
        json.dumps(
            {"source": "Actual Fusion window recordings", "cuts": cuts, "output": str(result)},
            indent=2,
        )
    )
    print(result)


if __name__ == "__main__":
    main()
