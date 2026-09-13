"""Run authoritative indexed removal; export sparse visualization checkpoints."""
from pathlib import Path
import json,time
import numpy as np
from cncsim.simulator import simulate
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'examples/indexed-housing'
OUT=ROOT/'workspace-housing/simulation'
plan=json.loads((BASE/'plan.json').read_text())
last=time.monotonic(); removed=None; initial=None

def step(s):
    global last,removed,initial
    if initial is None:
        initial=s['nominal'].copy();removed=np.full(len(initial),-1,dtype=np.int32)
    removed[(removed<0)&initial&~s['nominal']]=s['move']
    if time.monotonic()-last>10:
        print('Move',s['move'],'/',len(plan['moves']),flush=True);last=time.monotonic()
    if s['move']==len(plan['moves'])-1:
        np.savez_compressed(OUT/'removal.npz',initial=initial,removed=removed,origin=s['origin'],shape=s['shape'],pitch=s['pitch'])
OUT.mkdir(parents=True,exist_ok=True)
result=simulate(plan,base_dir=BASE,output_dir=OUT,on_step=step,snapshot_stride=30)
print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},indent=2),flush=True)
