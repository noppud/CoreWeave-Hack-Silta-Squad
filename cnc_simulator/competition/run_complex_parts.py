"""Three new high-feature-count indexed parts; retain every attempt and verdict."""
import sys,copy,time,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camloop.indexed.parts import prepare,top,side,ring_holes
from camloop.indexed.runner import read,optimize
from camloop.indexed.sequential import remember
from camloop.indexed.artifacts import export_part
from camloop.common import save,file_hash
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'workspace-complex-three'
parts=[
 dict(id='13-twelve-window-carrier',name='Twelve-window carrier',split='complex_stress_test',stock_shape=dict(kind='cylinder',radius=44,height=60),features=[top('Deep central cavity',[0,0],[0,0],26,8),top('Stepped bearing register',[0,0],[0,0],31,48)]+[side(f'Radial window {a}',a,0,24,40,5,20) for a in range(0,360,30)]+ring_holes(37,12,60)),
 dict(id='14-multi-gallery-manifold',name='Multi-gallery manifold',split='complex_stress_test',stock_shape=dict(kind='box',size=[88,76,60]),features=[top(f'Deep chamber {x}',[x,0],[x,0],10,10) for x in [-24,0,24]]+[top('Connecting upper gallery',[-24,0],[24,0],6,28)]+[top(f'Counterbore {x}',[x,0],[x,0],13,50) for x in [-24,0,24]]+[side(f'Cross port {a} offset {y}',a,y,22,22,6,8) for a in [0,90,180,270] for y in [-16,16]]+[top(f'Mount {x} {y}',[x,y],[x,y],4,48) for x in [-35,35] for y in [-27,27]]),
 dict(id='15-staggered-lattice-drum',name='Staggered lattice drum',split='complex_stress_test',stock_shape=dict(kind='cylinder',radius=42,height=56),features=[top('Deep interior',[0,0],[0,0],27,8),top('Upper register',[0,0],[0,0],31,48)]+[side(f'Lower window {a}',a,0,18,22,5,21) for a in range(0,360,45)]+[side(f'Upper window {a}',a+22.5,0,39,43,5,21) for a in range(0,360,45)]+ring_holes(36,8,56))]
def main():
 global WORK
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--workspace',type=Path,default=WORK)
 parser.add_argument('--memory-seed',type=Path,help='Optional retained memory JSON; default starts at version zero')
 parser.add_argument('--prepare-only',action='store_true',help='Freeze and validate CAD without model calls or simulation')
 args=parser.parse_args();WORK=args.workspace.resolve()
 seed=args.memory_seed.resolve() if args.memory_seed else None
 memory=read(seed) if seed else dict(version=0,episodes=[],strategy_prior=None)
 if WORK.exists():raise ValueError('Refusing to overwrite complex-part evidence')
 WORK.mkdir(parents=True)
 save(WORK/'protocol.json',dict(created_at=time.time(),parts=copy.deepcopy(parts),attempts_per_part=2,memory_seed_sha256=file_hash(seed) if seed else None,initial_memory_version=memory['version'],purpose='Stress-test complex new indexed geometry; all failures retained, not a controlled memory-transfer experiment. Fixed 1 mm cells and 3 mm demo tolerance.'))
 prepare(WORK,parts=parts);save(WORK/'memory.json',memory);save(WORK/'memory/versions'/f"{memory['version']:04d}.json",memory)
 if args.prepare_only:
  print("CAD frozen and validated; no model or simulation was run",flush=True);return
 results=[]
 for entry in read(WORK/'catalog.json')['parts']:
  job=read(entry['job']);print('PART',job['id'],'FEATURES',len(job['features']),flush=True)
  loaded=copy.deepcopy(memory);m=optimize(job,WORK,loaded,attempts=2,paired=False)
  m['loaded_memory_version']=loaded['version'];m['loaded_memory_sha256']=file_hash(WORK/'memory.json')
  memory=remember(WORK,loaded,m);m['saved_memory_version']=memory['version'];save(WORK/'runs'/job['id']/'manifest.json',m)
  try:
   receipt=export_part(WORK,job['id']);m['playback_export']=receipt
  except Exception as error:m['playback_error']=str(error)
  save(WORK/'runs'/job['id']/'manifest.json',m);results.append(dict(id=job['id'],name=job['name'],features=len(job['features']),orientations=len({tuple(f['bc']) for f in job['features']}),status=m['status'],reference=m['reference']['result'] if m.get('reference') else None,best=m['best']['result'] if m.get('best') else None,attempts=[r['result'] for r in m['attempts']],loaded_memory_version=loaded['version'],saved_memory_version=memory['version'],playback_error=m.get('playback_error')))
  save(WORK/'summary.json',results);print('FINISHED',job['id'],m['status'],flush=True)
 print('ALL THREE FINISHED',flush=True)
if __name__=='__main__':main()
