"""Validate the completed fresh-install run without promoting it to a benchmark."""
import hashlib,json,urllib.request
from pathlib import Path
R=Path(__file__).parent/'release';source=R/'live-source/cnc_simulator';job='d6c0b4356c2b'
with urllib.request.urlopen('http://127.0.0.1:2745/api/jobs/'+job) as r:s=json.load(r)
assert s['status']=='completed',s['status']
m=s['manifest'];assert m['best']['result']['passed']
assert m['loaded_memory_version']==0 and m['loaded_memory']['episodes']==[]
assert m['saved_memory_version']==1
saved=json.loads((source/'workspace-live/memory.json').read_text());assert len(saved['episodes'])==1
archive=json.loads((R/'source-manifest.json').read_text())
for item in archive['files']:
 assert hashlib.sha256((source/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
plan=json.loads((Path(m['best']['path'])/'plan.json').read_text())
assert hashlib.sha256(Path(plan['target']['path']).read_bytes()).hexdigest()==m['target_sha256']
assets={}
for name in ['playback.json','surfaces.json','surfaces.bin']:
 with urllib.request.urlopen(f'http://127.0.0.1:2745/assets/study/workspace-live/{job}/{name}') as r:
  data=r.read();assert data;assets[name]=len(data)
receipt=dict(job=job,status=s['status'],reference_seconds=m['reference']['result']['estimated_time_seconds'],best_seconds=m['best']['result']['estimated_time_seconds'],memory_before=0,memory_after=1,source_files_verified=len(archive['files']),archive_sha256=archive['sha256'],target_unchanged=True,served_playback_bytes=assets,trace_enabled=m['telemetry']['enabled'],scope='Fresh dependency environment and extracted source. Real Astra PDF/CAM run and deterministic verification; not a controlled memory-transfer experiment. Weave intentionally unconfigured for this clean install.')
(R/'clean-live-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
