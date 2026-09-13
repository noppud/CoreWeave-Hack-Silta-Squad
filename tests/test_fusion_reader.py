"""Reader transport tests; fixture UI text does not prove a live simulation."""

import json
from types import SimpleNamespace

import pytest

from silta.cnc import fusion_reader as module


@pytest.fixture
def client(monkeypatch):
    class Client:
        def __init__(self, config, approval_handler):
            self.calls = []
            self.closed = False
            self.reply = {
                "content": [
                    {
                        "type": "text",
                        "text": module._MARKER + json.dumps("Full AX\nVerification 100%"),
                    }
                ]
            }

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def initialize(self):
            pass

        def thread_start(self, params):
            self.calls.append(("thread/start", params))
            return SimpleNamespace(thread=SimpleNamespace(id="reader-test"))

        def request(self, method, params, response_model):
            self.calls.append((method, params))
            return response_model.model_validate(self.reply)

    created = []

    def factory(*args, **kwargs):
        obj = Client(*args, **kwargs)
        created.append(obj)
        return obj

    monkeypatch.setattr(module, "CodexClient", factory)
    return created


def test_reader_preserves_full_text_and_native_response_without_model_turn(tmp_path, client):
    with module.FusionUIReader(tmp_path) as reader:
        native = client[0]
        text = "Verification 100%\n" + "Collision between tool and fixture\n" * 500
        native.reply = {
            "content": [
                {"type": "text", "text": "Unrelated documentation"},
                {"type": "text", "text": module._MARKER + json.dumps(text)},
            ],
            "_meta": {"native": True},
        }
        result = reader.read()
        assert result["raw_text"] == text
        assert result["raw_mcp_response"]["_meta"] == {"native": True}
        assert result["raw_mcp_response"]["content"] == native.reply["content"]
        assert result["thread_id"] == "reader-test"
        assert [call[0] for call in native.calls] == [
            "thread/start",
            "mcpServer/tool/call",
            "mcpServer/tool/call",
        ]
        assert native.calls[1][1]["arguments"]["code"] == module._OPEN
        assert "disableDiffing: true" in result["arguments"]["code"]
        assert "emit: false" in result["arguments"]["code"]
    assert native.closed
    with pytest.raises(RuntimeError, match="context manager"):
        reader.read()


@pytest.mark.parametrize(
    "texts",
    [[], ["No changes"], [module._MARKER + '""'], [module._MARKER + '"a"', module._MARKER + '"b"']],
)
def test_missing_empty_or_ambiguous_snapshot_is_collection_failure(tmp_path, client, texts):
    with module.FusionUIReader(tmp_path) as reader:
        client[0].reply = {"content": [{"type": "text", "text": text} for text in texts]}
        with pytest.raises(RuntimeError, match="unique full state") as exc:
            reader.read()
        assert exc.value.evidence["raw_mcp_response"]["content"] == client[0].reply["content"]


def test_native_error_preserves_receipt_and_cannot_become_snapshot(tmp_path, client):
    with module.FusionUIReader(tmp_path) as reader:
        client[0].reply = {"content": [{"type": "text", "text": "locked"}], "isError": True}
        with pytest.raises(RuntimeError, match="collection failed") as exc:
            reader.read()
        assert exc.value.evidence["raw_mcp_response"]["isError"] is True


def test_malformed_snapshot_preserves_raw_evidence(tmp_path, client):
    with module.FusionUIReader(tmp_path) as reader:
        client[0].reply = {"content": [{"type": "text", "text": module._MARKER + '"broken'}]}
        with pytest.raises(RuntimeError, match="malformed state") as exc:
            reader.read()
        assert exc.value.evidence["raw_mcp_response"]["content"] == client[0].reply["content"]


def test_optional_screenshot_uses_fixed_reader_and_preserves_image(tmp_path, client):
    with module.FusionUIReader(tmp_path) as reader:
        client[0].reply["content"].append(
            {"type": "image", "mimeType": "image/png", "data": "test-image"}
        )
        result = reader.read(screenshot=True)
        assert result["arguments"]["code"] == module._READ_SCREENSHOT
        assert result["raw_mcp_response"]["content"][-1]["data"] == "test-image"


def test_native_focus_uses_exact_observed_document(tmp_path, client, monkeypatch):
    from silta.cnc import stock_export

    calls = []

    class Native:
        def __init__(self, document, directory):
            calls.append((document, directory))

        def ui(self, action):
            assert action == "focus"
            return {"foreground": True, "windows": []}

    monkeypatch.setattr(stock_export, "StockExporter", Native)
    with module.FusionUIReader(tmp_path) as reader:
        client[0].reply["content"][0]["text"] = module._MARKER + json.dumps(
            'Window: "Candidate 42 - Autodesk Fusion (Trial) ", App: Fusion.'
        )
        result = reader.bring_to_front()
    assert calls[0][0] == "Candidate 42"
    assert result["native_focus"]["foreground"] is True


def test_focus_does_not_guess_missing_document_title(tmp_path, client):
    with module.FusionUIReader(tmp_path) as reader:
        with pytest.raises(RuntimeError, match="observed document"):
            reader.bring_to_front()
