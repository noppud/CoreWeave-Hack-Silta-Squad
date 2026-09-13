"""Exercise the running live server with real PDFs and real Astra/simulation calls."""
import json,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:2744';checks=[]
def call(path,body=None,filename='test.pdf'):
 r=urllib.request.Request(BASE+path,data=body,headers={'Origin':BASE,'Content-Type':'application/pdf','X-Filename':filename})
 try:
  with urllib.request.urlopen(r,timeout=20) as f:return f.status,json.load(f)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def wait(id,statuses,timeout=600):
 end=time.time()+timeout
 while time.time()<end:
  _,s=call('/api/jobs/'+id)
  if s['status'] in statuses:return s
  time.sleep(1)
 raise RuntimeError('Job timed out: '+id)
code,_=call('/api/jobs',b'not a pdf');assert code==400;checks.append('Non-PDF upload rejected')
code,second=call('/api/jobs',(ROOT/'output/pdf/instrument-pocket.pdf').read_bytes(),'instrument-pocket.pdf');assert code==201
code,unsupported=call('/api/jobs',(ROOT.parent/'output/pdf/umc-actuator-housing.pdf').read_bytes(),'unsupported-islands.pdf');assert code==201
s=wait(unsupported['id'],{'needs_input','error'});assert s['status']=='needs_input';checks.append('Unsupported side/island drawing stops before CAM')
s=wait(second['id'],{'review','error','needs_input'});assert s['status']=='review',s
# First browser-driven run must finish before starting the second live simulation.
end=time.time()+600
while time.time()<end:
 _,jobs=call('/api/jobs');first=next((j for j in jobs if j['filename']=='bearing-pocket.pdf'),None)
 if first and first['status']=='completed':break
 if first and first['status']=='error':raise RuntimeError(first['message'])
 time.sleep(1)
else:raise RuntimeError('Browser-driven first job not completed')
checks.append('Browser PDF run completed with a verified plan')
code,_=call('/api/jobs/'+second['id']+'/run',b'{}');assert code==200
code,_=call('/api/jobs/'+second['id']+'/run',b'{}');assert code==400;checks.append('Duplicate run rejected')
s=wait(second['id'],{'completed','failed','error'},900);assert s['status']=='completed',s
assert s['manifest']['best']['result']['passed'];checks.append('Second distinct PDF completed with a verified plan')
assert s['memory_version']==first['memory_version']+1;checks.append('Second run persisted the next memory version')
for j in [first,s]:
 assert j['manifest']['target_sha256']
 assert j['playback']
 assert all('judge' not in a for a in j['manifest']['attempts'] if not a['result']['passed'])
checks.append('Failed candidates excluded from timing judge; both actual replays exported')
result={'passed':True,'checks':checks,'jobs':[first['id'],second['id']],'unsupported_job':unsupported['id']}
(ROOT/'workspace-live/integration-test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
