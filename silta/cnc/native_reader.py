"""Read Fusion Issues with the same fixed macOS transport used for stock export."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from time import monotonic

from .stock_export import StockExporter


class NativeFusionReader:
    def __init__(self, bridge, directory):
        self.bridge, self.directory = bridge, directory
        self.native = None
        self.open_evidence = None
        self.missing_summary_reads = 0
        self.issues_refreshed = False
        self.issues_recovery_evidence = None

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
        """Bounded focus-only readiness recovery before simulation is launched.

        StockExporter already handles one missing-window recovery. Reuse its
        flag so a subsequent foreground error cannot create a retry cascade.
        Pinned-document validation belongs to the existing document opener;
        Display controls are inspected only after simulation launch.
        """
        started = monotonic()
        evidence = {
            "stage": "fusion_focus_preflight",
            "status": "checking",
            "completed": False,
            "recovery_attempted": False,
            "attempt_errors": [],
            "scope": "Window focus readiness only; not manufacturing verification",
        }

        def retain():
            evidence["wall_time_s"] = monotonic() - started
            evidence["recovery_attempted"] = bool(
                getattr(self.native, "space_restore_attempted", False)
            )
            if self.directory is not None:
                path = Path(self.directory) / "fusion-readiness-preflight.json"
                path.write_text(json.dumps(evidence, indent=2))

        try:
            try:
                state = self.native.ui("focus")
            except RuntimeError as error:
                evidence["attempt_errors"].append(str(error))
                focus_only = str(error) in {
                    "Fusion is not foreground; no input sent",
                    "Fusion lost foreground access; export stopped",
                }
                if not focus_only or getattr(self.native, "space_restore_attempted", False):
                    raise
                self.native.space_restore_attempted = True
                # Native AX Raise alone does not reliably activate Fusion.
                # This changes focus only; never replay a simulation mutation.
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application id "com.autodesk.fusion360" to activate',
                        "-e",
                        'tell application "System Events" to tell process '
                        '"Autodesk Fusion" to set frontmost to true',
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                state = self.native.ui("focus")
            if state.get("foreground") is not True:
                raise RuntimeError("Focus preflight did not confirm Fusion foreground")
            evidence["status"] = "ready"
            evidence["completed"] = True
            retain()
            return {**state, "preflight": evidence}
        except Exception as error:
            evidence["status"] = "preflight_failed"
            evidence["error"] = f"{type(error).__name__}: {error}"
            retain()
            failure = RuntimeError("Fusion readiness preflight failed: " + str(error))
            failure.evidence = evidence
            raise failure from error

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
                row
                for row in state["elements"]
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
            elif not any(
                "SimulationIssues" in row.get("AXIdentifier", "") or row.get("AXTitle") == "Close"
                for row in state["elements"]
            ):
                # Entire panel absent, not a partial summary or an unrelated dialog.
                # Consume the same single retry budget before any bridge action.
                self.issues_refreshed = True
                receipt = {
                    "reason": "issues_panel_absent_after_three_reads",
                    "simulation_restarted": False,
                    "open_requested": False,
                }
                try:
                    binding = self.bridge.request("simulation_dialog", timeout=15)
                    receipt["binding"] = binding
                    actual = binding.get("result", {})
                    if (
                        binding.get("status") != "ok"
                        or actual.get("document") != self.native.document
                        or actual.get("active_command") != "IronMachineSimulation"
                    ):
                        raise RuntimeError("Cannot reopen Issues: exact active simulation changed")
                    receipt["open_requested"] = True
                    reply = self.bridge.request(
                        "simulation_command", {"command_id": "SimulationIssues"}
                    )
                    receipt["reply"] = reply
                    if reply.get("status") != "ok":
                        raise RuntimeError("Could not open missing Fusion Issues panel")
                    state = self.native.ui("inspect-ax")
                    receipt["panel_observed_after"] = any(
                        "SimulationIssues" in row.get("AXIdentifier", "")
                        for row in state["elements"]
                    )
                except Exception as error:
                    receipt["error"] = str(error)
                    error.evidence = {"issues_panel_recovery": receipt}
                    raise
                finally:
                    self.issues_recovery_evidence = receipt
                    self.directory.mkdir(parents=True, exist_ok=True)
                    (self.directory / "issues-panel-recovery.json").write_text(
                        json.dumps(receipt, indent=2)
                    )
        return {
            "issues_panel_recovery": self.issues_recovery_evidence,
            "native_state": state,
            "raw_text": json.dumps(state["elements"], sort_keys=True),
        }
