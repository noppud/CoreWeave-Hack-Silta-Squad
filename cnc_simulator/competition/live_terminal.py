"""Read-only terminal view of persisted real jobs, with an optional evidence tape."""
import argparse,json,time,urllib.request,urllib.error
from pathlib import Path

def watch(job, *, port=2744, tape=None, fetch=None, sleep=time.sleep, emit=print, max_failures=5):
    url=f'http://127.0.0.1:{port}/api/jobs/{job}'
    def request():
        with urllib.request.urlopen(url,timeout=10) as response:return json.load(response)
    fetch=fetch or request
    last=None;seen=set();start=time.monotonic();failures=0
    def out(kind,value):
        text=value if isinstance(value,str) else json.dumps(value,indent=2)
        emit('\n'+kind.upper()+'\n'+text,flush=True)
        if tape:
            with Path(tape).open('a') as f:f.write(json.dumps(dict(elapsed=time.monotonic()-start,kind=kind,value=value))+'\n')
    out('source',url+' · actual local job state')
    while True:
        try:s=fetch()
        except (OSError,ValueError) as error:
            failures+=1
            out('connection',dict(state='temporarily unavailable',consecutive_failures=failures,error=str(error)))
            if failures>=max_failures:
                out('observation stopped','Cannot read the job. Its execution status is unverified; no job was restarted.');return 1
            sleep(.5);continue
        if failures:out('connection','Restored; continuing the same job.');failures=0
        m=s.get('manifest') or {}
        if s['status']!=last:out('stage',s['status']+' · '+s.get('message',''));last=s['status']
        for key,value in [('frozen target',s.get('target_sha256')),('reviewed dimensions',s.get('spec')),('generated CAM',s.get('proposal')),('memory loaded',m.get('loaded_memory_version'))]:
            identity=(key,json.dumps(value,sort_keys=True))
            if value is not None and identity not in seen:seen.add(identity);out(key,value)
        for row in m.get('attempts',[]):
            key=('attempt',row['index'])
            # A persisted proposal/check can precede the simulation result.
            result=row.get('result')
            if result is not None and key not in seen:
                seen.add(key);out('verification',dict(candidate=row['index']+1,stage=row['stage'],passed=result['passed'],issues=result['issues'],seconds=result.get('estimated_time_seconds'),artifact=row['path']))
            if row.get('judge') and ('judge',row['index']) not in seen:
                seen.add(('judge',row['index']));out('timing judge',row['judge']['value'])
        if s['status'] in ['completed','failed','error','needs_input']:
            out('result',dict(status=s['status'],memory_saved=s.get('memory_version'),evidence=m.get('loop_evidence'),manifest=f'/api/jobs/{job}/manifest.json'));return 0 if s['status']=='completed' else 1
        if s['status']=='review':
            out('action','Review and confirm dimensions in the application before CAM starts. This viewer cannot approve a drawing.');return 0
        sleep(.5)

def main():
    p=argparse.ArgumentParser();p.add_argument('job');p.add_argument('--port',type=int,default=2744);p.add_argument('--tape',type=Path);a=p.parse_args()
    raise SystemExit(watch(a.job,port=a.port,tape=a.tape))
if __name__=='__main__':main()
