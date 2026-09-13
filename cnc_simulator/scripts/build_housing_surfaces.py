"""Display-only B-rep-like mesh removal from actual tool sweeps, never the target.

Each convex swept cutter is an inscribed polygonal approximation (64 sides).
The conservative voxel verifier remains authoritative; this does not certify cuts.
"""
from pathlib import Path
import json,hashlib,time
import numpy as np
import trimesh
from cncsim.indexing import world_points,rotation
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'examples/indexed-housing';OUT=ROOT/'workspace-housing/simulation'
plan=json.loads((BASE/'plan.json').read_text());trajectory=json.loads((OUT/'trajectory.json').read_text())
stock=trimesh.load_mesh(BASE/plan['stock']['path']);frames=[];batch=[];bc=plan['indexing']['initial_bc_degrees'];previous_volume=stock.volume

def save_frame(row):
    global stock,previous_volume,batch
    if batch:
        cutter=trimesh.boolean.union(batch,engine='manifold') if len(batch)>1 else batch[0]
        stock=trimesh.boolean.difference([stock,cutter],engine='manifold');batch=[]
    assert stock.is_volume and stock.volume<=previous_volume+1e-3
    previous_volume=stock.volume
    frames.append(dict(move=row['move'],elapsed_seconds=row['elapsed_seconds'],volume_mm3=float(stock.volume),positions=np.round(stock.vertices,5).ravel().tolist(),indices=stock.faces.ravel().tolist()))
    print('Surface',len(frames),'move',row['move'],'triangles',len(stock.faces),flush=True)

save_frame(trajectory[0])
for row in trajectory[1:]:
    bc=row['bc_degrees']
    if row['type']=='cut':
        tool=plan['tools'][row['tool']];a=np.array(row['from']);b=np.array(row['position'])
        c=trimesh.creation.cylinder(radius=tool['diameter_mm']/2,height=tool['flute_length_mm'],sections=64)
        verts=c.vertices+np.array([0,0,tool['flute_length_mm']/2])
        points=np.concatenate([verts+a,verts+b])
        offset=world_points(np.zeros((1,3)),bc,plan['indexing'])[0]
        points=(points-offset)@rotation(bc)
        sweep=trimesh.convex.convex_hull(points)
        # Cuts completely outside the current stock AABB need no boolean.
        if np.all(sweep.bounds[1]>=stock.bounds[0]) and np.all(sweep.bounds[0]<=stock.bounds[1]):batch.append(sweep)
    if (row['move']+1)%24==0 or row['type']=='index' or row is trajectory[-1]:save_frame(row)
result=json.loads((OUT/'result.json').read_text());lo,hi=result['stock_metrics']['final_volume_bounds_mm3'];assert lo<=stock.volume<=hi
stock.export(OUT/'display_final_stock.ply')
output=ROOT/'viewer/dist/assets/housing-surfaces.json';output.write_text(json.dumps(dict(frames=frames,source_sha256=hashlib.sha256((BASE/'plan.json').read_bytes()).hexdigest(),display_only=True),separators=(',',':')))
(OUT/'surface-receipt.json').write_text(json.dumps(dict(frames=len(frames),final_volume_mm3=stock.volume,inside_verifier_volume_bounds=True,method='Boolean subtraction of convex swept inscribed 64-sided cutting cylinders; target mesh is not loaded.',source_sha256=hashlib.sha256((BASE/'plan.json').read_bytes()).hexdigest()),indent=2))
