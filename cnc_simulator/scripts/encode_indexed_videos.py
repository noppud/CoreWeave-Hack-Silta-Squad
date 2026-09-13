"""Encode captured local videos, verify decoding, and create a five-part reel."""
import argparse,json,time,subprocess,hashlib
from pathlib import Path
import imageio_ffmpeg
p=argparse.ArgumentParser();p.add_argument('workspace');p.add_argument('--reel-name',default='five-part-machining-reel.mp4');a=p.parse_args();root=Path(a.workspace).resolve();videos=root/'videos';videos.mkdir(exist_ok=True)
parts=json.loads((root/'catalog.json').read_text())['parts'];done=set();ff=imageio_ffmpeg.get_ffmpeg_exe()
while len(done)<len(parts):
    for part in parts:
        id=part['id'];src=videos/f'{id}.webm';dst=videos/f'{id}.mp4'
        if id in done or not src.exists():continue
        try:
            m=json.loads((root/'runs'/id/'manifest.json').read_text())
            selected=m.get('best') or next((a for a in reversed(m['attempts']) if a.get('stage')=='simulated'),m.get('reference'))
            caption=videos/f'{id}-caption.txt'
            caption.write_text(m['name']+' | '+('PASS' if selected['result']['passed'] else 'FAIL - geometry not verified')+'\nEstimated cycle: '+str(round(selected['result']['estimated_time_seconds'],1))+' s | Indexed 3+2 | 3 mm demo tolerance\nAccelerated simulation replay - actual swept stock removal')
            video_filter="fps=30,format=yuv420p,drawtext=textfile='"+str(caption)+"':fontsize=27:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=16:x=36:y=36:line_spacing=8"
            with (videos/f'{id}-encode.log').open('w') as log:
                subprocess.run([ff,'-y','-i',str(src),'-vf',video_filter,'-c:v','libx264','-crf','19','-movflags','+faststart',str(dst)],check=True,stdout=log,stderr=log)
                frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(dst))
                if frames<800 or not 29<seconds<32:raise ValueError('Unexpected capture duration')
                subprocess.run([ff,'-y','-ss',str(max(0,seconds-1)),'-i',str(dst),'-frames:v','1',str(videos/f'{id}.png')],check=True,stdout=log,stderr=log)
            m=json.loads((root/'runs'/id/'manifest.json').read_text())
            selected=m.get('best') or next((a for a in reversed(m['attempts']) if a.get('stage')=='simulated'),m.get('reference'))
            receipt=dict(part=id,frames=frames,seconds=seconds,video_sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),best_plan_sha256=hashlib.sha256((Path(selected['path'])/'plan.json').read_bytes()).hexdigest(),estimated_cycle_seconds=selected['result']['estimated_time_seconds'],passed=selected['result']['passed'])
            (videos/f'{id}.json').write_text(json.dumps(receipt,indent=2));done.add(id);print('VIDEO VERIFIED',id,frames,seconds,flush=True)
        except Exception as e:print('Capture encoding pending',id,str(e),flush=True)
    if len(done)<len(parts):time.sleep(3)
listing=videos/'reel-input.txt';listing.write_text(''.join("file '"+str(videos/(p['id']+'.mp4')).replace("'","'\\''")+"'\n" for p in parts))
subprocess.run([ff,'-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(videos/a.reel_name)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('REEL VERIFIED',imageio_ffmpeg.count_frames_and_secs(str(videos/a.reel_name)),flush=True)
