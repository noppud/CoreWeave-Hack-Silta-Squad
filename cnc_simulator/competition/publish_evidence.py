"""Publish retained programmatic-CAM evidence, explicitly not a fresh simulation."""
import json,os,hashlib,time
from pathlib import Path
import weave
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def collect():
 rows=[]
 for p in sorted((ROOT/'workspace-loop-demo/runs').glob('*/manifest.json')):
  m=read(p);job=read(ROOT/'workspace-loop-demo/parts'/m['id']/'job.json')
  if sha(job['plan']['target']['path'])!=m['target_sha256']:raise ValueError('Target changed: '+m['id'])
  def record(r):
   if r is None:return None
   return dict(passed=r['result']['passed'],seconds=r['result'].get('estimated_time_seconds'),issues=r['result']['issues'],strategy=r['strategy'])
  rows.append(dict(part=m['id'],target_sha256=m['target_sha256'],source_sha256=sha(p),reference=record(m.get('reference')),best=record(m.get('best')),cold=record(m.get('paired_audit',{}).get('cold')),warm=record(m.get('paired_audit',{}).get('warm')),attempts=[record(a) for a in m['attempts']],loaded_memory_version=m.get('loaded_memory_version'),saved_memory_version=m.get('saved_memory_version')))
 return rows
if __name__=='__main__':
 rows=collect();scope='Retained five-part indexed 3+2 evidence. Not new simulation. 1 mm cells / 3 mm tolerance. Four one-sample cold/warm comparisons; no generalization claim.'
 os.environ['WANDB_API_KEY']=os.environ.pop('COREWEAVE_WANDB_API_KEY')
 project='silta/coreweave-hack-silta-squad';client=weave.init(project)
 data=weave.Dataset(name='programmatic-cam-five-part-evidence',rows=rows);uri=weave.publish(data).uri();receipt=dict(dataset_uri=uri,scope=scope,evaluations=[])
 for arm in ['reference','best','cold','warm']:
  logger=weave.EvaluationLogger(name='programmatic-cam-'+arm,model={'name':arm,'engine':'bounded-cncsim','scope':scope},dataset=data,eval_attributes={'scope':scope,'objective':'machining seconds on passing plans only'})
  count=0;valid=0
  for row in rows:
   result=row[arm]
   if result is None:continue
   count+=1;valid+=int(result['passed'])
   with logger.log_prediction(inputs={'part':row['part'],'target_sha256':row['target_sha256'],'source_sha256':row['source_sha256']},output=result,example_id=row['part']) as prediction:
    prediction.log_score('geometry_pass',result['passed'])
    if result['passed']:prediction.log_score('machining_seconds',result['seconds'])
  logger.log_summary({'cases':count,'passing':valid,'scope':scope},auto_summarize=True);client.flush()
  call=client.get_call(logger._evaluate_call.id)
  if call.ended_at is None or call.exception:raise RuntimeError('Evaluation readback not complete')
  receipt['evaluations'].append(dict(arm=arm,url=f'https://wandb.ai/{project}/r/call/{call.id}',readback_complete=True))
  Path(__file__).with_name('weave-publication.json').write_text(json.dumps(receipt,indent=2))
 print(json.dumps(receipt,indent=2))
