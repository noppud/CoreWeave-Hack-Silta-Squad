"""Adapter contracts with explicit model/Fusion doubles; no live CAM assertions."""

import ast
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from silta.cnc.agents import (
    _CAM_RESOURCE_PRELUDE,
    _CAM_SCOPE_SCRIPT,
    _CUTTING_PARAMETERS_SCRIPT,
    _FINALIZE_CAM_SCRIPT,
    _FRESH_CAD_SCRIPT,
    _GEOMETRY_SCRIPT,
    _PREPARE_CAM_SCRIPT,
    _REGISTER_TARGET_SCRIPT,
    _TARGET_STEP_SCRIPT,
    AstraCheckLearner,
    AstraMainAgent,
    AstraSupervisor,
)
from silta.cnc.evaluation import VersionStore
from silta.cnc.models import Artifact, Candidate, JobContext, JobInputs, VerificationResult


class ClientDouble:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def ask(self, prompt, *, workspace, schema):
        self.calls.append((prompt, workspace, schema))
        return next(self.replies)


GEOMETRY = {"method": "test-fingerprint", "bodies": [{"volume_cm3": 12}]}
CAD_REPLY = {"source": "result = {'dimensions': 'test'}", "explanation": "test", "unresolved": []}
CAM_REPLY = {
    "source": "result = {'operation_names': ['test pocket']}",
    "explanation": "test", "unresolved": [],
}
PREPARED_SETUP = {"setup_index": 0, "tools": [{"number": 1, "description": "approved test tool"}]}


def machining_source(source):
    """Read the literal agent program from the trusted resource wrapper in doubles."""
    if not source.startswith(_CAM_RESOURCE_PRELUDE):
        return source
    wrapper = ast.parse(source.removeprefix(_CAM_RESOURCE_PRELUDE))
    compile_call = wrapper.body[0].value.args[0]
    assert isinstance(compile_call, ast.Call) and compile_call.func.id == "compile"
    assert ast.literal_eval(compile_call.args[1]) == "<silta-machining-plan>"
    return ast.literal_eval(compile_call.args[0])
ACCEPT_REPLY = {
    "accepted": True,
    "unresolved": [],
    "explanation": "test comparison",
    "comparisons": [
        {
            "drawing_reference": "drawing page 1",
            "requirement": "test width",
            "observed": "test width",
            "matches": True,
        }
    ],
}


class BridgeDouble:
    def __init__(self):
        self.actions = []
        self.script_calls = []
        self.geometry = GEOMETRY.copy()
        self.change_geometry = False
        self.omit_nc = False
        self.generation_polls = 0
        self.inspection = {"operations": [{"id": "1", "has_toolpath": True}], "nc_programs": [{}]}

    def request(self, action, payload=None, **kwargs):
        payload = payload or {}
        self.actions.append(action)
        if action == "run_script":
            source = payload["source"]
            self.script_calls.append(json.loads(json.dumps(payload)))
            if source == _PREPARE_CAM_SCRIPT:
                return {"result": PREPARED_SETUP.copy()}
            if source == _GEOMETRY_SCRIPT:
                return {"result": self.geometry.copy()}
            if source == _REGISTER_TARGET_SCRIPT:
                return {"result": {"target_body_ids": ["test-part-body"]}}
            if source == _CAM_SCOPE_SCRIPT:
                return {"result": {"scope": "accepted_target_only", "setups": []}}
            if source == _TARGET_STEP_SCRIPT:
                Path(payload["arguments"]["path"]).write_text("test part-only STEP")
                return {"result": {"scope": "accepted_target_only"}}
            if source == _FINALIZE_CAM_SCRIPT:
                post = payload["arguments"]["inputs"]["setup"]["postprocessor"]
                return {
                    "result": {
                        **({} if self.omit_nc else {"nc_program_index": 0}),
                        "vendor": "test",
                        "description": "test",
                        "sha256": hashlib.sha256(Path(post["path"]).read_bytes()).hexdigest(),
                    }
                }
            if source == _CUTTING_PARAMETERS_SCRIPT:
                return {
                    "result": {
                        "operations": [
                            {
                                "id": "1",
                                "has_error": False,
                                "cutting_parameters": {"spindle_rpm": 2000, "feed_mm_min": 100},
                            }
                        ]
                    }
                }
            if "saveAsImageFile" in source:
                # Test double extracts literal output path; it never executes generated source.
                tree = ast.parse(source)
                path = Path(next(
                    node.args[0].value for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "saveAsImageFile"
                ))
                path.write_bytes(b"test preview placeholder")
                return {"result": {"saved": True}}
            if source.startswith(_CAM_RESOURCE_PRELUDE):
                if self.change_geometry:
                    self.geometry = {"method": "test-fingerprint", "bodies": [{"volume_cm3": 13}]}
                return {"result": {"operation_names": ["test pocket"]}}
            return {"result": {"created": True}}
        if action in {"export_step", "export_f3d"}:
            Path(payload["path"]).write_text("test CAD artifact")
            return {"result": {"path": payload["path"]}}
        if action == "inspect":
            return {"result": json.loads(json.dumps(self.inspection))}
        if action == "generation_status":
            self.generation_polls += 1
            return {"completed": True}
        if action == "machining_time":
            return {"metrics": {"machining_seconds": 123}, "result": {"assumptions": payload}}
        if action == "postprocess":
            directory = Path(payload["output_directory"])
            directory.mkdir()
            (directory / "part.nc").write_text("test NC placeholder")
            return {"completed": False}
        if action == "collect_outputs":
            return {
                "completed": True,
                "result": {"files": [{"path": str(Path(payload["output_directory"]) / "part.nc")}]},
            }
        return {"completed": True}


@pytest.fixture
def inputs(tmp_path):
    drawing = tmp_path / "drawing.pdf"
    drawing.write_text("test drawing")
    post = tmp_path / "test.cps"
    post.write_text("test postprocessor content")
    return JobInputs(
        (Artifact.from_path(drawing),),
        {
            "axes": 3,
            "time_estimation": {
                "feed_scale_percent": 100,
                "rapid_feed_cm_s": 20,
                "tool_change_seconds": 5,
            },
        },
        {"tools": ["test tool"]},
        {
            "postprocessor": {
                "path": str(post),
                "sha256": hashlib.sha256(post.read_bytes()).hexdigest(),
            }
        },
        {"linear_mm": 0.1},
    )


def prepare(tmp_path, inputs, more_replies=()):
    bridge = BridgeDouble()
    client = ClientDouble([CAD_REPLY, ACCEPT_REPLY, *more_replies])
    main = AstraMainAgent(client, bridge)
    workspace = tmp_path / "workspace"
    target = main.establish_target(inputs, str(workspace))
    return main, bridge, client, JobContext(inputs, target, inputs.digest, {}, str(tmp_path))


def test_actual_source_export_and_post_sequence_produces_unverified_candidate(tmp_path, inputs):
    main, bridge, client, context = prepare(tmp_path, inputs, [CAM_REPLY])
    candidate = main.propose(context, None, {}, "group operations", 1)
    candidate.verify()
    assert {"f3d", "analysis", "nc-0"} <= candidate.artifacts.keys()
    analysis = json.loads(Path(candidate.artifacts["analysis"].path).read_text())
    assert analysis["verification_status"] == "not_run"
    assert analysis["timing"]["metrics"]["machining_seconds"] == 123
    assert analysis["inspection"]["operations"][0]["cutting_parameters"]["spindle_rpm"] == 2000
    assert "simulation" not in bridge.actions
    assert bridge.actions.index("generate_toolpaths") < bridge.actions.index("postprocess")
    assert "group operations" in client.calls[-1][0]
    assert all(
        name in client.calls[-1][0] for name in ("`cam`", "`setup`", "`tools`", "`target_bodies`")
    )
    assert json.dumps(PREPARED_SETUP) in client.calls[-1][0]
    machining = next(
        call for call in bridge.script_calls if call["source"].startswith(_CAM_RESOURCE_PRELUDE)
    )
    assert machining_source(machining["source"]) == CAM_REPLY["source"]
    assert machining["arguments"] == {
        "inputs": json.loads(json.dumps(asdict(context.inputs))), "setup_index": 0,
    }
    scripts = [call["source"] for call in bridge.script_calls]
    assert scripts.index(_PREPARE_CAM_SCRIPT) < scripts.index(machining["source"])
    assert scripts.index(machining["source"]) < scripts.index(_FINALIZE_CAM_SCRIPT)
    assert "nc_program_index" not in CAM_REPLY["source"]


def test_ambiguous_drawing_never_executes_fusion(tmp_path, inputs):
    bridge = BridgeDouble()
    client = ClientDouble([dict(CAD_REPLY, unresolved=["missing depth"])])
    with pytest.raises(ValueError, match="missing depth"):
        AstraMainAgent(client, bridge).establish_target(inputs, str(tmp_path))
    assert not bridge.actions


def test_resolved_manual_postprocessing_note_keeps_export_evidence_in_review(tmp_path, inputs):
    scoped_inputs = replace(inputs, setup={
        **inputs.setup,
        "material": "AL6061",
        "stock": {"precondition": "Deburring remains a manual final step; no edge-break size."},
    })
    note = "Manual deburring is the supplied final step; no edge-break geometry added."
    client = ClientDouble([dict(CAD_REPLY, explanation=note), ACCEPT_REPLY])
    bridge = BridgeDouble()
    target = AstraMainAgent(client, bridge).establish_target(scoped_inputs, str(tmp_path))
    target.verify()
    # Review must see the fixed scope and actual exported files, not only the
    # generator's claimed dimensions/material. These doubles do not prove CAD quality.
    review, _ = json.JSONDecoder().raw_decode(client.calls[1][0].split("\n", 1)[1])
    assert review["inputs"]["setup"] == scoped_inputs.setup
    assert review["exported_artifacts"] == {
        kind: target.artifacts[kind].path for kind in ("f3d", "step")
    }
    assert all(Path(path).is_file() for path in review["exported_artifacts"].values())
    assert json.loads((tmp_path / "cad-source.json").read_text())["explanation"] == note


def test_manual_scope_does_not_bypass_reported_missing_requirement(tmp_path, inputs):
    scoped_inputs = replace(inputs, setup={
        **inputs.setup, "stock": {"precondition": "Deburring remains a manual final step."},
    })
    bridge = BridgeDouble()
    client = ClientDouble([dict(
        CAD_REPLY,
        explanation="Deburring is manual.",
        unresolved=["Required counterbore depth is missing from the drawing."],
    )])
    with pytest.raises(ValueError, match="counterbore depth"):
        AstraMainAgent(client, bridge).establish_target(scoped_inputs, str(tmp_path))
    assert not bridge.actions
    assert len(client.calls) == 1


def test_failed_cad_assessment_does_not_accept_target(tmp_path, inputs):
    rejected = dict(ACCEPT_REPLY, accepted=False)
    client = ClientDouble([CAD_REPLY, rejected] * 3)
    with pytest.raises(ValueError, match="acceptance unresolved"):
        AstraMainAgent(client, BridgeDouble()).establish_target(inputs, str(tmp_path))
    assert len(client.calls) == 6
    assert (tmp_path / "target-assessment.json").is_file()
    assert (tmp_path / "target-repair-03" / "target-assessment.json").is_file()


def test_rejected_material_is_repaired_before_target_acceptance(tmp_path, inputs):
    rejected = dict(
        ACCEPT_REPLY, accepted=False, explanation="STEP material is Steel; drawing requires AL6061",
        unresolved=["material conflict"],
    )
    corrected = dict(CAD_REPLY, source="result = {'material': 'AL6061'}")
    client = ClientDouble([CAD_REPLY, rejected, corrected, ACCEPT_REPLY])
    target = AstraMainAgent(client, BridgeDouble()).establish_target(inputs, str(tmp_path))
    target.verify()
    assert "drawing requires AL6061" in client.calls[2][0]
    assert "target-repair-02" in target.artifacts["step"].path
    assert json.loads((tmp_path / "target-assessment.json").read_text())["accepted"] is False
    assert json.loads(Path(target.artifacts["assessment"].path).read_text())["accepted"] is True


def test_geometry_mutation_stops_before_generation(tmp_path, inputs):
    main, bridge, _, context = prepare(tmp_path, inputs, [CAM_REPLY])
    bridge.change_geometry = True
    with pytest.raises(ValueError, match="changed accepted target"):
        main.propose(context, None, {}, "", 1)
    assert "generate_toolpaths" not in bridge.actions
    assert not any(call["source"] == _FINALIZE_CAM_SCRIPT for call in bridge.script_calls)


def test_finalizer_missing_nc_program_never_generates_or_posts(tmp_path, inputs):
    main, bridge, _, context = prepare(tmp_path, inputs, [CAM_REPLY])
    bridge.omit_nc = True
    with pytest.raises(ValueError, match="Deterministic NC program creation failed"):
        main.propose(context, None, {}, "", 1)
    assert "postprocess" not in bridge.actions
    assert "generate_toolpaths" not in bridge.actions


def test_changed_postprocessor_fails_before_posting(tmp_path, inputs):
    main, bridge, _, context = prepare(tmp_path, inputs, [CAM_REPLY])
    Path(inputs.setup["postprocessor"]["path"]).write_text("different")
    with pytest.raises(ValueError, match="Actual NC postprocessor differs"):
        main.propose(context, None, {}, "", 1)
    assert "postprocess" not in bridge.actions


def test_generation_timeout_never_reissues_generation(tmp_path, inputs):
    main, bridge, _, context = prepare(tmp_path, inputs, [CAM_REPLY])
    original = bridge.request

    def request(action, payload=None, **kwargs):
        if action == "generation_status":
            return {"completed": False}
        return original(action, payload, **kwargs)

    bridge.request = request
    main.operation_timeout = 0
    with pytest.raises(TimeoutError):
        main.propose(context, None, {}, "", 1)
    assert bridge.actions.count("generate_toolpaths") == 1
    assert "postprocess" not in bridge.actions


def role_context(tmp_path, inputs, kind, content):
    store = VersionStore(tmp_path / "versions")
    ref = store.put(kind, content)
    store.initialize(kind, ref)
    _, _, _, context = prepare(tmp_path, inputs)
    context = replace(context, versions={kind: ref})
    nc = tmp_path / "test.nc"
    nc.write_text("test")
    candidate = Candidate.from_paths("case", context.target.digest, {"nc": str(nc)})
    evidence = tmp_path / "test-evidence.json"
    evidence.write_text("test verdict")
    verdict = VerificationResult(
        "passed",
        True,
        context.input_digest,
        candidate.digest,
        "test",
        (Artifact.from_path(evidence),),
        "test",
        (),
        100,
    )
    return store, context, candidate, verdict


def test_supervisor_pins_prompt_and_only_registers_proposed_replacement(tmp_path, inputs):
    store, context, candidate, verdict = role_context(
        tmp_path, inputs, "supervisor_prompt", "baseline"
    )
    client = ClientDouble(
        [
            {
                "action": "stop",
                "instructions": "",
                "reusable_proposals": [
                    {"kind": "supervisor_prompt", "content": "better", "reason": "evidence"}
                ],
            }
        ]
    )
    decision = AstraSupervisor(client, version_store=store).decide(context, candidate, verdict, [])
    assert client.calls[0][0].startswith("baseline")
    assert decision.reusable_proposals
    assert store.active()["supervisor_prompt"] == context.versions["supervisor_prompt"]
    assert store.get(decision.reusable_proposals[0].proposed_version)["content"] == "better"


def test_supervisor_refuses_unknown_without_calling_model(tmp_path, inputs):
    store, context, candidate, verdict = role_context(
        tmp_path, inputs, "supervisor_prompt", "baseline"
    )
    client = ClientDouble([])
    with pytest.raises(ValueError, match="requires a verified pass"):
        AstraSupervisor(client, version_store=store).decide(
            context, candidate, replace(verdict, status="unknown"), []
        )
    assert not client.calls


def test_check_proposal_is_stored_without_executing_or_promoting(tmp_path, inputs):
    store, context, candidate, verdict = role_context(tmp_path, inputs, "checks", "baseline")
    sentinel = tmp_path / "should-not-exist"
    code = f"open({str(sentinel)!r}, 'w').write('must not execute')\ndef check(data): return {{}}"
    client = ClientDouble([{"propose": True, "source": code, "reason": "test"}])
    (proposal,) = AstraCheckLearner(client, version_store=store).propose_checks(
        context, candidate, replace(verdict, status="failed", issues=("collision",))
    )
    assert not sentinel.exists()
    assert store.get(proposal.proposed_version)["content"] == code
    assert store.active()["checks"] == proposal.base_version


def test_missing_pinned_prompt_never_falls_back(tmp_path, inputs):
    main, _, _, context = prepare(tmp_path, inputs, [CAM_REPLY])
    with pytest.raises(ValueError, match="requires its version store"):
        main.propose(replace(context, versions={"main_prompt": "missing"}), None, {}, "", 1)


class FakeCollection(list):
    @property
    def count(self):
        return len(self)

    def item(self, index):
        return self[index]

    def add(self, value):
        self.append(value)
        return value


class FakeAttributes:
    def __init__(self):
        self.items = {}

    def add(self, group, key, value):
        from types import SimpleNamespace

        attribute = SimpleNamespace(value=value)
        self.items[group, key] = attribute
        return attribute

    def itemByName(self, group, key):
        return self.items.get((group, key))


class FakeBody:
    def __init__(self, token, volume=1):
        from types import SimpleNamespace

        self.entityToken, self.volume = token, volume
        self.nativeObject = self.assemblyContext = None
        self.attributes = FakeAttributes()
        self.isSolid = True
        self.area = 6
        self.faces, self.edges, self.vertices = [FakeCollection([0])] * 3
        points = [SimpleNamespace(asArray=lambda v=v: v) for v in ([0, 0, 0], [1, 0, 0], [0, 1, 0])]
        mesh = SimpleNamespace(nodeCount=3, nodeCoordinates=points, nodeIndices=[0, 1, 2])
        self.meshManager = SimpleNamespace(
            createMeshCalculator=lambda: SimpleNamespace(calculate=lambda: mesh)
        )
        self.boundingBox = SimpleNamespace(minPoint=points[0], maxPoint=points[1])


def script_environment(bodies, setups=()):
    from types import SimpleNamespace

    root = SimpleNamespace(bRepBodies=FakeCollection(bodies), allOccurrences=FakeCollection())
    def resolve(token):
        entities = list(root.bRepBodies) + list(root.allOccurrences)
        for occurrence in root.allOccurrences:
            entities.extend(occurrence.bRepBodies)
        native_entities = [entity.nativeObject or entity for entity in entities]
        return [entity for i, entity in enumerate(native_entities)
                if entity.entityToken == token and entity not in native_entities[:i]]

    design = SimpleNamespace(rootComponent=root, findEntityByToken=resolve)
    cam = SimpleNamespace(setups=FakeCollection(setups), designRootOccurrence=None)
    products = SimpleNamespace(
        itemByProductType=lambda kind: design if kind == "DesignProductType" else cam
    )
    app = SimpleNamespace(activeDocument=SimpleNamespace(products=products))
    adsk = SimpleNamespace(
        fusion=SimpleNamespace(
            Design=SimpleNamespace(cast=lambda item: item),
            BRepBody=SimpleNamespace(
                cast=lambda item: item if isinstance(item, FakeBody) else None
            ),
            Occurrence=SimpleNamespace(cast=lambda item: None),
        ),
        cam=SimpleNamespace(
            CAM=SimpleNamespace(cast=lambda item: item),
            SetupStockModes=SimpleNamespace(SolidStock=1),
        ),
    )
    return {"app": app, "adsk": adsk, "payload": {}, "result": None}, root


def execute_script(source, environment):
    exec(compile(source, "<trusted-script-test>", "exec"), environment)
    return environment["result"]


def test_fixture_addition_and_fixture_shape_change_do_not_change_part_fingerprint():
    part = FakeBody("part")
    environment, root = script_environment([part])
    registration = execute_script(_REGISTER_TARGET_SCRIPT, environment)
    assert len(registration["target_body_ids"]) == 1
    before = execute_script(_GEOMETRY_SCRIPT, environment)
    fixture = FakeBody("vise", 100)
    root.bRepBodies.append(fixture)
    assert execute_script(_GEOMETRY_SCRIPT, environment) == before
    fixture.volume = 200
    assert execute_script(_GEOMETRY_SCRIPT, environment) == before
    part.volume = 2
    assert execute_script(_GEOMETRY_SCRIPT, environment) != before


def test_lost_or_duplicated_body_registration_cannot_hide_target_change():
    part = FakeBody("part")
    environment, root = script_environment([part])
    execute_script(_REGISTER_TARGET_SCRIPT, environment)
    copy = FakeBody("copy")
    copy.attributes = part.attributes
    root.bRepBodies.append(copy)
    with pytest.raises(RuntimeError, match="missing or duplicated"):
        execute_script(_GEOMETRY_SCRIPT, environment)
    root.bRepBodies.remove(copy)
    part.attributes.items.clear()
    with pytest.raises(RuntimeError, match="missing or duplicated"):
        execute_script(_GEOMETRY_SCRIPT, environment)


def test_cam_scope_separates_fixture_and_target_and_rejects_rogue_models():
    from types import SimpleNamespace

    part, fixture, stock = FakeBody("part"), FakeBody("vise"), FakeBody("stock")
    setup = SimpleNamespace(
        name="Setup",
        stockMode=1,
        models=FakeCollection([part]),
        fixtures=FakeCollection([fixture]),
        stockSolids=FakeCollection([stock]),
    )
    environment, root = script_environment([part], [setup])
    execute_script(_REGISTER_TARGET_SCRIPT, environment)
    root.bRepBodies.extend([fixture, stock])
    result = execute_script(_CAM_SCOPE_SCRIPT, environment)
    assert result["scope"] == "accepted_target_only"
    assert result["setups"][0]["fixture_body_count"] == 1
    assert result["setups"][0]["stock_body_count"] == 1
    setup.models.append(fixture)
    with pytest.raises(RuntimeError, match="includes non-target"):
        execute_script(_CAM_SCOPE_SCRIPT, environment)
    setup.models.remove(fixture)
    setup.fixtures.clear()
    with pytest.raises(RuntimeError, match="Every non-target"):
        execute_script(_CAM_SCOPE_SCRIPT, environment)


@pytest.mark.parametrize("material_names", [("Aluminum 6061",), ("Aluminum 6061", "Brass")])
def test_step_export_preserves_component_material_and_only_target_geometry(
    tmp_path, material_names
):
    from types import SimpleNamespace

    parts = [FakeBody(f"part-{index}") for index in range(len(material_names))]
    for part, name in zip(parts, material_names, strict=True):
        part.material = SimpleNamespace(name=name)
    fixture = FakeBody("vise")
    environment, root = script_environment(parts.copy())
    execute_script(_REGISTER_TARGET_SCRIPT, environment)
    root.bRepBodies.append(fixture)
    restored, closed, exported, child_components, transforms = [], [], [], [], []
    original = environment["app"].activeDocument
    original.activate = lambda: restored.append(True)
    source_material = SimpleNamespace(name="Source root default")
    root.material = source_material
    export_root = SimpleNamespace(bRepBodies=FakeCollection(), material="Default Steel")
    identity = object()

    def add_component(transform):
        transforms.append(transform)
        component = SimpleNamespace(bRepBodies=FakeCollection(), material="Default Steel")
        child_components.append(component)
        return SimpleNamespace(component=component)

    export_root.occurrences = SimpleNamespace(addNewComponent=add_component)
    copied_materials = {}

    def copy_material(original, name):
        copied_materials[name] = SimpleNamespace(name=name)
        return copied_materials[name]

    def export(options):
        # Real failure: STEP consumes owner material, even with a body override.
        # Inspect at export time, so assigning components after export cannot pass.
        owners = child_components if len(parts) > 1 else [export_root]
        for owner, name in zip(owners, material_names, strict=True):
            assert owner.material is copied_materials[name]
            assert owner.bRepBodies[0].material is owner.material
        exported.append(options)
        return True

    export_manager = SimpleNamespace(
        createSTEPExportOptions=lambda path, geometry: (path, geometry), execute=export,
    )
    export_design = SimpleNamespace(
        rootComponent=export_root, exportManager=export_manager,
        materials=SimpleNamespace(
            itemByName=lambda name: copied_materials.get(name), addByCopy=copy_material,
        ),
    )
    temporary = SimpleNamespace(
        products=SimpleNamespace(itemByProductType=lambda _: export_design),
        close=lambda save: closed.append(save),
    )
    environment["app"].documents = SimpleNamespace(add=lambda _: temporary)
    environment["adsk"].core = SimpleNamespace(
        DocumentTypes=SimpleNamespace(FusionDesignDocumentType=1),
        Matrix3D=SimpleNamespace(create=lambda: identity),
    )
    environment["adsk"].fusion.DesignTypes = SimpleNamespace(DirectDesignType=0)
    environment["adsk"].fusion.TemporaryBRepManager = SimpleNamespace(
        get=lambda: SimpleNamespace(copy=lambda body: FakeBody(body.entityToken))
    )
    environment["payload"] = {"path": str(tmp_path / "target.step")}
    result = execute_script(_TARGET_STEP_SCRIPT, environment)
    staged = [body for component in [export_root, *child_components]
              for body in component.bRepBodies]
    assert result["scope"] == "accepted_target_only" and result["body_count"] == len(parts)
    assert len(staged) == len(parts)
    assert [body.entityToken for body in staged] == [body.entityToken for body in parts]
    assert all(body not in parts and body is not fixture for body in staged)
    assert all(part.material is not copied_materials[name]
               for part, name in zip(parts, material_names, strict=True))
    assert transforms == ([identity] * len(parts) if len(parts) > 1 else [])
    assert exported[0][1] is export_root
    assert closed == [False] and restored == [True]
    assert root.bRepBodies == [*parts, fixture] and root.material is source_material


def test_fixed_box_stock_scope_does_not_read_solid_stock_property():
    part = FakeBody("part")

    class FixedBoxSetup:
        name = "Fixed Box"
        stockMode = 0
        models = FakeCollection([part])
        fixtures = FakeCollection()

        @property
        def stockSolids(self):
            raise AssertionError("Fusion raises when stockMode is not SolidStock")

    environment, _ = script_environment([part], [FixedBoxSetup()])
    execute_script(_REGISTER_TARGET_SCRIPT, environment)
    result = execute_script(_CAM_SCOPE_SCRIPT, environment)
    assert result["setups"][0]["stock_body_count"] == 0
    assert environment["adsk"].cam.SetupStockModes.SolidStock == 1


class ScriptFailureBridge(BridgeDouble):
    def __init__(self, bad_source, *, timeout=False, partial_cam=False):
        super().__init__()
        self.bad_source = bad_source
        self.timeout = timeout
        self.partial_cam = partial_cam
        self.failed_executions = 0
        self.fresh_documents = 0
        self.opens = 0
        self.steps = []

    def request(self, action, payload=None, **kwargs):
        payload = payload or {}
        if action == "open_cad":
            self.opens += 1
            self.geometry = GEOMETRY.copy()
            self.steps.append("open-frozen")
        if action == "run_script":
            source = payload["source"]
            if source == _FRESH_CAD_SCRIPT:
                self.fresh_documents += 1
                self.steps.append("fresh-cad")
            if source == _PREPARE_CAM_SCRIPT:
                self.steps.append("prepare-setup")
            if source == _GEOMETRY_SCRIPT:
                self.steps.append("verify-geometry")
            if source == _FINALIZE_CAM_SCRIPT:
                self.steps.append("finalize-nc")
            if machining_source(source) == self.bad_source:
                self.failed_executions += 1
                self.steps.append("source-error")
                if self.timeout:
                    raise TimeoutError("request-test timed out; do not blindly retry")
                if self.partial_cam:
                    self.geometry = {"method": "test-fingerprint", "bodies": [{"volume_cm3": 999}]}
                return {
                    "status": "error",
                    "completed": False,
                    "issues": [
                        {
                            "type": "fusion_api_error",
                            "message": "3 : root component name cannot be changed",
                        }
                    ],
                    "result": {"traceback": "Traceback: generated-source.py line 9"},
                }
            if (
                source.startswith(_CAM_RESOURCE_PRELUDE)
                and machining_source(source) == CAM_REPLY["source"]
            ):
                self.steps.append("repaired-cam")
        return super().request(action, payload, **kwargs)


def test_confirmed_cad_script_error_is_repaired_on_fresh_document_and_preserved(tmp_path, inputs):
    bad = dict(CAD_REPLY, source="raise RuntimeError('root rename')")
    bridge = ScriptFailureBridge(bad["source"])
    client = ClientDouble([bad, CAD_REPLY, ACCEPT_REPLY])
    target = AstraMainAgent(client, bridge).establish_target(inputs, str(tmp_path))
    target.verify()
    assert bridge.failed_executions == 1 and bridge.fresh_documents == 2
    assert "root component name cannot be changed" in client.calls[1][0]
    assert "generated-source.py line 9" in client.calls[1][0]
    assert "current_inspection" in client.calls[1][0]
    assert "fresh empty CAD document" in client.calls[1][0]
    assert (tmp_path / "cad-attempt-01.py").read_text() == bad["source"]
    assert (tmp_path / "cad-attempt-02.py").read_text() == CAD_REPLY["source"]
    failure = json.loads((tmp_path / "cad-attempt-01-execution.json").read_text())
    assert failure["status"] == "confirmed_script_error"
    assert failure["bridge_response"]["result"]["traceback"]
    assert (tmp_path / "cad-attempt-02-execution.json").is_file()


def test_transport_timeout_never_resubmits_generated_source(tmp_path, inputs):
    bad = dict(CAD_REPLY, source="raise RuntimeError('uncertain request')")
    bridge = ScriptFailureBridge(bad["source"], timeout=True)
    client = ClientDouble([bad])
    with pytest.raises(TimeoutError, match="do not blindly retry"):
        AstraMainAgent(client, bridge).establish_target(inputs, str(tmp_path))
    assert bridge.failed_executions == 1 and bridge.fresh_documents == 1
    assert len(client.calls) == 1
    failure = json.loads((tmp_path / "cad-attempt-01-execution.json").read_text())
    assert failure["status"] == "interrupted" and failure["bridge_response"] is None
    assert not (tmp_path / "cad-attempt-02.py").exists()


def test_cam_source_repair_reopens_frozen_candidate_before_executing_replacement(tmp_path, inputs):
    bad = dict(CAM_REPLY, source="raise RuntimeError('bad CAM parameter')")
    main, _, client, context = prepare(tmp_path, inputs, [bad, CAM_REPLY])
    bridge = ScriptFailureBridge(bad["source"], partial_cam=True)
    main.bridge = bridge
    ask = client.ask

    def ask_with_prepared_setup(prompt, **kwargs):
        # The first model call already sees deterministic setup/tool preparation.
        assert "prepare-setup" in bridge.steps
        return ask(prompt, **kwargs)

    client.ask = ask_with_prepared_setup
    candidate = main.propose(context, None, {}, "shorter paths", 1)
    candidate.verify()
    assert bridge.opens == 2 and bridge.failed_executions == 1
    assert bridge.steps == [
        "open-frozen", "prepare-setup", "verify-geometry", "source-error",
        "open-frozen", "prepare-setup", "verify-geometry", "repaired-cam",
        "verify-geometry", "finalize-nc", "verify-geometry",
    ]
    assert "partially mutated setup" in client.calls[-1][0]
    directory = Path(context.job_directory) / "workspace/cam-0001"
    baseline = json.loads((directory / "cam-attempt-02-baseline.json").read_text())
    assert baseline["geometry"] == GEOMETRY
    assert baseline["cam_setup"] == PREPARED_SETUP
    replacement = (directory / "cam-attempt-02.py").read_text()
    assert machining_source(replacement) == CAM_REPLY["source"]


def test_compiled_machining_source_preserves_future_import_and_provided_resources(tmp_path):
    class ExecutingBridge:
        def request(self, action, payload):
            assert action == "run_script"
            namespace = {"payload": payload["arguments"]}
            exec(compile(payload["source"], "test-bridge-wrapper", "exec"), namespace)
            return {"result": namespace["result"]}

    source = (
        "from __future__ import annotations\n"
        "selected: FusionTool = tools[payload['tool_number']]\n"
        "result = {'selected': selected, 'annotation': __annotations__['selected']}\n"
    )
    main = AstraMainAgent(ClientDouble([]), ExecutingBridge())
    _, execution = main._execute_with_repair(
        dict(CAM_REPLY, source=source), "test task", tmp_path, "cam", lambda _: None,
        source_prefix="tools = {1: 'approved cutter'}\n",
        script_arguments={"tool_number": 1},
    )
    assert execution["result"] == {"selected": "approved cutter", "annotation": "FusionTool"}


@pytest.mark.parametrize("prepared", [{"setup_index": 0, "tools": []}, {"tools": [{"number": 1}]}])
def test_incomplete_deterministic_setup_stops_before_asking_model(tmp_path, inputs, prepared):
    main, bridge, client, context = prepare(tmp_path, inputs, [CAM_REPLY])
    request = bridge.request

    def unavailable(action, payload=None, **kwargs):
        if action == "run_script" and payload["source"] == _PREPARE_CAM_SCRIPT:
            return {"result": prepared}
        return request(action, payload, **kwargs)

    bridge.request = unavailable
    initial_calls = len(client.calls)
    with pytest.raises(RuntimeError, match="Deterministic Fusion setup or tool loading failed"):
        main.propose(context, None, {}, "", 1)
    assert len(client.calls) == initial_calls
    assert "generate_toolpaths" not in bridge.actions


def test_repeated_confirmed_source_errors_stop_after_three_attempts(tmp_path, inputs):
    bad = dict(CAD_REPLY, source="raise RuntimeError('still unsupported')")
    bridge = ScriptFailureBridge(bad["source"])
    client = ClientDouble([bad, bad, bad])
    with pytest.raises(RuntimeError, match="source attempts exhausted \\(3\\)"):
        AstraMainAgent(client, bridge).establish_target(inputs, str(tmp_path))
    assert bridge.failed_executions == bridge.fresh_documents == len(client.calls) == 3
    assert len(list(tmp_path.glob("cad-attempt-*-execution.json"))) == 3


def test_unresolved_source_repair_stops_before_another_document_or_execution(tmp_path, inputs):
    bad = dict(CAD_REPLY, source="raise RuntimeError('missing API access')")
    bridge = ScriptFailureBridge(bad["source"])
    client = ClientDouble([bad, dict(CAD_REPLY, unresolved=["Fusion feature access required"])])
    with pytest.raises(ValueError, match="feature access required"):
        AstraMainAgent(client, bridge).establish_target(inputs, str(tmp_path))
    assert bridge.failed_executions == 1 and bridge.fresh_documents == 1


class FakeOccurrence:
    def __init__(self, token, bodies=(), *, native=None, parent=None):
        self.entityToken = token
        self.nativeObject = native
        self.assemblyContext = parent
        self.bRepBodies = FakeCollection(bodies)
        self.childOccurrences = FakeCollection()


def test_cam_scope_resolves_alternate_tokens_and_only_removes_cam_wrapper():
    from types import SimpleNamespace

    part = FakeBody("part-original-token")
    setup = SimpleNamespace(
        name="Setup", stockMode=0, models=FakeCollection([part]),
        fixtures=FakeCollection(),
    )
    environment, _ = script_environment([part], [setup])
    execute_script(_REGISTER_TARGET_SCRIPT, environment)
    products = environment["app"].activeDocument.products
    design = products.itemByProductType("DesignProductType")
    cam = products.itemByProductType("CAMProductType")
    wrapper = FakeOccurrence("cam-only-wrapper-token")
    cam.designRootOccurrence = wrapper
    alternate = FakeBody("same-part-different-token")
    alternate.attributes = part.attributes
    proxy = FakeBody("cam-proxy-token")
    proxy.nativeObject, proxy.assemblyContext = alternate, wrapper
    old_resolver = design.findEntityByToken
    design.findEntityByToken = lambda token: (
        [part] if token == alternate.entityToken else old_resolver(token)
    )
    setup.models[:] = [proxy]
    result = execute_script(_CAM_SCOPE_SCRIPT, environment)
    assert result["setups"][0]["model_body_ids"] == [
        part.attributes.itemByName("silta", "accepted_target_body").value
    ]


def test_cam_scope_preserves_nested_occurrence_instance_identity():
    from types import SimpleNamespace

    part, fixture = FakeBody("part"), FakeBody("shared-fixture-body")
    setup = SimpleNamespace(
        name="Setup", stockMode=0, models=FakeCollection([part]),
        fixtures=FakeCollection(),
    )
    environment, root = script_environment([part], [setup])
    execute_script(_REGISTER_TARGET_SCRIPT, environment)
    products = environment["app"].activeDocument.products
    design = products.itemByProductType("DesignProductType")
    cam = products.itemByProductType("CAMProductType")
    wrapper = FakeOccurrence("cam-wrapper")
    cam.designRootOccurrence = wrapper
    parent_a, parent_b = FakeOccurrence("parent-a"), FakeOccurrence("parent-b")
    child = FakeOccurrence("shared-child-native")
    design_child = FakeOccurrence("design-child-proxy", native=child, parent=parent_a)
    design_body = FakeBody("fixture-design-proxy")
    design_body.nativeObject, design_body.assemblyContext = fixture, design_child
    design_child.bRepBodies.append(design_body)
    root.allOccurrences.extend([parent_a, design_child])
    original_resolver = design.findEntityByToken
    design.findEntityByToken = lambda token: (
        [parent_b] if token == parent_b.entityToken else original_resolver(token)
    )
    parent_a_cam = FakeOccurrence("parent-a-cam", native=parent_a, parent=wrapper)
    child_cam = FakeOccurrence("child-cam", native=child, parent=parent_a_cam)
    fixture_cam = FakeBody("fixture-cam-proxy")
    fixture_cam.nativeObject, fixture_cam.assemblyContext = fixture, child_cam
    setup.fixtures.append(fixture_cam)
    assert execute_script(_CAM_SCOPE_SCRIPT, environment)["setups"][0]["fixture_body_count"] == 1

    # Same native body and same child component, but another assembly instance.
    # Ignoring all occurrence paths would incorrectly accept this placement.
    child_cam.assemblyContext = FakeOccurrence("parent-b-cam", native=parent_b, parent=wrapper)
    with pytest.raises(RuntimeError, match="exactly one Design instance"):
        execute_script(_CAM_SCOPE_SCRIPT, environment)


def test_target_preview_fits_and_refreshes_before_capture(tmp_path, inputs):
    from types import SimpleNamespace

    class CapturingBridge(BridgeDouble):
        def request(self, action, payload=None, **kwargs):
            if action == "run_script" and "saveAsImageFile" in payload["source"]:
                self.preview_source = payload["source"]
            return super().request(action, payload, **kwargs)

    bridge = CapturingBridge()
    client = ClientDouble([CAD_REPLY, ACCEPT_REPLY])
    AstraMainAgent(client, bridge).establish_target(inputs, tmp_path)
    source = bridge.preview_source
    events = []
    viewport = SimpleNamespace(
        fit=lambda: events.append("fit") or True,
        refresh=lambda: events.append("refresh") or True,
        saveAsImageFile=lambda *args: events.append("capture") or True,
    )
    environment = {"app": SimpleNamespace(activeViewport=viewport)}
    exec(source, environment)
    assert events == ["fit", "refresh", "capture"]
    events.clear()
    viewport.fit = lambda: False
    with pytest.raises(RuntimeError, match="fit/refresh"):
        exec(source, environment)
    assert events == []


def test_linked_cam_saves_exact_version_and_forks_before_improvement(tmp_path, inputs):
    inputs = replace(inputs, machine={**inputs.machine,
        "simulation_model_cloud": {"project_id": "test-project"}})
    main, _, client, context = prepare(tmp_path, inputs, [CAM_REPLY, CAM_REPLY])

    class CloudBridge(BridgeDouble):
        def __init__(self):
            super().__init__()
            self.timeline = []
            self.counter = 0
            self.reference = None

        def request(self, action, payload=None, **kwargs):
            payload = payload or {}
            source = payload.get("source", "")
            if action == "run_script" and "cam_documents.py" in source:
                args = payload["arguments"]
                if "['begin_save']" in source:
                    self.counter += 1
                    self.timeline.append(("save", args.get("previous_data_file_id")))
                    self.reference = {
                        "data_file_id": f"lineage-{self.counter}",
                        "version_id": f"urn:adsk.wipprod:fs.file:vf.test{self.counter}?version=1",
                        "version_number": 1, "project_id": "test-project",
                        "document_name": args["name"],
                    }
                    return {"result": {"doc_name": args["name"]}}
                if "['save_status']" in source:
                    return {"result": {"completed": True, "reference": self.reference}}
                if "['open_version']" in source:
                    self.timeline.append(("open-version", args["reference"]["version_id"]))
                    return {"result": args["reference"]}
                raise AssertionError(source)
            if source == _PREPARE_CAM_SCRIPT:
                self.timeline.append(("prepare", None))
            if source.startswith(_CAM_RESOURCE_PRELUDE):
                self.timeline.append(("machining", None))
            return super().request(action, payload, **kwargs)

    bridge = CloudBridge()
    main.bridge = bridge
    first = main.propose(context, None, {}, "", 1)
    frozen_reference = Path(first.artifacts["fusion_document"].path).read_text()
    first.verify()
    first_version = json.loads(frozen_reference)
    bridge.timeline.clear()
    second = main.propose(context, first, {}, "reduce tool changes", 2)
    second.verify()
    assert bridge.timeline == [
        ("open-version", first_version["version_id"]),
        ("save", first_version["data_file_id"]),
        ("prepare", None), ("machining", None), ("save", None),
    ]
    assert bridge.actions.count("open_cad") == 1  # Only the initial part-only target.
    assert Path(first.artifacts["fusion_document"].path).read_text() == frozen_reference
    assert json.loads(Path(second.artifacts["fusion_document"].path).read_text())[
        "data_file_id"] != first_version["data_file_id"]
