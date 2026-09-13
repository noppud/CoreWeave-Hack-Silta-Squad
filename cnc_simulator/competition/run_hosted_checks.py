"""Execute frozen exact-failure check inputs in hosted isolation and trace real work."""
import json,os,sys,hashlib
from pathlib import Path
import cwsandbox,weave
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camloop.indexed.learning import geometry_key
from camloop.indexed.runner import read
from camloop.common import file_hash
OUT=Path(__file__).resolve().parent
key=os.environ.pop('COREWEAVE_WANDB_API_KEY');os.environ['WANDB_API_KEY']=key
project='silta/coreweave-hack-silta-squad';client=weave.init(project)
audit=read(OUT/'failure-memory-eval/result.json');memory=read(OUT/'failure-memory-eval/frozen-memory.json')
rows=[]
for row in audit['cases']:
 path=Path(row['source']).parent/'plan.json';plan=read(path)
 # Audit persisted contract hash; derive trusted applicability key from the same evaluated contract.
 part='03-bearing-block' if row['name']=='other-valid-part' else '02-hydraulic-manifold'
 job=read(ROOT/'workspace-loop-demo/parts'/part/'job.json')
 if row['name']=='changed-fixture-scope':
  job['plan']['fixtures'][0]['min'][0]-=300;job['plan']['fixtures'][0]['max'][0]-=300
 rows.append(dict(name=row['name'],geometry_key=geometry_key(job,row['strategy']),full_simulation_passed=row['full_simulation_passed'],plan_sha256=file_hash(path)))
payload=dict(rules=memory['learned_checks'],cases=rows)
code='''import json
from pathlib import Path
x=json.loads(Path('/tmp/input.json').read_text())
keys={r['geometry_key'] for r in x['rules']}
rows=[dict(name=c['name'],rejected=c['geometry_key'] in keys,full_simulation_passed=c['full_simulation_passed']) for c in x['cases']]
assert not any(r['rejected'] and r['full_simulation_passed'] for r in rows)
Path('/tmp/output.json').write_text(json.dumps(rows))
'''
@weave.op(name='programmatic_hosted_failure_checks',enable_code_capture=False)
def execute(inputs):
 auth=cwsandbox.AuthHeaders(headers={'x-wandb-api-key':key},strategy='wandb_api_key')
 with cwsandbox.Sandbox.run(auth=auth,placement_mode='serverless',container_image='python:3.11-slim',max_lifetime_seconds=120,request_timeout_seconds=30,resources={'cpu':'1','memory':'512Mi'},network=cwsandbox.NetworkOptions(deny_egress=True,deny_ingress=True),environment_variables={},tags=['silta-frozen-check-evaluation']) as box:
  box.write_file('/tmp/check.py',code.encode(),timeout_seconds=20).result()
  box.write_file('/tmp/input.json',json.dumps(payload).encode(),timeout_seconds=20).result()
  p=box.exec(['python','-I','/tmp/check.py'],timeout_seconds=20).result()
  if p.returncode:raise RuntimeError('Hosted check execution failed')
  result=json.loads(box.read_file('/tmp/output.json',timeout_seconds=20).result())
  return dict(cases=result,signals={'false_rejections':sum(r['rejected'] and r['full_simulation_passed'] for r in result),'caught_invalid':sum(r['rejected'] and not r['full_simulation_passed'] for r in result),'full_simulations_avoided':sum(r['rejected'] for r in result)},scope='Actual hosted execution of exact applicability membership. Geometry identity computed by trusted host; no guest credentials; no generalization claim.')
inputs=dict(check_sha256=hashlib.sha256(code.encode()).hexdigest(),memory_sha256=file_hash(OUT/'failure-memory-eval/frozen-memory.json'),cases=rows,network='deny ingress and egress')
result,call=execute.call(inputs)
client.flush();remote=client.get_call(call.id)
if remote.ended_at is None or remote.exception:raise RuntimeError('Trace readback incomplete')
receipt=dict(result=result,inputs=inputs,trace_url=f'https://wandb.ai/{project}/r/call/{call.id}',readback_complete=True)
(OUT/'hosted-checks.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
