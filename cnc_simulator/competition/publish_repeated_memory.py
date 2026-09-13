"""Publish retained scores from the completed repeated model/simulator experiment."""
import json,os
from pathlib import Path
import weave
R=Path(__file__).with_name('repeated-memory-study');data=json.loads((R/'result.json').read_text());assert len(data['rows'])==12
rows=[]
for p in data['pairs']:
 arms={x['arm']:x for x in data['rows'] if x['part']==p['part'] and x['repetition']==p['repetition']}
 rows.append(dict(pair_id=p['part']+'-r'+str(p['repetition']),part=p['part'],repetition=p['repetition'],cold=arms['cold'],warm=arms['warm']))
os.environ['WANDB_API_KEY']=os.environ.pop('COREWEAVE_WANDB_API_KEY');project='silta/coreweave-hack-silta-squad';c=weave.init(project)
dataset=weave.Dataset(name='repeated-cam-memory-six-pairs',rows=rows);uri=weave.publish(dataset).uri();receipt=dict(dataset_uri=uri,protocol=data['protocol'],scope='Publication scores retained files from fresh 12-proposal experiment; this evaluation runtime is not simulator runtime.',evaluations=[])
for arm in ['cold','warm']:
 logger=weave.EvaluationLogger(name='repeated-cam-memory-'+arm,model={'name':arm,'proposal_model':'gpt-6-astra','memory_frozen':True},dataset=dataset,eval_attributes={'scope':receipt['scope']})
 for row in rows:
  record=row[arm];result=record.get('result',{}).get('result',{});available=bool(result)
  with logger.log_prediction(inputs={'part':row['part'],'repetition':row['repetition'],'target_sha256':record['target_sha256']},output=record,example_id=row['pair_id']) as pred:
   pred.log_score('result_available',available)
   if available:
    pred.log_score('geometry_pass',result['passed'])
    if result['passed']:pred.log_score('machining_seconds',result['estimated_time_seconds'])
 logger.log_summary({'protocol':data['protocol'],'cases':len(rows)},auto_summarize=True);c.flush();call=c.get_call(logger._evaluate_call.id)
 assert call.ended_at is not None and not call.exception
 receipt['evaluations'].append(dict(arm=arm,url=f'https://wandb.ai/{project}/r/call/{call.id}',readback_complete=True))
 (R/'weave-publication.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
