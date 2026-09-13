from silta.cnc.native_reader import NativeFusionReader


def test_missing_summary_reopens_only_observed_issues_panel_once():
    close = {'AXTitle': 'Close', 'AXIdentifier': 'Qt.SimulationIssuesPanelCategory.close',
             'window': ''}
    label = {'AXIdentifier': 'Qt.SimulationIssuesWidget.verificationLabel',
             'AXValue': 'Verification: 100% | Errors: 52 | Warnings: 0 | Process: 0'}
    calls = []

    class Native:
        def ui(self, action, *args):
            calls.append((action, *args))
            restored = any(c[0] == 'press' for c in calls)
            return {'elements': [close, label] if restored else [close]}

    class Bridge:
        def request(self, action, payload):
            assert (action, payload) == ('simulation_command', {'command_id': 'SimulationIssues'})
            return {'status': 'ok'}

    reader = NativeFusionReader(Bridge(), None)
    reader.native = Native()
    reader.read()
    reader.read()
    assert not any(c[0] == 'press' for c in calls)
    result = reader.read()
    assert label in result['native_state']['elements']
    reader.read()
    assert sum(c[0] == 'press' for c in calls) == 1


def test_missing_summary_does_not_close_unrelated_dialog():
    class Native:
        def ui(self, action, *args):
            assert action == 'inspect-ax'
            return {'elements': [{'AXTitle': 'Close', 'AXIdentifier': 'OtherDialog.close'}]}

    reader = NativeFusionReader(None, None)
    reader.native = Native()
    for _ in range(5):
        assert 'verificationLabel' not in reader.read()['raw_text']
    assert not reader.issues_refreshed
