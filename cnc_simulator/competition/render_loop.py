"""Readable map of the implemented loop, not an execution animation."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
OUT=Path(__file__).parent/'film';font='/System/Library/Fonts/Helvetica.ttc'
im=Image.new('RGB',(1920,1080),'#101613');d=ImageDraw.Draw(im)
def text(x,y,t,size=28,color='#f3f6f2'):
 d.text((x,y),t,font=ImageFont.truetype(font,size),fill=color)
def box(x,y,w,h,title,detail):
 d.rounded_rectangle((x,y,x+w,y+h),radius=14,fill='#1d2a23',outline='#637e6b',width=2)
 text(x+24,y+25,title,34);text(x+24,y+80,detail,23,'#b5c8ba')
def arrow(points,color='#91bca0'):
 d.line(points,fill=color,width=4,joint='curve')
 x,y=points[-1];px,py=points[-2]
 if x>px:d.polygon([(x,y),(x-13,y-8),(x-13,y+8)],fill=color)
 elif x<px:d.polygon([(x,y),(x+13,y-8),(x+13,y+8)],fill=color)
 elif y>py:d.polygon([(x,y),(x-8,y-13),(x+8,y-13)],fill=color)
 else:d.polygon([(x,y),(x-8,y+13),(x+8,y+13)],fill=color)
text(110,82,'SILTA / THE IMPLEMENTED LOOP',25,'#a3b4a8')
text(110,165,'Keep the part. Improve the plan.',66)
text(110,275,'Frozen target + tools + stock + fixtures + machine limits',29,'#b5c8ba')
for x,title,detail in [(110,'CAM agent','Chooses plan changes'),(530,'Checks','Reject invalid movements'),(950,'Stock simulation','Geometry + collision gate'),(1370,'Timing judge','Accept or request faster')]:box(x,415,340,145,title,detail)
for x in [450,870,1290]:arrow([(x,487),(x+80,487)])
text(885,374,'pass',22,'#a3b4a8');text(1305,374,'pass',22,'#a3b4a8')
box(580,735,620,140,'Saved feedback and memory','Measured failures, passing strategies, timing')
arrow([(700,560),(700,660),(800,660),(800,735)])
arrow([(1120,560),(1120,735)])
text(790,615,'failure diagnosis',23,'#b5c8ba')
arrow([(1540,560),(1540,805),(1200,805)])
text(1310,670,'try faster',25,'#b5c8ba')
arrow([(580,805),(280,805),(280,560)])
text(110,960,'MACHINING TIME IS THE SCORE. GEOMETRY AND COLLISIONS ARE GATES.',26,'#a3b4a8')
im.save(OUT/'01-loop.png')
