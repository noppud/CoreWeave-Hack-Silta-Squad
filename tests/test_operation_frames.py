import json

import pytest

from fusion.operation_frames import read_diagnostic


def receipt(tmp_path, middle, count=1):
    rows = [
        {"type": "header", "schema_version": 1, "units": "mm"},
        {"type": "section", "id": 0},
        *middle,
        {"type": "footer", "completed": True, "motion_count": count},
    ]
    p = tmp_path / "frames.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return p


def test_arc_cannot_be_misrepresented_as_endpoints(tmp_path):
    p = receipt(
        tmp_path, [{"type": "circular", "section": 0, "start": [0, 0, 0], "end": [1, 1, 0]}]
    )
    with pytest.raises(ValueError, match="analytic arc"):
        read_diagnostic(p)


def test_unvalidated_receipt_never_enables_checks(tmp_path):
    p = receipt(tmp_path, [{"type": "linear", "section": 0, "start": [0, 0, 0], "end": [1, 1, 0]}])
    assert read_diagnostic(p)["usable_for_checks"] is False
    p.write_text(p.read_text().rsplit("\n", 1)[0])
    with pytest.raises(ValueError, match="Incomplete"):
        read_diagnostic(p)


def test_nonfinite_and_missing_motion_rejected(tmp_path):
    p = receipt(tmp_path, [{"type": "linear", "section": 0, "end": [float("nan"), 0, 0]}])
    with pytest.raises(ValueError, match="Nonfinite"):
        read_diagnostic(p)
    p = receipt(tmp_path, [], count=1)
    with pytest.raises(ValueError, match="count"):
        read_diagnostic(p)
