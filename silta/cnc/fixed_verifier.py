"""Fixed Fusion simulation commands and a direct, non-model UI reader."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .agents import _GEOMETRY_SCRIPT
from .cam_documents import open_snapshot
from .models import Artifact, VerificationResult, digest_json
from .simulation_report import parse_issues_ax, parse_issues_native
from .ui_verifier import (
    _BINDING_SCRIPT,
    FusionUIVerifier,
    _save,
    validate_simulation_coverage,
)

VERIFIER_VERSION = "fusion-fixed-ui-stock-v7-explicit-stock-regeneration"


class FixedFusionVerifier:
    def __init__(
        self, bridge, reader_factory=None, *, timeout=180, poll_seconds=1, stock_check=None
    ):
        if reader_factory is None:
            from .native_reader import NativeFusionReader

            def reader_factory(directory):
                return NativeFusionReader(bridge, directory)

        self.bridge, self.reader_factory = bridge, reader_factory
        self.timeout, self.poll_seconds = timeout, poll_seconds
        self.stock_check = stock_check or self._compare_stock

    def _compare_stock(self, document, context, directory):
        from .stock_comparison import compare_stock_to_step
        from .stock_export import StockExporter

        target_step = context.target.artifacts.get("step")
        tolerance = context.inputs.tolerances.get("linear_plus_minus_mm")
        if target_step is None or tolerance is None:
            return {
                "status": "unknown",
                "issues": [],
                "reason": "Target STEP and explicit linear_plus_minus_mm are required",
            }
        target_step.verify()
        exporter = StockExporter(document, directory / "stock-export", bridge=self.bridge)
        exported = exporter.export(directory / "finished-stock.stl")
        if exported["geometry"].get("coordinate_units") != "mm":
            raise ValueError("Fusion stock export did not confirm millimetre coordinates")
        result = compare_stock_to_step(
            Path(exported["path"]),
            Path(target_step.path),
            float(tolerance),
            directory / "stock-comparison",
        )
        result["export"] = exported
        return result

    def _request(self, action, payload=None):
        reply = self.bridge.request(action, payload)
        if reply.get("status") != "ok":
            raise RuntimeError(f"Fusion {action} failed: {reply.get('issues', [])}")
        return reply

    def verify(self, candidate, context):
        directory = Path(context.job_directory) / "workspace" / f"verify-{uuid.uuid4().hex}"
        directory.mkdir(parents=True, exist_ok=False)
        evidence = []
        report = None
        configured_coverage = None
        stock_comparison = None

        def save(name, value):
            evidence.append(_save(directory / name, value))

        try:
            candidate.verify()
            context.inputs.verify()
            context.target.verify()
            cloud = candidate.artifacts.get("fusion_document")
            f3d = candidate.artifacts.get("f3d")
            if not (cloud or f3d):
                raise ValueError("Exact candidate Fusion document is required")
            if context.inputs.machine.get("simulation_model_cloud") and not cloud:
                raise ValueError("Linked-machine candidate requires its saved cloud version")
            definition = context.inputs.machine["definition"]
            machine = Artifact(definition["path"], definition["sha256"])
            machine.verify()
            opened = (
                open_snapshot(self._request, json.loads(Path(cloud.path).read_text()))
                if cloud
                else self._request("open_cad", {"path": f3d.path})
            )
            geometry = self._request("run_script", {"source": _GEOMETRY_SCRIPT})["result"]
            frozen = json.loads(Path(context.target.artifacts["geometry"].path).read_text())
            if digest_json(geometry) != digest_json(frozen):
                raise ValueError("Candidate geometry differs from the accepted target")
            binding_payload = {
                "source": _BINDING_SCRIPT,
                "arguments": {"machine_path": machine.path},
            }
            binding = self._request("run_script", binding_payload)["result"]
            setups = binding.get("setups", [])
            if not setups or not all(
                s.get("machine_matches") and s.get("machine_simulation_model") and s.get("models")
                for s in setups
            ):
                raise ValueError("Candidate lacks its configured machine and full simulation model")
            if context.inputs.setup.get("fixture") and not all(
                s.get("fixture_enabled") and s.get("fixtures") for s in setups
            ):
                raise ValueError("Configured fixture is missing or disabled")
            operations = binding.get("operations", [])
            if not operations or any(
                not op.get("has_toolpath") or op.get("has_error") for op in operations
            ):
                raise ValueError("Candidate toolpaths are missing or have errors")
            save(
                "candidate-binding.json",
                {
                    "candidate_digest": candidate.digest,
                    "input_digest": context.input_digest,
                    "opened_document": opened,
                    "geometry": geometry,
                    "binding": binding,
                },
            )
            configured_coverage = validate_simulation_coverage(binding)
            save(
                "configured-coverage.json",
                {
                    "configured_coverage": configured_coverage,
                    "meaning": "Configured verification scope, not a geometric verdict",
                },
            )
            # Open the reader before launching so consent failure cannot leave a
            # freshly launched simulation with no observer. No model turn runs.
            with self.reader_factory(directory) as reader:
                if getattr(reader, "open_evidence", None):
                    save("reader-open.json", reader.open_evidence)
                if hasattr(reader, "bring_to_front"):
                    save("fusion-window-focus.json", reader.bring_to_front())
                launch = self._request(
                    "simulation_command",
                    {"command_id": "IronMachineSimulation", "setup_ids": [s["id"] for s in setups]},
                )
                save("simulation-launch.json", launch)
                save(
                    "issues-open.json",
                    self._request("simulation_command", {"command_id": "SimulationIssues"}),
                )
                deadline = time.monotonic() + self.timeout
                last_error = "No Issues summary observed"
                index = 0
                last_text = None
                issues_recovery_saved = False
                while time.monotonic() < deadline:
                    observation = reader.read()
                    if observation.get("issues_panel_recovery") and not issues_recovery_saved:
                        save("issues-panel-recovery.json", observation["issues_panel_recovery"])
                        issues_recovery_saved = True
                    if observation["raw_text"] != last_text:
                        save(f"native-read-{index:04d}.json", observation)
                        index += 1
                        last_text = observation["raw_text"]
                    try:
                        report = (
                            parse_issues_native(observation["native_state"])
                            if "native_state" in observation
                            else parse_issues_ax(observation["raw_text"])
                        )
                    except ValueError as error:
                        last_error = str(error)
                    else:
                        if report.completed:
                            break
                    time.sleep(self.poll_seconds)
                else:
                    raise TimeoutError("Verification completion was not observed: " + last_error)
            save("issues-report.json", asdict(report))
            dialog = self._request("simulation_dialog")
            save("simulation-dialog.json", dialog)
            if not report.errors and not report.process_errors and not report.warnings:
                stock_comparison = self.stock_check(
                    dialog.get("result", {}).get("document"), context, directory
                )
                save("stock-comparison-result.json", stock_comparison)
                for folder in (directory / "stock-export", directory / "stock-comparison"):
                    if folder.exists():
                        for path in sorted(folder.iterdir()):
                            if path.suffix in {".json", ".png", ".stl"}:
                                evidence.append(Artifact.from_path(path))
                stock_path = directory / "finished-stock.stl"
                if stock_path.exists():
                    evidence.append(Artifact.from_path(stock_path))
                if stock_comparison.get("status") in {"passed", "failed"}:
                    configured_coverage = {**configured_coverage, "target_stock_comparison": True}
            save(
                "simulation-stop.json",
                self._request("simulation_command", {"command_id": "SimulationStop"}),
            )
            if "body_references" in binding:
                binding_payload["arguments"]["body_references"] = binding["body_references"]
            after = self._request("run_script", binding_payload)["result"]
            after_geometry = self._request("run_script", {"source": _GEOMETRY_SCRIPT})["result"]
            save("candidate-binding-after.json", {"binding": after, "geometry": after_geometry})
            if digest_json(after) != digest_json(binding) or digest_json(
                after_geometry
            ) != digest_json(geometry):
                raise ValueError("Candidate or setup changed during verification")
            candidate.verify()
            context.inputs.verify()
            context.target.verify()
            if report.process_errors:
                raise ValueError(f"Fusion reported {report.process_errors} process errors")
            timing = self._request("machining_time", context.inputs.machine["time_estimation"])
            save("machining-estimate.json", timing)
            seconds = timing.get("metrics", {}).get("machining_seconds")
            feedback = {
                "summary": asdict(report),
                "metrics": timing.get("metrics", {}),
                "cost_assumptions": context.inputs.cost_assumptions,
                "details_may_be_partial": True,
                "target_stock_comparison": stock_comparison,
                "configured_coverage": configured_coverage,
                "workspace": str(directory),
            }
            if report.errors:
                # One completed, evidenced collision is enough to reject a CAM
                # candidate. Approval still requires complete coverage/comparison.
                verdict = VerificationResult(
                    "failed",
                    True,
                    context.input_digest,
                    candidate.digest,
                    VERIFIER_VERSION,
                    tuple(evidence),
                    "Completed Fusion internal CAM machine verification; observed Issues. "
                    "No stock-comparison or posted-NC approval.",
                    (
                        f"Fusion verification: {report.errors} errors",
                        *dict.fromkeys(report.observed_details),
                    ),
                    seconds,
                    FusionUIVerifier._cost(seconds, context.inputs.cost_assumptions),
                    feedback,
                )
                verdict.validate(candidate, context)
                return verdict
            stock_status = (stock_comparison or {}).get("status", "unknown")
            if stock_status in {"passed", "failed"} and not report.warnings:
                stock_issues = tuple(
                    f"{issue['type']}: at least {issue['minimum_deviation_mm']:.4f} mm "
                    f"at {issue['point_mm']}"
                    for issue in stock_comparison.get("issues", [])
                )
                if stock_status == "failed" and not stock_issues:
                    raise ValueError("Stock comparison failure requires localized evidence")
                verdict = VerificationResult(
                    stock_status,
                    True,
                    context.input_digest,
                    candidate.digest,
                    VERIFIER_VERSION,
                    tuple(evidence),
                    "Fusion internal CAM machine verification and bounded stock-to-target "
                    "surface comparison; no posted-NC or cutting-physics certification",
                    stock_issues,
                    seconds,
                    FusionUIVerifier._cost(seconds, context.inputs.cost_assumptions),
                    feedback,
                )
                verdict.validate(candidate, context)
                return verdict
            return VerificationResult(
                "unknown",
                False,
                context.input_digest,
                candidate.digest,
                VERIFIER_VERSION,
                tuple(evidence),
                "Fusion verification completed; numerical stock conformity unresolved",
                (
                    (stock_comparison or {}).get("reason", "Stock comparison is unresolved"),
                    *(
                        [f"Fusion verification: {report.warnings} warnings"]
                        if report.warnings
                        else []
                    ),
                ),
                feedback=feedback,
            )
        except Exception as error:
            if getattr(error, "evidence", None):
                save("collection-error.json", error.evidence)
            return VerificationResult(
                "unknown",
                False,
                context.input_digest,
                candidate.digest,
                VERIFIER_VERSION,
                tuple(evidence),
                "Fusion collection incomplete; no manufacturing approval",
                (f"{type(error).__name__}: {error}",),
                feedback={
                    "workspace": str(directory),
                    "summary": asdict(report) if report else None,
                    "target_stock_comparison": stock_comparison,
                    "configured_coverage": configured_coverage,
                },
            )
