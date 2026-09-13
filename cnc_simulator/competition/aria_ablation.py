"""Execute ARIA-recommended matched cleanup/stepover ablation; no rule promotion."""
import sys,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camloop.indexed.runner import read,evaluate
from camloop.common import save,file_hash
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).with_name('aria-ablation');STUDY=ROOT/'workspace-loop-demo'
OUT.mkdir(exist_ok=True)
rows=[]
for part,steps in [('02-hydraulic-manifold',[.708,.75,.95]),('04-trunnion-cage',[.75,.83,.95])]:
 job=read(STUDY/'parts'/part/'job.json');base=read(STUDY/'runs'/part/'manifest.json')['best']['strategy']
 for step in steps:
  for cleanup in [False,True]:
   name=f'{part}-{step}-{int(cleanup)}';p=OUT/name
   if (p/'evaluation.json').exists():r=read(p/'evaluation.json')
   else:
    s=copy.deepcopy(base);s.update(stepover_fraction=step,junction_cleanup=cleanup)
    print('EVALUATING',name,flush=True);r=evaluate(job,s,p)
   rows.append(dict(part=part,stepover=step,cleanup=cleanup,passed=r['result']['passed'],seconds=r['result'].get('estimated_time_seconds') if r['result']['passed'] else None,issues=r['result']['issues'],source=str(p/'evaluation.json')))
   save(OUT/'progress.json',rows);print(name,rows[-1]['passed'],rows[-1]['seconds'],flush=True)
save(OUT/'result.json',dict(scope='ARIA-recommended selected 12-case ablation; same fixed best strategy except stepover and cleanup. No held-out claim or automatic rule promotion.',review_sha256=file_hash(Path(__file__).with_name('aria-review.md')),rows=rows))
