"""The fixed setup rejects ambiguous or non-finite machine placement before Fusion writes."""

import json
from pathlib import Path

import pytest

from fusion.prepare_cam_setup import fixed_parameters


def _inputs():
    return json.loads((Path(__file__).parents[1] / "config/soft-jaw-job.json").read_text())


@pytest.mark.parametrize("offset", [float("nan"), float("inf")])
def test_invalid_placement_rejected(offset):
    inputs = _inputs()
    inputs["setup"]["machine_position"]["translation_mm"][1] = offset
    with pytest.raises(ValueError, match="finite offsets"):
        fixed_parameters(inputs)


def test_non_setup_parameter_cannot_be_injected():
    inputs = _inputs()
    inputs["setup"]["stock"]["api_parameters"]["tool_spindleSpeed"] = "99999 rpm"
    with pytest.raises(ValueError, match="Unexpected fixed setup parameter"):
        fixed_parameters(inputs)


def test_different_work_coordinate_system_requires_explicit_implementation():
    inputs = _inputs()
    inputs["setup"]["work_coordinate_system"]["name"] = "G55"
    with pytest.raises(ValueError, match="fixed G54"):
        fixed_parameters(inputs)
