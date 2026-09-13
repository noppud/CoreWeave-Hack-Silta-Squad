"""Fresh same-part simulation with nested Weave gate and result signals."""
import sys,os,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import weave
from camloop.indexed.runner import read,evaluate
from camloop.common import save,file_hash
os.environ['WANDB_API_KEY']=os.environ.pop('COREWEAVE_WANDB_API_KEY')
project='silta/coreweave-hack-silta-squad';client=weave.init(project);out=ROOT/'competition/live-verification';out.mkdir(exist_ok=True)
job=read(ROOT/'workspace-live/parts/02de8c83d5bd/job.json');manifest=read(ROOT/'workspace-live/runs/02de8c83d5bd/manifest.json')
@weave.op(name='programmatic_fixed_verification',enable_code_capture=False)
def verify(strategy,case):
 row=evaluate(job,strategy,out/case)
 return dict(passed=row['result']['passed'],issues=row['result']['issues'],seconds=row['result'].get('estimated_time_seconds'),time_breakdown=row['result'].get('time_breakdown'),stage=row['stage'],artifact=str(out/case/'evaluation.json'))
@weave.op(name='programmatic_verification_signals',enable_code_capture=False)
def signals(reference,candidate):
 both=reference['passed'] and candidate['passed']
 return dict(geometry_pass=candidate['passed'],paired_coverage=both,paired_reduction_percent=100*(reference['seconds']-candidate['seconds'])/reference['seconds'] if both else None,uncertain_issue_count=sum(i.get('code')=='uncertain' for i in candidate['issues']),target_unchanged=file_hash(job['plan']['target']['path'])==job['target_sha256'])
@weave.op(name='programmatic_fresh_verification_job',enable_code_capture=False)
def run(part,target_sha256):
 a=verify(manifest['reference']['strategy'],'reference');b=verify(manifest['best']['strategy'],'candidate')
 return dict(reference=a,candidate=b,signals=signals(a,b),scope='Fresh simulations of retained Astra-generated strategy and fixed reference; no new model proposal. 1 mm cells, 3 mm tolerance.')
result,call=run.call(job['id'],job['target_sha256']);client.flush();remote=client.get_call(call.id)
if remote.ended_at is None or remote.exception:raise RuntimeError('Trace not finalized')
save(out/'receipt.json',dict(result=result,trace_url=f'https://wandb.ai/{project}/r/call/{call.id}',readback_complete=True));print(json.dumps(result,indent=2))
