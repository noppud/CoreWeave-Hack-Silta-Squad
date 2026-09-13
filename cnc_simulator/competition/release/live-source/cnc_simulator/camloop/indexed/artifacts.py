"""Generate compact swept-stock display checkpoints from a retained verified CAM plan."""
import hashlib,json,math
from pathlib import Path
import numpy as np
import trimesh
import manifold3d
from cncsim.indexing import rotation,world_points
from ..common import save,file_hash


def export_part(root,part_id,selection=None):
    root=Path(root).resolve();m=json.loads((root/'runs'/part_id/'manifest.json').read_text())
    selected=m.get('best') or next((a for a in reversed(m['attempts']) if a.get('stage')=='simulated'),m.get('reference'))
    if not selected or selected.get('stage')!='simulated':raise ValueError('No simulated plan to render')
    if selection=='reference':selected=m['reference']
    elif selection is not None:selected=m['attempts'][int(selection.split('-')[1])]
    asset_id=part_id+('--'+selection if selection else '')
    best=Path(selected['path']);plan=json.loads((best/'plan.json').read_text());sim=best/'simulation'
    trajectory=json.loads((sim/'trajectory.json').read_text());job=json.loads((root/'parts'/part_id/'job.json').read_text())
    if file_hash(plan['target']['path'])!=job['target_sha256']:raise ValueError('Target hash changed')
    destination=Path(__file__).resolve().parents[2]/'viewer/dist/assets/study'/root.name/asset_id
    destination.mkdir(parents=True,exist_ok=True)
    stock=trimesh.load_mesh(plan['stock']['path']);initial_volume=float(stock.volume);batch=[];frames=[];chunks=[];offset=0;last_volume=initial_volume
    stride=max(1,math.ceil(len(trajectory)/44))
    def snapshot(row):
        nonlocal stock,batch,last_volume,offset
        if batch:
            cutter=trimesh.boolean.union(batch,engine='manifold') if len(batch)>1 else batch[0]
            stock=trimesh.boolean.difference([stock,cutter],engine='manifold');batch=[]
        if not stock.is_volume or stock.volume>last_volume+1e-3:raise ValueError('Non-monotonic display stock')
        last_volume=float(stock.volume)
        # Simplify ONLY the display copy. The verifier and Boolean stock used for
        # subsequent removals are never simplified or replaced by target geometry.
        solid=manifold3d.Manifold(manifold3d.Mesh(np.asarray(stock.vertices,np.float32),np.asarray(stock.faces,np.uint32)))
        sm=solid.simplify(.005).to_mesh()
        display=trimesh.Trimesh(vertices=sm.vert_properties[:,:3],faces=sm.tri_verts,process=False)
        display=trimesh.graph.smooth_shade(display,angle=np.radians(30),facet_minarea=None)
        positions=np.asarray(display.vertices,dtype='<f4').ravel();normals=np.asarray(display.vertex_normals,dtype='<f4').ravel();indices=np.asarray(display.faces,dtype='<u4').ravel()
        frames.append(dict(move=row['move'],elapsed_seconds=row['elapsed_seconds'],volume_mm3=last_volume,offset=offset,vertex_values=len(positions),index_values=len(indices)))
        chunk=positions.tobytes()+normals.tobytes()+indices.tobytes();chunks.append(chunk);offset+=len(chunk)
    snapshot(trajectory[0])
    for row in trajectory[1:]:
        if row['type']=='cut':
            t=plan['tools'][row['tool']];a=np.array(row['from']);b=np.array(row['position']);bc=row['bc_degrees']
            c=trimesh.creation.cylinder(radius=t['diameter_mm']/2,height=t['flute_length_mm'],sections=64)
            verts=c.vertices+[0,0,t['flute_length_mm']/2];points=np.concatenate([verts+a,verts+b]);origin=world_points(np.zeros((1,3)),bc,plan['indexing'])[0]
            sweep=trimesh.convex.convex_hull((points-origin)@rotation(bc))
            if np.all(sweep.bounds[1]>=stock.bounds[0]) and np.all(sweep.bounds[0]<=stock.bounds[1]):batch.append(sweep)
        if (row['move']+1)%stride==0 or row['type']=='index' or row is trajectory[-1]:snapshot(row)
    lo,hi=selected['result']['stock_metrics']['final_volume_bounds_mm3']
    if not lo<=stock.volume<=hi:raise ValueError('Display stock outside verifier volume bounds')
    stock.export(sim/'display_final_stock.ply')
    (destination/'surfaces.bin').write_bytes(b''.join(chunks))
    save(destination/'surfaces.json',dict(frames=frames,binary='surfaces.bin',initial_volume_mm3=initial_volume,source_plan_sha256=file_hash(best/'plan.json'),display_tolerance_mm=.005))
    phases=json.loads((best/'phases.json').read_text())
    save(destination/'playback.json',dict(plan=plan,result=selected['result'],design=dict(name=job['name'],phases=phases,stock_shape=job['stock_shape']),trajectory=trajectory,duration=selected['result']['estimated_time_seconds']))
    receipt=dict(part=part_id,source_plan_sha256=file_hash(best/'plan.json'),frames=len(frames),bytes=offset,final_display_volume_mm3=last_volume,within_verifier_bounds=True,passed=selected['result']['passed'],selection=selection or ('best passing plan' if m.get('best') else 'last failed simulated attempt'),method='Boolean subtraction of swept inscribed 64-sided cutters; display copy simplified <=0.005 mm. No target geometry used to construct stock.')
    save(destination/'receipt.json',receipt);save(root/'runs'/part_id/('video-source'+('--'+selection if selection else '')+'.json'),receipt)
    print('Display exported',part_id,len(frames),'frames',offset,'bytes',flush=True);return receipt
