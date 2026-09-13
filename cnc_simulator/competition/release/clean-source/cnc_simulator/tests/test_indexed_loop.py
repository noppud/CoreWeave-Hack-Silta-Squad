import copy,json
from pathlib import Path
import numpy as np
import pytest
from cncsim import simulate,InputError
from camloop.indexed.cam import BASELINE,compile_plan,cheap_checks
from camloop.indexed.parts import catalog,prepare
from camloop.indexed.runner import judge
BASE=Path(__file__).resolve().parents[1]/'examples'

def test_cache_is_reusable_and_content_addressed(tmp_path):
    p=json.loads((BASE/'pocket.json').read_text());a=simulate(p,base_dir=BASE);b=simulate(p,base_dir=BASE)
    assert a['stock_metrics']==b['stock_metrics'] and a['passed']==b['passed']
    p['moves']=[];c=simulate(p,base_dir=BASE)
    assert not c['passed'] and c['stock_metrics']['removed_nominal_volume_mm3']==0

def test_ten_distinct_targets_and_compiled_moves(tmp_path):
    entries=prepare(tmp_path);hashes=[]
    for e in entries:
        job=json.loads(Path(e['job']).read_text());hashes.append(job['target_sha256']);plan,phases=compile_plan(job,BASELINE)
        assert not cheap_checks(job,plan)
        assert phases and any(m['type']=='index' for m in plan['moves'])
        assert len({tuple(f['bc']) for f in job['features']})>=2
        changed=copy.deepcopy(BASELINE);changed['cut_feed_mm_min']=901
        with pytest.raises(InputError):compile_plan(job,changed)
    assert len(set(hashes))==10
    assert [e['split'] for e in entries].count('development')==2

def test_judge_has_no_geometry_or_strategy():
    class Roles:
        def ask(self,role,context):
            assert role=='supervisor'
            assert not {'part','features','plan','strategy','target','stock','guidance'}&context.keys()
            return {'action':'stop','reason':'budget exhausted','guidance_proposal':None},'test'
    row={'result':{'passed':True,'estimated_time_seconds':12,'time_breakdown':{'cutting':10,'indexing':2}}}
    assert judge(Roles(),row,row,[row],0)['value']['action']=='stop'
    row['result']['passed']=False
    with pytest.raises(ValueError):judge(Roles(),row,row,[row],0)


def test_large_grid_broad_phase_matches_unfiltered_sweep():
    from cncsim.geometry import sweep
    rng=np.random.default_rng(417)
    points=rng.uniform(-20,20,(200003,3))
    for start,end,margin in [(np.array([0.,0,0]),np.array([8.,3.,-4.]),.8),(np.array([1.,2,3]),np.array([1.,2,3]),-.4)]:
        actual=sweep(points,start,end,4,0,12,margin)
        expected=np.concatenate([sweep(points[i:i+50000],start,end,4,0,12,margin) for i in range(0,len(points),50000)])
        assert np.array_equal(actual,expected)

@pytest.mark.parametrize('repair_passes',[True,False])
def test_failed_reference_reaches_cam_and_only_pass_reaches_judge(tmp_path,monkeypatch,repair_passes):
    import camloop.indexed.runner as runner
    calls=[]
    class Roles:
        def __init__(self,*a,**k):pass
    def evaluation(passed,path):
        path.mkdir(parents=True,exist_ok=True);(path/'plan.json').write_text('{}')
        return dict(path=str(path),strategy=copy.deepcopy(BASELINE),result=dict(passed=passed,issues=[],estimated_time_seconds=10,time_breakdown={}))
    monkeypatch.setattr(runner,'Astra',Roles)
    monkeypatch.setattr(runner,'record_failure',lambda *a:None)
    monkeypatch.setattr(runner,'evaluate',lambda job,strategy,path:evaluation(False,path))
    def candidate(roles,job,previous,feedback,memory,path):
        calls.append('cam');assert feedback['passed'] is False
        return evaluation(repair_passes,path)
    monkeypatch.setattr(runner,'ask_candidate',candidate)
    def fake_judge(*args):
        calls.append('judge');assert args[1]['result']['passed'];return dict(value=dict(action='stop'))
    monkeypatch.setattr(runner,'judge',fake_judge);monkeypatch.setattr(runner,'verify_job',lambda job:None)
    m=runner.optimize(dict(id='test',name='test',split='test',target_sha256='frozen'),tmp_path,None,attempts=1)
    assert calls==(['cam','judge'] if repair_passes else ['cam'])
    assert m['status']==('completed' if repair_passes else 'failed')


def test_memory_commit_has_immutable_source_and_readback(tmp_path):
    from camloop.indexed.sequential import remember
    from camloop.common import file_hash
    m=dict(id='test',target_sha256='frozen',status='failed',attempts=[],best=None)
    memory=remember(tmp_path,dict(version=0,episodes=[],strategy_prior=None),m)
    commit=json.loads((tmp_path/'memory/commit-0001.json').read_text())
    assert commit['read_back_verified'] and commit['sha256']==file_hash(tmp_path/'memory.json')
    assert commit['source_manifest_sha256']==file_hash(commit['source_snapshot'])
    assert memory['version']==1 and memory['episodes'][0]['part']=='test'


def test_exact_learned_check_changes_with_geometry_and_compiler(tmp_path):
    from camloop.indexed.learning import learned_preflight,record_failure
    memory={};job={'id':'same','target_sha256':'unchanged'}
    row=dict(strategy=copy.deepcopy(BASELINE),path='observed-failure',result=dict(issues=[{'code':'excess_material'}]))
    record_failure(memory,job,row)
    assert learned_preflight(job,dict(BASELINE,cut_feed_mm_min=800),memory)
    assert not learned_preflight(job,dict(BASELINE,junction_cleanup=True),memory)
    assert not learned_preflight(dict(job,target_sha256='different'),BASELINE,memory)


def test_junction_cleanup_preserves_contract_and_adds_safe_plunges(tmp_path):
    entries=prepare(tmp_path,count=2);job=json.loads(Path(entries[1]['job']).read_text())
    before=job['target_sha256'];plan,phases=compile_plan(job,dict(BASELINE,junction_cleanup=True))
    assert not cheap_checks(job,plan)
    assert any(p['name']=='Intersecting-pocket junction cleanup' for p in phases)
    assert job['target_sha256']==before
