"""Explicit operator consent for the SDK's native Fusion access request."""

from __future__ import annotations

import sys


class FusionAppApproval:
    """One visible consent per launcher session; unrelated requests stay denied."""

    def __init__(self, *, prompt=None):
        self.prompt = prompt
        self.approved = False
        self.receipts: list[dict] = []

    def __call__(self, method: str, params: dict | None) -> dict:
        params = params or {}
        if method == "mcpServer/elicitation/request":
            message = params.get("message")
            expected = (
                params.get("serverName") == "cua_repl"
                and message == 'Allow Computer Use to use "Fusion"?'
                and params.get("mode") == "form"
                and params.get("requestedSchema") == {"type": "object", "properties": {}}
            )
            if expected and not self.approved:
                if self.prompt is not None:
                    answer = self.prompt(message)
                elif sys.stdin.isatty():
                    answer = input(
                        "\nAllow this Silta session to use Fusion for CNC simulation? [yes/no] "
                    )
                else:
                    print(
                        "Fusion access needs operator consent; "
                        "run Silta in an interactive terminal.",
                        file=sys.stderr,
                    )
                    answer = "no"
                self.approved = isinstance(answer, str) and answer.strip().lower() == "yes"
            accepted = expected and self.approved
            self.receipts.append(
                {"method": method, "fusion_request": expected, "accepted": accepted}
            )
            return {
                "action": "accept" if accepted else "cancel",
                "content": {} if accepted else None,
            }
        if method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
            return {"decision": "decline"}
        return {}
