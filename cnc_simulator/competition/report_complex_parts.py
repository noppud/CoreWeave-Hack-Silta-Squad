"""Report all three complex-part trials, including failed attempts and export gaps."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'workspace-complex-three'
def main():
 rows=json.loads((WORK/'summary.json').read_text());assert len(rows)==3,'All three cases must finish before final reporting'
 lines=['# Three complex indexed parts','','Three new frozen targets, each with a fixed reference and up to two Astra CAM revisions. Earlier memory is supplied and later episodes are persisted. This is a complexity stress test, not a controlled test of memory benefit.','', '| Part | Features / orientations | Reference | Best passing | Attempt gates | Memory |','| --- | --- | --- | --- | --- | --- |']
 for r in rows:
  ref=r['reference'];best=r['best'];reftext=f"{ref['estimated_time_seconds']:.1f} s" if ref and ref['passed'] else 'FAIL'
  besttext=f"{best['estimated_time_seconds']:.1f} s" if best else 'No passing plan'
  attempts=', '.join('PASS' if x['passed'] else 'FAIL' for x in r['attempts'])
  lines.append(f"| {r['name']} | {r['features']} / {r['orientations']} | {reftext} | {besttext} | {attempts} | {r['loaded_memory_version']} → {r['saved_memory_version']} |")
 for r in rows:
  lines+=['',f"## {r['name']}",'',f"[Actual stock replay](http://127.0.0.1:2746/housing.html?part={r['id']}&study=workspace-complex-three&embed=1)"]
  for i,a in enumerate(r['attempts']):
   if a['issues']:lines+=['',f'Attempt {i+1} issues: '+json.dumps(a['issues'])]
  if r['playback_error']:lines+=['','Playback error: '+r['playback_error']]
 lines+=['','Geometry: indexed 3+2, flat-end mills, 1 mm cells and 3 mm demo tolerance. Configured tool/fixture collision and travel gates; no whole-machine, cutting-force or controller certification. Timing assumes constant commanded speeds. Frozen CAD previews are distinct from machined-stock replay.']
 (WORK/'RESULTS.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines[:10]))
if __name__=='__main__':main()
