from camloop.telemetry import Trace

def test_disabled_tracing_never_requires_credentials(monkeypatch):
 monkeypatch.delenv('CAMLOOP_WEAVE_PROJECT',raising=False)
 t=Trace('test');t.advance('checks',{})
 assert t.finish({})=={'enabled':False,'error':None}

def test_broken_tracing_does_not_change_verdict():
 class Broken:
  def create_call(self,*args,**kwargs):raise RuntimeError('offline')
 t=Trace.__new__(Trace);t.client=Broken();t.root=None;t.stage=None;t.error=None;t.url=None
 m={'id':'test','attempts':[],'target_sha256':'fixed','loaded_memory_version':0}
 t.advance('checks',m)
 assert t.error=='RuntimeError'
 assert m['target_sha256']=='fixed'
 assert t.finish(m)['error']=='RuntimeError'

def test_stage_does_not_claim_previous_candidate_result():
 class Client:
  def __init__(self):self.outputs=[]
  def finish_call(self,call,output):self.outputs.append(output)
 t=Trace.__new__(Trace);t.client=Client();t.stage=object();t.stage_name='simulating';t.stage_attempt=1
 m={'attempts':[{'index':0,'result':{'passed':True}}]}
 t._finish_stage(m)
 assert 'result' not in t.client.outputs[-1]
 t.stage=object();t.stage_name='cam_planning';m['current_candidate']={'index':1,'proposal':{'strategy':'new'}}
 t._finish_stage(m)
 assert t.client.outputs[-1]['proposal']['index']==1
 assert 'result' not in t.client.outputs[-1]
