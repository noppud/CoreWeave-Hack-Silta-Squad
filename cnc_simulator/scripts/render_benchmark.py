"""Render frozen part geometry and measured evaluation results (no model calls)."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def render(workspace):
    root = Path(workspace).resolve()
    out = root / 'report'; out.mkdir(exist_ok=True)
    index = json.loads((root / 'benchmark.json').read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10, 'axes.spines.top':False, 'axes.spines.right':False})
    fig = plt.figure(figsize=(16,7), facecolor='#f5f7f8')
    for i, case in enumerate(index['cases']):
        ax = fig.add_subplot(2,5,i+1,projection='3d',facecolor='#f5f7f8')
        mesh = trimesh.load_mesh(Path(case['job']).parent / 'target.stl')
        faces = Poly3DCollection(mesh.triangles, facecolors='#91b1bb', linewidths=0, antialiased=False, shade=True, lightsource=matplotlib.colors.LightSource(azdeg=310, altdeg=45))
        ax.add_collection3d(faces)
        lo,hi = mesh.bounds
        ax.set(xlim=(lo[0],hi[0]), ylim=(lo[1],hi[1]),zlim=(0,hi[2]))
        ax.set_box_aspect(hi-lo); ax.view_init(elev=58,azim=-65); ax.set_axis_off()
        ax.set_title(case['id'].replace('part-','').replace('-',' '),fontsize=11,pad=0)
    fig.suptitle('Ten frozen target parts · different pocket topologies',fontsize=19,y=.98)
    fig.text(.5,.03,'14 × 14 × 6 mm stock · straight slots, wells, intersecting channels and stepped depths',ha='center',color='#52616b')
    fig.subplots_adjust(left=.015,right=.985,top=.88,bottom=.09,hspace=.12,wspace=.02)
    fig.savefig(out/'ten-parts.png',dpi=180); plt.close(fig)
    results_path = root/'results.json'
    if not results_path.exists(): return
    results = json.loads(results_path.read_text())
    fig,(ax,curve) = plt.subplots(1,2,figsize=(15,6),gridspec_kw={'width_ratios':[1.1,1]})
    rows = results['parts']; x=np.arange(len(rows))
    ax.barh(x-.18,[r['reference_seconds'] for r in rows],height=.34,color='#a5b3b9',label='Verified reference')
    ax.barh(x+.18,[r['best_valid_seconds'] or 0 for r in rows],height=.34,color='#318c75',label='Best verified Astra plan')
    ax.set_yticks(x,[r['part'].replace('part-','').replace('-',' ') for r in rows]); ax.invert_yaxis()
    ax.set_xlabel('Estimated machining seconds (lower is better)'); ax.legend(frameon=False)
    ax.set_title('Compare plans for the same part',pad=16)
    for r in rows:
        m=json.loads(Path(r['manifest']).read_text()); best=None; values=[]
        for a in m['attempts']:
            result=a.get('result')
            if result and result['validity']=='valid':
                best=min(best if best is not None else np.inf,result['estimated_time_seconds'])
            values.append(np.nan if best is None else 100*best/r['reference_seconds'])
        curve.step(np.arange(1,len(values)+1),values,where='post',label=r['part'].split('-')[1],alpha=.8)
    curve.axhline(100,color='#7b878d',ls='--',lw=1)
    curve.set(xlabel='Candidate number (1 = supplied invalid seed)',ylabel='Best valid time as % of same-part reference',title='Retained valid plans across attempts')
    curve.legend(title='Part',ncol=5,frameon=False,loc='upper right');curve.set_ylim(0,110)
    fig.suptitle('Measured CAM optimization · only passing plans score',fontsize=17)
    fig.text(.5,.025,'Constant commanded speeds; no controller dynamics. Across-part time differences are not evidence of learning.',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.06,1,.94]);fig.savefig(out/'optimization-results.png',dpi=180);plt.close(fig)
    transfer = root/'transfer-results.json'
    if transfer.exists():
        audit=json.loads(transfer.read_text())
        (out/'transfer-summary.md').write_text(f"# Retained-learning audit\n\nCold valid: {audit['cold_valid']}/10. Learned valid: {audit['learned_valid']}/10.\n\nLearned faster on {audit['faster_learned']} jointly valid pairs; slower on {audit['slower_learned']}.\n\n{audit['limitations']}\n")
    print(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('workspace',type=Path)
    render(parser.parse_args().workspace)
