"""Quarantine dead-process in-flight requests; never retry their actions."""

import json
import os
import uuid
from pathlib import Path


def proven_dead(pid):
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError, OverflowError):
        return False
    return False


def recover_dead_requests(root: Path, *, dead=proven_dead):
    """Caller must hold the bridge's exclusive owner lock. Unknown/live stay blocked."""
    recovered = []
    for request in sorted((root / "processing").glob("*.json")):
        owner = request.with_suffix(".owner")
        try:
            provenance = json.loads(owner.read_text())
        except (OSError, ValueError):
            continue
        if (
            not isinstance(provenance, dict)
            or not isinstance(provenance.get("session"), str)
            or not provenance["session"]
            or not dead(provenance.get("pid"))
        ):
            continue
        folder = root / "abandoned" / uuid.uuid4().hex
        folder.mkdir(parents=True)
        request.replace(folder / request.name)
        owner.replace(folder / owner.name)
        receipt = {
            "status": "unknown",
            "completed": False,
            "replayed": False,
            "reason": "In-flight owner process is proven dead; operation outcome unknown",
            "owner": provenance,
            "request": str(folder / request.name),
            "existing_response_preserved": (root / "responses" / request.name).is_file(),
            "response_path": str(root / "responses" / request.name),
        }
        (folder / "recovery.json").write_text(json.dumps(receipt, indent=2))
        recovered.append(receipt)
    return recovered
