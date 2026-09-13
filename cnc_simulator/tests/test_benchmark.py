"""Contract and accounting checks for multi-feature evaluation."""
import copy
import json
from pathlib import Path

import pytest
from camloop.common import load_job, save
from camloop.benchmark import report


def test_multiple_pocket_description_and_rejection(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'examples/pocket.json'
    plan = json.loads(source.read_text())
    plan['target']['path'] = str(source.parent / 'pocket_target.stl')
    save(tmp_path / 'plan.json', plan)
    f = dict(centerline_start=[4,5], centerline_end=[8,5], radius=2, floor_z=3, stock_top_z=6)
    job = dict(id='multi', plan='plan.json', family='pocket_set', feature=dict(pockets=[f, copy.deepcopy(f)]), feed_limits_mm_min={'T1':240,'T2':240}, max_moves=100)
    save(tmp_path / 'job.json', job)
    assert len(load_job(tmp_path / 'job.json')['feature']['pockets']) == 2
    job['feature']['pockets'][1]['floor_z'] = 7
    save(tmp_path / 'job.json', job)
    with pytest.raises(ValueError, match='below stock top'):
        load_job(tmp_path / 'job.json')


def test_report_keeps_unknown_out_of_improvement(tmp_path):
    save(tmp_path / 'benchmark.json', dict(cases=[dict(id='test', reference_seconds=12)]))
    save(tmp_path / 'runs/benchmark-test/manifest.json', dict(status='incomplete', reason='attempt budget',
        attempts=[dict(stage='simulated', result=dict(validity='invalid', verification='unresolved', estimated_time_seconds=1)),
                  dict(stage='simulated', result=dict(validity='valid', estimated_time_seconds=8))],
        best=dict(seconds=8, attempt=1), learning=[], loaded_knowledge=dict(version=0)))
    row = report(tmp_path)['parts'][0]
    assert row['best_valid_seconds'] == row['first_valid_seconds'] == 8
    assert row['uncertain_failures'] == 1
    assert row['improvement_vs_reference_percent'] == pytest.approx(100/3)
    assert row['status'] == 'incomplete'
