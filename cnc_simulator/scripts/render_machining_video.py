"""MP4 from recorded voxel-removal times and exact submitted XYZ trajectories."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def render(playback_path, destination, fps=12, duration=10):
    playback_path=Path(playback_path); base=playback_path.parent
    data=json.loads(playback_path.read_text());plan=data['plan']
    if plan['stock']['type'] != 'box':raise ValueError('Video heightfield renderer requires box stock')
    shape=tuple(data['shape']);origin=np.array(data['origin']);pitch=data['pitch']
    initial=np.fromfile(base/'initial.bin',dtype='u1').reshape(shape).astype(bool)
    removal=np.fromfile(base/'removal.bin',dtype='<f4').reshape(shape)
    total=data['result']['estimated_time_seconds']; bounds=np.array(data['stock_bounds'])
    expected=np.load(base/f'states/{len(plan["moves"]):05d}.npz')['nominal']
    if not np.array_equal(initial & (removal>total+1e-5),expected):raise ValueError('Video source does not match final simulated stock')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.stem+'.rendering.mp4')
    fig=plt.figure(figsize=(10,7.04),dpi=100,facecolor='#111a20')
    ax=fig.add_axes([.04,.12,.92,.78],projection='3d',facecolor='#111a20')
    ax.set(xlim=(bounds[0,0]-2,bounds[1,0]+2),ylim=(bounds[0,1]-2,bounds[1,1]+2),zlim=(bounds[0,2]-1,bounds[1,2]+10))
    ax.set_box_aspect([18,18,16]);ax.view_init(elev=48,azim=-60);ax.set_axis_off()
    fig.text(.055,.945,'SILTA  /  SIMULATED MACHINING',color='#c4e8df',fontsize=15,weight='bold')
    fig.text(.055,.90,destination.stem.replace('-',' '),color='white',fontsize=18)
    clock=fig.text(.055,.07,'',color='white',fontsize=13,family='monospace')
    fig.text(.055,.027,'Recorded XYZ + nominal voxel stock • fixed target • constant-speed timing',color='#9fb0b8',fontsize=10)
    stock_artist=None;tool_artists=[]
    xx,yy=np.meshgrid(origin[0]+np.arange(shape[0])*pitch,origin[1]+np.arange(shape[1])*pitch,indexing='ij')
    loz=bounds[0,2]
    def stock_faces(t):
        alive=initial & (removal>t)
        heights=np.max(np.where(alive,np.arange(shape[2])[None,None,:]+1,0),axis=2)*pitch+origin[2]
        present=alive.any(axis=2)
        if not np.allclose(alive.sum(axis=2)[present]*pitch,(heights-loz)[present]):raise ValueError('Undercut/disconnected stock cannot be represented by this video renderer')
        i,j=np.where(present);x=xx[i,j];y=yy[i,j];z=heights[i,j]
        faces=[np.stack([np.stack([x,y,z],1),np.stack([x+pitch,y,z],1),np.stack([x+pitch,y+pitch,z],1),np.stack([x,y+pitch,z],1)],1)]
        colors=[np.tile([.49,.67,.72,1],(len(i),1))]
        for axis,sign in [(0,-1),(0,1),(1,-1),(1,1)]:
            neighbor=np.full_like(heights,loz)
            if axis==0 and sign==-1: neighbor[1:]=np.where(present[:-1],heights[:-1],loz)
            if axis==0 and sign==1: neighbor[:-1]=np.where(present[1:],heights[1:],loz)
            if axis==1 and sign==-1: neighbor[:,1:]=np.where(present[:,:-1],heights[:,:-1],loz)
            if axis==1 and sign==1: neighbor[:,:-1]=np.where(present[:,1:],heights[:,1:],loz)
            ii,jj=np.where(present & (heights>neighbor+1e-8));x=xx[ii,jj];y=yy[ii,jj];z=heights[ii,jj];low=neighbor[ii,jj]
            if axis==0:
                x=x+(pitch if sign==1 else 0);q=[(x,y,low),(x,y+pitch,low),(x,y+pitch,z),(x,y,z)]
            else:
                y=y+(pitch if sign==1 else 0);q=[(x,y,low),(x+pitch,y,low),(x+pitch,y,z),(x,y,z)]
            faces.append(np.stack([np.stack(v,1) for v in q],1));colors.append(np.tile([.29,.46,.53,1],(len(ii),1)))
        return np.concatenate(faces),np.concatenate(colors)
    def pose(t):
        p=np.array(plan['initial_position'],float);tool=plan['initial_tool'];elapsed=0
        for m in plan['moves']:
            if m['type'] in ('cut','rapid'):
                end=np.array(m['to']);speed=m.get('feed_mm_per_min',plan['rapid_mm_per_min']);secs=np.linalg.norm(end-p)*60/speed
                if elapsed+secs>=t and secs>0:return p+(end-p)*np.clip((t-elapsed)/secs,0,1),tool,m['type']
                p=end
            elif m['type']=='dwell':secs=m['seconds']
            else:secs=plan['tool_change_seconds'];tool=m['tool']
            if elapsed+secs>=t:return p,tool,m['type']
            elapsed+=secs
        return p,tool,'finished'
    proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo','-s','1000x704','-pix_fmt','rgb24','-r',str(fps),'-i','-','-an','-vcodec','libx264','-pix_fmt','yuv420p','-crf','20','-movflags','+faststart',str(temporary)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for frame,t in enumerate(np.linspace(0,total,int(fps*duration))):
            if stock_artist is not None:stock_artist.remove()
            faces,colors=stock_faces(t);stock_artist=Poly3DCollection(faces,facecolors=colors,linewidths=0,antialiased=False);ax.add_collection3d(stock_artist)
            for artist in tool_artists:artist.remove()
            tool_artists=[];p,tool,kind=pose(t);g=plan['tools'][tool]
            z0=p[2]
            for radius,length,color in [(g['diameter_mm']/2,g['flute_length_mm'],'#d7d9c3'),(g['shaft_diameter_mm']/2,g['shaft_length_mm'],'#b4bcc0'),(g['holder_diameter_mm']/2,g['holder_length_mm'],'#485861')]:
                theta=np.linspace(0,2*np.pi,25);zz=np.array([z0,z0+length]);theta,zz=np.meshgrid(theta,zz)
                for capz in [z0,z0+length]:
                    ring=np.linspace(0,2*np.pi,25)
                    cap=Poly3DCollection([np.column_stack([p[0]+radius*np.cos(ring),p[1]+radius*np.sin(ring),np.full_like(ring,capz)])],facecolors=color,linewidths=0)
                    ax.add_collection3d(cap);tool_artists.append(cap)
                tool_artists.append(ax.plot_surface(p[0]+radius*np.cos(theta),p[1]+radius*np.sin(theta),zz,color=color,linewidth=0,shade=True));z0+=length
            clock.set_text(f'{t:5.2f} / {total:.2f} s    {kind.upper():10}    X {p[0]:.2f}  Y {p[1]:.2f}  Z {p[2]:.2f}')
            fig.canvas.draw();rgb=np.asarray(fig.canvas.buffer_rgba())[:,:,:3].copy();proc.stdin.write(rgb.tobytes())
        proc.stdin.close();stderr=proc.stderr.read();code=proc.wait()
        if code:raise RuntimeError(stderr.decode())
    finally:
        plt.close(fig)
        if proc.poll() is None:proc.kill()
    temporary.replace(destination)
    receipt=dict(source_sha256=hashlib.sha256(playback_path.read_bytes()).hexdigest(),source=str(playback_path.resolve()),video=str(destination.resolve()),frames=int(fps*duration),fps=fps,
                 simulated_seconds=total,video_seconds=duration,passed=data['result'].get('passed',data['result']['validity']=='valid'),
                 representation='Top surfaces and vertical walls reconstructed from nominal voxel stock. Suitable for these top-access pocket parts; not an undercut renderer.')
    destination.with_suffix('.json').write_text(json.dumps(receipt,indent=2))
    print(destination,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('playback');parser.add_argument('destination');parser.add_argument('--fps',type=int,default=12);parser.add_argument('--duration',type=float,default=10)
    args=parser.parse_args();render(args.playback,args.destination,args.fps,args.duration)
