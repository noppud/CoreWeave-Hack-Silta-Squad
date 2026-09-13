from pathlib import Path
import subprocess
from PIL import Image,ImageDraw
import imageio_ffmpeg
root=Path(__file__).parent/'film';ff=imageio_ffmpeg.get_ffmpeg_exe();times=[2,14,27,39,51,64,77,90,98,104,109,113];sheet=Image.new('RGB',(1440,1080),'#202020')
for i,t in enumerate(times):
 p=root/f'review-{t}.png';subprocess.run([ff,'-y','-loglevel','error','-ss',str(t),'-i',str(root/'silta-evidence-first-cut.mp4'),'-frames:v','1',str(p)],check=True)
 im=Image.open(p);im.thumbnail((480,260));x=(i%3)*480;y=(i//3)*270;sheet.paste(im,(x,y));ImageDraw.Draw(sheet).text((x+8,y+244),f'{t}s',fill='white')
sheet.save(root/'contact-sheet.jpg')
