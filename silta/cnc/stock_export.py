"""Deterministic foreground export of Fusion's current simulated stock.

Requires an already-running machine simulation. Exports geometry only: an STL
is not a collision verdict or a stock-to-target comparison. No model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import struct
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .fusion import FusionBridge

ROOT = Path(__file__).resolve().parents[2]
NATIVE_SOURCE = ROOT / "scripts/fusion/native_ui.swift"
NAME_ID = "QTApplication.QTFrameWindow.MainWidget.editName"
LOCAL_ID = "QTApplication.QTFrameWindow.standardActions.checkLocalSave"
CLOUD_ID = "QTApplication.QTFrameWindow.MainWidget.checkSaveIn"
PATH_ID = "QTApplication.QTFrameWindow.standardActions.labelLocalSavePath"


def native_binary(source: Path = NATIVE_SOURCE, *, cache: Path | None = None) -> Path:
    """Compile once per source version; publish only a completed executable."""
    cache = cache or ROOT / ".private/fusion-native-cache"
    cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    binary = cache / f"native-ui-{digest}"
    if not binary.is_file():
        with tempfile.TemporaryDirectory(dir=cache) as staging:
            pending = Path(staging) / "native-ui"
            subprocess.run(
                ["swiftc", str(source), "-o", str(pending)],
                check=True, capture_output=True, text=True, timeout=60,
            )
            pending.replace(binary)
    return binary


def inspect_binary_stl(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 134:
        raise ValueError("Stock STL is empty or truncated")
    count = struct.unpack_from("<I", data, 80)[0]
    if count == 0 or len(data) != 84 + 50 * count:
        raise ValueError("Stock STL has an invalid binary triangle count")
    low, high = [math.inf] * 3, [-math.inf] * 3
    volume = 0.0
    for i in range(count):
        values = struct.unpack_from("<12f", data, 84 + i * 50)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Stock STL contains non-finite coordinates")
        a, b, c = values[3:6], values[6:9], values[9:12]
        for vertex in (a, b, c):
            for axis in range(3):
                low[axis] = min(low[axis], vertex[axis])
                high[axis] = max(high[axis], vertex[axis])
        volume += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            + a[1] * (b[2] * c[0] - b[0] * c[2])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6
    if any(h <= lo for lo, h in zip(low, high, strict=True)):
        raise ValueError("Stock STL has a degenerate bounding box")
    return {
        "bytes": len(data),
        "triangles": count,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bounds": [low, high],
        "signed_volume": volume,
        "coordinate_units": "mm" if data[:80].startswith(b"application/sla;MM ") else "unknown",
        "units_note": "Fusion MM header is used when present; STL has no standard units field",
    }


def compare_reported_volume(geometry: dict, text: str) -> dict:
    matches = re.findall(r"^\s*volume, eDropDownEntry, Volume, ([\d.]+) cm\^3", text, re.M)
    if len(matches) != 1 or geometry.get("coordinate_units") != "mm":
        return {"status": "not_available", "reason": "No unique volume or confirmed mesh units"}
    displayed = matches[0]
    reference_mm3 = float(displayed) * 1000
    digits = len(displayed.partition(".")[2])
    # Fusion rounds its displayed volume. Permit one half of its last digit,
    # plus floating-point noise from STL coordinates, rather than a percentage.
    rounding_mm3 = 0.5 * 10**-digits * 1000 + 0.01
    difference = abs(abs(geometry["signed_volume"]) - reference_mm3)
    return {
        "status": "matched" if difference <= rounding_mm3 else "different",
        "fusion_volume_mm3": reference_mm3,
        "difference_mm3": difference,
        "display_rounding_allowance_mm3": rounding_mm3,
        "meaning": (
            "Diagnostic only: Fusion's displayed volume did not track increased stock accuracy "
            "in live testing. Geometric comparison decides conformity."
        ),
    }


def find_text(state: dict, label: str, *, region=None) -> tuple[float, float]:
    """Require an unambiguous high-confidence OCR label in a bounded UI region."""
    matches = []
    for item in state["texts"]:
        if item["text"].strip().rstrip(".\u2026") != label or item["confidence"] < 0.8:
            continue
        x, y, w, h = item["bounds"]
        center = (x + w / 2, y + h / 2)
        if region and not (
            region[0] <= center[0] <= region[2] and region[1] <= center[1] <= region[3]
        ):
            continue
        matches.append(center)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one visible {label!r} control, found {len(matches)}")
    return matches[0]


def dialog_element(state: dict, identifier: str) -> dict:
    matches = [
        e
        for e in state["elements"]
        if e.get("window") == "Save Stock" and e.get("AXIdentifier") == identifier
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Save Stock control: {identifier}")
    return matches[0]


def accuracy_handle(state: dict) -> tuple[float, float, float]:
    """Locate the observed slider handle in the supported Fusion Display panel.

    The Qt slider has no AX value. Anchor its bounded field to the visible
    Accuracy label and 250-point simulation panel, then detect its vertical bar.
    Unexpected layouts fail collection instead of sending speculative clicks.
    """
    import numpy as np
    from PIL import Image

    label_x, y = find_text(state, "Accuracy")
    wx, wy, width, _ = state["window_bounds"]
    panels = [
        w["bounds"]
        for w in state["windows"]
        if 248 <= w["bounds"]["Width"] <= 252
        and w["bounds"]["X"] - wx < label_x < w["bounds"]["X"] - wx + 100
        and w["bounds"]["Y"] - wy < y < (w["bounds"]["Y"] - wy + w["bounds"]["Height"])
    ]
    if len(panels) != 1:
        raise RuntimeError("Expected the calibrated Fusion simulation Display panel")
    left = panels[0]["X"] - wx
    pixels = np.asarray(Image.open(state["screenshot"]).convert("RGB"))
    scale = pixels.shape[1] / width
    rows = np.r_[
        int((y - 8) * scale) : int((y - 3) * scale),
        int((y + 3) * scale) : int((y + 8) * scale),
    ]
    columns = np.arange(int(left + 120), int(left + 210))
    dark = pixels[rows[:, None], (columns * scale).astype(int), :].max(axis=2) < 175
    bars = columns[dark.mean(axis=0) > 0.6]
    if len(bars) < 1 or len(bars) > 7 or bars[-1] - bars[0] != len(bars) - 1:
        raise RuntimeError("Could not identify one Fusion stock accuracy slider handle")
    return float(bars.mean()), y, left + 204


class StockExporter:
    def __init__(self, document: str, directory: Path, *, bridge=None):
        self.document = document
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.bridge = bridge or FusionBridge()
        self.sequence = 0
        self.state = None
        self.binary = native_binary()

    def ui(self, action: str, *arguments) -> dict:
        self.sequence += 1
        stem = self.directory / f"{self.sequence:03d}-{action}"
        process = subprocess.run(
            [
                str(self.binary),
                self.document,
                str(stem.with_suffix(".png")),
                action,
                *map(str, arguments),
            ],
            capture_output=True,
            text=True,
            timeout=25,
        )
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            stem.with_suffix(".txt").write_text(process.stdout + process.stderr)
            raise RuntimeError(
                "Native Fusion UI did not return a structured observation"
            ) from error
        stem.with_suffix(".json").write_text(json.dumps(result, indent=2))
        if process.returncode or result.get("error"):
            raise RuntimeError(result.get("error", process.stderr))
        if not result["foreground"]:
            raise RuntimeError("Fusion lost foreground access; export stopped")
        self.state = result
        return result

    def click_text(self, label: str, *, region=None):
        x, y = find_text(self.state, label, region=region)
        return self.ui("click", x, y, "left")

    def menu(self):
        # A first click can only focus the canvas. Retry once, after observing
        # the menu is absent. Never replay Save blindly after an uncertain result.
        _, _, width, height = self.state["window_bounds"]
        for _attempt in range(2):
            if any(w["title"] == "Marking Menu" for w in self.state["windows"]):
                find_text(self.state, "End of Toolpath")
                return
            self.ui("click", width * 0.55, height * 0.42, "right")
        find_text(self.state, "End of Toolpath")

    def wait_dialog(self, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            if any(
                e.get("AXIdentifier") == PATH_ID and e.get("window") == "Save Stock"
                for e in self.state["elements"]
            ):
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("Save Stock did not expose its fields")
            time.sleep(0.5)
            self.ui("inspect")

    def maximum_accuracy(self):
        if not any(t["text"] == "Accuracy" for t in self.state["texts"]):
            # The persistent Display tab is separate from the toolbar menu.
            _, _, width, height = self.state["window_bounds"]
            self.click_text("Display", region=(width * 0.75, 180, width, height))
        x, y, endpoint = accuracy_handle(self.state)
        self.ui("drag", x, y, endpoint, y)
        x, y, _ = accuracy_handle(self.state)
        # Drag tooltip can retain the starting value. Press the observed final
        # handle without moving it to read its actual numeric value.
        self.ui("click", x, y, "left")
        values = [
            t
            for t in self.state.get("small_window_texts", [])
            if t["text"] == "8"
            and t["confidence"] >= 0.8
            and abs(t["bounds"][0] - x) < 100
            and 0 < t["bounds"][1] - y < 55
        ]
        if len(values) != 1:
            raise RuntimeError("Fusion maximum stock accuracy 8 was not read back")
        return {"value": 8, "verified_by": "numeric slider tooltip", "control": values[0]}

    def open_stock_dialog(self):
        # Fusion sometimes publishes an empty AX object for a checkbox. Reopening
        # this unsaved dialog restored it live. Never retry the Save action.
        for attempt in range(2):
            self.menu()
            _, _, width, height = self.state["window_bounds"]
            self.click_text("Stock", region=(width * 0.25, height * 0.4, width * 0.78, height))
            self.click_text("Save Stock")
            self.wait_dialog()
            try:
                for identifier in (CLOUD_ID, LOCAL_ID, PATH_ID):
                    dialog_element(self.state, identifier)
                return
            except RuntimeError:
                if attempt:
                    raise
                cancel = "QTApplication.QTFrameWindow.standardActions.CancelButton"
                dialog_element(self.state, cancel)
                self.ui("press", "Save Stock", cancel)

    def export(self, output: Path) -> dict:
        output = output.resolve()
        if output.exists():
            raise FileExistsError(output)
        before = self.bridge.request("simulation_dialog", timeout=15)
        (self.directory / "simulation-before.json").write_text(json.dumps(before, indent=2))
        actual = before.get("result", {})
        if before.get("status") != "ok" or actual.get("document") != self.document:
            raise RuntimeError("Current Fusion document does not match the requested export")
        if actual.get("active_command") != "IronMachineSimulation":
            raise RuntimeError("Start machine simulation before exporting its stock")
        self.ui("focus")
        if any(w["title"] == "Save Stock" for w in self.state["windows"]):
            raise RuntimeError("A previous Save Stock dialog is still open; resolve it first")
        issues_close = [
            e
            for e in self.state["elements"]
            if e.get("AXTitle") == "Close"
            and "SimulationIssuesPanelCategory" in e.get("AXIdentifier", "")
        ]
        if len(issues_close) > 1:
            raise RuntimeError("Multiple Fusion Issues panels are open")
        if issues_close:
            control = issues_close[0]
            self.ui("press", control["window"], control["AXIdentifier"])
        accuracy = self.maximum_accuracy()
        self.menu()
        self.click_text("End of Toolpath")
        self.open_stock_dialog()
        if dialog_element(self.state, CLOUD_ID).get("AXValue") not in (0, "0"):
            self.ui("press", "Save Stock", CLOUD_ID)
        if dialog_element(self.state, LOCAL_ID).get("AXValue") not in (1, "1"):
            self.ui("press", "Save Stock", LOCAL_ID)
        export_name = "silta-stock-" + uuid.uuid4().hex
        if any(e.get("AXIdentifier") == NAME_ID for e in self.state["elements"]):
            self.ui("set", "Save Stock", NAME_ID, export_name)
            if dialog_element(self.state, NAME_ID).get("AXValue") != export_name:
                raise RuntimeError("Export filename did not update")
        else:
            # Some Fusion Qt text fields intermittently return an empty AX object.
            # Locate this field between its observed Name and Type labels, type
            # only the generated UUID name, and require exact OCR before Save.
            name = dialog_element(self.state, "QTApplication.QTFrameWindow.MainWidget.labelName")[
                "bounds"
            ]
            kind = dialog_element(self.state, "QTApplication.QTFrameWindow.MainWidget.labelType")[
                "bounds"
            ]
            wx, wy, _, _ = self.state["window_bounds"]
            self.ui("click", name[0] - wx + 100, (name[1] + name[3] + kind[1]) / 2 - wy, "left")
            self.ui("export-name", export_name)
            # A blinking caret can be OCR'd as a trailing character. The observed
            # static label removes that ambiguity without editing the filename.
            self.click_text("Name:")
            find_text(self.state, export_name)
        local_directory = Path(dialog_element(self.state, PATH_ID)["AXValue"])
        if not local_directory.is_absolute() or not local_directory.is_dir():
            raise RuntimeError("Save Stock did not expose a valid local directory")
        source = local_directory / (export_name + ".stl")
        if source.exists():
            raise FileExistsError(source)
        self.click_text("Save")
        deadline = time.monotonic() + 30
        previous_size = None
        while time.monotonic() < deadline:
            if source.exists():
                size = source.stat().st_size
                if size == previous_size and size > 84:
                    geometry = inspect_binary_stl(source)
                    break
                previous_size = size
            time.sleep(0.5)
        else:
            raise TimeoutError(f"Stock export file was not completed: {source}")
        after = self.bridge.request("simulation_dialog", timeout=15)
        (self.directory / "simulation-after.json").write_text(json.dumps(after, indent=2))
        if after.get("result", {}).get("document") != self.document:
            raise RuntimeError("Fusion document changed during export")
        volume_evidence = compare_reported_volume(
            geometry, after.get("result", {}).get("raw_text", "")
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects caller files even if another process creates
        # the destination after the initial check. Retain the Fusion original.
        with output.open("xb") as target, source.open("rb") as exported:
            shutil.copyfileobj(exported, target)
        result = {
            "status": "exported",
            "document": self.document,
            "path": str(output),
            "fusion_original": str(source),
            "geometry": geometry,
            "end_of_toolpath_requested": True,
            "foreground_required": True,
            "volume_crosscheck": volume_evidence,
            "stock_accuracy": accuracy,
            "verification_pass": False,
            "meaning": "Simulated stock mesh exported; target comparison is separate",
            "evidence_directory": str(self.directory),
        }
        (self.directory / "result.json").write_text(json.dumps(result, indent=2))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--evidence", type=Path, required=True, help="New directory for native UI observations"
    )
    args = parser.parse_args()
    exporter = StockExporter(args.document, args.evidence)
    try:
        result = exporter.export(args.output)
    except Exception as error:
        (exporter.directory / "failure.json").write_text(json.dumps({"error": str(error)}))
        raise
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
