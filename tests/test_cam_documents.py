from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fusion.cam_documents import begin_save, open_version, save_status


def _reference():
    return {"data_file_id": "lineage", "version_id": "urn:adsk.wipprod:fs.file:vf.abc?version=2",
            "version_number": 2, "document_name": "candidate-uuid", "project_id": "project"}


def test_delayed_save_polled_without_reissuing_mutation():
    project = SimpleNamespace(id="project", rootFolder=object())
    doc = SimpleNamespace(name="candidate-uuid", dataFile=None, saveAs=Mock(return_value=True))
    app = SimpleNamespace(activeDocument=doc, data=SimpleNamespace(
        dataProjects=SimpleNamespace(itemById=lambda _: project)))
    handle = begin_save(app, {"project_id": "project", "name": "candidate-uuid"})
    assert save_status(app, handle) == {"completed": False}
    ref = _reference()
    doc.dataFile = SimpleNamespace(id=ref["data_file_id"], versionId=ref["version_id"],
                                   versionNumber=2, parentProject=project, isComplete=False)
    assert save_status(app, handle) == {"completed": False}
    doc.dataFile.isComplete = True
    assert save_status(app, handle) == {"completed": True, "reference": ref}
    assert doc.saveAs.call_count == 1


@pytest.mark.parametrize("version", ["urn:adsk.wipprod:fs.file:vf.abc", "latest",
                                     "urn:adsk.wipprod:fs.file:vf.abc?version=3"])
def test_unpinned_or_mismatched_version_rejected_before_lookup(version):
    reference = {**_reference(), "version_id": version}
    with pytest.raises(ValueError, match="explicit Fusion version"):
        open_version(SimpleNamespace(), {"reference": reference})


def test_save_status_cannot_attach_another_active_document():
    with pytest.raises(RuntimeError, match="Active document changed"):
        save_status(SimpleNamespace(activeDocument=SimpleNamespace(name="other")),
                    {"doc_name": "candidate-uuid"})


def test_fork_cannot_reuse_parent_identity():
    document = SimpleNamespace(name="candidate-uuid", dataFile=SimpleNamespace(
        isComplete=True, id="parent"))
    with pytest.raises(RuntimeError, match="independent candidate"):
        save_status(SimpleNamespace(activeDocument=document),
                    {"doc_name": "candidate-uuid", "previous_data_file_id": "parent"})


def test_host_save_timeout_does_not_resubmit(monkeypatch):
    from silta.cnc.cam_documents import save_snapshot

    calls = []

    def request(action, payload):
        calls.append(payload["source"])
        if "['begin_save']" in payload["source"]:
            return {"result": {"doc_name": "pending"}}
        return {"result": {"completed": False}}

    with pytest.raises(TimeoutError, match="inspect before retrying"):
        save_snapshot(request, "project", "test", timeout=0)
    assert sum("['begin_save']" in source for source in calls) == 1
    assert sum("['save_status']" in source for source in calls) == 1


def test_open_rejects_dirty_copy_or_wrong_opened_version():
    ref = _reference()
    data = SimpleNamespace(id=ref["data_file_id"], versionId=ref["version_id"],
        isComplete=True, parentProject=SimpleNamespace(id=ref["project_id"]))
    document = SimpleNamespace(dataFile=data, isModified=True)
    class Documents(list):
        def open(self, *_):
            return document

    app = SimpleNamespace(data=SimpleNamespace(findFileById=lambda _: data),
        documents=Documents())
    with pytest.raises(RuntimeError, match="unmodified pinned version"):
        open_version(app, {"reference": ref})
    document.isModified = False
    document.dataFile = SimpleNamespace(versionId="newer-version")
    with pytest.raises(RuntimeError, match="unmodified pinned version"):
        open_version(app, {"reference": ref})


@pytest.mark.parametrize("export_succeeds", [False, True])
def test_reopen_preserves_modified_copy_before_closing(tmp_path, monkeypatch, export_succeeds):
    import sys
    from pathlib import Path
    from types import ModuleType

    import fusion.cam_documents as module

    monkeypatch.setattr(module, '__file__', str(tmp_path/'fusion/cam_documents.py'))
    ref = _reference()
    data = SimpleNamespace(id=ref['data_file_id'], versionId=ref['version_id'],
                           isComplete=True, parentProject=SimpleNamespace(id=ref['project_id']))
    saved = []

    def export(path):
        if export_succeeds:
            Path(path).write_bytes(b'preserved modified document')
            saved.append(path)
        return export_succeeds

    exporter = SimpleNamespace(createFusionArchiveExportOptions=lambda p: p, execute=export)
    design = SimpleNamespace(exportManager=exporter)
    adsk = ModuleType('adsk')
    adsk.fusion = ModuleType('adsk.fusion')
    adsk.fusion.Design = SimpleNamespace(cast=lambda d: d)
    monkeypatch.setitem(sys.modules, 'adsk', adsk)
    monkeypatch.setitem(sys.modules, 'adsk.fusion', adsk.fusion)
    dirty = SimpleNamespace(dataFile=data, isModified=True, activate=Mock(),
                            products=SimpleNamespace(itemByProductType=lambda _: design),
                            close=Mock(return_value=True))
    clean = SimpleNamespace(dataFile=data, isModified=False, name='candidate')

    class Documents(list):
        def open(self, *_):
            return clean

    app = SimpleNamespace(data=SimpleNamespace(findFileById=lambda _: data),
                          documents=Documents([dirty]))
    if not export_succeeds:
        with pytest.raises(RuntimeError, match='preserve modified'):
            open_version(app, {'reference': ref})
        dirty.close.assert_not_called()
    else:
        result = open_version(app, {'reference': ref})
        assert result['preserved_modified_archives'] == saved
        assert Path(saved[0]).read_bytes() == b'preserved modified document'
        dirty.close.assert_called_once_with(False)
