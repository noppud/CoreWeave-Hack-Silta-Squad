"""Failure-derived exact checks and immediate timing-observation memory.

Exact repeats may be rejected; transferable diagnosis is advisory and cannot pass
or reject a new geometry. No generated code runs in the verifier.
"""
import copy
from pathlib import Path
from ..common import digest,file_hash


def geometry_key(job,strategy):
    # Include implementation bytes so rules cannot survive a compiler/verifier fix.
    root=Path(__file__).resolve().parents[2]
    sources=['camloop/indexed/cam.py','cncsim/simulator.py','cncsim/geometry.py','cncsim/indexing.py']
    parameters={k:v for k,v in strategy.items() if 'feed' not in k}
    parameters.setdefault('junction_cleanup',False)
    return digest(dict(contract=job,parameters=parameters,implementation={p:file_hash(root/p) for p in sources}))


def learned_preflight(job,strategy,memory):
    key=geometry_key(job,strategy)
    for rule in (memory or {}).get('learned_checks',[]):
        if rule['geometry_key']==key:
            return [dict(code='learned_identical_failure',description='This exact geometry and motion configuration already failed full simulation. Changing feed alone cannot repair material removal or clearance.',moves=[],source=rule['source'],original_issues=rule['issues'])]
    return []


def record_failure(memory,job,row):
    rule=dict(id='exact-'+geometry_key(job,row['strategy'])[:12],geometry_key=geometry_key(job,row['strategy']),source=row['path'],issues=copy.deepcopy(row['result']['issues']),semantics='Blocks only identical geometry/motion under matching implementation and fixed inputs. Feed-only changes do not change geometric validity.')
    if not any(r['id']==rule['id'] for r in memory.setdefault('learned_checks',[])):memory['learned_checks'].append(rule)
    observation=dict(part=job['id'],source=row['path'],issues=rule['issues'],advisory='Repair geometry before optimizing time. For excess material at intersecting pockets, consider junction_cleanup; any changed path must pass simulation.')
    memory.setdefault('repair_observations',[]).append(observation)
    return rule


def record_timing(memory,job,row,decision):
    note=dict(part=job['id'],source=decision['evidence'],seconds=row['result']['estimated_time_seconds'],text='The timing judge requested a faster verified plan. '+decision['value']['reason'])
    memory.setdefault('speed_guidance',[]).append(note)
    return note
