import copy,json
from pathlib import Path
import numpy as np
import pytest
from cncsim import simulate,InputError
from cncsim.indexing import world_points,index_samples
from cncsim.simulator import validate
BASE=Path(__file__).resolve().parents[1]/'examples'

def indexed():
    p=json.loads((BASE/'pocket.json').read_text())
    p['indexing']=dict(pivot_mm=[0,0,0],work_offset_mm=[0,0,0],initial_bc_degrees=[0,0],b_limits_degrees=[-35,110],degrees_per_second=30,settle_seconds=2,head_mount_mm=[0,0,10],gauge_length_mm=10)
    return p

def test_index_return_preserves_stock_and_times():
    p=indexed();p['moves'] += [dict(type='rapid',to=[0,0,30]),dict(type='index',b_degrees=90,c_degrees=90),dict(type='index',b_degrees=0,c_degrees=0)]
    p['travel_limits']={'min':[-50,-50,-50],'max':[50,50,50]}
    states=[];r=simulate(p,base_dir=BASE,on_step=states.append)
    assert r['passed'],r['issues']
    assert r['time_breakdown']['indexing']==10
    assert np.array_equal(states[-1]['nominal'],states[-3]['nominal'])
    assert states[-2]['bc_degrees']==[90,90]

def test_index_rotation_collision_fails():
    p=indexed();p['initial_position']=[5,-5,3];p['moves']=[dict(type='index',b_degrees=0,c_degrees=180)]
    r=simulate(p,base_dir=BASE)
    assert not r['passed']
    assert any(i['code']=='index_stock_collision' for i in r['issues'])

def test_b_overtravel_fails():
    p=indexed();p['initial_position']=[0,0,30];p['moves']=[dict(type='index',b_degrees=120,c_degrees=0)]
    r=simulate(p,base_dir=BASE)
    assert not r['passed'] and any(i['code']=='axis_overtravel' for i in r['issues'])

def test_no_simultaneous_cut_or_silent_fields():
    p=indexed();p['moves'][0]['b_degrees']=30
    with pytest.raises(InputError):validate(p)

def test_transform_known_answer_and_motion_bound():
    p=indexed()['indexing'];a=np.array([[1.,0,0]])
    assert world_points(a,[90,0],p)[0]==pytest.approx([0,0,1])
    assert world_points(a,[0,90],p)[0]==pytest.approx([0,-1,0])
    samples=list(index_samples(a,[0,0],[90,90],p))
    for i,(mid,guard) in enumerate(samples):
        for f in [i/len(samples),(i+1)/len(samples)]:
            point=world_points(a,[90*f,90*f],p)
            assert np.linalg.norm(mid-point)<=guard+1e-10

@pytest.mark.parametrize('obstacle', ['stock', 'cutter_fixture', 'holder_fixture'])
def test_index_sweep_catches_mid_rotation_contact_with_clear_endpoints(obstacle, tmp_path):
    """At C=0/180 the obstacle is clear; at C=90 it crosses the tool.

    This cannot pass through an endpoint-only collision implementation. The
    holder variant is above the flute and shaft, so checking just the cutter
    during table rotation would miss it.
    """
    p=indexed()
    center=dict(type='box',min=[-1,-1,0],max=[1,1,2])
    orbit=dict(type='box',min=[8,-1,0],max=[12,1,2])
    p['stock']=copy.deepcopy(orbit if obstacle=='stock' else center)
    import trimesh
    bounds=np.array([p['stock']['min'],p['stock']['max']])
    target=trimesh.creation.box(bounds[1]-bounds[0]);target.apply_translation(bounds.mean(axis=0))
    target.export(tmp_path/'target.stl')
    p['target']=dict(type='mesh',path=str(tmp_path/'target.stl'))
    if obstacle!='stock':
        fixture=copy.deepcopy(orbit)
        if obstacle=='holder_fixture':
            fixture['min'][2]=13;fixture['max'][2]=15
        p['fixtures']=[fixture]
    p['initial_position']=[0,-10,0]
    p['travel_limits']=dict(min=[-50,-50,-50],max=[50,50,50])
    p['resolution_mm']=.4;p['tolerance_mm']=.8;p['moves']=[]
    for angle in [0,180]:
        endpoint=copy.deepcopy(p)
        endpoint['indexing']['initial_bc_degrees']=[0,angle]
        result=simulate(endpoint)
        assert result['passed'],result['issues']
    p['moves']=[dict(type='index',b_degrees=0,c_degrees=180)]
    states=[];result=simulate(p,on_step=states.append)
    code='index_stock_collision' if obstacle=='stock' else 'fixture_collision'
    assert not result['passed']
    assert any(i['code']==code and i['certainty']=='definite' and i['moves']==[0] for i in result['issues'])
    assert np.array_equal(states[0]['nominal'],states[-1]['nominal'])
