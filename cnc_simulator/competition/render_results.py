"""Paired reference/best chart drawn directly from retained manifests."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1];out=root/'competition/film'
font='/System/Library/Fonts/Helvetica.ttc'
im=Image.new('RGB',(1920,1080),'#101613');d=ImageDraw.Draw(im)
def text(x,y,s,size=30,c='#eff5ef'):d.text((x,y),s,font=ImageFont.truetype(font,size),fill=c)
rows=[]
for p in sorted((root/'workspace-complex-three/runs').glob('*/manifest.json')):
 m=json.loads(p.read_text());r=m['reference']['result'];b=m['best']['result']
 if r['passed'] and b['passed']:rows.append((m['name'],r['estimated_time_seconds'],b['estimated_time_seconds']))
old=sum(r[1] for r in rows);new=sum(r[2] for r in rows)
text(100,70,'SILTA / SAME PARTS, SAME CONSTRAINTS',25,'#99ad9f')
text(100,165,f'{100*(old-new)/old:.1f}% less machining time',72)
text(100,280,f'{old:,.1f}s reference  /  {new:,.1f}s verified plans',32,'#afc2b4')
for i,(name,a,b) in enumerate(rows):
 y=390+i*130;text(100,y,name,29);x=600;scale=1000/max(v[1] for v in rows)
 d.rounded_rectangle((x,y,x+a*scale,y+25),radius=3,fill='#47574d')
 d.rounded_rectangle((x,y+35,x+b*scale,y+60),radius=3,fill='#9dc5a7')
 text(x+a*scale+15,y-4,f'{a:.1f}s',24,'#a8b4ac');text(x+b*scale+15,y+31,f'{b:.1f}s',24)
trials=[json.loads(p.read_text()) for p in sorted((root/'workspace-complex-three/runs').glob('*/manifest.json'))]
carrier=trials[0]['attempts']; first=carrier[0]['result']['estimated_time_seconds']; later=carrier[1]['result']['estimated_time_seconds']
text(100,825,f'After judge feedback: carrier {first:.1f}s to {later:.1f}s ({100*(first-later)/first:.1f}% further reduction)',28)
text(100,875,'Manifold tied. Drum got slower; the loop retained its earlier best.',27,'#afc2b4')
text(100,965,'3 new complex parts / all passing pairs. Estimated times; 3 mm demo tolerance.',24,'#8da293')
im.save(out/'03-results.png')
