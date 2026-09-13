"""Fresh fixed-verifier counterexample audit for a failure-derived exact check."""
import copy,json,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camloop.common import save,file_hash,digest
from camloop.indexed.runner import read,evaluate
from camloop.indexed.learning import record_failure,learned_preflight
ROOT=Path(__file__).resolve().parents[1];STUDY=ROOT/'workspace-loop-demo';OUT=Path(__file__).with_name('failure-memory-eval')
def main():
 OUT.mkdir(exist_ok=True)
 if (OUT/'result.json').exists():raise SystemExit('Completed audit exists; preserve it.')
 job=read(STUDY/'parts/02-hydraulic-manifold/job.json');manifest=read(STUDY/'runs/02-hydraulic-manifold/manifest.json')
 source=manifest['reference'];assert not source['result']['passed']
 memory={};record_failure(memory,job,source);save(OUT/'frozen-memory.json',memory)
 bearing=read(STUDY/'parts/03-bearing-block/job.json');bearing_m=read(STUDY/'runs/03-bearing-block/manifest.json')
 faster=copy.deepcopy(source['strategy']);faster['cut_feed_mm_min']=min(job['limits']['cut_feed_mm_min'],faster['cut_feed_mm_min']*1.1)
 changed=copy.deepcopy(job);changed['plan']['fixtures'][0]['min'][0]-=300;changed['plan']['fixtures'][0]['max'][0]-=300
 cases=[('original-failure',job,source['strategy']),('feed-only-repeat',job,faster),('corrected-junction',job,manifest['best']['strategy']),('other-valid-part',bearing,bearing_m['best']['strategy']),('changed-fixture-scope',changed,source['strategy'])]
 receipt={'scope':'Fresh five-case fixed-verifier audit of exact failure memory; selected counterexamples, not broad generalization. Check abstention is not a geometry pass.','memory_sha256':file_hash(OUT/'frozen-memory.json'),'implementation':{x:file_hash(ROOT/x) for x in ['camloop/indexed/cam.py','camloop/indexed/learning.py','cncsim/simulator.py','cncsim/geometry.py','cncsim/indexing.py']},'cases':[]}
 for name,j,s in cases:
  print('SIMULATING',name,flush=True)
  start=time.perf_counter();baseline=evaluate(j,s,OUT/name,memory=None);duration=time.perf_counter()-start
  if baseline['stage']!='simulated':raise ValueError('Expected actual full simulation for '+name)
  start=time.perf_counter();issues=learned_preflight(j,s,memory);gate_seconds=time.perf_counter()-start
  row=dict(name=name,contract_sha256=digest(j),strategy=s,full_simulation_passed=baseline['result']['passed'],issues=baseline['result']['issues'],memory_rejects=bool(issues),cold_rejects=False,full_simulation_seconds=duration,check_seconds=gate_seconds,source=str(OUT/name/'evaluation.json'))
  receipt['cases'].append(row);save(OUT/'progress.json',receipt)
  print(name,'valid',row['full_simulation_passed'],'memory blocks',row['memory_rejects'],flush=True)
 rows=receipt['cases'];receipt['summary']=dict(cases=len(rows),invalid=sum(not r['full_simulation_passed'] for r in rows),valid=sum(r['full_simulation_passed'] for r in rows),caught_invalid=sum(r['memory_rejects'] and not r['full_simulation_passed'] for r in rows),false_rejections=sum(r['memory_rejects'] and r['full_simulation_passed'] for r in rows),scope_abstentions=sum(not r['memory_rejects'] for r in rows),avoided_full_simulations=sum(r['memory_rejects'] for r in rows))
 assert receipt['summary']['false_rejections']==0
 assert rows[0]['memory_rejects'] and rows[1]['memory_rejects']
 assert not rows[2]['memory_rejects'] and rows[2]['full_simulation_passed']
 assert not rows[3]['memory_rejects'] and rows[3]['full_simulation_passed']
 assert not rows[4]['memory_rejects']
 save(OUT/'result.json',receipt);print(json.dumps(receipt['summary']),flush=True)
if __name__=='__main__':main()
