"""Reader transport tests; fixture UI text does not prove a live simulation."""

import json
import shutil
import subprocess
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
            "thread/start", "mcpServer/tool/call", "mcpServer/tool/call"
        ]
        assert native.calls[1][1]["arguments"]["code"] == module._OPEN
        assert "disableDiffing: true" in result["arguments"]["code"]
        assert "emit: false" in result["arguments"]["code"]
    assert native.closed
    with pytest.raises(RuntimeError, match="context manager"):
        reader.read()


@pytest.mark.parametrize("texts", [[], ["No changes"], [module._MARKER + '""'], [
    module._MARKER + '"a"', module._MARKER + '"b"'
]])
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


def _run_front_script(states):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to exercise the fixed JS selector")
    harness = """
        const states = STATES;
        const calls = [];
        const siltaFusion = {
            getAXState: async options => {
                calls.push(['read', options]); return states.shift();
            },
            click: async index => calls.push(['click', index])
        };
        const nodeRepl = {write: value => calls.push(['write', value])};
        (async () => {
            try { SCRIPT; console.log(JSON.stringify({calls})); }
            catch (error) { console.log(JSON.stringify({calls, error: error.message})); }
        })();
    """.replace("STATES", json.dumps(states)).replace("SCRIPT", module._BRING_TO_FRONT)
    result = subprocess.run([node, "-e", harness], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def test_front_focus_uses_fresh_semantic_indexes_and_one_final_snapshot():
    snapshots = [
        'Window: "Fusion"\n0 dialog\n39 menu bar\n'
        '\t48 Window, Secondary Actions: Cancel, Pick',
        'Window: "Fusion"\n\t999 Bring All to Front, ID: qt_itemFired:\n\t1000 Other item',
        'Window: "Fusion"\n1 text Focused simulation',
    ]
    result = _run_front_script(snapshots)
    assert "error" not in result
    assert [x for x in result["calls"] if x[0] == "click"] == [["click", 48], ["click", 999]]
    reads = [x for x in result["calls"] if x[0] == "read"]
    assert len(reads) == 3
    assert all(x[1] == {"disableDiffing": True, "emit": False} for x in reads)
    writes = [x[1] for x in result["calls"] if x[0] == "write"]
    assert [json.loads(x.split(":", 1)[1]) for x in writes] == [snapshots[-1]]
    # Native nodeRepl concatenates writes into one block without a separator.
    # Our successful routine must still produce one independently decodable AX.
    evidence = {"raw_mcp_response": {"content": [{"type": "text", "text": "".join(writes)}]}}
    assert module.FusionUIReader._snapshot(evidence)["raw_text"] == snapshots[-1]


@pytest.mark.parametrize("state", [
    "0 dialog", "12 Window\n13 Window", "12 Window (disabled)", "12 Window, Other label"
])
def test_front_focus_missing_or_ambiguous_window_does_not_click(state):
    result = _run_front_script([state])
    assert "Expected one visible Fusion menu item: Window" in result["error"]
    assert not any(x[0] == "click" for x in result["calls"])


def test_front_focus_missing_command_does_not_click_stale_index():
    result = _run_front_script(["12 menu Window", "12 Other command\n40 menu item Close"])
    assert "Bring All to Front" in result["error"]
    assert [x for x in result["calls"] if x[0] == "click"] == [["click", 12]]
    diagnostic = next(x[1] for x in result["calls"] if x[0] == "write")
    diagnostic = json.loads(diagnostic.split(":", 1)[1])
    assert diagnostic["before"] == "12 menu Window"
    assert diagnostic["menu"] == "12 Other command\n40 menu item Close"


def test_focus_methods_use_only_fixed_scripts(tmp_path, client):
    with module.FusionUIReader(tmp_path) as reader:
        result = reader.bring_to_front()
        assert result["arguments"]["code"] == module._BRING_TO_FRONT
        result = reader.focus_next_panel()
        assert result["arguments"]["code"] == module._FOCUS_NEXT_PANEL
        assert 'pressKey("ctrl+F6")' in result["arguments"]["code"]
