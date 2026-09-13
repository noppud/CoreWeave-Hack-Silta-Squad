"""Evidence-led first cut, built from actual captured machining and source metrics."""
from pathlib import Path
import json,subprocess
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).with_name('film');OUT.mkdir(exist_ok=True)
ff=imageio_ffmpeg.get_ffmpeg_exe();font='/System/Library/Fonts/Helvetica.ttc'
def card(name,kicker,title,lines):
 im=Image.new('RGB',(1920,1080),'#101613');d=ImageDraw.Draw(im)
 def text(y,s,size,color='#f3f6f2'):d.text((130,y),s,font=ImageFont.truetype(font,size),fill=color)
 text(100,'SILTA  /  '+kicker,25,'#a3b4a8');text(240,title,66)
 for i,line in enumerate(lines):text(410+i*92,line,34,'#c2cec5')
 text(975,'RECORDED EVIDENCE · PROGRAMMATIC SIMULATOR · INDEXED 3+2',20,'#8a9b8f')
 p=OUT/(name+'.png');im.save(p);return p
subprocess.run([__import__('sys').executable,str(Path(__file__).with_name('render_loop.py'))],check=True)
intro=OUT/'01-loop.png'
subprocess.run([__import__('sys').executable,str(Path(__file__).with_name('render_results.py'))],check=True)
results=OUT/'03-results.png'
learning=card('05-learning','MEMORY, TESTED','Catch the mistake before repeating it.', ['Fresh simulations: 2 repeated failures caught early.','Both valid controls retained. Changed setup sent to simulation.','Hosted sandbox execution + completed Weave trace.'])
subprocess.run([__import__('sys').executable,str(Path(__file__).with_name('render_failure_loop.py'))],check=True)
end=card('07-scope','LIVE DEMO FOLLOWS','Drawing > CAM > verified stock.', ['Actual generated movements, checks and saved memory.','Only passing plans receive a machining-time score.','1 mm cells / 3 mm demo tolerance. Not production certification.'])
def evidence_frame(source,name,title):
 im=Image.new('RGB',(1920,1080),'#101613');shot=Image.open(OUT/source).convert('RGB');ratio=min(1792/shot.width,930/shot.height);shot=shot.resize((round(shot.width*ratio),round(shot.height*ratio)),Image.Resampling.LANCZOS);im.paste(shot,((1920-shot.width)//2,100))
 ImageDraw.Draw(im).text((64,30),title,font=ImageFont.truetype(font,30),fill='#f3f6f2')
 path=OUT/name;im.save(path);return path
weave_frame=evidence_frame('weave-evaluation.png','weave-frame.png','WEAVE / Scored retained simulator evidence · 5 best plans pass')
aria_frame=evidence_frame('aria-advisory.png','aria-frame.png','ARIA / Review → 12-case experiment → tested, scoped advisory')
subprocess.run([__import__('sys').executable,str(Path(__file__).with_name('render_transfer_overview.py'))],check=True)
segments=[(intro,8,None),(ROOT/'workspace-complex-three/videos/13-twelve-window-carrier.webm',15,14),(results,12,None),(ROOT/'workspace-complex-three/videos/15-staggered-lattice-drum.webm',15,14),(learning,12,None),(weave_frame,6,None),(aria_frame,6,None),(OUT/'transfer-overview.png',8,None),(ROOT/'workspace-complex-three/videos/14-multi-gallery-manifold.webm',8,21),(OUT/'terminal/recorded-terminal.mp4',20,0),(end,6,None)]
paths=[];timeline=[];cursor=0
for i,(source,duration,offset) in enumerate(segments):
 timeline.append(dict(source=str(source),start_seconds=cursor,duration_seconds=duration,source_offset_seconds=offset));cursor+=duration
 dst=OUT/f'segment-{i:02d}.mp4';args=[ff,'-y','-loglevel','error']
 if offset is None:args+=['-loop','1','-i',str(source)]
 else:args+=['-ss',str(offset),'-i',str(source)]
 args+=['-t',str(duration),'-an','-vf','scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p','-c:v','libx264','-preset','fast','-crf','19',str(dst)]
 subprocess.run(args,check=True);paths.append(dst)
listing=OUT/'concat.txt';listing.write_text(''.join(f"file '{p}'\n" for p in paths))
subprocess.run([ff,'-y','-loglevel','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(OUT/'silta-evidence-first-cut.mp4')],check=True)
frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(OUT/'silta-evidence-first-cut.mp4'))
(OUT/'receipt.json').write_text(json.dumps(dict(frames=frames,seconds=seconds,status='Silent rehearsal film with actual machining captures, live event excerpts and observed Weave/ARIA screenshots; review contact sheet retained',sources=[str(x[0]) for x in segments],timeline=timeline),indent=2))
print(frames,seconds,flush=True)

subprocess.run([__import__('sys').executable,str(Path(__file__).with_name('finalize_film.py'))],check=True)
