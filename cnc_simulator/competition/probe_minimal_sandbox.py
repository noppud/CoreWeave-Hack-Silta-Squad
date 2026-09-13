"""Read team access and execute one bounded hosted-sandbox smoke check."""
import os,json,time
from pathlib import Path
import wandb,cwsandbox
key=os.environ.pop('COREWEAVE_WANDB_API_KEY')
receipt={'checked_at':time.time(),'entity':'silta','project':'coreweave-hack-silta-squad'}
try:
 api=wandb.Api(api_key=key,timeout=30)
 runs=api.runs('silta/coreweave-hack-silta-squad',per_page=3)
 receipt['wandb']={'accessible':True,'recent_runs':[{'id':r.id,'state':r.state} for r in list(runs)[:3]]}
except Exception as e:receipt['wandb']={'accessible':False,'error':str(e).replace(key,'[redacted]')[:500]}
try:
 auth=cwsandbox.AuthHeaders(headers={'x-wandb-api-key':key,'x-wandb-sdk-version':wandb.__version__},strategy='wandb_api_key')
 with cwsandbox.Sandbox.run(auth=auth,placement_mode='serverless',container_image='python:3.11-slim',max_lifetime_seconds=120,request_timeout_seconds=30,resources={'cpu':'1','memory':'512Mi'},network=cwsandbox.NetworkOptions(deny_egress=True,deny_ingress=True),environment_variables={},tags=['silta-competition-smoke']) as box:
  result=box.exec(['python','-I','-c','import json; print(json.dumps({"isolated_execution": True, "sum": sum(range(10))}))'],timeout_seconds=20).result()
  receipt['sandbox']={'available':result.returncode==0,'returncode':result.returncode,'stdout':str(result.stdout)[:500]}
except Exception as e:receipt['sandbox']={'available':False,'error':str(e).replace(key,'[redacted]')[:800]}
p=Path(__file__).with_name('sponsor-minimal-access.json');p.write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
