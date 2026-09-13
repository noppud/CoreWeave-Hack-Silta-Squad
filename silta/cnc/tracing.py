"""Application-stage tracing without exposing adapter clients or SDK internals.

The runtime injects weave.op; the controller and its tests need no Weave client.
Wrappers return the original objects and let exceptions reach the caller unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, is_dataclass
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _application_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _application_value(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, dict):
        return {key: _application_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_application_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Never serialize arbitrary client instances, their attributes or their repr.
    return {"unrecorded_type": type(value).__name__}


def trace_call(method: Callable, name: str, op: Callable) -> Callable:
    @wraps(method)
    def invoke(*args, **kwargs):
        return method(*args, **kwargs)

    return op(
        name=name,
        enable_code_capture=False,
        postprocess_inputs=_application_value,
        postprocess_output=_application_value,
    )(invoke)


def trace_adapter(adapter: Any, methods: dict[str, str], op: Callable) -> Any:
    return SimpleNamespace(
        **{
            method: trace_call(getattr(adapter, method), name, op)
            for method, name in methods.items()
        }
    )


def trace_controller(controller: Any, op: Callable) -> Any:
    """Apply equally to live and benchmark controllers, including integrity checks."""
    stages = {
        "main": {"establish_target": "cad_target", "propose": "cam_candidate"},
        "checks": {"run": "candidate_checks"},
        "fusion": {"verify": "fusion_verification"},
        "supervisor": {"decide": "supervisor_decision"},
        "learner": {"propose_checks": "check_learning_proposal"},
    }
    for attribute, methods in stages.items():
        adapter = getattr(controller, attribute)
        if adapter is not None:
            setattr(controller, attribute, trace_adapter(adapter, methods, op))
    factory = getattr(controller, "check_runner_factory", None)
    if factory is not None:
        # Promoted checks are reconstructed later; retain their stage trace too.
        controller.check_runner_factory = lambda ref: trace_adapter(
            factory(ref), {"run": "candidate_checks"}, op
        )
    return controller
