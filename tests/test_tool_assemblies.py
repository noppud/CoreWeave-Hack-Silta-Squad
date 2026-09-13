"""Pinned selection and import-migration failures that must block tool readiness."""

import copy
import json
from pathlib import Path

import pytest

from fusion.prepare_tool_assemblies import prepare, verify_readback

CONFIG = Path(__file__).resolve().parents[1] / "config/soft-jaw-job.json"


@pytest.fixture
def prepared(tmp_path):
    report = prepare(CONFIG, tmp_path / "prepared")
    return json.loads(Path(report["input_path"]).read_text())


def test_two_enabled_assemblies_have_correct_gauge_and_constrained_presets(prepared):
    assert [t["post-process"]["number"] for t in prepared["data"]] == [1, 2]
    for tool, gauge, feed in zip(prepared["data"], [96.52, 90.17], [1371.6, 685.8], strict=True):
        assert tool["geometry"]["assemblyGaugeLength"] * 25.4 == pytest.approx(gauge)
        assert tool["holder"]["product-id"] == "04-0010"
        assert len(tool["holder"]["segments"]) > 10
        assert len(tool["start-values"]["presets"]) == 1
        preset = tool["start-values"]["presets"][0]
        assert preset["n"] == 6000
        assert "v_f_retract" not in preset and "f_n" not in preset
        assert preset["v_f"] * 25.4 == pytest.approx(feed)
        assert preset["v_f_plunge"] == pytest.approx(preset["v_f"] / 3)
        assert verify_readback(tool, tool)["assembly_gauge_length_mm"] == pytest.approx(gauge)


@pytest.mark.parametrize(
    "mutation, match",
    [
        (lambda t: t["geometry"].update(assemblyGaugeLength=1.3), "assemblyGaugeLength"),
        (lambda t: t["geometry"].update(LB=1.0), "geometry.LB"),
        (lambda t: t["holder"]["segments"][0].update(height=0.5), "holder segment"),
        (lambda t: t["start-values"]["presets"][0].update(n=15278), "preset.n"),
        (lambda t: t["start-values"]["presets"][0].update(v_f=275), "preset.v_f"),
        (lambda t: t["post-process"].update(number=0), "post-process number"),
    ],
)
def test_roundtrip_migration_changes_fail(prepared, mutation, match):
    expected = prepared["data"][0]
    actual = copy.deepcopy(expected)
    mutation(actual)
    with pytest.raises(ValueError, match=match):
        verify_readback(expected, actual)


def test_unsafe_extra_preset_cannot_survive(prepared):
    expected = prepared["data"][0]
    actual = copy.deepcopy(expected)
    actual["start-values"]["presets"].append({"n": 60000, "v_f": 2500})
    with pytest.raises(ValueError, match="exactly one"):
        verify_readback(expected, actual)


def test_changed_source_hash_blocks_before_writing(tmp_path):
    config = json.loads(CONFIG.read_text())
    source = config["tools"].get("source_library", config["tools"]["library"])
    source["sha256"] = "0" * 64
    modified = tmp_path / "config.json"
    modified.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="source changed"):
        prepare(modified, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_wrong_gauge_sum_is_not_silently_repaired(tmp_path):
    config = json.loads(CONFIG.read_text())
    config["tools"]["entries"][0]["assembled_gauge_length_mm"] = 33.02
    modified = tmp_path / "config.json"
    modified.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="assembly gauge sum"):
        prepare(modified, tmp_path / "output")


def test_existing_attempt_evidence_is_not_overwritten(tmp_path):
    prepare(CONFIG, tmp_path)
    with pytest.raises(FileExistsError):
        prepare(CONFIG, tmp_path)


@pytest.mark.parametrize("return_unspecified", [False, True])
def test_live_api_shape_uses_versioned_library_not_single_tool_envelope(
    tmp_path, monkeypatch, return_unspecified
):
    import sys
    from types import ModuleType, SimpleNamespace

    from fusion.prepare_tool_assemblies import apply

    imported = []

    class Library:
        @staticmethod
        def createFromJson(text):
            value = json.loads(text)
            assert isinstance(value["data"], list) and value["version"] == 36
            assert [t["post-process"]["number"] for t in value["data"]] == [1, 2]
            imported.append(value)
            return Library(value)

        def __init__(self, value):
            self.value = value
            self.count = len(value["data"])

        def item(self, index):
            # Single Tool.toJson returns an object, never the library envelope.
            value = self.value["data"][index]
            if return_unspecified:
                # Characteristic actual tools-v1 failure (wrong API input shape).
                value = {"unit": "millimeters", "type": "unspecified", "geometry": {"DC": 0}}
            return SimpleNamespace(toJson=lambda: json.dumps(value))

        def toJson(self):
            return json.dumps(self.value)

    def reject_single_tool_envelope(_):
        pytest.fail("Library envelope must never be sent to Tool.createFromJson")

    adsk = ModuleType("adsk")
    cam = ModuleType("adsk.cam")
    cam.ToolLibrary = Library
    cam.Tool = SimpleNamespace(createFromJson=reject_single_tool_envelope)
    adsk.cam = cam
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.cam", cam)
    output = tmp_path / "live-shape"
    payload = {"config_path": str(CONFIG), "output_directory": str(output)}
    if return_unspecified:
        with pytest.raises(ValueError, match="Fusion changed tool unit"):
            apply(SimpleNamespace(version="test-double"), payload)
        assert (
            json.loads((output / "tool-1-fusion-readback.json").read_text())["type"]
            == "unspecified"
        )
        assert not (output / "tool-assembly-report.json").exists()
    else:
        report = apply(SimpleNamespace(version="test-double"), payload)
        assert report["status"] == "fusion_tool_library_roundtrip_passed_not_assigned"
        assert [tool["number"] for tool in report["tools"]] == [1, 2]
        assert report["manufacturing_verified"] is False
    assert len(imported) == 1


@pytest.mark.parametrize("missing", ["v_f", "v_f_plunge", "v_f_ramp", "f_z"])
def test_missing_operative_milling_preset_value_is_rejected(prepared, missing):
    expected = prepared["data"][0]
    actual = copy.deepcopy(expected)
    del actual["start-values"]["presets"][0][missing]
    with pytest.raises(ValueError, match=f"preset.{missing}"):
        verify_readback(expected, actual)


def test_live_milling_preset_without_retract_and_with_fn_alias_is_accepted(prepared):
    expected = prepared["data"][0]
    actual = copy.deepcopy(expected)
    preset = actual["start-values"]["presets"][0]
    preset["f_n"] = preset["f_z"]  # Observed Fusion milling serialization.
    assert "v_f_retract" not in preset
    report = verify_readback(expected, actual)
    assert report["retract_verification"]["status"] == "deferred_to_operation_and_simulation"
    assert report["feed_mm_min"] == pytest.approx(1371.6)


def test_reprepare_configured_library_uses_original_catalog_without_compounded_changes(tmp_path):
    configured = json.loads(CONFIG.read_text())
    source = configured["tools"]["source_library"]
    catalog = json.loads(Path(source["path"]).read_text())
    # Recover the initial setup state from its preserved source identity.
    original = copy.deepcopy(configured)
    original["tools"]["library"] = original["tools"].pop("source_library")
    for entry in original["tools"]["entries"]:
        if "source_geometry" in entry:
            entry["geometry"] = entry.pop("source_geometry")
    original_path = tmp_path / "original-config.json"
    original_path.write_text(json.dumps(original))
    initial = prepare(original_path, tmp_path / "initial")
    rebuilt = prepare(CONFIG, tmp_path / "rebuilt")
    first = json.loads(Path(initial["input_path"]).read_text())
    second = json.loads(Path(rebuilt["input_path"]).read_text())
    assert first == second
    assert second["version"] == catalog["version"]
    assert rebuilt["cutter_source_sha256"] == source["sha256"]
    assert rebuilt["cutter_source_path"] == str(Path(source["path"]).resolve())
    assert rebuilt["cutter_source_version"] == catalog["version"]
    for tool, expected_feed in zip(second["data"], [1371.6, 685.8], strict=True):
        preset = tool["start-values"]["presets"][0]
        assert preset["v_f"] * 25.4 == pytest.approx(expected_feed)
        assert preset["v_f_plunge"] == pytest.approx(preset["v_f"] / 3)
        assert preset["n"] == 6000


def test_changed_preserved_source_geometry_blocks_repreparation(tmp_path):
    configured = json.loads(CONFIG.read_text())
    configured["tools"]["entries"][0]["source_geometry"]["LCF"] = 0.25
    path = tmp_path / "bad-source-config.json"
    path.write_text(json.dumps(configured))
    with pytest.raises(ValueError, match="Configured geometry differs"):
        prepare(path, tmp_path / "output")
