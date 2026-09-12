"""Boundary tests for deterministic resources; these do not emulate CAM simulation."""

import copy
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from fusion.cam_resources import finalize_nc, load_tools, tool_for_number

CONFIG = Path(__file__).resolve().parents[1] / "config/soft-jaw-job.json"


class Attributes:
    def __init__(self):
        self.items = {}

    def add(self, group, key, value):
        self.items[group, key] = SimpleNamespace(value=value)

    def itemByName(self, group, key):
        return self.items.get((group, key))


class Parameters(list):
    def itemByName(self, name):
        return next((parameter for parameter in self if parameter.name == name), None)


class Tool:
    def __init__(self, data):
        self.data = copy.deepcopy(data)

    def toJson(self):
        return json.dumps(self.data)


class Operation:
    def __init__(self, tool):
        self._tool = tool
        self.operationId, self.name, self.isSuppressed = 101, "Agent pocket", False
        self.parameters = Parameters(
            [
                SimpleNamespace(name="tool_feedCutting", expression="1234 mm/min"),
                SimpleNamespace(name="tool_spindleSpeed", expression="5500 rpm"),
                SimpleNamespace(name="tool_feedRamp", expression="250 mm/min"),
                SimpleNamespace(name="tool_feedRetract", expression="800 mm/min"),
                SimpleNamespace(name="maximumStepdown", expression="2 mm"),
            ]
        )
        self.tool_assignments = 0

    @property
    def tool(self):
        return self._tool

    @tool.setter
    def tool(self, tool):
        self._tool = tool
        self.tool_assignments += 1
        # Documented actual setter behavior: resets preset after assignment.
        for parameter in self.parameters:
            if parameter.name.startswith("tool_"):
                parameter.expression = "default preset value"


class Collection(list):
    @property
    def count(self):
        return len(self)

    def item(self, index):
        return self[index]

    def createInput(self):
        return SimpleNamespace()

    def add(self, nc_input):
        program = SimpleNamespace(attributes=Attributes(), operations=nc_input.operations)
        self.append(program)
        return program


@pytest.fixture
def state(monkeypatch, tmp_path):
    inputs = json.loads(CONFIG.read_text())
    raw = json.loads(Path(inputs["tools"]["library"]["path"]).read_text())
    operation = Operation(Tool(raw["data"][0]))
    setup = SimpleNamespace(attributes=Attributes(), allOperations=[operation], machine=object())
    setup.attributes.add("silta", "controller_setup", "v1")
    post_state = SimpleNamespace(mode="valid")

    class NCProgram:
        def __init__(self, nc_input):
            self.operations = nc_input.operations
            self.attributes = Attributes()
            self.parameters = Parameters()

        @property
        def postConfiguration(self):
            return self.actual_post

        @postConfiguration.setter
        def postConfiguration(self, value):
            self.assigned_post = value
            # Reproduce live transient wrapper inequality despite same CPS.
            self.actual_post = SimpleNamespace(
                vendor=value.vendor, description=value.description, isValid=False
            )
            post_path = tmp_path / "fusion-bound-post.tmp"
            post_path.write_text(value.content if post_state.mode != "wrong_bytes" else "wrong CPS")
            if post_state.mode == "unreadable":
                post_path.unlink()
            self.parameters = Parameters()
            if post_state.mode != "missing_parameter":
                resolved = None if post_state.mode == "missing_value" else str(post_path)
                self.parameters.append(
                    SimpleNamespace(name="nc_program_post", value=SimpleNamespace(value=resolved))
                )

    class NCPrograms(Collection):
        def add(self, nc_input):
            program = NCProgram(nc_input)
            self.append(program)
            return program

    cam = SimpleNamespace(setups=Collection([setup]), ncPrograms=NCPrograms())
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(products=SimpleNamespace(itemByProductType=lambda _: cam))
    )
    loads = []

    def load_library(text):
        library = json.loads(text)
        loads.append(library)
        return Collection([Tool(tool) for tool in library["data"]])

    adsk, module = ModuleType("adsk"), ModuleType("adsk.cam")
    module.CAM = SimpleNamespace(cast=lambda value: value)
    module.ToolLibrary = SimpleNamespace(createFromJson=load_library)
    module.Operation = SimpleNamespace(
        cast=lambda value: value if isinstance(value, Operation) else None
    )
    module.PostConfiguration = SimpleNamespace(
        createFromContent=lambda content: SimpleNamespace(
            vendor="Haas", description="Pinned CPS", content=content
        )
    )
    adsk.cam = module
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.cam", module)
    return SimpleNamespace(
        inputs=inputs,
        app=app,
        cam=cam,
        setup=setup,
        operation=operation,
        loads=loads,
        module=module,
        post_state=post_state,
    )


def test_load_enabled_pinned_tools_without_global_state(state):
    result = load_tools(state.app, {"inputs": state.inputs})
    assert set(result["tools"]) == {1, 2}
    assert result["inventory"][0]["assembly_gauge_length_mm"] == pytest.approx(96.52)
    assert state.loads[0]["version"] == 37
    assert tool_for_number(state.inputs, 2).data["product-id"] == "03-0083"
    with pytest.raises(ValueError, match="not enabled"):
        tool_for_number(state.inputs, 3)
    assert state.operation.tool_assignments == 0 and state.cam.ncPrograms.count == 0


def test_finalize_restores_chosen_feeds_and_reuses_only_owned_nc(state):
    expressions = {parameter.name: parameter.expression for parameter in state.operation.parameters}
    first = finalize_nc(state.app, {"inputs": state.inputs, "setup_index": 0})
    second = finalize_nc(state.app, {"inputs": state.inputs, "setup_index": 0})
    assert state.operation.tool_assignments == 2
    assert {p.name: p.expression for p in state.operation.parameters} == expressions
    assert state.cam.ncPrograms.count == 1
    program = state.cam.ncPrograms.item(0)
    assert program.operations == [state.operation] and program.machine is state.setup.machine
    assert first["sha256"] == second["sha256"] == state.inputs["setup"]["postprocessor"]["sha256"]
    assert first["nc_program_index"] == 0
    assert program.postConfiguration != program.assigned_post
    assert first["resolved_post_sha256"] == first["sha256"]
    assert (
        Path(first["resolved_post_path"]).read_bytes().decode("utf-8")
        == program.assigned_post.content
    )
    assert "not officially supported" in first["post_api_status"]


@pytest.mark.parametrize(
    "bad", ["foreign_setup", "foreign_nc", "unknown_tool", "wrong_product", "bad_cps_pin"]
)
def test_invalid_inputs_do_not_mutate_operations_or_nc(state, bad):
    if bad == "foreign_setup":
        state.setup.attributes.items.clear()
    elif bad == "foreign_nc":
        state.cam.ncPrograms.append(SimpleNamespace(attributes=Attributes()))
    elif bad == "unknown_tool":
        state.operation.tool.data["post-process"]["number"] = 99
    elif bad == "wrong_product":
        state.operation.tool.data["product-id"] = "not-the-pinned-tool"
    else:
        state.inputs["setup"]["postprocessor"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        finalize_nc(state.app, {"inputs": state.inputs})
    assert state.operation.tool_assignments == 0
    assert state.cam.ncPrograms.count == (1 if bad == "foreign_nc" else 0)


def test_fusion_tool_geometry_drift_is_rejected_before_assignment(state):
    original = state.module.ToolLibrary.createFromJson

    def drift(text):
        library = original(text)
        library[0].data["geometry"]["assemblyGaugeLength"] = 1.3
        return library

    state.module.ToolLibrary.createFromJson = drift
    with pytest.raises(ValueError, match="assemblyGaugeLength"):
        finalize_nc(state.app, {"inputs": state.inputs})
    assert state.operation.tool_assignments == 0 and state.cam.ncPrograms.count == 0


@pytest.mark.parametrize(
    "mode", ["wrong_bytes", "unreadable", "missing_parameter", "missing_value"]
)
def test_nc_post_requires_actual_bound_file_with_exact_pinned_bytes(state, mode):
    state.post_state.mode = mode
    with pytest.raises(RuntimeError, match="post"):
        finalize_nc(state.app, {"inputs": state.inputs})
    # No successful receipt is returned even if the post metadata still matches.
    program = state.cam.ncPrograms.item(0)
    assert program.postConfiguration.vendor == program.assigned_post.vendor
