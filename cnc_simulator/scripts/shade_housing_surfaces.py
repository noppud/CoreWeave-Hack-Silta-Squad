"""Compute display normals ahead of playback; positions remain on cut meshes."""
from pathlib import Path
import json
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'viewer/dist/assets/housing-surfaces.json';data=json.loads(p.read_text())
for i,f in enumerate(data['frames']):
    m=trimesh.Trimesh(vertices=np.asarray(f['positions']).reshape(-1,3),faces=np.asarray(f['indices']).reshape(-1,3),process=False)
    m=trimesh.graph.smooth_shade(m,angle=np.radians(30),facet_minarea=None)
    f['positions']=np.round(m.vertices,5).ravel().tolist();f['indices']=m.faces.ravel().tolist();f['normals']=np.round(m.vertex_normals,5).ravel().tolist()
    print('Normals',i,flush=True)
p.write_text(json.dumps(data,separators=(',',':')))
