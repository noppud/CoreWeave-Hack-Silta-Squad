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


@pytest.mark.parametrize('recover', [True, False])
def test_unsaved_stock_dialog_reopens_once_for_missing_checkbox(recover):
    from silta.cnc.stock_export import CLOUD_ID, LOCAL_ID, PATH_ID, StockExporter

    cancel = 'QTApplication.QTFrameWindow.standardActions.CancelButton'
    exporter = object.__new__(StockExporter)
    exporter.state = {'window_bounds': [0, 0, 1000, 800]}
    openings = []
    actions = []
    exporter.menu = lambda: None

    def click(label, **kwargs):
        if label == 'Save Stock':
            openings.append(label)
            ids = [CLOUD_ID, PATH_ID, cancel]
            if recover and len(openings) == 2:
                ids.append(LOCAL_ID)
            exporter.state['elements'] = [
                {'window': 'Save Stock', 'AXIdentifier': i} for i in ids
            ]

    exporter.click_text = click
    exporter.wait_dialog = lambda: None
    exporter.ui = lambda *args: actions.append(args)
    if recover:
        exporter.open_stock_dialog()
    else:
        with pytest.raises(RuntimeError, match='Expected one Save Stock'):
            exporter.open_stock_dialog()
    assert len(openings) == 2
    assert actions == [('press', 'Save Stock', cancel)]
