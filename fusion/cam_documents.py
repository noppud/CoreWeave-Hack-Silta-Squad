"""Version-pinned Fusion CAM documents retain the linked machine model."""

import re
import uuid
from pathlib import Path


def _text(payload, key):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {key}")
    return value


def _version(reference):
    version_id = _text(reference, "version_id")
    match = re.fullmatch(r"urn:adsk\.[^:]+:fs\.file:vf\.[^?\s]+\?version=([1-9][0-9]*)", version_id)
    if match is None or int(match.group(1)) != reference.get("version_number"):
        raise ValueError("A matching explicit Fusion version URN and number are required")
    _text(reference, "data_file_id")
    _text(reference, "project_id")
    return version_id


def begin_save(app, payload):
    """Issue Save As once. Poll the returned handle; never retry this mutation on timeout."""
    project_id, name = _text(payload, "project_id"), _text(payload, "name")
    project = app.data.dataProjects.itemById(project_id)
    if project is None or project.id != project_id:
        raise RuntimeError("The exact Fusion project is unavailable")
    document = app.activeDocument
    if document is None:
        raise RuntimeError("No active CAM document to save")
    previous = payload.get("previous_data_file_id")
    if previous is not None and (document.dataFile is None or document.dataFile.id != previous):
        raise RuntimeError("Active document is not the requested candidate to fork")
    if not document.saveAs(name, project.rootFolder, payload.get("description", ""), ""):
        raise RuntimeError("Fusion Save As failed")
    return {
        "saving": True,
        "doc_name": name,
        "project_id": project_id,
        "previous_data_file_id": previous,
    }


def save_status(app, payload):
    """Observe the same Save As operation without starting another save."""
    document = app.activeDocument
    if document is None or document.name != _text(payload, "doc_name"):
        raise RuntimeError("Active document changed while awaiting CAM save")
    data = document.dataFile
    if data is None or not data.isComplete:
        return {"completed": False}
    if data.id == payload.get("previous_data_file_id"):
        raise RuntimeError("Save As did not create an independent candidate")
    if data.parentProject.id != _text(payload, "project_id"):
        raise RuntimeError("CAM candidate was saved in an unexpected project")
    reference = {
        "data_file_id": data.id,
        "version_id": data.versionId,
        "version_number": data.versionNumber,
        "document_name": document.name,
        "project_id": data.parentProject.id,
    }
    _version(reference)
    return {"completed": True, "reference": reference}


def open_version(app, payload):
    """Open the exact saved candidate, never the latest version implicitly."""
    reference = payload["reference"]
    version_id = _version(reference)
    data = app.data.findFileById(version_id)
    if data is None or not data.isComplete:
        raise RuntimeError("The saved CAM version is unavailable or still processing")
    if (
        data.versionId != version_id
        or data.id != reference["data_file_id"]
        or data.parentProject.id != reference["project_id"]
    ):
        raise RuntimeError("Resolved CAM data file differs from its pinned reference")
    recovered = []
    # Fusion reuses an already-open document, including unsaved simulation/display
    # changes. Preserve that state locally before reopening the pinned cloud version.
    for existing in list(app.documents):
        file = existing.dataFile
        if (
            file is None
            or file.id != reference["data_file_id"]
            or file.versionId != version_id
            or not existing.isModified
        ):
            continue
        import adsk.fusion

        existing.activate()
        design = adsk.fusion.Design.cast(existing.products.itemByProductType("DesignProductType"))
        folder = Path(__file__).resolve().parents[1] / ".private/fusion-document-recovery"
        folder.mkdir(parents=True, exist_ok=True)
        backup = folder / (uuid.uuid4().hex + ".f3d")
        options = design.exportManager.createFusionArchiveExportOptions(str(backup))
        if not design.exportManager.execute(options) or not backup.is_file():
            raise RuntimeError("Could not preserve modified Fusion document before reopening")
        recovered.append(str(backup))
        if not existing.close(False):
            raise RuntimeError("Could not close preserved local document to reopen pinned version")
    document = app.documents.open(data, True)
    if document is None or document.dataFile is None:
        raise RuntimeError("Fusion could not open the saved CAM version")
    if document.dataFile.versionId != version_id or document.isModified:
        raise RuntimeError("Opened CAM document is not the unmodified pinned version")
    return {
        "document_name": document.name,
        "version_id": version_id,
        "data_file_id": document.dataFile.id,
        "preserved_modified_archives": recovered,
    }
