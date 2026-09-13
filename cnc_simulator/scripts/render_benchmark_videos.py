"""Watch completed runs and export each retained passing plan, then a reel."""
import argparse
import json
import subprocess
import time
from pathlib import Path
import imageio_ffmpeg
from render_machining_video import render

parser=argparse.ArgumentParser();parser.add_argument('workspace',type=Path);args=parser.parse_args()
root=args.workspace.resolve();out=root/'videos';out.mkdir(exist_ok=True)
while True:
    index=root/'benchmark.json'
    if not index.exists():time.sleep(2);continue
    cases=json.loads(index.read_text())['cases'];done=0;videos=[]
    for case in cases:
        p=root/'runs'/f'benchmark-{case["id"]}'/'manifest.json'
        if not p.exists():continue
        m=json.loads(p.read_text())
        if m['status']=='running':continue
        done+=1
        if m['best'] is None:continue
        video=out/f'{case["id"]}.mp4'
        if not video.exists():render(p.parent/m['best']['playback'],video,fps=24,duration=10)
        videos.append(video)
    if done==len(cases):
        if videos:
            listing=out/'concat.txt';listing.write_text(''.join(f"file '{v.name}'\n" for v in videos))
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(out/'ten-part-machining-reel.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        break
    time.sleep(3)
