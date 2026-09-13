"""Freeze two untouched geometry definitions and protocol before observing any CAM."""
import sys,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camloop.indexed.parts import prepare,top,side,ring_holes
from camloop.common import save,file_hash
R=Path(__file__).parent;OUT=R/'new-geometry-memory-study'
parts=[dict(id='11-indexed-instrument-shell',name='Indexed instrument shell',split='pre_registered_transfer',stock_shape=dict(kind='cylinder',radius=32,height=44),features=[top('Interior seat',[0,0],[0,0],20,10)]+[side(f'Window {a}',a,0,18,29,8,16) for a in [45,135,225,315]]+ring_holes(26,4,44)),dict(id='12-three-pocket-plate',name='Three-pocket fixture plate',split='pre_registered_transfer',stock_shape=dict(kind='box',size=[80,56,24]),features=[top('Left recess',[-25,-9],[-16,-9],7,8),top('Right recess',[16,-9],[25,-9],7,10),top('Rear circular seat',[0,13],[0,13],8,12)])]
if OUT.exists():raise ValueError('Protocol directory already exists; refusing to replace pre-registration')
OUT.mkdir();save(OUT/'pre-registration.json',dict(parts=copy.deepcopy(parts),selection='Geometry-only: cylinder with indexed side windows and flange holes resembles source actuator; low rectangular three-pocket top-only plate is deliberately dissimilar. Definitions frozen before any model proposal or timing.',memory_sha256=file_hash(R/'repeated-memory-study/frozen-memory.json'),repetitions=3,proposal_random_seed=None,seed_limitation='Codex transport exposes no sampling seed. Independent ephemeral calls are recorded; do not claim paired or reproducible seeds.',primary='Per-part median of passing paired warm-minus-cold percentage; report all feasibility differences separately. Warm-only failure defeats an applicability claim. Opposite signs indicate mixed transfer. No automated promotion.',sensitivity='Report all pair deltas and effect after removing the largest absolute delta; repeated movement hashes count once for strategy diversity.'))
prepare(OUT/'geometry',parts=parts)
