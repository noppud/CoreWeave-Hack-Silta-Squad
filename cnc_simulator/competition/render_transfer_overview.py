"""Include both the repeated selected-part study and pre-registered new geometry screen."""
from pathlib import Path
import json,statistics
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).parent;im=Image.new('RGB',(1920,1080),'#101613');d=ImageDraw.Draw(im);font='/System/Library/Fonts/Helvetica.ttc'
def t(x,y,s,n=30,c='#d2ded5'):d.text((x,y),s,font=ImageFont.truetype(font,n),fill=c)
t(90,65,'SILTA / MEMORY TRANSFER, MEASURED',25,'#a3b4a8');t(90,140,'Memory transfer across four different parts.',53,'#f3f6f2')
t(90,240,'Frozen actuator memory · three cold/warm pairs per part · all plans pass',31)
t(90,345,'PART',25,'#a3b4a8');t(745,345,'MEDIAN WARM − COLD',25,'#a3b4a8');t(1280,345,'WARM WINS / TIES / LOSSES',25,'#a3b4a8')
rows=[]
for folder,names in [('repeated-memory-study',{'03-bearing-block':'Bearing block','04-trunnion-cage':'Trunnion cage'}),('new-geometry-memory-study',{'11-indexed-instrument-shell':'New indexed shell','12-three-pocket-plate':'New three-pocket plate'})]:
 data=json.loads((R/folder/'result.json').read_text())
 for part,name in names.items():
  pairs=[p for p in data['pairs'] if p['part']==part];assert len(pairs)==3 and all(p['paired_coverage'] for p in pairs)
  delta=[p['warm_minus_cold_seconds'] for p in pairs];median=statistics.median([100*p['warm_minus_cold_seconds']/p['cold_seconds'] for p in pairs]);rows.append((name,median,sum(x< -1e-6 for x in delta),sum(abs(x)<=1e-6 for x in delta),sum(x>1e-6 for x in delta)))
for i,(name,median,wins,ties,losses) in enumerate(rows):
 y=420+i*110;d.line((90,y+77,1810,y+77),fill='#34423a');t(90,y,name,35);t(790,y,f'{median:+.3f}%',37,'#b8d8bf' if median<0 else '#d9b297' if median>0 else '#d2ded5');t(1380,y,f'{wins} / {ties} / {losses}',35)
t(90,900,'No general speed benefit established. Failure-memory avoidance is evaluated separately.',30)
t(90,966,'New geometries were frozen before proposals. Seeds unavailable; repeated paths are not new strategies.',25)
t(90,1010,'Cage aggregate gains are dominated by one conservative cold draw. Full per-pair results are retained.',24,'#a3b4a8')
im.save(R/'film/transfer-overview.png')
