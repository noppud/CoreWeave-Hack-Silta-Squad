"""Frozen manufacturing assets must retain identity and survive source relocation."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from silta.cnc.benchmarks import case_input_hash, decode_inputs
from silta.cnc.models import Artifact, Candidate, JobInputs, Target
from silta.cnc.store import JobStore


@pytest.fixture
def assets(tmp_path):
    def pin(name, content):
        path = tmp_path / name
        path.write_text(content)
        return asdict(Artifact.from_path(path))

    drawing = pin("drawing.pdf", "test drawing")
    machine = pin("machine.mch", "test machine definition")
    geometry = pin("machine.f3d", "test machine simulation geometry")
    tools = pin("tools.json", "test cutter library")
    holder = pin("holder.json", "test holder library")
    fixture = pin("fixture.f3d", "test vise")
    post = pin("post.cps", "test postprocessor")
    inputs = JobInputs(
        (Artifact(**drawing),),
        {
            "axes": 3,
            "definition": {**machine, "source_url": "https://example.test/machine"},
            "simulation_geometry": geometry,
            "postprocessor": post,
        },
        {"library": tools, "holders": [{"artifact": holder, "gauge_mm": 80}]},
        {"fixture": {"artifact": fixture, "translation_mm": [0, 0, 0]}, "postprocessor": post},
        {"linear_mm": 0.1},
    )
    return inputs


def collect(inputs):
    pins = []
    inputs.map_artifacts(lambda artifact: pins.append(artifact) or artifact)
    return pins


@pytest.mark.parametrize(
    "field", ["machine", "machine_geometry", "tools", "holder", "fixture", "post"]
)
def test_each_nested_manufacturing_asset_is_verified(assets, field):
    inputs = assets
    pin = {
        "machine": inputs.machine["definition"],
        "machine_geometry": inputs.machine["simulation_geometry"],
        "tools": inputs.tools["library"],
        "holder": inputs.tools["holders"][0]["artifact"],
        "fixture": inputs.setup["fixture"]["artifact"],
        "post": inputs.setup["postprocessor"],
    }[field]
    inputs.verify()
    Path(pin["path"]).write_text("modified asset")
    with pytest.raises(ValueError, match="Artifact changed"):
        inputs.verify()


def test_snapshot_copies_all_pins_preserves_metadata_and_survives_deleted_sources(tmp_path, assets):
    store = JobStore(tmp_path / "jobs", "one")
    original = asdict(assets)
    copied = store.inputs(assets)
    assert copied.digest == assets.digest
    assert copied.machine["definition"]["source_url"] == "https://example.test/machine"
    assert copied.tools["holders"][0]["gauge_mm"] == 80
    assert copied.setup["fixture"]["translation_mm"] == [0, 0, 0]
    assert asdict(assets) == original
    pins = collect(copied)
    assert len(pins) == 8  # drawing, machine, model, duplicate post pins, tools, holder, fixture
    assert all(Path(pin.path).is_relative_to(store.directory / "inputs") for pin in pins)
    assert all(not Path(pin.path).stat().st_mode & 0o222 for pin in pins)
    for source in {pin.path for pin in collect(assets)}:
        Path(source).unlink()
    copied.verify()
    manifest = json.loads(store.manifest_path.read_text())
    reconstructed = decode_inputs(manifest["inputs"])
    reconstructed.verify()
    assert reconstructed.digest == copied.digest == manifest["input_digest"]


def test_snapshot_mutation_is_detected(tmp_path, assets):
    copied = JobStore(tmp_path / "jobs", "one").inputs(assets)
    machine = Path(copied.machine["definition"]["path"])
    machine.chmod(0o644)
    machine.write_text("mutated job-local machine")
    with pytest.raises(ValueError, match="Artifact changed"):
        copied.verify()


def test_path_relocation_preserves_benchmark_identity_but_content_or_metadata_change_does_not(
    tmp_path, assets
):
    copied = JobStore(tmp_path / "jobs", "one").inputs(assets)
    part = tmp_path / "part.step"
    part.write_text("test accepted target")
    nc = tmp_path / "part.nc"
    nc.write_text("test candidate")
    target = Target.from_paths({"step": str(part)}, "test")
    candidate = Candidate.from_paths("test", target.digest, {"nc": str(nc)})
    for kind in ("checks", "loop"):
        assert case_input_hash(kind, assets, target, candidate) == case_input_hash(
            kind, decode_inputs(asdict(copied)), target, candidate
        )
    changed_metadata = replace(copied, tools={**copied.tools, "holder_extension_mm": 10})
    assert changed_metadata.digest != copied.digest
    new_machine = tmp_path / "replacement.mch"
    new_machine.write_text("another machine")
    changed_content = replace(
        copied,
        machine={
            **copied.machine,
            "definition": {
                **copied.machine["definition"],
                **asdict(Artifact.from_path(new_machine)),
            },
        },
    )
    changed_content.verify()
    assert changed_content.digest != copied.digest


def test_failed_nested_pin_never_becomes_a_recorded_input_snapshot(tmp_path, assets):
    Path(assets.tools["library"]["path"]).unlink()
    store = JobStore(tmp_path / "jobs", "bad")
    with pytest.raises(FileNotFoundError):
        store.inputs(assets)
    assert "inputs" not in json.loads(store.manifest_path.read_text())
    assert not (store.directory / "inputs").exists()
