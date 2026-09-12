import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from silta.cnc.astra import AstraClient
from silta.cnc.cli import read_inputs
from silta.cnc.models import Artifact


def test_draft_config_cannot_run(tmp_path):
    config = tmp_path / "job.json"
    config.write_text(json.dumps({"status": "needs_setup", "unresolved": ["fixture not placed"]}))
    with pytest.raises(ValueError, match="fixture not placed"):
        read_inputs(config)


def test_config_rejects_replaced_drawing(tmp_path):
    drawing = tmp_path / "part.pdf"
    drawing.write_bytes(b"original test drawing")
    artifact = Artifact.from_path(drawing)
    drawing.write_bytes(b"changed test drawing")
    config = tmp_path / "job.json"
    config.write_text(json.dumps({"status": "ready", "drawings": [vars(artifact)]}))
    with pytest.raises(ValueError, match="Drawing content differs"):
        read_inputs(config)


def test_astra_child_environment_excludes_api_credentials(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "test-sentinel-never-a-real-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-separate-billing-sentinel")
    client = AstraClient(binary="/usr/bin/true")
    args = client._config(Path.cwd()).launch_args_override
    assert args[:2] == ("/usr/bin/env", "-i")
    assert not any("API_KEY=" in arg for arg in args)
    assert "test-sentinel-never-a-real-key" not in str(args)


def test_api_key_login_cannot_silently_replace_subscription():
    codex = SimpleNamespace(
        account=lambda: SimpleNamespace(
            account=SimpleNamespace(root=SimpleNamespace(type="apiKey"))
        )
    )
    with pytest.raises(RuntimeError, match="subscription login"):
        AstraClient._require_subscription(codex)


def test_ui_doctor_does_not_report_success_when_mac_is_locked(tmp_path, monkeypatch, capsys):
    from silta.cnc.cli import main

    class Client:
        def __init__(self, **kwargs):
            pass

        def check_access(self, workspace):
            return {"authenticated": True}

        def ask_with_evidence(self, *args, **kwargs):
            return {"value": {"status": "unavailable", "screen": "Mac is locked"}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("silta.cnc.cli.AstraClient", Client)
    monkeypatch.setattr("sys.argv", ["silta", "doctor", "--fusion-ui"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "incomplete"
