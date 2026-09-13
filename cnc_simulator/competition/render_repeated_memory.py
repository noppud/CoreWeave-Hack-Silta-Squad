"""Plot all six paired observations from the repeated memory study."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).with_name('repeated-memory-study');data=json.loads((R/'result.json').read_text());pairs=data['pairs'];summary=json.loads((R/'summary.json').read_text());assert len(pairs)==6
im=Image.new('RGB',(1920,1080),'#101613');d=ImageDraw.Draw(im);font='/System/Library/Fonts/Helvetica.ttc'
def t(x,y,s,n=28,c='#d2ded5'):d.text((x,y),s,font=ImageFont.truetype(font,n),fill=c)
t(90,55,'SILTA / REPEATED MEMORY TRANSFER',24,'#a3b4a8');t(90,115,'Memory helps some parts. Measure every pair.',51,'#f3f6f2')
t(90,200,f"{summary['warm_faster']} warm faster · {summary['cold_faster']} cold faster · {summary['ties']} tie · all 12 plans pass",30)
maximum=max(max(p['cold_seconds'],p['warm_seconds']) for p in pairs);scale=900/maximum
for i,p in enumerate(pairs):
 y=300+i*98;label=('Bearing block' if p['part'].startswith('03') else 'Trunnion cage')+f" / {p['repetition']}";t(90,y+12,label,27)
 for j,(key,color) in enumerate([('cold_seconds','#849087'),('warm_seconds','#b8d8bf' if p['warm_minus_cold_seconds']<=0 else '#d9b297')]):
  value=p[key];yy=y+j*35;d.rectangle((460,yy,460+value*scale,yy+22),fill=color);t(480+value*scale,yy-4,f'{value:.2f}s',23)
 delta=p['warm_minus_cold_seconds'];t(1530,y+12,f'{delta:+.2f}s',29)
t(460,915,'Cold (gray) / frozen actuator memory (colored)',27);t(1460,915,'Warm minus cold',25)
t(90,980,'Three repetitions on each of two selected parts. Alternating order; no memory updates during study.',25)
t(90,1020,'Most aggregate savings come from one conservative cold cage plan. No unseen-part or physical machining claim.',23,'#a3b4a8')
im.save(R/'paired-comparison.png')
