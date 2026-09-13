from silta.cnc.approvals import FusionAppApproval

REQUEST = {
    "serverName": "cua_repl",
    "mode": "form",
    "message": 'Allow Computer Use to use "Fusion"?',
    "requestedSchema": {"type": "object", "properties": {}},
}


def test_explicit_fusion_consent_is_reused_only_for_fusion():
    prompts = []

    def prompt(message):
        prompts.append(message)
        return "yes"

    handler = FusionAppApproval(prompt=prompt)
    expected = {"action": "accept", "content": {}}
    assert handler("mcpServer/elicitation/request", REQUEST) == expected
    assert handler("mcpServer/elicitation/request", REQUEST) == expected
    assert len(prompts) == 1
    unrelated = {**REQUEST, "message": 'Allow Computer Use to use "Mail"?'}
    assert handler("mcpServer/elicitation/request", unrelated)["action"] == "cancel"
    assert handler("item/commandExecution/requestApproval", {}) == {"decision": "decline"}


def test_decline_or_unrecognized_schema_never_grants():
    handler = FusionAppApproval(prompt=lambda _: "no")
    assert handler("mcpServer/elicitation/request", REQUEST)["action"] == "cancel"
    handler = FusionAppApproval(prompt=lambda _: "yes")
    changed = {**REQUEST, "requestedSchema": {"type": "object", "properties": {"admin": {}}}}
    assert handler("mcpServer/elicitation/request", changed)["action"] == "cancel"
    assert not handler.approved


def test_noninteractive_launch_has_no_implicit_consent(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert FusionAppApproval()("mcpServer/elicitation/request", REQUEST)["action"] == "cancel"
