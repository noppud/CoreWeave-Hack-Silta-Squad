"""Read Fusion Issues with the same fixed macOS transport used for stock export."""

from __future__ import annotations

import json

from .stock_export import StockExporter


class NativeFusionReader:
    def __init__(self, bridge, directory):
        self.bridge, self.directory = bridge, directory
        self.native = None
        self.open_evidence = None
        self.missing_summary_reads = 0
        self.issues_refreshed = False

    def __enter__(self):
        reply = self.bridge.request("simulation_dialog", timeout=15)
        document = reply.get("result", {}).get("document")
        if reply.get("status") != "ok" or not document:
            raise RuntimeError("Native reader needs the current Fusion document")
        self.native = StockExporter(document, self.directory / "native-reader", bridge=self.bridge)
        self.open_evidence = {"transport": "fixed macOS AX", "document": document}
        return self

    def __exit__(self, *args):
        self.native = None

    def bring_to_front(self):
        return self.native.ui("focus")

    def read(self):
        state = self.native.ui("inspect-ax")
        summary = any(
            row.get("AXIdentifier", "").endswith(".SimulationIssuesWidget.verificationLabel")
            for row in state["elements"]
        )
        self.missing_summary_reads = 0 if summary else self.missing_summary_reads + 1
        if self.missing_summary_reads >= 3 and not self.issues_refreshed:
            # Fusion sometimes omits the summary from AX until this panel is
            # reopened. Refresh only its exact observed Close control, once.
            controls = [
                row for row in state["elements"]
                if row.get("AXTitle") == "Close"
                and "SimulationIssuesPanelCategory" in row.get("AXIdentifier", "")
            ]
            if len(controls) == 1:
                row = controls[0]
                self.issues_refreshed = True
                self.native.ui("press", row["window"], row["AXIdentifier"])
                reply = self.bridge.request(
                    "simulation_command", {"command_id": "SimulationIssues"}
                )
                if reply.get("status") != "ok":
                    raise RuntimeError("Could not reopen the observed Fusion Issues panel")
                state = self.native.ui("inspect-ax")
        return {
            "native_state": state,
            "raw_text": json.dumps(state["elements"], sort_keys=True),
        }
