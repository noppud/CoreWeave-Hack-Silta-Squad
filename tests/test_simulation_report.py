import pytest

from silta.cnc.simulation_report import parse_issues_ax, parse_issues_native


def snapshot(percent=100, errors=54, warnings=0, process=0):
    # Structure observed in Fusion 2705.1.15. Offscreen details may be absent.
    widget = "QTApplication.SimulationIssuesWidget"
    return (
        'Window: "", App: Fusion.\n'
        f" 1 text Value: Verification: {percent}%  |  Errors: {errors}  |  "
        f"Warnings: {warnings}  |  Process: {process}, ID: {widget}.verificationLabel\n"
        f" 2 container Fixture+Cutter, ID: {widget}.SimulationIssuesTreeView\n"
        f" 3 container Rapid move into stock, ID: {widget}.SimulationIssuesTreeView\n"
    )


def test_completed_collision_is_failure_with_observed_details():
    result = parse_issues_ax(snapshot())
    assert result.completed and result.result == "failed"
    assert result.errors == 54
    assert result.observed_details == ("Fixture+Cutter", "Rapid move into stock")


@pytest.mark.parametrize("percent,process", [(99.9, 0), (100, 1), (0, 0)])
def test_partial_or_process_failure_is_not_manufacturing_verdict(percent, process):
    assert parse_issues_ax(snapshot(percent=percent, process=process)).result == "unknown"


def test_zero_errors_does_not_bypass_stock_comparison():
    assert parse_issues_ax(snapshot(errors=0)).result == "requires_stock_comparison"


@pytest.mark.parametrize(
    "text",
    [
        "Verification: 100% | Errors: 0 | Warnings: 0 | Process: 0",
        snapshot().replace("App: Fusion.", "App: Other."),
        snapshot().replace("verificationLabel", "animationLabel"),
        snapshot() + snapshot(),
        snapshot(percent=101),
        snapshot().replace("Errors: 54", "Errors: unknown"),
    ],
)
def test_missing_changed_or_ambiguous_evidence_is_rejected(text):
    with pytest.raises(ValueError):
        parse_issues_ax(text)


def test_native_rows_require_actual_unique_summary_not_ocr_or_animation():
    row = {
        "AXIdentifier": "QTApplication.SimulationIssuesWidget.verificationLabel",
        "AXValue": "Verification: 100%  |  Errors: 0  |  Warnings: 0  |  Process: 0",
    }
    state = {"foreground": True, "document": "Candidate", "elements": [row]}
    assert parse_issues_native(state).result == "requires_stock_comparison"
    for changed in (
        {**state, "foreground": False},
        {**state, "elements": []},
        {**state, "elements": [row, row]},
        {**state, "elements": [{**row, "AXIdentifier": "animationLabel"}]},
    ):
        with pytest.raises(ValueError):
            parse_issues_native(changed)
