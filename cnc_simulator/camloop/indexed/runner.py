"""Measured indexed CAM -> checks -> simulation -> timing judge, plus held-out audit."""
import copy,json,time,traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from cncsim import simulate
from ..astra import Astra
from ..common import save,digest,file_hash
from .learning import learned_preflight,record_failure,record_timing
from .cam import BASELINE,compile_plan,cheap_checks,verify_job

CONTRACT='''Return CAM parameters, not tool movements. A deterministic compiler creates movements before tests and simulation. It clears each capsule/circular feature in depth layers using a centerline and nested capsule contours, with radial track spacing diameter*stepover_fraction. It retracts with the cutter engaged to a common clearance plane 8 mm above the stock. Changing B/C or tools requires the fixed park. orientation order groups B/C then tool; tool order groups tool then B/C. shortest_c picks the equivalent C angle closest to the current C angle. Every plan ends at the same park and top orientation. Depth and stepover can change coverage certification. junction_cleanup=true adds safe smaller-tool plunge cleanup inside the union of overlapping pockets at common depths. Enable this when separate feature clearing leaves junction material. It adds actual cutting/tool-change time and is still fully simulated. More circle segments reduce chord error but increase move count, not a separate optimization cost. Simulation uses conservative voxel bounds. Never change geometry, resolution, tolerance, machine, tools or speed ceilings. Only estimated machining seconds of passing plans score. This is geometric/timing simulation; physical cutting forces and controller acceleration are not modeled.'''


def read(path):return json.loads(Path(path).read_text())

def evaluate(job,strategy,path,memory=None):
    path=Path(path);path.mkdir(parents=True,exist_ok=False);started=time.time()
    row=dict(strategy=copy.deepcopy(strategy),path=str(path),stage='checks')
    try:
        plan,phases=compile_plan(job,strategy);save(path/'plan.json',plan);save(path/'phases.json',phases)
        checks=cheap_checks(job,plan)+learned_preflight(job,strategy,memory);save(path/'checks.json',dict(passed=not checks,issues=checks))
        if checks:row['result']=dict(passed=False,validity='invalid',verification='checks',issues=checks)
        else:
            fingerprint=digest(plan);result=simulate(plan,output_dir=path/'simulation',snapshot_stride=max(1,len(plan['moves'])//12))
            if digest(plan)!=fingerprint:raise ValueError('Simulator changed plan')
            verify_job(job);row.update(result=result,stage='simulated',moves=len(plan['moves']))
    except (ValueError,TypeError,KeyError) as error:
        row['result']=dict(passed=False,validity='invalid',verification='checks',issues=[dict(code='input',description=str(error),moves=[])])
    row['wall_seconds']=time.time()-started;save(path/'evaluation.json',row);return row


def planner_context(job,previous,feedback,memory):
    return dict(compiler_contract=CONTRACT,part=dict(id=job['id'],name=job['name'],stock=job['stock_shape'],features=job['features']),fixed_tools=job['plan']['tools'],fixed_limits=job['limits'],resolution_mm=job['plan']['resolution_mm'],tolerance_mm=job['plan']['tolerance_mm'],parameter_ranges=dict(stepover_fraction=[.15,.95],stepdown_mm=[1,12],segments_per_circle=[24,96]),previous_strategy=previous,feedback=feedback,retained_memory=memory)


def ask_candidate(roles,job,previous,feedback,memory,path):
    proposal,evidence=roles.ask('indexed_planner',planner_context(job,previous,feedback,memory))
    row=evaluate(job,proposal['strategy'],path,memory=memory);row.update(proposal=proposal,evidence=evidence);save(Path(path)/'evaluation.json',row);return row


def judge(roles,row,best,history,remaining):
    result=row['result']
    if not result['passed']:raise ValueError('Failed simulation cannot reach timing judge')
    context=dict(objective='Minimize estimated machining seconds among passing plans',current_seconds=result['estimated_time_seconds'],time_breakdown=result['time_breakdown'],best_seconds=best['result']['estimated_time_seconds'],verified_time_history=[x['result']['estimated_time_seconds'] for x in history if x['result']['passed']],attempts_remaining=remaining,guidance_evaluation_available=False,active_guidance=[])
    decision,evidence=roles.ask('supervisor',context)
    return dict(value=decision,evidence=evidence)


def optimize(job,root,memory,*,attempts=3,paired=False):
    directory=Path(root)/'runs'/job['id'];directory.mkdir(parents=True,exist_ok=False)
    roles=Astra(directory/'evidence',timeout=240)
    manifest=dict(id=job['id'],name=job['name'],split=job['split'],status='running',started_at=time.time(),loaded_memory=copy.deepcopy(memory),target_sha256=job['target_sha256'],attempts=[],events=[],best=None,reference=None)
    def event(kind,**values):
        manifest['events'].append(dict(type=kind,time=time.time(),**values));manifest['stage']=kind;save(directory/'manifest.json',manifest);print(job['id'],kind,flush=True)
    active_memory=copy.deepcopy(memory or {})
    manifest['feedback_memory']=active_memory
    def persist_feedback():save(directory/'feedback-memory.json',active_memory)
    try:
        event('reference_simulation')
        baseline=evaluate(job,BASELINE,directory/'reference');manifest['reference']=baseline
        best=baseline if baseline['result']['passed'] else None
        previous=BASELINE;feedback=baseline['result']
        if best is None:
            event('reference_failed_repair_required',issues=feedback['issues'])
            record_failure(active_memory,job,baseline);persist_feedback();event('simulation_to_test_memory')
        if paired:
            arms={};order=['cold','warm'] if int(job['id'][:2])%2 else ['warm','cold']
            for arm in order:
                event('held_out_'+arm+'_planning')
                arms[arm]=ask_candidate(roles,job,BASELINE,baseline['result'],active_memory if arm=='warm' else None,directory/f'audit-{arm}')
            manifest['paired_audit']=arms;event('held_out_pair_completed')
            # Only the warm arm can seed the warm optimization. Cold evidence is withheld.
            first=arms['warm']
        else:first=None
        for i in range(attempts):
            event('cam_planning',attempt=i)
            row=first if i==0 and first else ask_candidate(roles,job,previous,feedback,active_memory,directory/f'attempt-{i:02d}')
            row['index']=i;manifest['attempts'].append(row)
            event('simulation_pass' if row['result']['passed'] else 'simulation_fail',attempt=i,issues=row['result']['issues'])
            if row['result']['passed']:
                if best is None or row['result']['estimated_time_seconds']<best['result']['estimated_time_seconds']:best=row;event('best_updated',seconds=best['result']['estimated_time_seconds'])
                manifest['best']=best;decision=judge(roles,row,best,manifest['attempts'],attempts-i-1);row['judge']=decision
                event('timing_judge',action=decision['value']['action'])
                if decision['value']['action']=='stop':manifest['status']='completed';break
                record_timing(active_memory,job,row,decision);persist_feedback();event('judge_to_cam_memory')
                previous=best['strategy'];feedback=dict(result=row['result'],request='Try a faster strategy. The timing judge does not prescribe a strategy.')
            else:
                if row.get('stage')=='simulated':
                    record_failure(active_memory,job,row);persist_feedback();event('simulation_to_test_memory')
                event('test_gate_to_cam_repair')
                previous=row['strategy'];feedback=row['result']
        else:
            # A final failed proposal still leaves the verified incumbent. Ask the
            # timing-only judge about that incumbent, recording budget exhaustion.
            manifest['budget_exhausted']=True
            if best is not None:
                decision=judge(roles,best,best,manifest['attempts']+[baseline],0);manifest['final_judge']=decision
                manifest['status']='completed' if decision['value']['action']=='stop' else 'incomplete'
            else:manifest['status']='failed'
        manifest['best']=best
        if best is not None:save(directory/'best-plan.json',read(Path(best['path'])/'plan.json'))
        verify_job(job)
        event('run_completed',status=manifest['status'])
    except Exception as error:
        manifest.update(status='incomplete',error=str(error),traceback=traceback.format_exc());event('interrupted',reason=str(error))
    manifest['finished_at']=time.time();save(directory/'manifest.json',manifest);return manifest


def promote_memory(root,dev_runs):
    root=Path(root);path=root/'learning';path.mkdir(exist_ok=True)
    candidates=[m['best'] for m in dev_runs if m.get('best') and m['best']['result']['passed']]
    if len(candidates)!=2:raise ValueError('Both development runs must retain passing CAM')
    candidates.sort(key=lambda r:r['result']['estimated_time_seconds']/next(m['reference']['result']['estimated_time_seconds'] for m in dev_runs if m['best'] is r))
    chosen=candidates[0]['strategy'];roles=Astra(path/'evidence',timeout=240)
    evidence_context=[dict(part=m['id'],reference_seconds=m['reference']['result']['estimated_time_seconds'],attempts=[dict(strategy=a['strategy'],result=a['result']) for a in m['attempts']]) for m in dev_runs]
    proposal,evidence=roles.ask('indexed_learner',dict(development_evidence=evidence_context,selected_prior=chosen,instruction='Summarize transferable planning lessons supported by these trials. This is a proposal, not a validated claim. No held-out part is available.'))
    checks=[]
    for m in dev_runs:
        job=read(root/'parts'/m['id']/'job.json')
        checks.append(evaluate(job,chosen,path/f'gate-{m["id"]}'))
    promoted=all(r['result']['passed'] and r['result']['estimated_time_seconds']<m['reference']['result']['estimated_time_seconds'] for r,m in zip(checks,dev_runs))
    # Guidance text is not promoted on trust: this gate promotes only the tested
    # strategy prior. The text remains an unverified explanatory proposal.
    memory=dict(version=1 if promoted else 0,strategy_prior=chosen if promoted else None,training_parts=[m['id'] for m in dev_runs],guidance='Retrieve this evaluated CAM strategy as a starting prior; re-plan for the new geometry and run both gates. Prior success is not a validity guarantee.' if promoted else '',scope='Indexed capsule-feature jobs under the fixed compiler and manufacturing limits',promoted=promoted)
    save(path/'evaluation.json',dict(proposal=proposal,proposal_evidence=evidence,checks=checks,promoted=promoted,criterion='The same strategy must pass fresh simulation on both development parts and beat each fixed reference. Only strategy prior is promoted; free-text proposal is not treated as verified guidance.'))
    save(root/'memory-frozen.json',memory);return memory


def worker(args):
    job_path,root,memory,attempts=args
    return optimize(read(job_path),root,memory,attempts=attempts,paired=True)


def run_benchmark(root,attempts=3):
    root=Path(root).resolve();catalog=read(root/'catalog.json')['parts'];runs=[]
    for entry in catalog[:2]:runs.append(optimize(read(entry['job']),root,None,attempts=attempts))
    memory=promote_memory(root,runs)
    # Both geometry split and memory are fixed before any held-out inference.
    save(root/'holdout-freeze.json',dict(memory_sha256=file_hash(root/'memory-frozen.json'),parts=catalog[2:],frozen_at=time.time()))
    with ProcessPoolExecutor(max_workers=2) as pool:
        for result in pool.map(worker,[(e['job'],str(root),memory,attempts) for e in catalog[2:]]):runs.append(result)
    from .report import report
    return report(root)
