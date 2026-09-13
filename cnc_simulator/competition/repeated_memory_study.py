"""Repeated, alternating-order cold/warm study with a frozen one-part memory."""
import sys,json,copy,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camloop.astra import Astra
from camloop.indexed.runner import read,ask_candidate
from camloop.indexed.cam import BASELINE,verify_job
from camloop.common import save,file_hash
from camloop.live_evidence import movement_identity
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).with_name('repeated-memory-study');STUDY=ROOT/'workspace-loop-demo'
OUT.mkdir(exist_ok=True)
source=STUDY/'runs/02-hydraulic-manifold/manifest.json';memory=read(source)['loaded_memory']
assert [x['part'] for x in memory['episodes']]==['01-actuator-housing']
save(OUT/'frozen-memory.json',memory)
save(OUT/'protocol.json',dict(parts=['03-bearing-block','04-trunnion-cage'],repetitions=3,order='Alternating cold/warm within pair, reversed by part index',memory_sha256=file_hash(OUT/'frozen-memory.json'),scope='New model proposals and simulations on two existing benchmark parts, frozen memory from actuator only. No within-study updates. Selected-part transfer experiment, not unseen-part or physical validation.',objective='Machining seconds only among passing paired plans. All failures and inference errors retained.'))
roles=Astra(OUT/'evidence',timeout=240);rows=[]
for repetition in range(3):
 for pi,part in enumerate(['03-bearing-block','04-trunnion-cage']):
  job=read(STUDY/'parts'/part/'job.json');verify_job(job);reference=read(STUDY/'runs'/part/'manifest.json')['reference']['result']
  order=['cold','warm'] if (repetition+pi)%2==0 else ['warm','cold']
  for arm in order:
   name=f'{part}-r{repetition+1}-{arm}';path=OUT/name
   if (path/'record.json').exists():row=read(path/'record.json')
   else:
    print('START',name,flush=True);started=time.time()
    try:
     result=ask_candidate(roles,job,BASELINE,copy.deepcopy(reference),copy.deepcopy(memory) if arm=='warm' else None,path)
     row=dict(case=name,part=part,repetition=repetition+1,arm=arm,order=order,result=result,wall_seconds=time.time()-started,movement_sha256=movement_identity(read(path/'plan.json')),target_sha256=job['target_sha256'])
    except Exception as e:
     path.mkdir(exist_ok=True);row=dict(case=name,part=part,repetition=repetition+1,arm=arm,order=order,error=str(e),wall_seconds=time.time()-started,target_sha256=job['target_sha256'])
    save(path/'record.json',row)
   rows.append(row);save(OUT/'progress.json',rows);print('DONE',name,row.get('result',{}).get('result',{}).get('passed'),flush=True)
summary=[]
for part in ['03-bearing-block','04-trunnion-cage']:
 for rep in range(1,4):
  pair={x['arm']:x for x in rows if x['part']==part and x['repetition']==rep};a=pair['cold'].get('result',{}).get('result',{});b=pair['warm'].get('result',{}).get('result',{})
  coverage=a.get('passed') is True and b.get('passed') is True
  summary.append(dict(part=part,repetition=rep,cold_passed=a.get('passed'),warm_passed=b.get('passed'),paired_coverage=coverage,cold_seconds=a.get('estimated_time_seconds') if a.get('passed') else None,warm_seconds=b.get('estimated_time_seconds') if b.get('passed') else None,warm_minus_cold_seconds=b['estimated_time_seconds']-a['estimated_time_seconds'] if coverage else None))
save(OUT/'result.json',dict(protocol=read(OUT/'protocol.json'),rows=rows,pairs=summary));print('COMPLETE',json.dumps(summary),flush=True)
