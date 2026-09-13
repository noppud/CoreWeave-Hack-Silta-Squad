"""Post-run distance diagnostics on retained stock; never changes verification or memory."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cncsim.geometry import Solid
from camloop.common import file_hash,save

def bounds_for_masks(distances,lower,upper,radius,tolerance):
 if not np.isfinite(distances).all():raise ValueError('Nonfinite signed distance cannot produce bounds')
 if np.any(lower & ~upper):raise ValueError('Stock occupancy bounds are inconsistent')
 maximum=lambda v:max(0.,float(np.max(v))) if len(v) else 0.
 excess=[maximum(-distances[lower]-radius),maximum(-distances[upper]+radius)]
 missing=[maximum(distances[~upper]-radius),maximum(distances[~lower]+radius)]
 return {'excess_material':{'deviation_mm':excess,'relative_to_tolerance_mm':[x-tolerance for x in excess]},'missing_material':{'deviation_mm':missing,'relative_to_tolerance_mm':[x-tolerance for x in missing]}}

def diagnose(directory):
 directory=Path(directory);plan=json.loads((directory/'plan.json').read_text());result=json.loads((directory/'simulation/result.json').read_text());snapshot=sorted((directory/'simulation/states').glob('*.npz'))[-1]
 state=np.load(snapshot);lower=state['lower'].ravel();upper=state['upper'].ravel();pitch=float(state['pitch']);points=state['origin']+(np.indices(state['lower'].shape).reshape(3,-1).T+.5)*pitch
 target=Solid(plan['target'],'.',mesh_only=True);distances=target.signed(points);radius=result['numerics']['cell_radius_mm'];tol=plan['tolerance_mm'];metrics=bounds_for_masks(distances,lower,upper,radius,tol)
 possible=upper & (distances < -tol+radius);definite=lower & (distances < -tol-radius)
 coords=points[possible];region=[(coords.min(axis=0)-pitch/2).tolist(),(coords.max(axis=0)+pitch/2).tolist()] if len(coords) else None
 return dict(source=str(directory),snapshot_sha256=file_hash(snapshot),target_sha256=file_hash(plan['target']['path']),original_passed=result['passed'],original_verification=result['verification'],resolution_mm=pitch,tolerance_mm=tol,diagnostics=metrics,possible_excess_cells=int(possible.sum()),definite_excess_cells=int(definite.sum()),possible_excess_region_part_coordinates_mm=region,implicated_moves=None,scope='Post-run conservative cell-radius bounds using the existing floating-point signed-distance backend. No resolution refinement, physical measurement, changed verdict, or new failure-memory rule. Region is in original part coordinates; final stock alone cannot attribute moves.')

if __name__=='__main__':
 root=Path(__file__).parent;rows=[]
 for name in ['02-hydraulic-manifold-0.708-0','02-hydraulic-manifold-0.708-1','04-trunnion-cage-0.95-0']:
  print('DIAGNOSE',name,flush=True);rows.append(diagnose(root/'aria-ablation'/name));save(root/'stock-diagnostics.json',rows)
 print('COMPLETE',flush=True)
