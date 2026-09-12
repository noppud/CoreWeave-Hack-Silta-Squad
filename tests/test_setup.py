import sys
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from silta import setup


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(setup, "load_dotenv", lambda: None)
    for name, value in {
        "WANDB_API_KEY": "test-secret",
        "WANDB_ENTITY": "test-team",
        "WANDB_PROJECT": "test-project",
        "WANDB_INFERENCE_MODEL": "",
    }.items():
        monkeypatch.setenv(name, value)


def test_models_can_be_discovered_before_selecting_one(configured, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["setup", "--models"])
    response = httpx.Response(
        200,
        json={"data": [{"id": "model-b"}, {"id": "model-a"}]},
        request=httpx.Request("GET", "https://api.inference.wandb.ai/v1/models"),
    )
    get = Mock(return_value=response)
    monkeypatch.setattr(httpx, "get", get)
    setup.main()
    assert get.call_args.kwargs["headers"]["OpenAI-Project"] == "test-team/test-project"
    output = capsys.readouterr().out
    assert "model-a\nmodel-b" in output
    assert "test-secret" not in output


def test_trace_does_not_need_a_model_or_make_inference_calls(configured, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["setup", "--trace"])
    client = Mock()
    init = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "weave", SimpleNamespace(init=init, op=lambda: lambda fn: fn))
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: pytest.fail("Unexpected HTTP request"))
    setup.main()
    init.assert_called_once_with("test-team/test-project")
    client.flush.assert_called_once_with()
    assert "inference credits are still unverified" in capsys.readouterr().out


def test_failed_model_listing_reports_status_without_secret(configured, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["setup", "--models"])
    response = httpx.Response(
        401, request=httpx.Request("GET", "https://api.inference.wandb.ai/v1/models")
    )
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    with pytest.raises(SystemExit) as exc:
        setup.main()
    assert exc.value.code == 1
    output = capsys.readouterr().err
    assert "HTTP 401" in output
    assert "test-secret" not in output
