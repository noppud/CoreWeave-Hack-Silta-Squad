"""Render the actual retained failure -> Astra repair -> verified result."""
from pathlib import Path
import json,textwrap
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).with_name('film');m=json.loads((ROOT/'workspace-loop-demo/runs/02-hydraulic-manifold/manifest.json').read_text());audit=json.loads((Path(__file__).with_name('failure-memory-eval')/'result.json').read_text())
failure=m['reference']['result'];repair=m['attempts'][0];assert not failure['passed'] and repair['result']['passed']
im=Image.new('RGB',(1920,1080),'#101613');d=ImageDraw.Draw(im);font='/System/Library/Fonts/Helvetica.ttc'
def text(x,y,value,size=30,color='#d2ded5'):d.text((x,y),value,font=ImageFont.truetype(font,size),fill=color)
text(100,70,'SILTA / THE FAILURE-REPAIR LOOP',25,'#a3b4a8');text(100,140,'Failed verification becomes the next CAM input.',52,'#f3f6f2')
for x in [100,1010]:d.rounded_rectangle((x,265,x+810,790),radius=18,fill='#1b2520')
text(135,300,'1  SIMULATION FAILS',30,'#e1b493');text(1045,300,'2  ASTRA REPAIRS · SIMULATOR PASSES',30,'#a7d2b4')
text(135,370,'Hydraulic manifold / fixed target',31)
for i,line in enumerate(['passed: false','issue: '+failure['issues'][0]['code'],'certainty: '+failure['issues'][0]['certainty']]):text(135,450+i*58,line,32)
text(135,685,'Grid cannot establish a pass.',29);text(135,735,'Failure saved before the next proposal.',27)
for i,line in enumerate(textwrap.wrap(repair['proposal']['summary'],49)):text(1045,375+i*47,line,28)
text(1045,590,'junction_cleanup: true',32);text(1045,645,'Other CAM parameters also change.',25)
text(1045,710,f"passed: true   ·   {repair['result']['estimated_time_seconds']:.2f} seconds",35,'#a7d2b4')
a=audit['summary'];text(100,850,f"Fresh failure-memory audit: {a['caught_invalid']} repeated failures caught; {a['false_rejections']} of {a['valid']} valid controls rejected.",33)
text(100,915,'Same frozen geometry. Failed reference has no qualifying speedup score.',28)
text(100,1000,'RETAINED RUN EXCERPTS · SELECTED COUNTEREXAMPLE AUDIT · INDEXED 3+2 / 3 MM DEMO TOLERANCE',20,'#8a9b8f')
im.save(OUT/'05-learning.png')
