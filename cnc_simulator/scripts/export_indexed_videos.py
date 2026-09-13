"""Watch completed indexed runs and build their deterministic playback data."""
import argparse,json,time
from pathlib import Path
from camloop.indexed.artifacts import export_part
p=argparse.ArgumentParser();p.add_argument('workspace');a=p.parse_args();root=Path(a.workspace)
parts=json.loads((root/'catalog.json').read_text())['parts'];done=set()
while len(done)<len(parts):
    for part in parts:
        if part['id'] in done:continue
        path=root/'runs'/part['id']/'manifest.json'
        if not path.exists():continue
        m=json.loads(path.read_text())
        if m['status']=='running':continue
        if m.get('best') or any(a.get('stage')=='simulated' for a in m['attempts']) or m.get('reference',{}).get('stage')=='simulated':export_part(root,part['id'])
        done.add(part['id'])
    if len(done)<len(parts):time.sleep(10)
