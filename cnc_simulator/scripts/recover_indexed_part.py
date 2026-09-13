"""Run a failed part again without removing its original evidence."""
import json
from pathlib import Path
from camloop.indexed.runner import optimize,read
from camloop.indexed.sequential import remember
from camloop.indexed.report import report
from camloop.common import save,file_hash
from camloop.astra import Astra
root=Path(__file__).resolve().parents[1]/'workspace-indexed-five'
part='02-hydraulic-manifold';original=root/'runs'/part/'manifest.json'
save(root/'runs'/part/'original-manifest.json',read(original))
# Preserve exact pre-commit manifests for the existing memory receipts.
for commit in sorted((root/'memory').glob('commit-*.json')):
    c=read(commit);m=read(root/'runs'/c['part']/'manifest.json');m.pop('saved_memory_version',None)
    snapshot=root/'memory'/f"source-{c['version']:04d}.json";save(snapshot,m)
    if file_hash(snapshot)!=c['source_manifest_sha256']:raise ValueError('Historical source hash mismatch')
    c['source_snapshot']=str(snapshot);save(commit,c)
fresh=read(root/'memory.json');job=read(root/'parts'/part/'job.json');job['split']='sequential recovery'
m=optimize(job,root/'recovery',fresh,attempts=3,paired=False)
m.update(loaded_memory_version=fresh['version'],loaded_memory_sha256=file_hash(root/'memory.json'),recovery_of=str(root/'runs'/part/'original-manifest.json'))
save(original,m)
new=remember(root,fresh,m,Astra(root/'memory/evidence/recovery-02',timeout=180))
m['saved_memory_version']=new['version'];save(original,m);report(root)
print('RECOVERY COMMITTED',new['version'],m['status'],flush=True)
