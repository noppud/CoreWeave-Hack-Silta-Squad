"""Native-provenance verifier contract tests; all Fusion/UI captures are doubles."""

import json
from pathlib import Path

import pytest

from silta.cnc.agents import _GEOMETRY_SCRIPT
from silta.cnc.models import Artifact, Candidate, JobContext, JobInputs, Target
from silta.cnc.ui_verifier import _BINDING_SCRIPT, REQUIRED_COVERAGE, FusionUIVerifier

KINDS = [
    "completion",
    "machine",
    "setup",
    "coverage",
    "issues",
    "process_issues",
    "target_comparison",
]
NATIVE_TEXT = "Window: Autodesk Fusion\nVerification completed\nHAAS VF-2\nSetup 1\nNo issues"
GEOMETRY = {"method": "test", "bodies": [{"volume": 1}]}
BINDING = {
    "setups": [
        {
            "id": "1",
            "name": "Setup 1",
            "machine_model": "HAAS VF-2",
            "machine_matches": True,
            "machine_simulation_model": True,
            "fixture_enabled": True,
            "fixtures": [{"token": "fixture"}],
            "models": [{"token": "part"}],
        }
    ],
    "operations": [{"id": "op1", "has_toolpath": True, "has_error": False}],
}


class BridgeDouble:
    def __init__(self):
        self.binding = BINDING
        self.geometry = GEOMETRY
        self.actions = []

    def request(self, action, payload=None):
        self.actions.append(action)
        if action == "run_script":
            if payload["source"] == _GEOMETRY_SCRIPT:
                return {"result": self.geometry}
            assert payload["source"] == _BINDING_SCRIPT
            return {"result": self.binding}
        if action == "machining_time":
            return {"metrics": {"machining_seconds": 360}}
        return {"completed": True}


class UIDouble:
    def __init__(self, *, mutate_value=None, mutate_capture=None, during_ui=None):
        self.mutate_value = mutate_value
        self.mutate_capture = mutate_capture
        self.during_ui = during_ui
        self.calls = 0

    def ask_with_evidence(self, prompt, *, workspace, schema):
        self.calls += 1
        value = {
            "verification_completed": True,
            "machine_observed": "HAAS VF-2",
            "setups_verified": ["Setup 1"],
            "coverage": dict.fromkeys(REQUIRED_COVERAGE, True),
            "target_comparison_passed": True,
            "issues": [],
            "process_issues": [],
            "unresolved": [],
            "summary": "Explicit test double, not live simulation",
            "observations": [
                {
                    "kind": kind,
                    "source": "accessibility_text",
                    "quote": "Verification completed",
                    "cua_observation_index": 0,
                }
                for kind in KINDS
            ],
        }
        capture = {
            "model": "gpt-6-astra",
            "thread_id": "test-thread",
            "turn_id": "test-turn",
            "items": [
                {
                    "type": "mcpToolCall",
                    "id": "call-test",
                    "server": "cua_repl",
                    "tool": "js",
                    "status": "completed",
                    "arguments": {"code": "await app.getState();"},
                    "result": {"content": [{"type": "text", "text": NATIVE_TEXT}]},
                }
            ],
        }
        if self.mutate_value:
            self.mutate_value(value)
        if self.mutate_capture:
            self.mutate_capture(capture)
        if self.during_ui:
            self.during_ui()
        path = workspace / "sdk-items.json"
        path.write_text(json.dumps(capture))
        return {"value": value, "items_file": str(path), "thread_id": "test-thread", "evidence": []}


@pytest.fixture
def case(tmp_path):
    def artifact(name, content):
        path = tmp_path / name
        path.write_text(content)
        return Artifact.from_path(path)

    drawing = artifact("drawing.pdf", "test drawing")
    machine = artifact("machine.mch", "test machine")
    inputs = JobInputs(
        (drawing,),
        {
            "definition": {"path": machine.path, "sha256": machine.sha256},
            "time_estimation": {
                "feed_scale_percent": 100,
                "rapid_feed_cm_s": 20,
                "tool_change_seconds": 5,
            },
        },
        {"T1": {}},
        {"fixture": {"test": True}},
        {"linear_mm": 0.1},
        {
            "machine_rate_per_hour": 100,
            "batch_size": 2,
            "setup_seconds": 600,
            "setup_rate_per_hour": 60,
            "material_cost_per_part": 0,
            "tool_wear_cost_per_part": 0,
        },
    )
    target = Target(
        {
            "f3d": artifact("target.f3d", "test target"),
            "geometry": artifact("geometry.json", json.dumps(GEOMETRY)),
        },
        "test",
    )
    candidate = Candidate("test", target.digest, {"f3d": artifact("candidate.f3d", "test CAM")})
    return candidate, JobContext(inputs, target, inputs.digest, {}, str(tmp_path))


def test_completed_native_observed_pass_preserves_provenance_and_estimates(case):
    candidate, context = case
    result = FusionUIVerifier(UIDouble(), BridgeDouble()).verify(candidate, context)
    assert result.status == "passed"
    assert result.completed is True
    assert result.machining_seconds == 360 and result.estimated_cost == 15
    assert any(Path(a.path).name == "sdk-items.json" for a in result.evidence)
    assert result.feedback["observations"][0]["sdk_item_id"] == "call-test"
    assert "Not posted NC" in result.coverage
    for artifact in result.evidence:
        artifact.verify()


def test_observed_collision_is_failure_not_unknown_or_pass(case):
    client = UIDouble(
        mutate_value=lambda v: v.update(issues=["Holder hits fixture at operation 1"])
    )
    result = FusionUIVerifier(client, BridgeDouble()).verify(*case)
    assert result.status == "failed" and result.completed
    assert result.issues == ("Holder hits fixture at operation 1",)


@pytest.mark.parametrize(
    "defect",
    [
        "unfinished",
        "process_error",
        "coverage",
        "no_comparison",
        "wrong_setup",
        "wrong_machine",
        "unobserved_quote",
        "unresolved",
    ],
)
def test_incomplete_or_unbound_ui_claims_never_pass(case, defect):
    def mutation(value):
        if defect == "unfinished":
            value["verification_completed"] = False
        elif defect == "process_error":
            value["process_issues"] = ["simulation error"]
        elif defect == "coverage":
            value["coverage"]["machine_collisions"] = False
        elif defect == "no_comparison":
            value["observations"] = value["observations"][:-1]
        elif defect == "wrong_setup":
            value["setups_verified"] = ["another setup"]
        elif defect == "wrong_machine":
            value["machine_observed"] = "another machine"
        elif defect == "unobserved_quote":
            value["observations"][0]["quote"] = "invented UI text"
        else:
            value["unresolved"] = ["not visible"]

    result = FusionUIVerifier(UIDouble(mutate_value=mutation), BridgeDouble()).verify(*case)
    assert result.status == "unknown" and not result.completed


@pytest.mark.parametrize(
    "defect", ["no_tools", "docs_only", "denied", "failed_call", "other_model"]
)
def test_generic_receipt_docs_and_permission_denial_are_not_native_evidence(case, defect):
    def mutation(capture):
        if defect == "no_tools":
            capture["items"] = []
        elif defect == "other_model":
            capture["model"] = "not-astra"
        elif defect == "failed_call":
            capture["items"][0]["status"] = "failed"
        else:
            text = (
                "Computer Use was not approved to use Fusion"
                if defect == "denied"
                else "## Computer Use\nExample: Window: Fusion Verification completed"
            )
            capture["items"][0]["result"]["content"] = [{"type": "text", "text": text}]

    result = FusionUIVerifier(UIDouble(mutate_capture=mutation), BridgeDouble()).verify(*case)
    assert result.status == "unknown"


def test_cam_edit_during_observation_invalidates_result(case):
    bridge = BridgeDouble()

    def mutate():
        bridge.binding = {**BINDING, "changed": "CAM settings modified"}

    result = FusionUIVerifier(UIDouble(during_ui=mutate), bridge).verify(*case)
    assert result.status == "unknown"
    assert "changed during" in result.issues[0]


def test_missing_machine_or_fixture_blocks_before_ui(case):
    bridge = BridgeDouble()
    bridge.binding = {**BINDING, "setups": [{**BINDING["setups"][0], "fixture_enabled": False}]}
    client = UIDouble()
    result = FusionUIVerifier(client, bridge).verify(*case)
    assert result.status == "unknown" and client.calls == 0


def test_visual_comparison_mismatch_is_failed_simulation(case):
    client = UIDouble(mutate_value=lambda v: v.update(target_comparison_passed=False))
    result = FusionUIVerifier(client, BridgeDouble()).verify(*case)
    assert result.status == "failed" and result.completed
    assert "Final stock comparison" in result.issues[0]


def test_required_coverage_cannot_be_silently_removed():
    with pytest.raises(ValueError, match="cannot be weakened"):
        FusionUIVerifier(UIDouble(), BridgeDouble(), required_coverage=["machine_collisions"])


def test_binding_script_does_not_read_stock_solids_for_fixed_box_stock():
    from types import SimpleNamespace

    from test_simulation_coverage import _api_machine

    expected_machine, machine_api, _, _ = _api_machine()

    class FixedBoxSetup:
        name = "Fixed Box"
        operationId = 1
        stockMode = 0
        models = []
        fixtures = []
        fixtureEnabled = False
        parameters = []
        machine = SimpleNamespace(
            model="VF-2", equivalentTo=lambda _: True, hasSimulationModel=True,
            elements=expected_machine.elements,
        )

        @property
        def stockSolids(self):
            raise AssertionError("Fusion throws for non-SolidStock setups")

    cam_product = SimpleNamespace(setups=[FixedBoxSetup()], allOperations=[])
    design = SimpleNamespace(rootComponent=SimpleNamespace(
        bRepBodies=SimpleNamespace(count=0), allOccurrences=[]))
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(
            products=SimpleNamespace(itemByProductType=lambda kind:
                design if kind == "DesignProductType" else cam_product)
        )
    )
    adsk = SimpleNamespace(
        fusion=SimpleNamespace(Design=SimpleNamespace(cast=lambda value: value)),
        cam=SimpleNamespace(
            **vars(machine_api),
            CAM=SimpleNamespace(cast=lambda value: value),
            Machine=SimpleNamespace(createFromFile=lambda *args: expected_machine),
            LibraryLocations=SimpleNamespace(LocalLibraryLocation=0),
            SetupStockModes=SimpleNamespace(SolidStock=1),
        )
    )
    environment = {"app": app, "adsk": adsk, "payload": {"machine_path": "test.mch"}}
    exec(compile(_BINDING_SCRIPT, "<binding-test>", "exec"), environment)
    assert environment["result"]["setups"][0]["stock_solids"] == []
    assert environment["result"]["setups"][0]["stock_mode"] == 0


def test_binding_resolves_frozen_entity_handles_across_token_changes():
    from types import SimpleNamespace

    from test_simulation_coverage import _api_machine

    machine, machine_api, _, _ = _api_machine()

    class Collection(list):
        @property
        def count(self):
            return len(self)

        def item(self, index):
            return self[index]

    body = SimpleNamespace(entityToken="original", nativeObject=None, assemblyContext=None)
    root = SimpleNamespace(bRepBodies=Collection([body]), allOccurrences=[])
    handles = {"original": body}
    design = SimpleNamespace(
        rootComponent=root,
        findEntityByToken=lambda token: [handles[token]] if token in handles else [],
    )
    setup = SimpleNamespace(
        name="Setup", operationId=1, stockMode=0, models=[body], fixtures=[],
        fixtureEnabled=False, parameters=[],
        machine=SimpleNamespace(model="VF-2", equivalentTo=lambda _: True, hasSimulationModel=True,
                                elements=machine.elements),
    )
    cam = SimpleNamespace(setups=[setup], allOperations=[], designRootOccurrence=None)
    app = SimpleNamespace(activeDocument=SimpleNamespace(products=SimpleNamespace(
        itemByProductType=lambda kind: design if kind == "DesignProductType" else cam)))
    adsk = SimpleNamespace(
        fusion=SimpleNamespace(
            Design=SimpleNamespace(cast=lambda value: value),
            BRepBody=SimpleNamespace(cast=lambda value: value if value is body else None),
        ),
        cam=SimpleNamespace(
            **vars(machine_api),
            CAM=SimpleNamespace(cast=lambda value: value),
            Machine=SimpleNamespace(createFromFile=lambda *args: machine),
            LibraryLocations=SimpleNamespace(LocalLibraryLocation=0),
            SetupStockModes=SimpleNamespace(SolidStock=1),
        ),
    )

    def inspect(arguments):
        environment = {"app": app, "adsk": adsk, "payload": arguments}
        exec(compile(_BINDING_SCRIPT, "<binding-test>", "exec"), environment)
        return environment["result"]

    first = inspect({"machine_path": "test.mch"})
    assert first["setups"][0]["models"] == [{"body_references": [0]}]
    body.entityToken = "new-token-for-same-body"
    handles[body.entityToken] = body
    second = inspect({"machine_path": "test.mch", "body_references": first["body_references"]})
    assert second == first
    # A lost/deleted original entity must not be replaced by an unrelated body
    # occupying the same collection index during simulation observation.
    del handles["original"]
    with pytest.raises(RuntimeError, match="no longer resolves uniquely"):
        inspect({"machine_path": "test.mch", "body_references": first["body_references"]})


def test_cloud_candidate_verifies_exact_saved_version_without_local_reimport(case, tmp_path):
    from dataclasses import replace

    candidate, context = case
    reference = {"data_file_id": "lineage", "version_id": "exact-version",
                 "version_number": 1, "project_id": "project"}
    path = tmp_path / "fusion-document.json"
    path.write_text(json.dumps(reference))
    candidate = replace(candidate, artifacts={**candidate.artifacts,
        "fusion_document": Artifact.from_path(path)})
    inputs = replace(context.inputs, machine={**context.inputs.machine,
        "simulation_model_cloud": {"project_id": "project"}})
    context = replace(context, inputs=inputs, input_digest=inputs.digest)

    class CloudBridge(BridgeDouble):
        def request(self, action, payload=None):
            if action == "run_script" and "['open_version']" in payload["source"]:
                assert payload["arguments"]["reference"] == reference
                self.actions.append("open-version")
                return {"result": reference}
            return super().request(action, payload)

    bridge = CloudBridge()
    result = FusionUIVerifier(UIDouble(), bridge).verify(candidate, context)
    assert result.status == "passed"
    assert "open-version" in bridge.actions and "open_cad" not in bridge.actions
    binding = next(a for a in result.evidence if Path(a.path).name == "candidate-binding.json")
    assert json.loads(Path(binding.path).read_text())["opened_document"] == reference
