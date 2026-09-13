from pathlib import Path
import json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'examples/indexed-housing';OUT=ROOT/'workspace-housing/simulation'
plan=json.loads((BASE/'plan.json').read_text());result=json.loads((OUT/'result.json').read_text())
assert result['target_sha256']==hashlib.sha256((BASE/'target.stl').read_bytes()).hexdigest()
r=np.load(OUT/'removal.npz');trajectory=json.loads((OUT/'trajectory.json').read_text())
assert len(trajectory)==len(plan['moves'])+1
last=np.load(OUT/result['artifacts']['states'][-1])['nominal'].ravel()
assert np.array_equal(last,r['initial']&(r['removed']<0))
data=dict(plan=plan,result=result,design=json.loads((BASE/'design.json').read_text()),trajectory=trajectory,duration=result['estimated_time_seconds'],initial_count=int(r['initial'].sum()),initial=r['initial'].astype(int).tolist(),removed=r['removed'].tolist(),origin=r['origin'].tolist(),shape=r['shape'].tolist(),pitch=float(r['pitch']))
p=ROOT/'viewer/dist/assets/housing.json';p.write_text(json.dumps(data,separators=(',',':')))
(OUT/'viewer-receipt.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256((OUT/'removal.npz').read_bytes()).hexdigest(),viewer_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),matches_final_stock=True,passed=result['passed']),indent=2))
print('Exported',p,'passed',result['passed'])
