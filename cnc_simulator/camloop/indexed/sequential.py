"""Five sequential live runs with persisted, auditable episodic CAM memory."""
import copy,time
from pathlib import Path
from ..astra import Astra
from ..common import save,file_hash,digest
from .runner import read,optimize
from .report import report


def remember(root,previous,manifest,roles=None):
    root=Path(root);version=previous['version']+1
    episode=dict(part=manifest['id'],target_sha256=manifest['target_sha256'],status=manifest['status'],attempts=len(manifest['attempts']),passed_attempts=sum(a['result']['passed'] for a in manifest['attempts']),failed_attempts=sum(not a['result']['passed'] for a in manifest['attempts']),source_manifest=str(root/'runs'/manifest['id']/'manifest.json'),saved_at=time.time())
    best=manifest.get('best')
    episode['best_seconds']=best['result']['estimated_time_seconds'] if best else None
    episode['best_strategy']=best['strategy'] if best else None
    episode['failures']=[dict(strategy=a['strategy'],issues=a['result']['issues'][:8]) for a in manifest['attempts'] if not a['result']['passed']]
    if roles:
        try:
            proposal,evidence=roles.ask('indexed_learner',dict(observed_episode=episode,instruction='Summarize an observed planning lesson for the next part. State uncertainty. Do not invent performance improvements or a validation claim.'))
            episode.update(proposed_note=proposal,evidence=evidence,note_status='unvalidated suggestion; future candidates still require checks and simulation')
        except Exception as error:episode['note_error']=str(error)
    memory=dict(version=version,episodes=previous['episodes']+[episode],strategy_prior=copy.deepcopy(episode['best_strategy'] or previous.get('strategy_prior')),prior_source_part=manifest['id'] if best else previous.get('prior_source_part'),guidance='These are observed prior runs, not proof of validity on new geometry. Use the most recent passing strategy only as a starting candidate; adapt it and repeat checks and simulation.',semantics='Episodic memory persistence. No claim that notes or strategy transfer are generally valid.')
    for field in ['learned_checks','repair_observations','speed_guidance']:
        memory[field]=copy.deepcopy(manifest.get('feedback_memory',previous).get(field,[]))
    version_path=root/'memory/versions'/f'{version:04d}.json';save(version_path,memory);save(root/'memory.json',memory)
    if digest(read(root/'memory.json'))!=digest(memory):raise ValueError('Memory read-back mismatch')
    snapshot=root/'memory'/f'source-{version:04d}.json';save(snapshot,manifest)
    save(root/'memory'/f'commit-{version:04d}.json',dict(source_snapshot=str(snapshot),version=version,sha256=file_hash(root/'memory.json'),part=manifest['id'],source_manifest_sha256=file_hash(snapshot),read_back_verified=True))
    return memory


def run_sequential(root,attempts=3):
    root=Path(root).resolve();catalog=read(root/'catalog.json')
    # The explicit five-part sequence supersedes the earlier development/holdout split.
    catalog['learning_split']='Five sequential parts. Each run sees only memories committed after earlier parts. Later cold/warm first proposals compare no memory with accumulated prior-run memory.'
    for entry in catalog['parts']:entry['split']='sequential'
    save(root/'catalog.json',catalog)
    memory=read(root/'memory.json') if (root/'memory.json').exists() else dict(version=0,episodes=[],strategy_prior=None)
    if not (root/'memory.json').exists():save(root/'memory.json',memory);save(root/'memory/versions/0000.json',memory)
    for i,entry in enumerate(catalog['parts']):
        existing=root/'runs'/entry['id']/'manifest.json'
        if existing.exists():
            # Resume only fully committed runs; do not silently double-run models.
            if i<len(memory['episodes']) and memory['episodes'][i]['part']==entry['id']:continue
            raise ValueError('Uncommitted existing run requires explicit recovery: '+entry['id'])
        fresh=read(root/'memory.json')
        if digest(fresh)!=digest(memory):raise ValueError('Memory changed unexpectedly')
        job=read(entry['job']);job['split']='sequential'
        m=optimize(job,root,fresh if fresh['version'] else None,attempts=attempts,paired=fresh['version']>0)
        m['loaded_memory_version']=fresh['version'];m['loaded_memory_sha256']=file_hash(root/'memory.json');save(existing,m)
        roles=Astra(root/'memory/evidence'/entry['id'],timeout=180)
        memory=remember(root,fresh,m,roles)
        m['saved_memory_version']=memory['version'];save(existing,m)
        print('MEMORY COMMITTED',memory['version'],'after',entry['id'],flush=True)
        report(root)
    return report(root)
