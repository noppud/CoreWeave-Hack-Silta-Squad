"""Host orchestration for version-pinned Fusion documents with external references."""

import time
import uuid
from pathlib import Path

_HELPER = Path(__file__).resolve().parents[2] / "fusion" / "cam_documents.py"


def document_call(request, operation, arguments):
    source = (
        f"import runpy\nresult = runpy.run_path({str(_HELPER)!r})"
        f"[{operation!r}](app, payload)"
    )
    return request("run_script", {"source": source, "arguments": arguments})["result"]


def save_snapshot(request, project_id, name, *, previous=None, timeout=300, receipt=None):
    """Save As once, then poll completion; an uncertain save is never reissued."""
    handle = document_call(request, "begin_save", {
        "project_id": project_id,
        "name": f"{name}-{uuid.uuid4().hex[:12]}",
        "description": "Silta CAM candidate; simulation status is recorded separately.",
        "previous_data_file_id": previous,
    })
    if receipt:
        receipt(handle)
    deadline = time.monotonic() + timeout
    while True:
        status = document_call(request, "save_status", handle)
        if status.get("completed") is True:
            return status["reference"]
        if time.monotonic() >= deadline:
            raise TimeoutError("Fusion CAM save still processing; inspect before retrying")
        time.sleep(0.25)


def open_snapshot(request, reference):
    return document_call(request, "open_version", {"reference": reference})
