"""Display the preselected first warm trial of each new part, not a best-of-study plan."""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camloop.common import save
from camloop.indexed.artifacts import export_part
ROOT=Path(__file__).resolve().parents[1];STUDY=Path(__file__).with_name('new-geometry-memory-study');OUT=ROOT/'workspace-transfer-preview';receipts=[]
for part in ['11-indexed-instrument-shell','12-three-pocket-plate']:
 row=json.loads((STUDY/(part+'-r1-warm')/'record.json').read_text());trial=row['result'];assert trial['result']['passed']
 job=json.loads((STUDY/'geometry/parts'/part/'job.json').read_text());job['name']+=' / first warm trial'
 save(OUT/'parts'/part/'job.json',job)
 save(OUT/'runs'/part/'manifest.json',dict(id=part,name=job['name'],status='retained_trial',attempts=[trial],best=None,reference=None,provenance=str(STUDY/(part+'-r1-warm')/'record.json')))
 receipt=export_part(OUT,part,selection='attempt-0');receipt['selection_semantics']='Preselected first warm trial; no best-of-study selection';receipts.append(receipt)
save(STUDY/'preview-receipts.json',receipts)
