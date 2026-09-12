import hashlib
from types import SimpleNamespace

import pytest

from silta.cnc.local_checks import LocalCheckRunner
from silta.cnc.models import Artifact


def make(tmp_path, source, timeout=2):
    script = tmp_path / "checks.py"
    script.write_text(source)
    artifact = tmp_path / "analysis.json"
    artifact.write_text('{"answer":42}')
    candidate = SimpleNamespace(
        verify=lambda: None,
        digest="candidate",
        parameters={},
        artifacts={"analysis": Artifact.from_path(artifact)},
    )
    context = SimpleNamespace(
        versions={"checks": "v1"},
        input_digest="setup",
        inputs=SimpleNamespace(machine={}, tools={}, setup={}, tolerances={}),
    )
    runner = LocalCheckRunner(
        script,
        version="v1",
        sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        timeout_seconds=timeout,
    )
    return runner, candidate, context


def test_actual_process_copied_artifact_and_clean_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "must-not-inherit")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-inherit")
    runner, candidate, context = make(
        tmp_path,
        """
import os, json
def check(data):
    path = data['candidate']['artifacts']['analysis']['path']
    assert 'silta-check-' in path
    assert json.load(open(path))['answer'] == 42
    assert not os.environ.get('WANDB_API_KEY')
    assert not os.environ.get('OPENAI_API_KEY')
    assert os.environ['HOME'] == os.getcwd()
    return {'passed': True, 'issues': []}
""",
    )
    assert runner.run(candidate, context).passed


@pytest.mark.parametrize(
    "source,reason",
    [
        ("raise RuntimeError('private exception')", "check_execution_failed"),
        ("def check(data): return {'passed': 'yes', 'issues': []}", "invalid_check_output"),
        ("def check(data): return {'passed': True, 'issues': ['bad']}", "invalid_check_output"),
    ],
)
def test_failures_are_sanitized(tmp_path, source, reason):
    runner, candidate, context = make(tmp_path, source)
    result = runner.run(candidate, context)
    assert not result.passed
    assert result.issues == (reason,)


def test_wall_timeout(tmp_path):
    runner, candidate, context = make(tmp_path, "import time\ntime.sleep(10)", timeout=0.1)
    result = runner.run(candidate, context)
    assert result.issues == ("check_timeout",)
    assert result.runtime_s < 2


def test_artifact_pin_mismatch_before_execution(tmp_path):
    runner, candidate, context = make(tmp_path, "raise RuntimeError('should not execute')")
    (tmp_path / "analysis.json").write_text("changed")
    with pytest.raises(ValueError, match="Candidate artifact changed"):
        runner.run(candidate, context)


def test_check_pin_mismatch(tmp_path):
    runner, candidate, context = make(tmp_path, "raise RuntimeError('should not execute')")
    runner.check_path.write_text("changed")
    with pytest.raises(ValueError, match="Pinned check code changed"):
        runner.run(candidate, context)
