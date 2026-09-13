"""Astra-observed Fusion verification with native computer-use provenance.

Fusion computes the verification. Astra reads its UI; the controller retains raw
SDK tool observations. Provenance checks do not turn visual judgment into a
formal geometric proof. No imported generic JSON receipt is an approval source.
"""

from __future__ import annotations

import base64
import json
import math
import re
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .agents import _GEOMETRY_SCRIPT, _TARGET_BODY_HELPERS
from .cam_documents import open_snapshot
from .models import Artifact, Candidate, JobContext, VerificationResult, digest_json
from .simulation_coverage import MACHINE_COVERAGE_SOURCE
from .simulation_coverage import validate_simulation_coverage as validate_simulation_coverage

REQUIRED_COVERAGE = (
    "machine_collisions",
    "tool_holder_fixture_collisions",
    "rapid_stock_collisions",
    "axis_overtravel",
    "target_stock_comparison",
)
VERIFIER_VERSION = "fusion-astra-ui-v1"


class UIAstraClient(Protocol):
    def ask_with_evidence(self, prompt: str, *, workspace: Path, schema: dict) -> dict: ...


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_STRING = {"type": "string"}
_STRINGS = {"type": "array", "items": _STRING}
_OBSERVATION = _object(
    {
        "kind": {
            "type": "string",
            "enum": [
                "completion",
                "machine",
                "setup",
                "coverage",
                "issues",
                "process_issues",
                "target_comparison",
            ],
        },
        "source": {"type": "string", "enum": ["accessibility_text", "screenshot"]},
        "quote": _STRING,
        "cua_observation_index": {"type": "integer", "minimum": 0},
    }
)

# Controller-owned inspection; CAM/model settings may not change while the UI
# observer selects simulation display options. All values come from Fusion.
_BINDING_SCRIPT = _TARGET_BODY_HELPERS + MACHINE_COVERAGE_SOURCE + """import json
import math
import re
_product = app.activeDocument.products.itemByProductType("CAMProductType")
_cam = adsk.cam.CAM.cast(_product)
if not _cam:
    raise RuntimeError("No CAM product to bind verification")
_expected = adsk.cam.Machine.createFromFile(
    adsk.cam.LibraryLocations.LocalLibraryLocation, payload["machine_path"])
if not _expected:
    raise RuntimeError("Cannot load the configured machine definition")
def _parameters(collection):
    return {p.name: p.expression for p in collection}
def _entity(entity):
    return {"body_references": sorted(_body_key(body) for body in _selection_bodies(entity))}
_setups = []
for _setup in _cam.setups:
    _machine = _setup.machine
    _setups.append({"id": str(_setup.operationId), "name": _setup.name,
        "machine_model": _machine.model if _machine else None,
        "machine_matches": bool(_machine and _machine.equivalentTo(_expected)),
        "machine_simulation_model": bool(_machine and _machine.hasSimulationModel),
        "machine_coverage": _inspect_machine_coverage(_machine, adsk.cam),
        "fixture_enabled": _setup.fixtureEnabled,
        "fixtures": [_entity(x) for x in _setup.fixtures],
        "models": [_entity(x) for x in _setup.models],
        "stock_mode": int(_setup.stockMode),
        "stock_solids": ([_entity(x) for x in _setup.stockSolids]
            if _setup.stockMode == adsk.cam.SetupStockModes.SolidStock else []),
        "parameters": _parameters(_setup.parameters)})
_operations = []
for _base in _cam.allOperations:
    _op = adsk.cam.Operation.cast(_base)
    if _op:
        _operations.append({"id": str(_op.operationId), "name": _op.name,
            "has_toolpath": _op.hasToolpath, "has_error": _op.hasError,
            "parameters": _parameters(_op.parameters),
            "tool": json.loads(_op.tool.toJson()) if _op.tool else None})
result = {"setups": _setups, "operations": _operations,
          "expected_machine_coverage": _inspect_machine_coverage(_expected, adsk.cam),
          "body_references": _body_reference_handles()}
"""


def _save(path: Path, value: dict) -> Artifact:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return Artifact.from_path(path)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _observation_content(item: dict) -> list[dict]:
    """Exclude CUA documentation and permission messages from UI evidence."""
    observed = []
    for block in item.get("result", {}).get("content", []):
        if block.get("type") == "image" and block.get("data"):
            observed.append(block)
        elif block.get("type") == "text":
            text = block.get("text", "")
            if any(
                denial in text.casefold()
                for denial in (
                    "was not approved",
                    "permission denied",
                    "access denied",
                    "not authorized",
                )
            ):
                return []
            if text.lstrip().startswith(("## Computer Use", "## API", "# Documentation")):
                continue
            if re.search(r"(?m)^(?:Window:|App:|Application:|Focused window:|AX[A-Z])", text):
                observed.append(block)
    return observed


def _native_cua_items(capture: dict) -> list[dict]:
    """Only native SDK MCP records from the installed computer-use server count."""
    if capture.get("model") != "gpt-6-astra" or not capture.get("thread_id"):
        raise ValueError("Capture is missing Astra/thread provenance")
    result = []
    for item in capture.get("items", []):
        server = item.get("server", "")
        tool = item.get("tool", "")
        if (
            item.get("type") == "mcpToolCall"
            and item.get("status") == "completed"
            and server in {"cua_repl", "mcp__cua_repl"}
            and tool in {"js", "mcp__cua_repl__js"}
            and not item.get("error")
            and isinstance(item.get("result"), dict)
        ):
            result.append(item)
    if not result or not any(_observation_content(item) for item in result):
        raise ValueError("No native Fusion UI observations in SDK capture")
    return result


def _validate_observations(value: dict, items: list[dict]) -> list[dict]:
    bound = []
    required = {
        "completion",
        "machine",
        "setup",
        "coverage",
        "issues",
        "process_issues",
        "target_comparison",
    }
    for observation in value.get("observations", []):
        index = observation.get("cua_observation_index")
        if type(index) is not int or not 0 <= index < len(items):
            raise ValueError("Observation does not reference a captured native CUA response")
        item = items[index]
        content = _observation_content(item)
        quote = observation.get("quote", "").strip()
        if not quote:
            raise ValueError("Observation requires the observed text or visual description")
        if observation.get("source") == "accessibility_text":
            native = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
            if _normalized(quote) not in _normalized(native):
                raise ValueError("Quoted UI text is absent from the captured tool response")
        elif observation.get("source") == "screenshot":
            if not any(b.get("type") == "image" and b.get("data") for b in content):
                raise ValueError("Visual observation has no captured screenshot")
        else:
            raise ValueError("Unsupported observation evidence source")
        required.discard(observation.get("kind"))
        bound.append({**observation, "sdk_item_id": item["id"]})
    if required:
        raise ValueError("Missing native observations: " + ", ".join(sorted(required)))
    return bound


class FusionUIVerifier:
    def __init__(self, client: UIAstraClient, bridge, *, required_coverage=REQUIRED_COVERAGE):
        self.client, self.bridge = client, bridge
        self.required_coverage = tuple(required_coverage)
        if set(self.required_coverage) != set(REQUIRED_COVERAGE):
            raise ValueError("Required verification coverage cannot be weakened")

    @staticmethod
    def _schema() -> dict:
        return _object(
            {
                "verification_completed": {"type": "boolean"},
                "machine_observed": _STRING,
                "setups_verified": _STRINGS,
                "coverage": _object({name: {"type": "boolean"} for name in REQUIRED_COVERAGE}),
                "target_comparison_passed": {"type": "boolean"},
                "issues": _STRINGS,
                "process_issues": _STRINGS,
                "unresolved": _STRINGS,
                "observations": {"type": "array", "items": _OBSERVATION},
                "summary": _STRING,
            }
        )

    def _request(self, action: str, payload=None) -> dict:
        reply = self.bridge.request(action, payload)
        if reply.get("status") in {"failed", "error"} or reply.get("error"):
            raise RuntimeError(f"Fusion {action} failed")
        return reply

    def verify(self, candidate: Candidate, context: JobContext) -> VerificationResult:
        evidence: list[Artifact] = []
        coverage = (
            "Fusion internal CAM, native UI observed by Astra; machine/holder/fixture "
            "collisions, rapid stock collision, overtravel and visual stock comparison. "
            "Not posted NC verification or physical tolerance certification."
        )
        directory = Path(context.job_directory) / "workspace" / f"verify-{uuid.uuid4().hex}"
        directory.mkdir(parents=True, exist_ok=False)
        try:
            candidate.verify()
            context.inputs.verify()
            context.target.verify()
            f3d = candidate.artifacts.get("f3d")
            cloud = candidate.artifacts.get("fusion_document")
            if not (f3d or cloud):
                raise ValueError("Exact candidate document is required for UI verification")
            if context.inputs.machine.get("simulation_model_cloud") and cloud is None:
                raise ValueError("Linked-machine CAM requires its saved Fusion document reference")
            definition = context.inputs.machine.get("definition", {})
            machine = Artifact(definition["path"], definition["sha256"])
            machine.verify()
            opened = (
                open_snapshot(self._request, json.loads(Path(cloud.path).read_text()))
                if cloud else self._request("open_cad", {"path": f3d.path})
            )
            geometry = self._request("run_script", {"source": _GEOMETRY_SCRIPT})["result"]
            frozen = json.loads(Path(context.target.artifacts["geometry"].path).read_text())
            if digest_json(geometry) != digest_json(frozen):
                raise ValueError("Candidate geometry does not match the accepted CAD target")
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
                raise ValueError("Candidate setup lacks the configured machine/simulation model")
            if context.inputs.setup.get("fixture") and not all(
                s.get("fixture_enabled") and s.get("fixtures") for s in setups
            ):
                raise ValueError("Configured fixture is not enabled in every Fusion setup")
            operations = binding.get("operations", [])
            if not operations or any(
                not op.get("has_toolpath") or op.get("has_error") for op in operations
            ):
                raise ValueError("Candidate has missing toolpaths or operation errors")
            evidence.append(
                _save(
                    directory / "candidate-binding.json",
                    {
                        "candidate_digest": candidate.digest,
                        "input_digest": context.input_digest,
                        "f3d": asdict(f3d) if f3d else None,
                        "fusion_document": asdict(cloud) if cloud else None,
                        "opened_document": opened,
                        "geometry": geometry,
                        "binding": binding,
                    },
                )
            )
            expected_setups = [s["name"] for s in setups]
            prompt = (
                "Operate ONLY the Autodesk Fusion application using the native computer-use tool. "
                "The controller just opened the exact candidate document and checked its"
                " geometry, machine "
                "and CAM settings. Do not open another document, run scripts, "
                "regenerate or edit CAM, "
                "or change the machine/stock/fixture/tools. Select the specified setup(s), invoke "
                "Fusion's built-in Simulate with Machine, and wait for actual "
                "verification completion. "
                "Inspect Information > Issues and Process Issues; inspect collision/verification "
                "settings, machine model and each selected setup. Inspect final stock comparison "
                "against the target under the configured simulation resolution. A "
                "paused animation, "
                "an empty list before completion or absent settings is not a pass. Capture native "
                "screenshots/accessibility observations supporting each result. "
                "Unavailable coverage "
                "or ambiguous completion means unresolved, never invent a result. "
                "Return observations "
                "with cua_observation_index counting each completed native CUA tool"
                " response from 0 "
                "in this turn. For accessibility_text give an exact quote present "
                "in that response; "
                "for screenshot describe what is actually visible in that response image. Capture "
                "completion, machine, setup, coverage, issues, process_issues and "
                "target_comparison. "
                "These are Astra's visual judgments, not proof of physical "
                "manufacturing tolerances.\n"
                + json.dumps(
                    {
                        "expected_setups": expected_setups,
                        "expected_machine_models": [s["machine_model"] for s in setups],
                        "required_coverage": self.required_coverage,
                        "inputs": asdict(context.inputs),
                        "candidate_id": candidate.id,
                        "candidate_digest": candidate.digest,
                    }
                )
            )
            capture_result = self.client.ask_with_evidence(
                prompt, workspace=directory, schema=self._schema()
            )
            capture_file = Path(capture_result["items_file"]).resolve(strict=True)
            if not capture_file.is_relative_to(directory.resolve()):
                raise ValueError("SDK evidence must be captured in this verification workspace")
            capture = json.loads(capture_file.read_text())
            if capture_result.get("thread_id") != capture.get("thread_id"):
                raise ValueError("Captured SDK thread identity mismatch")
            evidence.append(Artifact.from_path(capture_file))
            native_items = _native_cua_items(capture)
            value = capture_result["value"]
            observations = _validate_observations(value, native_items)
            evidence.append(
                _save(
                    directory / "observed-verification.json",
                    {
                        "value": value,
                        "bound_observations": observations,
                        "thread_id": capture["thread_id"],
                    },
                )
            )
            for item_index, item in enumerate(native_items):
                for image_index, block in enumerate(item["result"].get("content", [])):
                    if block.get("type") != "image" or not block.get("data"):
                        continue
                    raw = base64.b64decode(block["data"], validate=True)
                    if len(raw) > 20_000_000:
                        raise ValueError("Captured screenshot exceeds evidence size limit")
                    extension = {"image/png": "png", "image/jpeg": "jpg"}.get(block.get("mimeType"))
                    if extension is None:
                        continue
                    path = directory / f"cua-{item_index}-{image_index}.{extension}"
                    path.write_bytes(raw)
                    evidence.append(Artifact.from_path(path))
            # UI automation is allowed to navigate simulation controls, never edit CAM.
            if "body_references" in binding:
                binding_payload["arguments"]["body_references"] = binding["body_references"]
            after_binding = self._request("run_script", binding_payload)["result"]
            after_geometry = self._request("run_script", {"source": _GEOMETRY_SCRIPT})["result"]
            if digest_json(after_binding) != digest_json(binding) or digest_json(
                after_geometry
            ) != digest_json(geometry):
                raise ValueError("Fusion candidate/setup changed during UI verification")
            candidate.verify()
            context.target.verify()
            if (
                value.get("verification_completed") is not True
                or value.get("process_issues")
                or value.get("unresolved")
            ):
                raise ValueError("UI verification is incomplete, unresolved or has process errors")
            if set(value.get("setups_verified", [])) != set(expected_setups):
                raise ValueError("UI evidence does not cover every configured setup")
            observed_machine = _normalized(value.get("machine_observed", ""))
            if not observed_machine or not all(
                _normalized(s["machine_model"]) in observed_machine for s in setups
            ):
                raise ValueError("Configured machine identity was not observed in Fusion")
            if not all(
                value.get("coverage", {}).get(name) is True for name in self.required_coverage
            ):
                raise ValueError("Fusion did not demonstrate all required verification coverage")
            issues = list(value.get("issues", []))
            if value.get("target_comparison_passed") is not True:
                issues.append("Final stock comparison does not match the accepted target")
            timing = self._request("machining_time", context.inputs.machine["time_estimation"])
            evidence.append(_save(directory / "machining-estimate.json", timing))
            seconds = timing.get("metrics", {}).get("machining_seconds")
            cost = self._cost(seconds, context.inputs.cost_assumptions)
            verdict = VerificationResult(
                "failed" if issues else "passed",
                True,
                context.input_digest,
                candidate.digest,
                VERIFIER_VERSION,
                tuple(evidence),
                coverage,
                tuple(issues),
                seconds,
                cost,
                {
                    "observations": observations,
                    "summary": value.get("summary"),
                    "metrics": timing.get("metrics"),
                    "cost_assumptions": context.inputs.cost_assumptions,
                },
            )
            verdict.validate(candidate, context)
            return verdict
        except Exception as error:
            return VerificationResult(
                "unknown",
                False,
                context.input_digest,
                candidate.digest,
                VERIFIER_VERSION,
                tuple(evidence),
                "Fusion UI verification incomplete; no manufacturing approval",
                (f"{type(error).__name__}: {error}",),
                feedback={"workspace": str(directory)},
            )

    @staticmethod
    def _cost(seconds: float | None, assumptions: dict) -> float | None:
        required = {
            "machine_rate_per_hour",
            "batch_size",
            "setup_seconds",
            "setup_rate_per_hour",
            "material_cost_per_part",
            "tool_wear_cost_per_part",
        }
        if seconds is None or not required <= assumptions.keys():
            return None
        if any(
            type(assumptions[key]) not in (int, float)
            or not math.isfinite(assumptions[key])
            or assumptions[key] < 0
            for key in required
        ):
            raise ValueError("Cost assumptions must be finite nonnegative numbers")
        if assumptions["batch_size"] <= 0:
            raise ValueError("Cost batch size must be positive")
        return (
            seconds / 3600 * assumptions["machine_rate_per_hour"]
            + assumptions["setup_seconds"]
            / 3600
            * assumptions["setup_rate_per_hour"]
            / assumptions["batch_size"]
            + assumptions["material_cost_per_part"]
            + assumptions["tool_wear_cost_per_part"]
        )
