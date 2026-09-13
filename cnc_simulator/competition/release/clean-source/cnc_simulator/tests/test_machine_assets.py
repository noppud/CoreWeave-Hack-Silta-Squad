"""Validate source-backed reference assets; these are not collision tests."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = json.loads((ROOT / 'viewer/dist/assets/haas-vf2.json').read_text())


def points(kind):
    return np.concatenate([np.asarray(m['positions']).reshape(-1, 3) for m in BUNDLE[kind]['meshes']])


def test_source_integrity():
    for item in BUNDLE['provenance']:
        assert item['pinned']
        assert hashlib.sha256((ROOT.parent / item['path']).read_bytes()).hexdigest() == item['sha256']
    for name, expected in BUNDLE['export_hashes'].items():
        assert hashlib.sha256((ROOT / 'assets/machine' / name).read_bytes()).hexdigest() == expected


def test_complete_mesh_inventory():
    assert len(BUNDLE['machine']['meshes']) == 11
    assert len(BUNDLE['fixture']['meshes']) == 19
    assert {m['group'] for m in BUNDLE['machine']['meshes']} == {'Static:1', 'X-Axis:1', 'Y-Axis:1', 'Z-Axis:1', 'Spindle:1'}
    for kind in ['machine', 'fixture', 'target']:
        for m in BUNDLE[kind]['meshes']:
            p = np.asarray(m['positions']).reshape(-1, 3)
            indices = np.asarray(m['indices'])
            assert np.isfinite(p).all()
            assert indices.size % 3 == 0 and indices.size > 0
            assert indices.min() >= 0 and indices.max() < len(p)


def test_setup_scale_and_table_contact():
    np.testing.assert_allclose(np.ptp(points('target'), axis=0), [152.4, 50.8, 25.4], atol=1e-4)
    assert abs(points('target')[:, 2].max()) < 1e-4
    assert abs(points('fixture')[:, 2].min() + BUNDLE['g54_translation_mm'][2]) < 1e-4


def test_parked_tool_assemblies_and_travel():
    assert len(BUNDLE['tools']) == 2
    translation = BUNDLE['g54_translation_mm']
    park = BUNDLE['park_g54_mm']
    assert abs(translation[0] + park[0]) <= 381
    assert abs(translation[1] + park[1]) <= 203
    np.testing.assert_allclose([t['diameter_mm'] for t in BUNDLE['tools']], [12.7, 6.35])
    for tool in BUNDLE['tools']:
        assert 0 < tool['flute_length_mm'] <= tool['stickout_mm'] < tool['gauge_length_mm']
        assert -508 <= translation[2] + park[2] + tool['gauge_length_mm'] - 610 <= 0
        assert all(s['height'] > 0 for s in tool['holder_segments'])
