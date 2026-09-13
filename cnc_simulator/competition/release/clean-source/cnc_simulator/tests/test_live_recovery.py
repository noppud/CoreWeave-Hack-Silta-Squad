"""Exercise orchestration failures while retaining independently verified work."""
import copy
import pytest
from camloop import live

@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.delenv('CAMLOOP_WEAVE_PROJECT', raising=False)
    monkeypatch.setattr(live, 'WORK', tmp_path)
    directory=tmp_path/'runs'/'testjob';directory.mkdir(parents=True)
    live.save(tmp_path/'memory.json', {'version':1})
    live.save(directory/'spec.json', dict(name='Recovery', blockers=[],stock_kind='box',stock_dimensions_mm=[64,52,24],features=[dict(name='pocket',a=[-12,0],b=[12,0],radius_mm=10,floor_z_mm=8)]))
    def prepare(path, parts):
        live.save(path/'parts'/'testjob'/'job.json', {'target_sha256':'frozen'})
    monkeypatch.setattr(live,'prepare',prepare)
    reference=dict(path=str(directory/'reference'),strategy={'feed':100},stage='simulated',result=dict(passed=True,estimated_time_seconds=100,issues=[]))
    monkeypatch.setattr(live,'evaluate',lambda *a:copy.deepcopy(reference))
    monkeypatch.setattr(live,'planner_context',lambda job,previous,feedback,active:dict(feedback=copy.deepcopy(feedback)))
    monkeypatch.setattr(live,'cheap_checks',lambda *a:[])
    monkeypatch.setattr(live,'learned_preflight',lambda *a:[])
    monkeypatch.setattr(live,'record_timing',lambda *a:None)
    monkeypatch.setattr(live,'export_part',lambda *a,**k:None)
    monkeypatch.setattr(live,'remember',lambda *a:dict(version=2))
    monkeypatch.setattr(live,'judge',lambda *a:dict(value=dict(action='improve')))
    monkeypatch.setattr(live,'compile_plan',lambda *a:({'moves':[{'type':'cut','to':[1,2,3],'feed':100}]},[]))
    monkeypatch.setattr(live,'simulate',lambda *a,**k:dict(passed=True,estimated_time_seconds=40,issues=[]))
    contexts=[]
    class Planner:
        def __init__(self,*a):pass
        def ask(self,role,context):
            contexts.append(context)
            return dict(strategy={'feed':200}), {}
    monkeypatch.setattr(live,'Astra',Planner)
    return directory,contexts

def test_compile_failure_is_repaired_without_losing_reference(harness,monkeypatch):
    directory,contexts=harness
    def fail(*a):raise ValueError('Unsupported strategy')
    monkeypatch.setattr(live,'compile_plan',fail)
    monkeypatch.setattr(live,'simulate',lambda *a,**k:pytest.fail('Invalid CAM reached simulation'))
    monkeypatch.setattr(live,'judge',lambda *a:pytest.fail('Invalid CAM reached timing judge'))
    live.run(directory)
    s=live.read(directory/'state.json');m=s['manifest']
    assert s['status']=='completed'
    assert m['best']==m['reference']
    assert len(m['attempts'])==3
    assert contexts[1]['feedback']['issues'][0]['code']=='compile_error'
    assert m['saved_memory_version']==2

def test_slower_passing_candidate_cannot_replace_reference(harness,monkeypatch):
    directory,_=harness
    monkeypatch.setattr(live,'simulate',lambda *a,**k:dict(passed=True,estimated_time_seconds=150,issues=[]))
    live.run(directory)
    m=live.read(directory/'manifest.json')
    assert m['status']=='completed'
    assert m['best']==m['reference']
    assert m['loop_evidence']['baseline_savings_percent']==0

def test_later_planner_failure_exposes_retained_best(harness,monkeypatch):
    directory,contexts=harness
    class Planner:
        def __init__(self,*a):pass
        def ask(self,role,context):
            if contexts:raise RuntimeError('Planner unavailable')
            contexts.append(context)
            return dict(strategy={'feed':200}),{}
    monkeypatch.setattr(live,'Astra',Planner)
    live.run(directory)
    s=live.read(directory/'state.json');m=live.read(directory/'manifest.json')
    assert s['status']=='error'
    assert s['manifest']==m
    assert m['best']['result']['estimated_time_seconds']==40
    assert m['loop_evidence']['baseline_savings_percent']==60
    assert 'retained' in m['stop_reason']

def test_playback_failure_keeps_newly_verified_result(harness,monkeypatch):
    directory,_=harness
    def fail(*a,**k):raise RuntimeError('Playback export failed')
    monkeypatch.setattr(live,'export_part',fail)
    live.run(directory)
    s=live.read(directory/'state.json')
    assert s['status']=='error'
    assert s['manifest']['best']['result']['estimated_time_seconds']==40
