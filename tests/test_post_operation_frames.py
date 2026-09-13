import runpy
from pathlib import Path

import pytest

require = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/fusion/post_operation_frames.py")
)["require_binding"]


def test_wrong_version_and_dirty_document_refused():
    ref = dict(data_file_id="file", version_id="v3", version_number=3, project_id="project")
    actual = dict(ref, is_modified=False)
    require(actual, ref)
    with pytest.raises(ValueError, match="version_id"):
        require(dict(actual, version_id="v4"), ref)
    with pytest.raises(ValueError, match="unmodified"):
        require(dict(actual, is_modified=True), ref)
