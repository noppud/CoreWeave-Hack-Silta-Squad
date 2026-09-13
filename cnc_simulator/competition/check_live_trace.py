"""Read back fresh live stage outputs and verify candidate association."""
import json,os
from pathlib import Path
import weave
r=Path(__file__).parent;s=json.loads((r/'rehearsal-02/fresh-live-rehearsal.json').read_text());url=s['manifest']['telemetry']['url'];id=url.rsplit('/',1)[-1]
os.environ['WANDB_API_KEY']=os.environ.pop('COREWEAVE_WANDB_API_KEY');c=weave.init('silta/coreweave-hack-silta-squad')
root=c.get_call(id);rows=[]
for x in c.get_calls(filter={'parent_ids':[id]}):
 rows.append(dict(id=x.id,op=x.op_name,ended=x.ended_at is not None,output=x.output))
assert root.ended_at is not None and not root.exception
assert root.output['paired_signals']['paired_coverage'] is True
for row in rows:
 assert row['ended']
 if row['output']['stage']=='cam_planning':assert 'result' not in row['output']
(r/'rehearsal-02/trace-readback.json').write_text(json.dumps(dict(url=url,root_output=root.output,stages=rows),indent=2,default=str))
print('Verified',len(rows),'completed stages and paired signals')
