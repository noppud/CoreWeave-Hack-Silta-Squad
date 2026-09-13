import os,json
from pathlib import Path
import weave
root=Path(__file__).resolve().parent;r=json.loads((root/'failure-memory-eval/result.json').read_text())
os.environ['WANDB_API_KEY']=os.environ.pop('COREWEAVE_WANDB_API_KEY')
project='silta/coreweave-hack-silta-squad';c=weave.init(project)
data=weave.Dataset(name='fresh-failure-memory-counterexamples',rows=r['cases']);uri=weave.publish(data).uri();receipt={'dataset_uri':uri,'scope':r['scope'],'evaluations':[]}
for arm in ['cold','memory']:
 e=weave.EvaluationLogger(name='fresh-failure-check-'+arm,model={'name':arm,'memory_sha256':r['memory_sha256'] if arm=='memory' else None,'implementation':r['implementation']},dataset=data)
 for row in r['cases']:
  rejected=row[arm+'_rejects']
  with e.log_prediction(inputs={'case':row['name'],'contract_sha256':row['contract_sha256']},output={'rejected':rejected,'full_simulation_passed':row['full_simulation_passed']},example_id=row['name']) as p:
   p.log_score('caught_invalid',rejected and not row['full_simulation_passed'])
   p.log_score('false_rejection',rejected and row['full_simulation_passed'])
   p.log_score('full_simulation_avoided',rejected)
 e.log_summary({'scope':r['scope'],'summary':r['summary'] if arm=='memory' else {'caught_invalid':0,'false_rejections':0,'avoided_full_simulations':0}},auto_summarize=True);c.flush()
 call=c.get_call(e._evaluate_call.id)
 if call.exception or call.ended_at is None:raise RuntimeError('Weave readback incomplete')
 receipt['evaluations'].append({'arm':arm,'url':f'https://wandb.ai/{project}/r/call/{call.id}','readback_complete':True})
 (root/'failure-eval-publication.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
