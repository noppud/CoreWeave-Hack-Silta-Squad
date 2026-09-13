"""Publish the retained-artifact audit, explicitly separate from machining runs."""
import hashlib,json,os
from pathlib import Path
import weave
root=Path(__file__).parent;path=root/'memory-chain-audit.json';report=json.loads(path.read_text())
os.environ['WANDB_API_KEY']=os.environ.pop('COREWEAVE_WANDB_API_KEY')
client=weave.init('silta/coreweave-hack-silta-squad')
call=client.create_call('audit_live_memory_persistence',inputs={'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'jobs':[r['job'] for r in report['jobs']]},attributes={'scope':'Read-only audit of retained local artifacts. No model, machining simulation or native Signals execution.'},use_stack=False)
client.finish_call(call,output=report);client.flush();actual=client.get_call(call.id)
assert actual.ended_at is not None and not actual.exception
assert actual.output['persistence_verified_jobs']==9 and actual.output['failed_checks']==0
receipt=dict(url=f'https://wandb.ai/silta/coreweave-hack-silta-squad/r/call/{call.id}',readback_complete=True,report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),scope='Publication and readback of retained-artifact persistence audit.')
(root/'memory-chain-weave.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
