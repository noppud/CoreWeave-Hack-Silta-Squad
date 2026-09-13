"""Fixed Fusion accessibility observations through Codex's direct MCP API.

No model turn is started. Fusion simulation commands belong to the bridge;
this reader observes the authorized app and provides fixed window-focus steps.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from openai_codex.client import CodexClient
from pydantic import BaseModel, ConfigDict

from .astra import MODEL, AstraClient

_OPEN = 'let siltaFusion = await cua.getApp("com.autodesk.fusion360");'
_MARKER = "SILTA_FUSION_AX_JSON:"
_READ = (
    'nodeRepl.write("SILTA_FUSION_AX_JSON:" + JSON.stringify('
    "await siltaFusion.getAXState({disableDiffing: true, emit: false})));"
)
_READ_SCREENSHOT = (
    "var siltaObservation = await siltaFusion.getAXStateAndScreenshot("
    "{disableDiffing: true, emit: false}); "
    'nodeRepl.write("SILTA_FUSION_AX_JSON:" + JSON.stringify(siltaObservation.state)); '
    "if (siltaObservation.screenshot) await nodeRepl.emitImage(siltaObservation.screenshot);"
)
_FOCUS_NEXT_PANEL = 'await siltaFusion.pressKey("ctrl+F6"); ' + _READ


class _McpReply(BaseModel):
    model_config = ConfigDict(extra="allow")
    content: list[dict[str, Any]]
    isError: bool | None = None
    structuredContent: Any = None


class FusionUIReader:
    def __init__(self, workspace: Path, app_approval=None):
        self.workspace = Path(workspace).resolve(strict=True)
        self.astra = AstraClient(computer_use=True, app_approval=app_approval)
        self.client = None
        self.thread_id = None
        self.open_evidence = None

    def __enter__(self):
        if self.client is not None:
            raise RuntimeError("Fusion reader is already open")
        self.client = CodexClient(
            self.astra._config(self.workspace), approval_handler=self.astra.app_approval
        )
        try:
            self.client.__enter__()
            self.client.initialize()
            started = self.client.thread_start(
                {
                    "model": MODEL,
                    "modelProvider": "openai",
                    "cwd": str(self.workspace),
                    "ephemeral": True,
                    "approvalPolicy": "on-request",
                    "sandbox": "read-only",
                }
            )
            self.thread_id = started.thread.id
            self.open_evidence = self._call(_OPEN)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, tb):
        client, self.client = self.client, None
        self.thread_id = None
        if client is not None:
            return client.__exit__(exc_type, exc, tb)
        return None

    def _call(self, code: str) -> dict:
        if self.client is None or self.thread_id is None:
            raise RuntimeError("Fusion reader must be used as a context manager")
        arguments = {"code": code, "title": "Read Fusion simulation state"}
        reply = self.client.request(
            "mcpServer/tool/call",
            {
                "threadId": self.thread_id,
                "server": "cua_repl",
                "tool": "js",
                "arguments": arguments,
            },
            response_model=_McpReply,
        ).model_dump(mode="json", by_alias=True)
        evidence = {
            "thread_id": self.thread_id,
            "server": "cua_repl",
            "tool": "js",
            "arguments": arguments,
            "raw_mcp_response": reply,
        }
        if reply.get("isError"):
            error = RuntimeError("Fusion accessibility collection failed")
            error.evidence = evidence
            raise error
        return evidence

    def read(self, *, screenshot: bool = False) -> dict:
        evidence = self._call(_READ_SCREENSHOT if screenshot else _READ)
        return self._snapshot(evidence)

    def bring_to_front(self) -> dict:
        """Activate the exact observed document with the proven native transport."""
        from .stock_export import StockExporter

        observation = self.read()
        match = re.search(r'^Window:\s*"(.+?) - Autodesk Fusion', observation["raw_text"], re.M)
        if match is None:
            raise RuntimeError("Fusion focus requires the observed document title")
        native = StockExporter(match.group(1), self.workspace / f"native-focus-{uuid.uuid4().hex}")
        focused = native.ui("focus")
        # Dismiss only an observed application menu left by an earlier attempt.
        after = self.read()
        if any(w["title"] == "Window" for w in focused["windows"]) or re.search(
            r"(?m)^\s*\d+ Window, Secondary Actions: Cancel", after["raw_text"]
        ):
            focused = native.ui("key", "escape")
        return {"native_focus": focused, "before": observation, **self.read()}

    def focus_next_panel(self) -> dict:
        """Advance native panel focus once and return its new full observation."""
        return self._snapshot(self._call(_FOCUS_NEXT_PANEL))

    @staticmethod
    def _snapshot(evidence: dict) -> dict:
        # Only our explicitly emitted AX value is state. Initial getApp output
        # also includes documentation, which must never be parsed as UI evidence.
        values = []
        for block in evidence["raw_mcp_response"]["content"]:
            if block.get("type") == "text" and block.get("text", "").startswith(_MARKER):
                try:
                    values.append(json.loads(block["text"][len(_MARKER) :]))
                except json.JSONDecodeError as cause:
                    error = RuntimeError("Fusion accessibility response has malformed state")
                    error.evidence = evidence
                    raise error from cause
        if len(values) != 1 or not isinstance(values[0], str) or not values[0].strip():
            error = RuntimeError("Fusion accessibility response has no unique full state")
            error.evidence = evidence
            raise error
        return {"raw_text": values[0], **evidence}
