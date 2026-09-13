"""Smoke-test archive contents independently of the editable source checkout."""
import json,hashlib,subprocess,sys,tarfile,tempfile
from pathlib import Path
root=Path(__file__).parent/'release';manifest=json.loads((root/'source-manifest.json').read_text())
with tempfile.TemporaryDirectory(prefix='silta-source-review-') as tmp:
 with tarfile.open(root/'simulator-source.tar.gz') as tar:tar.extractall(tmp,filter='data')
 source=Path(tmp)/'cnc_simulator'
 for row in manifest['files']:
  assert hashlib.sha256((source/row['path']).read_bytes()).hexdigest()==row['sha256']
 code='''import json,sys
from pathlib import Path
source=Path(sys.argv[1]);sys.path.insert(0,str(source))
import cncsim
assert Path(cncsim.__file__).is_relative_to(source)
p=source/'examples/pocket.json'
r=cncsim.simulate(json.loads(p.read_text()),base_dir=p.parent)
assert r['passed'], r['issues']
print(json.dumps(dict(passed=r['passed'],seconds=r['estimated_time_seconds'],imported_from_extracted_archive=True)))
'''
 result=subprocess.run([sys.executable,'-I','-c',code,str(source)],capture_output=True,text=True,check=True)
 receipt=dict(source_files_verified=len(manifest['files']),archive_sha256=manifest['sha256'],pocket=json.loads(result.stdout),scope='Extracted core engine smoke test using existing dependency environment; not an isolated dependency install or full live-demo deployment.')
 (root/'smoke-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
