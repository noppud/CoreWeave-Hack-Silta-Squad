"""Read-only readiness checks for the exact live job and local demo assets."""
import argparse,json,hashlib,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--job',default='3f1703103c1f');p.add_argument('--output',type=Path);a=p.parse_args();checks=[]
 def check(name,fn):
  try:detail=fn();checks.append(dict(name=name,passed=True,detail=detail))
  except Exception as e:checks.append(dict(name=name,passed=False,error=str(e)))
 def machine():
  f=ROOT/'viewer/dist/assets/umc750.json';m=json.loads(f.read_text());meshes=m['machine']['meshes'];assert len(meshes)>0
  for x in meshes:
   assert len(x['positions'])%3==0 and len(x['indices'])%3==0 and max(x['indices'],default=0)<len(x['positions'])//3
  for name,expected in m['provenance']['files'].items():
   assert hashlib.sha256((ROOT/'assets/umc750'/name).read_bytes()).hexdigest()==expected, 'Machine source changed: '+name
  return dict(meshes=len(meshes),groups=sorted({x['group'] for x in meshes}),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),provenance=m['provenance'])
 def live():
  with urllib.request.urlopen(f'http://127.0.0.1:2744/api/jobs/{a.job}',timeout=10) as r:s=json.load(r)
  assert s['status']=='completed';m=s['manifest'];assert m['best']['result']['passed'];assert m.get('telemetry',{}).get('readback_complete') is True;target=json.loads((Path(m['best']['path'])/'plan.json').read_text())['target']['path'];assert hashlib.sha256(Path(target).read_bytes()).hexdigest()==m['target_sha256']
  return dict(job=a.job,seconds=m['best']['result']['estimated_time_seconds'],memory_version=s['memory_version'],target_unchanged=True,trace_readback=m.get('telemetry',{}).get('readback_complete',False))
 def playback():
  root=ROOT/'viewer/dist/assets/study/workspace-live'/a.job;d=json.loads((root/'playback.json').read_text());s=json.loads((root/'surfaces.json').read_text());assert d['result']['passed'] and d['duration']>0 and len(s['frames'])>0
  if s.get('binary'):
   length=(root/s['binary']).stat().st_size
   for f in s['frames']:assert f['offset']>=0 and f['offset']+f['vertex_values']*8+f['index_values']*4<=length
  return dict(frames=len(s['frames']),duration=d['duration'])
 def film():
  r=json.loads((Path(__file__).with_name('film')/'receipt.json').read_text());f=Path(__file__).with_name('film')/'silta-demo.mp4';assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'] and r['seconds']<120 and r['decode_check']=='passed';return dict(seconds=r['seconds'],sha256=r['sha256'])
 for name,fn in [('Downloaded machine meshes',machine),('Completed job and frozen target',live),('Stock-removal playback buffers',playback),('Under-two-minute verified film',film)]:check(name,fn)
 result=dict(ready=all(c['passed'] for c in checks),checks=checks,scope='Local artifact/readiness checks; not a new machining simulation or judge-access verification.')
 if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2));raise SystemExit(0 if result['ready'] else 1)
if __name__=='__main__':main()
