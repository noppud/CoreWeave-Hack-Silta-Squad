"""Render frozen CAD targets; explicitly not machined-stock results."""
import json
from pathlib import Path
import numpy as np,trimesh,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
R=Path(__file__).resolve().parents[1];work=R/'workspace-complex-three'
fig=plt.figure(figsize=(17,6),facecolor='#f3f4f1')
entries=json.loads((work/'catalog.json').read_text())['parts']
for i,entry in enumerate(entries):
 job=json.loads(Path(entry['job']).read_text());mesh=trimesh.load_mesh(job['plan']['target']['path']);ax=fig.add_subplot(1,3,i+1,projection='3d',computed_zorder=True)
 light=np.array([-.5,-.7,1.]);light/=np.linalg.norm(light);intensity=.35+.6*np.maximum(0,mesh.face_normals@light)
 colors=np.column_stack([intensity*.86,intensity*.92,intensity,np.ones(len(intensity))])
 ax.add_collection3d(Poly3DCollection(mesh.triangles,facecolors=colors,edgecolors='none'))
 center=mesh.bounds.mean(axis=0);radius=np.ptp(mesh.bounds,axis=0).max()*.6
 ax.set(xlim=(center[0]-radius,center[0]+radius),ylim=(center[1]-radius,center[1]+radius),zlim=(center[2]-radius,center[2]+radius));ax.set_box_aspect((1,1,1));ax.view_init(27,-55);ax.set_axis_off();ax.set_facecolor('#f3f4f1')
 ax.set_title(job['name']+'\n'+str(len(job['features']))+' features · '+str(len({tuple(f['bc']) for f in job['features']}))+' orientations',fontsize=14,pad=-2)
fig.suptitle('NEW FROZEN CAD TARGETS — machining verification in progress',fontsize=18,y=.98)
fig.subplots_adjust(left=0,right=1,bottom=0,top=.86,wspace=0)
fig.savefig(R/'competition/complex-targets.png',dpi=150)
