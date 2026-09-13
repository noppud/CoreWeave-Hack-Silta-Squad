"""Two editable learning files; direct updates without benchmark promotion gates."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .local_checks import LocalCheckRunner
from .models import JobContext, ReusableProposal

BASIC_PROMPT = """You are the CAD/CAM planning agent. Read the supplied drawing/PDF and create
its dimensioned solid CAD with the specified physical material. Once accepted,
keep that target fixed. Plan machining using the supplied machine, tools, stock,
fixture and limits. Use simulation feedback to repair failures and the judge's
instructions to improve machining time and cost. Return the requested Fusion
Python source; the application executes it and measures the result. Report
missing critical dimensions instead of inventing them.
"""
EMPTY_CHECKS = '''"""Learned manufacturing checks. Initially there are none."""


def check(data):
    return {"passed": True, "issues": []}
'''


class SharedLearning:
    """Only two active files on disk. Content refs in run logs identify what ran."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.paths = {"main_prompt": self.root / "cad_cam.md", "checks": self.root / "checks.py"}
        self.objects: dict[str, dict] = {}
        for kind, content in (("main_prompt", BASIC_PROMPT), ("checks", EMPTY_CHECKS)):
            try:
                with self.paths[kind].open("x") as output:
                    output.write(content)
            except FileExistsError:
                pass

    def put(self, kind: str, content: str) -> str:
        ref = hashlib.sha256((kind + "\0" + content).encode()).hexdigest()
        self.objects[ref] = {"kind": kind, "content": content}
        return ref

    def get(self, ref: str) -> dict:
        return dict(self.objects[ref])

    def active(self) -> dict[str, str]:
        return {kind: self.put(kind, path.read_text()) for kind, path in self.paths.items()}

    def apply(self, proposal: ReusableProposal, context: JobContext) -> tuple[str, ...]:
        if proposal.kind not in self.paths:
            raise ValueError("Only the CAD/CAM prompt and learned checks are editable")
        current = self.active()[proposal.kind]
        if current != proposal.base_version or context.versions[proposal.kind] != current:
            raise ValueError("Learning file changed since the proposal was made")
        obj = self.get(proposal.proposed_version)
        if obj["kind"] != proposal.kind or not obj["content"].strip():
            raise ValueError("Learning update has wrong kind or empty content")
        if proposal.kind == "checks":
            compile(obj["content"], "<learned-checks>", "exec")
        path = self.paths[proposal.kind]
        # A completed write is replaced atomically; no extra persistent state file.
        fd, temporary = tempfile.mkstemp(dir=self.root)
        try:
            with os.fdopen(fd, "w") as output:
                output.write(obj["content"])
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return (str(path),)

    def make_checks(self, ref: str) -> LocalCheckRunner:
        content = self.get(ref)["content"]
        return LocalCheckRunner(
            self.paths["checks"], version=ref,
            sha256=hashlib.sha256(content.encode()).hexdigest(),
        )
