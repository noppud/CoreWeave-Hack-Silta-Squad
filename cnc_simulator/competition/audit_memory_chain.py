"""Audit actual saved memory bytes and the context supplied to the next CAM call."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'workspace-live'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(directory,work=WORK):
 m=read(directory/'manifest.json');v=m['loaded_memory_version'];saved=m.get('saved_memory_version')
 checks={};sources={}
 def check(name,path,predicate):
  sources[name]=str(path)
  if not path.exists():checks[name]=None;return
  try:checks[name]=bool(predicate(path))
  except (KeyError,ValueError,TypeError):checks[name]=False
 check('loaded_version_bytes',work/'memory/versions'/f'{v:04d}.json',lambda p:sha(p)==m['loaded_memory_sha256'] and read(p)==m['loaded_memory'])
 if m['attempts']:
  evidence=Path(m['attempts'][0]['evidence']);request=evidence.with_name(evidence.name.replace('.response.json','.request.json'))
  check('memory_reached_first_cam_request',request,lambda p:read(p)['context']['retained_memory']==m['loaded_memory'])
 if saved is not None:
  check('saved_episode',work/'memory/versions'/f'{saved:04d}.json',lambda p:read(p)['version']==v+1 and read(p)['episodes'][-1]['part']==m['id'] and len(read(p)['episodes'])==len(m['loaded_memory']['episodes'])+1)
  commit=work/'memory'/f'commit-{saved:04d}.json'
  check('saved_commit_readback',commit,lambda p:read(p)['read_back_verified'] and read(p)['sha256']==sha(work/'memory/versions'/f'{saved:04d}.json') and read(p)['source_manifest_sha256']==sha(Path(read(p)['source_snapshot'])))
  check('job_saved_snapshot',directory/'saved-memory.json',lambda p:read(p)==read(work/'memory/versions'/f'{saved:04d}.json'))
 return dict(job=m['id'],name=m['name'],loaded_version=v,saved_version=saved,checks=checks,sources=sources,persistence_verified=all(checks.get(k) is True for k in ['loaded_version_bytes','memory_reached_first_cam_request','saved_episode','saved_commit_readback']),fully_evidenced=bool(checks) and all(x is True for x in checks.values()),best_seconds=m['best']['result']['estimated_time_seconds'] if m.get('best') else None)
def main():
 rows=[audit(p.parent) for p in (WORK/'runs').glob('*/manifest.json') if read(p).get('status')=='completed']
 rows.sort(key=lambda x:x['loaded_version'])
 links=[dict(previous=a['job'],next=b['job'],verified=a['saved_version']==b['loaded_version'] and a['persistence_verified'] and b['persistence_verified']) for a,b in zip(rows,rows[1:])]
 report=dict(jobs=rows,chain_links=links,persistence_verified_jobs=sum(r['persistence_verified'] for r in rows),fully_evidenced_jobs=sum(r['fully_evidenced'] for r in rows),missing_evidence=sum(v is None for r in rows for v in r['checks'].values()),failed_checks=sum(v is False for r in rows for v in r['checks'].values()),claim='Verifies persistence and actual planner input, not a causal speed benefit from memory. Missing historical artifacts remain unverified.')
 out=Path(__file__).parent/'memory-chain-audit.json';out.write_text(json.dumps(report,indent=2)+'\n')
 lines=['# Memory persistence audit','','This audits saved bytes, commit receipts, and the actual first CAM request. Version counters alone do not establish learning.','', '| Job | Memory | Persistence + CAM input | Extra per-job copy |','| --- | --- | --- | --- |']
 for r in rows:lines.append(f"| {r['job']} / {r['name']} | {r['loaded_version']} → {r['saved_version']} | {'verified' if r['persistence_verified'] else 'unverified'} | {'verified' if r['checks'].get('job_saved_snapshot') is True else 'historical copy absent'} |")
 lines+=['',f"Persistence and actual CAM-input checks: {report['persistence_verified_jobs']}/{len(rows)}. Consecutive links verified: {sum(x['verified'] for x in links)}/{len(links)}. All artifact copies present: {report['fully_evidenced_jobs']}/{len(rows)}. Missing historical artifacts: {report['missing_evidence']}. Failed comparisons: {report['failed_checks']}.",'','This is not a memory-transfer experiment. Use the separate 24-plan study to assess speed effects.']
 (out.with_suffix('.md')).write_text('\n'.join(lines)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='jobs'}))
if __name__=='__main__':main()
