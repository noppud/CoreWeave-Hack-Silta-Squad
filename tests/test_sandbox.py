import hashlib
import json
from types import SimpleNamespace

import pytest

from silta.cnc.models import Artifact
from silta.cnc.sandbox import HostedCheckRunner, SandboxUnavailable


class Ref:
    def __init__(self, value):
        self.value = value

    def result(self):
        return self.value


class RemoteDouble:
    def __init__(self, output, failure=None):
        self.output = output
        self.failure = failure
        self.files = {}
        self.closed = False
        self.calls = []
        self.kwargs = {}

    def run(self, **kwargs):
        self.kwargs = kwargs
        if self.failure:
            raise self.failure
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def write_file(self, path, contents, **kwargs):
        self.files[path] = contents
        return Ref(None)

    def exec(self, command, **kwargs):
        # Deliberately does NOT execute generated code in the test process.
        self.calls.append(command)
        return Ref(SimpleNamespace(returncode=0))

    def read_file(self, *args, **kwargs):
        return Ref(self.output)


def setup(tmp_path, output=b'{"passed":true,"issues":[]}', failure=None):
    code = tmp_path / "checks.py"
    code.write_text("raise RuntimeError('must never execute on host')")
    analysis = tmp_path / "analysis.json"
    analysis.write_text('{"operations":[]}')
    candidate = SimpleNamespace(
        verify=lambda: None,
        digest="candidate",
        parameters={},
        artifacts={"analysis": Artifact.from_path(analysis)},
    )
    context = SimpleNamespace(
        versions={"checks": "v1"},
        input_digest="inputs",
        inputs=SimpleNamespace(machine={"axes": 3}, tools={}, setup={}, tolerances={}),
    )
    remote = RemoteDouble(output, failure)
    sdk = SimpleNamespace(Sandbox=remote, AuthHeaders=lambda **k: k, NetworkOptions=lambda **k: k)
    runner = HostedCheckRunner(
        code,
        version="v1",
        sha256=hashlib.sha256(code.read_bytes()).hexdigest(),
        api_key="TEST_SECRET",
        entity="silta",
        sdk=sdk,
    )
    return runner, candidate, context, remote


def test_remote_only_execution_cleanup_and_no_guest_credentials(tmp_path):
    runner, candidate, context, remote = setup(tmp_path)
    result = runner.run(candidate, context)
    assert result.passed
    assert result.version == "v1"
    assert remote.closed
    assert remote.calls == [["python", "-I", "/tmp/harness.py"]]
    assert all(b"TEST_SECRET" not in value for value in remote.files.values())
    assert remote.kwargs["environment_variables"] == {}
    assert remote.kwargs["network"] == {"deny_egress": True, "deny_ingress": True}
    data = json.loads(remote.files["/tmp/input.json"])
    assert data["candidate"]["artifacts"]["analysis"]["path"] == "/tmp/candidate-0.json"


def test_changed_check_pin_rejected_before_service(tmp_path):
    runner, candidate, context, remote = setup(tmp_path)
    runner.check_path.write_text("changed")
    with pytest.raises(ValueError, match="Pinned check code changed"):
        runner.run(candidate, context)
    assert not remote.kwargs


@pytest.mark.parametrize(
    "output",
    [
        b"{}",
        b'{"passed":"true","issues":[]}',
        b'{"passed":true,"issues":["collision"]}',
        b"not-json",
    ],
)
def test_malformed_output_fails_closed_and_cleans_up(tmp_path, output):
    runner, candidate, context, remote = setup(tmp_path, output)
    result = runner.run(candidate, context)
    assert not result.passed
    assert result.issues == ("invalid_check_output",)
    assert remote.closed


def test_entitlement_distinct_and_exception_redacted(tmp_path):
    runner, candidate, context, remote = setup(
        tmp_path, failure=RuntimeError("Organization not enabled; credential TEST_SECRET")
    )
    with pytest.raises(SandboxUnavailable) as caught:
        runner.run(candidate, context)
    assert caught.value.code == "organization_not_enabled"
    assert "TEST_SECRET" not in str(caught.value)


def test_guest_issue_text_is_bounded_and_redacted(tmp_path):
    output = json.dumps({"passed": False, "issues": ["TEST_SECRET\x1b\n" + "x" * 2000]}).encode()
    runner, candidate, context, remote = setup(tmp_path, output)
    result = runner.run(candidate, context)
    assert len(result.issues[0]) == 1000
    assert "TEST_SECRET" not in result.issues[0]
    assert "\x1b" not in result.issues[0]
