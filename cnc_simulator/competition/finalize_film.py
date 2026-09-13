"""Finalize the evidence film with selectable captions and verifiable provenance."""
import hashlib,json,subprocess
from pathlib import Path
import imageio_ffmpeg
ROOT=Path(__file__).parent;OUT=ROOT/'film'
CUES=[
(0,4,'The part stays fixed. The agent changes the machining plan.'),
(4,8,'Checks → stock-removal simulation → timing judge → CAM feedback.'),
(8,15,'Actual indexed machining replay, driven by the submitted movements.'),
(15,23,'The table reorients between cuts. Stock is removed along cutter sweeps.'),
(23,29,'Three new complex parts: 75.8 → 20.8 estimated minutes.'),
(29,35,'72.5% below reference. The carrier improved another 6.4% after judge feedback.'),
(35,42,'This staggered drum uses 17 indexed orientations and 26 features.'),
(42,50,'The drum’s next proposal was slower. The loop kept its earlier passing plan.'),
(50,56,'The manifold reference fails. Astra receives the diagnosis and revises CAM.'),
(56,62,'The repair passes. A saved exact-match check catches repeated failures.'),
(62,68,'Weave scores retained records: geometry gates and machining-time metrics.'),
(68,74,'ARIA suggested an experiment. We ran 12 cases and scoped its advice.'),
(74,78,'24 fresh plans across four parts: memory transfer is mixed.'),
(78,82,'New geometries show no useful general speed benefit from memory.'),
(82,90,'Three chambers, cross-ports and registers: actual manifold cutter movements.'),
(90,96,'Recorded fresh PDF job: reviewed drawing → CAM → checks → simulation.'),
(96,103,'These are actual saved events and artifacts. Waiting time is compressed.'),
(103,110,'Timing feedback and memory are retained for inspection and later proposals.'),
(110,115.9,'Prototype: indexed 3+2, 1 mm cells, 3 mm tolerance. Not production verification.')]
def stamp(t):
 ms=round(t*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finalize():
 ff=imageio_ffmpeg.get_ffmpeg_exe();source=OUT/'silta-evidence-first-cut.mp4'
 frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(source))
 assert seconds<120 and CUES[-1][1]<=seconds
 assert all(0<=a<b and len(t)<=150 for a,b,t in CUES)
 assert all(CUES[i][1]<=CUES[i+1][0] for i in range(len(CUES)-1))
 captions=OUT/'silta-demo.srt';captions.write_text(''.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{t}\n\n' for i,(a,b,t) in enumerate(CUES)))
 temp=OUT/'silta-demo.pending.mp4';destination=OUT/'silta-demo.mp4'
 subprocess.run([ff,'-y','-loglevel','error','-i',str(source),'-i',str(captions),'-map','0:v:0','-map','1:0','-c:v','copy','-c:s','mov_text','-metadata:s:s:0','language=eng','-metadata:s:s:0','title=Evidence narration','-disposition:s:0','default','-movflags','+faststart',str(temp)],check=True)
 subprocess.run([ff,'-v','error','-i',str(temp),'-map','0:v:0','-f','null','-'],check=True)
 # Round-trip the embedded captions, rather than trusting only the mux exit code.
 extracted=OUT/'captions-readback.srt'
 subprocess.run([ff,'-y','-loglevel','error','-i',str(temp),'-map','0:s:0',str(extracted)],check=True)
 text=extracted.read_text()
 assert all(caption in text for _,_,caption in CUES)
 temp.replace(destination)
 receipt=json.loads((OUT/'receipt.json').read_text())
 receipt.update(frames=frames,seconds=seconds,sha256=sha(destination),decode_check='passed',audio='silent; selectable embedded English captions and timed NARRATION.md',captions=dict(path=str(captions.resolve()),sha256=sha(captions),cues=len(CUES),embedded_readback=True),source_film_sha256=sha(source))
 receipt['source_hashes']={p:sha(Path(p)) for p in receipt['sources']}
 receipt['status']='Captioned evidence film; decoded and embedded captions read back successfully.'
 (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(seconds=seconds,frames=frames,captions=len(CUES),sha256=receipt['sha256'],decode='passed')))
if __name__=='__main__':finalize()
