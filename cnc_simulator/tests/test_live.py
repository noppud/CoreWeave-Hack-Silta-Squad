import copy
import pytest
from camloop.live import validate_spec
SPEC=dict(blockers=[],stock_kind='box',stock_dimensions_mm=[64,52,24],features=[dict(a=[-12,0],b=[12,0],radius_mm=10,floor_z_mm=8)])
def test_reviewed_spec_is_bounded():
 validate_spec(SPEC)
 for changes in [dict(floor_z_mm=0),dict(radius_mm=2),dict(a=[float('nan'),0]),dict(a=[40,0])]:
  spec=copy.deepcopy(SPEC);spec['features'][0].update(changes)
  with pytest.raises(ValueError):validate_spec(spec)
def test_blockers_cannot_be_run():
 with pytest.raises(ValueError):validate_spec(dict(SPEC,blockers=['Unsupported island']))

def test_loop_metrics_do_not_claim_memory_learning():
 from camloop.live_evidence import summarize
 def row(t):return dict(stage='simulated',result=dict(passed=True,estimated_time_seconds=t,issues=[]))
 m=dict(reference=row(100),attempts=[row(40),row(40)],best=row(40))
 s=summarize(m)
 assert s['baseline_savings_percent']==60
 assert s['within_run_savings_percent']==0
 assert 'not a causal memory benefit' in s['claim']
 m['reference']['result']['passed']=False
 assert summarize(m)['baseline_savings_percent'] is None

def test_duplicate_identity_tracks_actual_movements():
 from camloop.live_evidence import movement_identity
 a=dict(name='one',moves=[dict(type='cut',to=[1,2,3],feed=300)])
 assert movement_identity(a)==movement_identity(dict(a,name='two'))
 b=copy.deepcopy(a);b['moves'][0]['feed']=400
 assert movement_identity(a)!=movement_identity(b)


def test_new_install_starts_empty_without_fabricating_history(tmp_path):
 from camloop.live import initialize_workspace
 from camloop.common import save
 work=tmp_path/'fresh';seed=tmp_path/'absent.json'
 initial=initialize_workspace(work,seed)
 assert initial==dict(version=0,episodes=[],strategy_prior=None)
 assert (work/'memory/versions/0000.json').exists()
 save(seed,dict(version=8,episodes=[{'part':'another'}]))
 assert initialize_workspace(work,seed)==initial


def test_explicit_existing_study_seed_is_preserved(tmp_path):
 from camloop.live import initialize_workspace
 from camloop.common import save
 seed=tmp_path/'study.json';expected=dict(version=2,episodes=[{'part':'measured'}])
 save(seed,expected)
 assert initialize_workspace(tmp_path/'fresh',seed)==expected
