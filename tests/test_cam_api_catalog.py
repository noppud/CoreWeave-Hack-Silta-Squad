import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from fusion.cam_api_catalog import _requested, describe


@pytest.mark.parametrize(
    "payload",
    [
        {"setup_index": -1},
        {"setup_index": True},
        {"strategies": "pocket2d"},
        {"strategies": ["pocket2d", "pocket2d"]},
    ],
)
def test_invalid_catalog_request(payload):
    with pytest.raises(ValueError):
        _requested(payload)


def test_introspection_creates_inputs_but_never_adds_operations(monkeypatch):
    adsk, cam_module = ModuleType("adsk"), ModuleType("adsk.cam")
    adsk.cam = cam_module
    cam_module.CAM = SimpleNamespace(cast=lambda x: x)
    cam_module.ChoiceParameterValue = SimpleNamespace(cast=lambda x: x)
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.cam", cam_module)
    value = SimpleNamespace(
        objectType="adsk::cam::ChoiceParameterValue",
        value="climb",
        getChoices=lambda: (True, ["Climb"], ["climb"]),
    )
    parameter = SimpleNamespace(
        name="actualDirection",
        title="Direction",
        value=value,
        expression="'climb'",
        isEnabled=True,
        isEditable=True,
        isDeprecated=False,
    )
    operations = SimpleNamespace(
        count=0,
        add=Mock(),
        createInput=Mock(return_value=SimpleNamespace(parameters=[parameter])),
        compatibleStrategies=[
            SimpleNamespace(name="pocket2d", title="2D Pocket", isGenerationAllowed=True)
        ],
    )
    setup = SimpleNamespace(
        name="Silta",
        operations=operations,
        attributes=SimpleNamespace(itemByName=lambda *_: SimpleNamespace(value="v1")),
    )
    cam = SimpleNamespace(setups=SimpleNamespace(count=1, item=lambda _: setup))
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(products=SimpleNamespace(itemByProductType=lambda _: cam))
    )
    result = describe(app, {"strategies": ["pocket2d", "unknown"]})
    assert result["strategies"]["pocket2d"]["parameters"][0]["choices"] == [
        {"title": "Climb", "value": "climb"}
    ]
    assert "error" in result["strategies"]["unknown"]
    operations.createInput.assert_called_once_with("pocket2d")
    operations.add.assert_not_called()
