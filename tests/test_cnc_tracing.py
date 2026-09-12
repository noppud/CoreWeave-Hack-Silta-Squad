"""Stage instrumentation contracts with an injected recorder; no network calls."""

import inspect
import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from silta.cnc.models import CheckResult
from silta.cnc.tracing import trace_adapter, trace_call, trace_controller


class Recorder:
    def __init__(self):
        self.calls = []
        self.active = []

    def op(self, **options):
        assert options["enable_code_capture"] is False

        def decorate(function):
            def invoke(*args, **kwargs):
                record = {
                    "name": options["name"],
                    "parent": self.active[-1] if self.active else None,
                    "inputs": options["postprocess_inputs"](
                        inspect.signature(function).bind(*args, **kwargs).arguments
                    ),
                }
                self.calls.append(record)
                self.active.append(record["name"])
                try:
                    value = function(*args, **kwargs)
                    record["output"] = options["postprocess_output"](value)
                    return value
                except Exception as error:
                    record["exception"] = error
                    raise
                finally:
                    self.active.pop()
            return invoke
        return decorate


def test_application_values_are_recorded_without_bound_adapter_or_environment(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "secret-environment-sentinel")

    @dataclass
    class Plan:
        candidate_id: str
        version: str

    class Checks:
        credential = "secret-adapter-sentinel"
        reasoning = "private-model-reasoning-sentinel"

        def run(self, candidate):
            assert candidate is plan
            return result

    recorder = Recorder()
    plan = Plan("candidate-2", "checks-v1")
    result = CheckResult(False, ("Holder clearance is insufficient",), 0.01, "checks-v1")
    wrapped = trace_adapter(Checks(), {"run": "candidate_checks"}, recorder.op)
    assert wrapped.run(plan) is result
    record = recorder.calls[0]
    assert record["inputs"] == {
        "candidate": {"candidate_id": "candidate-2", "version": "checks-v1"},
    }
    assert record["output"]["passed"] is False
    assert record["output"]["issues"] == ["Holder clearance is insufficient"]
    assert "sentinel" not in json.dumps(record)
    assert "self" not in record["inputs"]


def test_exception_is_visible_and_rethrown_unchanged_without_retry():
    recorder = Recorder()
    failure = TimeoutError("Fusion request outcome is unknown")
    calls = []

    def verify(candidate_id):
        calls.append(candidate_id)
        raise failure

    with pytest.raises(TimeoutError) as raised:
        trace_call(verify, "fusion_verification", recorder.op)("candidate-1")
    assert raised.value is failure
    assert recorder.calls[0]["exception"] is failure
    assert "output" not in recorder.calls[0]
    assert calls == ["candidate-1"]


def test_controller_stages_and_benchmark_children_keep_results_and_order():
    recorder = Recorder()
    executed = []

    def operation(value):
        executed.append(value)
        return {"observed": value}

    def controller():
        return trace_controller(SimpleNamespace(
            main=SimpleNamespace(establish_target=operation, propose=operation),
            checks=SimpleNamespace(run=operation),
            fusion=SimpleNamespace(verify=operation),
            supervisor=SimpleNamespace(decide=operation),
            learner=SimpleNamespace(propose_checks=operation),
        ), recorder.op)

    live = controller()
    assert live.main.establish_target("target") == {"observed": "target"}
    live.main.propose("candidate")
    live.checks.run("check")
    live.fusion.verify("failed simulation")
    live.learner.propose_checks("learn")

    def benchmark(version):
        trial = controller()
        trial.main.propose(version)
        trial.checks.run("paired checks")
        trial.fusion.verify("passed simulation")
        return trial.supervisor.decide("stop")

    assert trace_call(benchmark, "paired_benchmark_run", recorder.op)("proposed-v2") == {
        "observed": "stop",
    }
    assert [call["name"] for call in recorder.calls] == [
        "cad_target", "cam_candidate", "candidate_checks", "fusion_verification",
        "check_learning_proposal", "paired_benchmark_run", "cam_candidate",
        "candidate_checks", "fusion_verification", "supervisor_decision",
    ]
    assert all(call["parent"] == "paired_benchmark_run" for call in recorder.calls[6:])
    assert len(executed) == 9
