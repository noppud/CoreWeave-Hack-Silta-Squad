import hashlib
import runpy
from pathlib import Path

relocate = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/demo/relocate_config.py")
)["relocate"]


def test_new_checkout_preserves_hashes_and_account_bindings(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    new.mkdir()
    (new / "asset").write_bytes(b"pinned")
    digest = hashlib.sha256(b"pinned").hexdigest()
    config = {
        "assets": [{"path": str(old / "asset"), "sha256": digest}],
        "library_url": "user://specific.mch",
        "version_id": "urn:exact",
    }
    moved, report = relocate(config, old, new)
    assert report["status"] == "verified"
    assert moved["assets"][0] == {"path": str(new / "asset"), "sha256": digest}
    assert moved["library_url"] == config["library_url"] and moved["version_id"] == "urn:exact"
    assert config["assets"][0]["path"] == str(old / "asset")
    (new / "asset").write_bytes(b"changed")
    assert relocate(config, old, new)[1]["status"] == "failed"


def test_outside_root_and_escape_are_not_silently_relocated(tmp_path):
    assert relocate({"path": "/unrelated/file"}, tmp_path / "old", tmp_path / "new")[1]["errors"]
    assert relocate(
        {"path": str(tmp_path / "old" / ".." / "escape")}, tmp_path / "old", tmp_path / "new"
    )[1]["errors"]
