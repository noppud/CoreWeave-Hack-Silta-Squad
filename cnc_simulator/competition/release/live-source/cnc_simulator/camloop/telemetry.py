"""Optional application-stage Weave traces; never changes verification decisions."""
import os
from .signals import verification_signals,paired_signals
class Trace:
 def __init__(self,job):
  self.client=None;self.root=None;self.stage=None;self.error=None;self.url=None;self.stage_name=None;self.stage_attempt=0
  project=os.environ.get('CAMLOOP_WEAVE_PROJECT')
  if not project:return
  try:
   import weave
   self.client=weave.init(project)
   self.root=self.client.create_call('programmatic_live_job',inputs={'job':job,'engine':'bounded-cncsim'},attributes={'scope':'Actual live job; indexed 3+2, 1 mm cells, 3 mm tolerance'},use_stack=False)
   self.url=f'https://wandb.ai/{project}/r/call/{self.root.id}'
  except Exception as e:self.error=type(e).__name__
 def advance(self,name,manifest):
  if not self.client or self.error:return
  try:
   self._finish_stage(manifest)
   self.stage_name=name;self.stage_attempt=len(manifest['attempts'])
   self.stage=self.client.create_call('programmatic_'+name,inputs={'job':manifest['id'],'attempts_completed':len(manifest['attempts']),'target_sha256':manifest['target_sha256'],'memory_version':manifest['loaded_memory_version']},parent=self.root,use_stack=False)
  except Exception as e:self.error=type(e).__name__
 def _finish_stage(self,m):
  if self.stage:
   name=self.stage_name
   output={'stage':name,'attempts_completed':len(m['attempts'])}
   if name=='reference_simulation':output['reference']=m.get('reference')
   elif name in ('simulating','checks') and len(m['attempts'])>self.stage_attempt:
    row=m['attempts'][self.stage_attempt]
    output.update(candidate_index=row['index'],result=row['result'],signals=verification_signals(row['result']))
   elif name=='cam_planning':output['proposal']=m.get('current_candidate')
   elif name=='judging' and m['attempts']:
    row=m['attempts'][-1];output.update(candidate_index=row['index'],judge=row.get('judge'))
   self.client.finish_call(self.stage,output=output)
   self.stage=None
 def finish(self,m):
  if not self.client or self.error:return {'enabled':bool(self.client),'error':self.error}
  try:
   self._finish_stage(m)
   self.client.finish_call(self.root,output={'status':m['status'],'loop_evidence':m.get('loop_evidence'),'paired_signals':paired_signals(m['reference']['result'],m['best']['result']) if m.get('reference') and m.get('best') else None,'target_sha256':m['target_sha256'],'stop_reason':m.get('stop_reason'),'error':m.get('error')})
   self.client.flush();r=self.client.get_call(self.root.id)
   return {'enabled':True,'url':self.url,'readback_complete':r.ended_at is not None and not r.exception}
  except Exception as e:return {'enabled':True,'url':self.url,'readback_complete':False,'error':type(e).__name__}
