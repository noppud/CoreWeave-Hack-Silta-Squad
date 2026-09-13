"""Create a reviewable source snapshot without private runs or credentials."""
from pathlib import Path
import hashlib,json,tarfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'competition/release';OUT.mkdir(exist_ok=True)
files=[]
for folder in ['cncsim','camloop','tests','examples']:
 for p in (ROOT/folder).rglob('*'):
  if p.name=='test_machine_assets.py':continue  # Legacy VF2/Fusion provenance lives in the complete workspace.
  if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.stl','.ply'}:files.append(p)
for p in ROOT.iterdir():
 if p.is_file() and (p.suffix=='.md' or p.name in ['pyproject.toml','requirements-lock.txt','requirements-loop-lock.txt']):files.append(p)
for name in ['workspace.html','workspace.css','workspace.js','housing.html','housing.js','study.html','study.js']:
 files.append(ROOT/'viewer/dist'/name)
for folder in ['viewer/dist/vendor','viewer/dist/examples','assets/umc750']:
 files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file())
files.append(ROOT/'viewer/dist/assets/umc750.json')
for name in ['scripts/serve_indexed.py','scripts/encode_indexed_videos.py','competition/run_complex_parts.py','competition/live_terminal.py']:
 files.append(ROOT/name)
files=sorted(set(files))
manifest=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
archive=OUT/'simulator-source.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in files:tar.add(p,arcname='cnc_simulator/'+str(p.relative_to(ROOT)),recursive=False)
(OUT/'source-manifest.json').write_text(json.dumps(dict(archive=archive.name,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=manifest,scope='Core engine, CAM orchestration, live viewer, UMC machine assets, tests and example CAD. Recorded studies, credentials and environments excluded. Legacy VF2/Fusion provenance test module is excluded; it requires separate parent-repository assets and is not a UMC engine test.'),indent=2)+'\n')
print(len(files),'files;',archive.stat().st_size,'bytes')
