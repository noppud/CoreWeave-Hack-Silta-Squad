"""Predeclared resolution-only follow-up; never rewrites original verdicts."""
import json,time,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cncsim import simulate
from camloop.common import save,file_hash
ROOT=Path(__file__).parent;OUT=ROOT/'resolution-refinement';CASES=['02-hydraulic-manifold-0.708-0','04-trunnion-cage-0.95-0']
def main():
 OUT.mkdir(exist_ok=False)
 contracts=[]
 for name in CASES:
  source=ROOT/'aria-ablation'/name;plan=json.loads((source/'plan.json').read_text());original=json.loads((source/'simulation/result.json').read_text())
  refined={**plan,'resolution_mm':.5,'max_cells':4_000_000};assert all(refined[k]==v for k,v in plan.items() if k not in ['resolution_mm','max_cells'])
  directory=OUT/name;directory.mkdir();save(directory/'plan.json',refined)
  contracts.append(dict(case=name,source=str(source),source_plan_sha256=file_hash(source/'plan.json'),refined_plan_sha256=file_hash(directory/'plan.json'),target_sha256=file_hash(plan['target']['path']),original_result=original))
 save(OUT/'pre-registration.json',dict(created_at=time.time(),cases=contracts,changes={'resolution_mm':.5,'max_cells':4_000_000},purpose='Resolve two previously uncertain cases. No CAM optimization or changed geometric tolerance. All outcomes retained.'))
 rows=[]
 for contract in contracts:
  name=contract['case'];directory=OUT/name;plan=json.loads((directory/'plan.json').read_text());tick=[0]
  def progress(s):
   if time.monotonic()-tick[0]>10:
    print(name,'MOVE',s['move'],'/',len(plan['moves']),flush=True);tick[0]=time.monotonic()
  print('START',name,flush=True);start=time.monotonic()
  result=simulate(plan,output_dir=directory/'simulation',snapshot_stride=len(plan['moves'])+1,on_step=progress)
  assert file_hash(plan['target']['path'])==contract['target_sha256']
  assert abs(result['estimated_time_seconds']-contract['original_result']['estimated_time_seconds'])<1e-9
  row=dict(**contract,result=result,wall_seconds=time.monotonic()-start);rows.append(row);save(OUT/'result.json',rows)
  print('RESULT',name,result['passed'],result['verification'],result['issues'],flush=True)
 print('COMPLETE',flush=True)
if __name__=='__main__':main()
