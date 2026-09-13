import json,time,urllib.request,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=Path(__file__).parent
base='http://127.0.0.1:2744'
if len(sys.argv)>1:
 out=out/sys.argv[1];out.mkdir(exist_ok=True)
drawing=sys.argv[2] if len(sys.argv)>2 else 'instrument-pocket'
expected={'instrument-pocket':[72,56,24],'bearing-pocket':[64,52,24]}[drawing]
def req(path,data=None):
 headers={'Origin':base,'Content-Type':'application/pdf','X-Filename':drawing+'.pdf'}
 with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=30) as r:return json.load(r)
r=req('/api/jobs',(root/'output/pdf'/(drawing+'.pdf')).read_bytes());id=r['id'];(out/'traced-job-id.txt').write_text(id);print('JOB',id,flush=True)
for _ in range(240):
 s=req('/api/jobs/'+id)
 if s['status'] in ['review','error','needs_input']:break
 time.sleep(1)
if s['status']!='review':raise RuntimeError(s['message'])
spec=s['spec'];assert spec['stock_dimensions_mm']==expected
print('REVIEWED',json.dumps(spec),flush=True)
req('/api/jobs/'+id+'/run',b'{}')
subprocess.run([sys.executable,str(Path(__file__).with_name('live_terminal.py')),id,'--tape',str(out/'fresh-live-terminal.jsonl')],check=True)
s=req('/api/jobs/'+id)
if s['status']!='completed':raise RuntimeError(s['message'])
if not s['manifest'].get('telemetry',{}).get('readback_complete'):raise RuntimeError('Live trace not verified')
(out/'fresh-live-rehearsal.json').write_text(json.dumps(s,indent=2));print('REHEARSAL VERIFIED',flush=True)
