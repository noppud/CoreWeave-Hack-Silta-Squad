from silta.cnc.native_reader import NativeFusionReader


def test_missing_summary_reopens_only_observed_issues_panel_once():
    close = {
        "AXTitle": "Close",
        "AXIdentifier": "Qt.SimulationIssuesPanelCategory.close",
        "window": "",
    }
    label = {
        "AXIdentifier": "Qt.SimulationIssuesWidget.verificationLabel",
        "AXValue": "Verification: 100% | Errors: 52 | Warnings: 0 | Process: 0",
    }
    calls = []

    class Native:
        def ui(self, action, *args):
            calls.append((action, *args))
            restored = any(c[0] == "press" for c in calls)
            return {"elements": [close, label] if restored else [close]}

    class Bridge:
        def request(self, action, payload):
            assert (action, payload) == ("simulation_command", {"command_id": "SimulationIssues"})
            return {"status": "ok"}

    reader = NativeFusionReader(Bridge(), None)
    reader.native = Native()
    reader.read()
    reader.read()
    assert not any(c[0] == "press" for c in calls)
    result = reader.read()
    assert label in result["native_state"]["elements"]
    reader.read()
    assert sum(c[0] == "press" for c in calls) == 1


def test_missing_summary_does_not_close_unrelated_dialog():
    class Native:
        def ui(self, action, *args):
            assert action == "inspect-ax"
            return {"elements": [{"AXTitle": "Close", "AXIdentifier": "OtherDialog.close"}]}

    reader = NativeFusionReader(None, None)
    reader.native = Native()
    for _ in range(5):
        assert "verificationLabel" not in reader.read()["raw_text"]
    assert not reader.issues_refreshed


def test_focus_preflight_restores_space_once_for_foreground_error(monkeypatch, tmp_path):
    import silta.cnc.native_reader as module

    calls = []

    class Native:
        space_restore_attempted = False

        def ui(self, action):
            calls.append(action)
            if len(calls) == 1:
                raise RuntimeError("Fusion is not foreground; no input sent")
            return {"foreground": True, "document": "pinned"}

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append("restore"))
    reader = NativeFusionReader(None, tmp_path)
    reader.native = Native()
    result = reader.bring_to_front()
    assert calls == ["focus", "restore", "focus"]
    assert result["preflight"]["status"] == "ready"
    assert result["preflight"]["recovery_attempted"]
    assert (tmp_path / "fusion-readiness-preflight.json").exists()


def test_failed_preflight_remains_failure_without_retry_cascade(monkeypatch, tmp_path):
    import pytest

    import silta.cnc.native_reader as module

    calls = []

    class Native:
        space_restore_attempted = False

        def ui(self, action):
            calls.append(action)
            raise RuntimeError("Fusion is not foreground; no input sent")

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append("restore"))
    reader = NativeFusionReader(None, tmp_path)
    reader.native = Native()
    with pytest.raises(RuntimeError) as failure:
        reader.bring_to_front()
    assert calls == ["focus", "restore", "focus"]
    assert failure.value.evidence["status"] == "preflight_failed"
    assert failure.value.evidence["completed"] is False


def test_preflight_does_not_repeat_transport_recovery(monkeypatch, tmp_path):
    import pytest

    import silta.cnc.native_reader as module

    class Native:
        space_restore_attempted = True

        def ui(self, action):
            raise RuntimeError("Fusion is not foreground; no input sent")

    def forbidden(*args, **kwargs):
        raise AssertionError("Second space normalization is forbidden")

    monkeypatch.setattr(module.subprocess, "run", forbidden)
    reader = NativeFusionReader(None, tmp_path)
    reader.native = Native()
    with pytest.raises(RuntimeError, match="readiness preflight failed"):
        reader.bring_to_front()


def test_preflight_does_not_replay_unrelated_error(monkeypatch, tmp_path):
    import pytest

    import silta.cnc.native_reader as module

    class Native:
        space_restore_attempted = False

        def ui(self, action):
            raise RuntimeError("Pinned document modified")

    def forbidden(*args, **kwargs):
        raise AssertionError("Unrelated failures must not trigger recovery")

    monkeypatch.setattr(module.subprocess, "run", forbidden)
    reader = NativeFusionReader(None, tmp_path)
    reader.native = Native()
    with pytest.raises(RuntimeError, match="Pinned document modified"):
        reader.bring_to_front()


def test_absent_panel_opens_once_after_exact_binding(tmp_path):
    calls = []

    class Native:
        document = "exact"

        def ui(self, action):
            assert action == "inspect-ax"
            return {"elements": []}

    class Bridge:
        def request(self, action, payload=None, **kwargs):
            calls.append(action)
            return {
                "status": "ok",
                "result": {"document": "exact", "active_command": "IronMachineSimulation"},
            }

    reader = NativeFusionReader(Bridge(), tmp_path)
    reader.native = Native()
    for _ in range(8):
        reader.read()
    assert calls == ["simulation_dialog", "simulation_command"]
    assert (tmp_path / "issues-panel-recovery.json").exists()


def test_absent_panel_wrong_document_never_opens(tmp_path):
    import pytest

    calls = []

    class Native:
        document = "exact"

        def ui(self, action):
            return {"elements": []}

    class Bridge:
        def request(self, action, **kwargs):
            calls.append(action)
            return {
                "status": "ok",
                "result": {"document": "other", "active_command": "IronMachineSimulation"},
            }

    reader = NativeFusionReader(Bridge(), tmp_path)
    reader.native = Native()
    reader.read()
    reader.read()
    with pytest.raises(RuntimeError, match="changed"):
        reader.read()
    reader.read()
    assert calls == ["simulation_dialog"]
