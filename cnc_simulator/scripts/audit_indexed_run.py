"""Verify persisted provenance, model settings, judge boundaries and frozen inputs."""
import argparse,json
from pathlib import Path
from camloop.common import file_hash,save
p=argparse.ArgumentParser();p.add_argument('workspace');a=p.parse_args();root=Path(a.workspace).resolve()
def read(p):return json.loads(Path(p).read_text())
commits=sorted((root/'memory').glob('commit-*.json'))
for cp in commits:
    c=read(cp);assert c['read_back_verified']
    assert file_hash(root/'memory/versions'/f"{c['version']:04d}.json")==c['sha256']
    assert file_hash(c['source_snapshot'])==c['source_manifest_sha256']
    m=read(c['source_snapshot']);assert m['loaded_memory_version']==c['version']-1
    assert m['loaded_memory_sha256']==file_hash(root/'memory/versions'/f"{c['version']-1:04d}.json")
for entry in read(root/'catalog.json')['parts']:
    j=read(entry['job'])
    for kind in ['target','stock']:assert file_hash(j['plan'][kind]['path'])==j[kind+'_sha256']
receipts=list(root.rglob('*.response.json'))
for rp in receipts:
    r=read(rp);assert r['model']=='gpt-6-astra' and r['requested_service_tier']=='fast' and r['reasoning_effort']=='low'
judges=list(root.rglob('supervisor-*.request.json'))
for jp in judges:
    c=read(jp)['context'];assert not {'part','features','plan','strategy','target','stock'}&c.keys()
    assert c['current_seconds']>=0 and c['active_guidance']==[]
for entry in read(root/'catalog.json')['parts']:
    m=read(root/'runs'/entry['id']/'manifest.json')
    for row in m['attempts']:
        if not row['result']['passed']:assert 'judge' not in row
result=dict(verified=True,memory_commits=len(commits),model_receipts=len(receipts),timing_only_judge_requests=len(judges),frozen_parts=len(read(root/'catalog.json')['parts']),checks=['Memory hashes and immutable source snapshots','Memory loaded from immediately previous version','All target and stock bytes unchanged','Astra fast requested and low reasoning on every response','Timing-only judge inputs; no failed candidate judged'])
save(root/'audit.json',result);print(json.dumps(result,indent=2))
# Check the two feedback routes against persisted transitions and request context.
routes=dict(simulation_failure_memories=0,judge_timing_memories=0)
for entry in read(root/'catalog.json')['parts']:
    m=read(root/'runs'/entry['id']/'manifest.json')
    if 'feedback_memory' not in m:continue
    kinds=[e['type'] for e in m['events']]
    routes['simulation_failure_memories']+=kinds.count('simulation_to_test_memory')
    routes['judge_timing_memories']+=kinds.count('judge_to_cam_memory')
    for i,kind in enumerate(kinds):
        if kind=='simulation_fail':
            next_planning=next((j for j in range(i+1,len(kinds)) if kinds[j]=='cam_planning'),len(kinds))
            assert 'test_gate_to_cam_repair' in kinds[i+1:next_planning]
    for row in m['attempts']:
        if row.get('judge',{}).get('value',{}).get('action')=='improve':
            assert any(n['source']==row['judge']['evidence'] for n in m['feedback_memory'].get('speed_guidance',[]))
result['loop_routes']=routes;save(root/'audit.json',result)
