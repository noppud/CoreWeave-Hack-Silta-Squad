import struct

import pytest

from silta.cnc.stock_export import dialog_element, find_text, inspect_binary_stl


def test_native_binary_reuses_build_and_invalidates_changed_source(tmp_path, monkeypatch):
    from pathlib import Path

    from silta.cnc.stock_export import native_binary

    source = tmp_path / "native.swift"
    source.write_text("version one")
    builds = []

    def compile_helper(args, **kwargs):
        builds.append(args)
        Path(args[-1]).write_bytes(b"compiled")

    monkeypatch.setattr("silta.cnc.stock_export.subprocess.run", compile_helper)
    cache = tmp_path / "cache"
    first = native_binary(source, cache=cache)
    assert native_binary(source, cache=cache) == first
    assert len(builds) == 1
    source.write_text("version two")
    assert native_binary(source, cache=cache) != first
    assert len(builds) == 2


def test_truncated_export_is_not_accepted(tmp_path):
    path = tmp_path / "stock.stl"
    path.write_bytes(bytes(80) + struct.pack("<I", 5) + bytes(50))
    with pytest.raises(ValueError, match="triangle count"):
        inspect_binary_stl(path)


def test_nonfinite_export_is_not_accepted(tmp_path):
    path = tmp_path / "stock.stl"
    path.write_bytes(
        bytes(80) + struct.pack("<I", 1) + struct.pack("<12fH", *([float("nan")] * 12), 0)
    )
    with pytest.raises(ValueError, match="non-finite"):
        inspect_binary_stl(path)


def test_duplicate_labels_do_not_choose_arbitrary_button():
    state = {
        "texts": [
            {"text": "Stock", "confidence": 1, "bounds": [500, 600, 40, 20]},
            {"text": "Stock", "confidence": 1, "bounds": [1500, 600, 40, 20]},
        ]
    }
    with pytest.raises(RuntimeError, match="found 2"):
        find_text(state, "Stock")
    assert find_text(state, "Stock", region=(400, 500, 1000, 800)) == (520, 610)


def test_low_confidence_text_cannot_trigger_save():
    state = {"texts": [{"text": "Save", "confidence": 0.5, "bounds": [1, 2, 3, 4]}]}
    with pytest.raises(RuntimeError, match="found 0"):
        find_text(state, "Save")


def test_save_stock_ellipsis_is_accepted():
    state = {"texts": [{"text": "Save Stock...", "confidence": 1, "bounds": [1, 2, 4, 6]}]}
    assert find_text(state, "Save Stock") == (3, 5)


def test_field_in_different_dialog_is_not_modified():
    state = {"elements": [{"window": "Export", "AXIdentifier": "name", "AXValue": "old"}]}
    with pytest.raises(RuntimeError, match="Expected one Save Stock"):
        dialog_element(state, "name")


def test_display_volume_difference_is_diagnostic_after_accuracy_change():
    from silta.cnc.stock_export import compare_reported_volume

    geometry = {"coordinate_units": "mm", "signed_volume": 183074.23}
    text = "  volume, eDropDownEntry, Volume, 183.074 cm^3 (93.1%)"
    assert compare_reported_volume(geometry, text)["status"] == "matched"
    result = compare_reported_volume({**geometry, "signed_volume": 182801.441}, text)
    assert result["status"] == "different"
    assert result["difference_mm3"] == pytest.approx(272.559)
    assert "Diagnostic only" in result["meaning"]


def test_missing_volume_does_not_claim_crosscheck():
    from silta.cnc.stock_export import compare_reported_volume

    assert compare_reported_volume({"coordinate_units": "unknown"}, "")["status"] == "not_available"


def test_fusion_mm_header_and_tetrahedron_volume(tmp_path):
    triangles = [
        ((0, 0, 0), (0, 1, 0), (1, 0, 0)),
        ((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        ((0, 0, 0), (0, 0, 1), (0, 1, 0)),
        ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    ]
    data = b"application/sla;MM".ljust(80, b" ") + struct.pack("<I", 4)
    for triangle in triangles:
        vertices = [v for point in triangle for v in point]
        data += struct.pack("<12fH", 0, 0, 0, *vertices, 0)
    path = tmp_path / "stock.stl"
    path.write_bytes(data)
    geometry = inspect_binary_stl(path)
    assert geometry["coordinate_units"] == "mm"
    assert geometry["triangles"] == 4
    assert geometry["signed_volume"] == pytest.approx(1 / 6)


def test_accuracy_handle_tracks_window_position_and_rejects_ambiguous_bars(tmp_path):
    from PIL import Image, ImageDraw

    from silta.cnc.stock_export import accuracy_handle

    path = tmp_path / "panel.png"
    frame = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(frame)
    draw.line((674, 507, 754, 507), fill="gray", width=2)
    draw.rectangle((700, 499, 703, 515), fill="gray")
    frame.save(path)
    state = {
        "window_bounds": [100, 50, 900, 700],
        "screenshot": str(path),
        "texts": [{"text": "Accuracy", "confidence": 1, "bounds": [560, 500, 55, 14]}],
        "windows": [{"bounds": {"X": 650, "Y": 200, "Width": 250, "Height": 500}}],
    }
    assert accuracy_handle(state) == (701.5, 507, 754)
    draw.rectangle((720, 499, 723, 515), fill="gray")
    frame.save(path)
    with pytest.raises(RuntimeError, match="one Fusion stock accuracy"):
        accuracy_handle(state)


@pytest.mark.parametrize("recover", [True, False])
def test_unsaved_stock_dialog_reopens_once_for_missing_checkbox(recover):
    from silta.cnc.stock_export import CLOUD_ID, LOCAL_ID, PATH_ID, StockExporter

    cancel = "QTApplication.QTFrameWindow.standardActions.CancelButton"
    exporter = object.__new__(StockExporter)
    exporter.state = {"window_bounds": [0, 0, 1000, 800]}
    openings = []
    actions = []
    exporter.menu = lambda: None

    def click(label, **kwargs):
        if label == "Save Stock":
            openings.append(label)
            ids = [CLOUD_ID, PATH_ID, cancel]
            if recover and len(openings) == 2:
                ids.append(LOCAL_ID)
            exporter.state["elements"] = [{"window": "Save Stock", "AXIdentifier": i} for i in ids]

    exporter.click_text = click
    exporter.wait_dialog = lambda **kwargs: None
    exporter.ui = lambda *args: actions.append(args)
    if recover:
        exporter.open_stock_dialog()
    else:
        with pytest.raises(RuntimeError, match="Expected one Save Stock"):
            exporter.open_stock_dialog()
    assert len(openings) == 2
    assert actions == [("press", "Save Stock", cancel)]


@pytest.mark.parametrize(
    "text,value", [("Stock generation: 23.5%", 23.5), ("Stock generation: 100.0%", 100)]
)
def test_stock_generation_progress_reads_actual_observed_status(text, value):
    from silta.cnc.stock_export import stock_generation_progress

    assert stock_generation_progress({"texts": [{"text": text, "confidence": 1}]}) == value


@pytest.mark.parametrize(
    "texts",
    [
        [{"text": "Stock generation: ?", "confidence": 1}],
        [{"text": "Stock generation: 101%", "confidence": 1}],
        [{"text": "Stock generation: 100%", "confidence": 0.2}],
        [{"text": "Stock generation: 20%", "confidence": 1}] * 2,
    ],
)
def test_stock_generation_progress_rejects_ambiguous_or_unreadable(texts):
    from silta.cnc.stock_export import stock_generation_progress

    with pytest.raises(RuntimeError):
        stock_generation_progress({"texts": texts})


def readiness_exporter(tmp_path, monkeypatch, progression):
    from types import SimpleNamespace

    from silta.cnc.stock_export import StockExporter

    exporter = object.__new__(StockExporter)
    exporter.document = "Exact CAM"
    exporter.directory = tmp_path
    states = iter(progression)
    elapsed = [0.0]
    monkeypatch.setattr("silta.cnc.stock_export.time.monotonic", lambda: elapsed[0])
    monkeypatch.setattr(
        "silta.cnc.stock_export.time.sleep",
        lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
    )

    def set_progress(value):
        exporter.state = {
            "texts": []
            if value is None
            else [{"text": f"Stock generation: {value}%", "confidence": 1}]
        }

    set_progress(next(states))

    def ui(action, *args):
        if action == "inspect":
            set_progress(next(states, progression[-1]))

    exporter.ui = ui
    exporter.menu = lambda: exporter.state["texts"].append({"text": "Play", "confidence": 1})
    raw = (
        "time, eDropDownEntry, Time, 0:00:00 (0.0%)\n"
        "description, eDropDownEntry, Description, Final operation\n"
        "x, eDropDownEntry, X position, 0 mm\n"
        "y, eDropDownEntry, Y position, 0 mm\n"
        "z, eDropDownEntry, Z position, 25 mm\n"
    )
    exporter.bridge = SimpleNamespace(
        request=lambda *a, **k: {
            "status": "ok",
            "result": {
                "document": exporter.document,
                "active_command": "IronMachineSimulation",
                "raw_text": raw,
            },
        }
    )
    return exporter


def test_stock_ready_waits_through_real_partial_export_progress(tmp_path, monkeypatch):
    exporter = readiness_exporter(tmp_path, monkeypatch, [23.5, 37.6, 100, None, None])
    result = exporter.wait_stock_ready(timeout=5)
    assert result["status"] == "ready"
    assert [x["progress_percent"] for x in result["samples"]] == [23.5, 37.6, 100, None]
    assert result["playback_stopped"]
    # Fusion's raw Time remains zero at this observed End of Toolpath; it is
    # not used as a substitute for stock-generation completion.
    assert result["final_position"]["percent"] == 0


def test_stock_ready_absence_without_observed_generation_is_not_completion(tmp_path, monkeypatch):
    exporter = readiness_exporter(tmp_path, monkeypatch, [None])
    with pytest.raises(TimeoutError, match="completion was not observed"):
        exporter.wait_stock_ready(timeout=1)
    import json

    receipt = json.loads((tmp_path / "stock-readiness.json").read_text())
    assert receipt["status"] == "collection_failed"


def test_stock_ready_partial_generation_times_out(tmp_path, monkeypatch):
    exporter = readiness_exporter(tmp_path, monkeypatch, [23.5, 37.6])
    with pytest.raises(TimeoutError):
        exporter.wait_stock_ready(timeout=1)


def test_stock_ready_requires_stopped_playback(tmp_path, monkeypatch):
    exporter = readiness_exporter(tmp_path, monkeypatch, [100, None, None])
    exporter.menu = lambda: None
    with pytest.raises(RuntimeError, match="not stopped"):
        exporter.wait_stock_ready(timeout=2)


def test_stock_ready_binds_exact_document(tmp_path, monkeypatch):
    exporter = readiness_exporter(tmp_path, monkeypatch, [100])
    exporter.document = "Wrong CAM"
    # Bind original result, independent of the requested document.
    from types import SimpleNamespace

    exporter.bridge = SimpleNamespace(
        request=lambda *a, **k: {"status": "ok", "result": {"document": "Exact CAM"}}
    )
    with pytest.raises(RuntimeError, match="exact Fusion document"):
        exporter.wait_stock_ready(timeout=1)


def test_export_never_opens_save_before_readiness(tmp_path, monkeypatch):
    exporter = readiness_exporter(tmp_path, monkeypatch, [23.5])
    exporter.state.update(windows=[], elements=[])
    actions = []
    exporter.maximum_accuracy = lambda: actions.append("accuracy")
    exporter.menu = lambda: actions.append("menu")
    exporter.click_text = lambda label: actions.append(label)
    exporter.open_stock_dialog = lambda: actions.append("Save Stock")

    def not_ready():
        actions.append("wait")
        raise TimeoutError("still generating")

    exporter.wait_stock_ready = not_ready
    with pytest.raises(TimeoutError, match="still generating"):
        exporter.export(tmp_path / "never-created.stl")
    assert actions == ["accuracy", "menu", "Start of Toolpath", "menu", "End of Toolpath", "wait"]
    assert not (tmp_path / "never-created.stl").exists()


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0, 601])
def test_stock_ready_rejects_unbounded_timeout(tmp_path, monkeypatch, timeout):
    exporter = readiness_exporter(tmp_path, monkeypatch, [100])
    with pytest.raises(ValueError, match="finite"):
        exporter.wait_stock_ready(timeout=timeout)


def test_untitled_marking_menu_is_not_closed_by_second_right_click():
    from silta.cnc.stock_export import StockExporter

    exporter = object.__new__(StockExporter)
    exporter.state = {"window_bounds": [0, 0, 1000, 800], "windows": [], "texts": []}
    calls = []

    def ui(*args):
        calls.append(args)
        if args[0] == "click":
            exporter.state["windows"] = [{"title": ""}]
            exporter.state["texts"] = [
                {"text": "End of Toolpath", "confidence": 1, "bounds": [500, 300, 100, 20]}
            ]
        return exporter.state

    exporter.ui = ui
    exporter.menu()
    assert sum(c[0] == "click" for c in calls) == 1
    exporter.menu()
    assert sum(c[0] == "click" for c in calls) == 1  # Already open; no toggle.


def test_native_marking_menu_with_only_pause_never_right_clicks_again():
    from silta.cnc.stock_export import StockExporter

    exporter = object.__new__(StockExporter)
    exporter.state = {
        "window_bounds": [0, 0, 1000, 800],
        "windows": [{"title": "Marking Menu"}],
        "texts": [{"text": "Pause", "confidence": 1, "bounds": [1, 1, 10, 10]}],
    }
    calls = []

    def ui(*args):
        calls.append(args)
        return exporter.state

    exporter.ui = ui
    exporter.menu()
    assert calls == [("inspect",)]
