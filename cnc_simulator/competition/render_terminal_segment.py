"""Edit genuine captured terminal events into a clearly labeled recorded segment."""
from pathlib import Path
import json,subprocess,textwrap
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
ROOT=Path(__file__).parent;OUT=ROOT/'film/terminal';OUT.mkdir(exist_ok=True)
events=[json.loads(x) for x in (ROOT/'fresh-live-terminal.jsonl').read_text().splitlines()]
selected=[]
for kind in ['generated CAM','verification','timing judge','result']:
 matches=[x for x in events if x['kind']==kind]
 if matches:selected.append(matches[0] if kind!='result' else matches[-1])
font='/System/Library/Fonts/Menlo.ttc';ff=imageio_ffmpeg.get_ffmpeg_exe();paths=[]
for i,e in enumerate(selected):
 im=Image.new('RGB',(1920,1080),'#101613');d=ImageDraw.Draw(im)
 d.text((90,70),'SILTA / RECORDED LIVE RUN / a1b399e521ac',font=ImageFont.truetype(font,25),fill='#9db5a5')
 d.text((90,135),f"+{e['elapsed']:.1f}s  {e['kind'].upper()}",font=ImageFont.truetype(font,36),fill='#f2f6f1')
 value=e['value']
 if e['kind']=='result':value={'status':value['status'],'memory_saved':value['memory_saved'],'evidence':value['evidence']}
 if e['kind']=='verification':value={k:v for k,v in value.items() if k!='artifact'}
 text=json.dumps(value,indent=2) if isinstance(value,dict) else str(value)
 lines=[]
 for line in text.splitlines():lines.extend(textwrap.wrap(line,100,replace_whitespace=False,drop_whitespace=False) or [''])
 for j,line in enumerate(lines[:24]):d.text((90,220+j*29),line,font=ImageFont.truetype(font,22),fill='#c4d4c9')
 d.text((90,1000),'Actual event order. Waiting time compressed. Full JSONL retained.',font=ImageFont.truetype(font,22),fill='#91a498')
 p=OUT/f'{i}.png';im.save(p);v=OUT/f'{i}.mp4'
 subprocess.run([ff,'-y','-loglevel','error','-loop','1','-i',str(p),'-t','5','-r','30','-pix_fmt','yuv420p','-c:v','libx264','-preset','fast',str(v)],check=True);paths.append(v.resolve())
l=OUT/'concat.txt';l.write_text(''.join(f"file '{p}'\n" for p in paths));subprocess.run([ff,'-y','-loglevel','error','-f','concat','-safe','0','-i',str(l),'-c','copy',str(OUT/'recorded-terminal.mp4')],check=True)
print('Rendered',len(selected),'actual events')
