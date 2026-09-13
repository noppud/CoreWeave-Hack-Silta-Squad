"""Reproducible ten-part live evaluation, with preserved failures and per-part controls."""
import copy
import json
from pathlib import Path

import numpy as np
import trimesh
from cncsim import simulate

from .astra import Astra
from .common import file_hash, load_job, save
from .controller import run_job
from .demo import ROOT, build_corpus


def prepare_benchmark(workspace):
    root = Path(workspace).resolve()
    if (root / 'benchmark.json').exists():
        return json.loads((root / 'benchmark.json').read_text())
    if not (root / 'corpus/index.json').exists():
        build_corpus(root)
    cases = []
    # Different pocket topologies, including intersecting and disconnected features.
    specs = [
        ("straight-slot", [([4,7],[10,7],3)]),
        ("round-recess", [([7,7],[7,7],2.8)]),
        ("twin-slots", [([4,4],[10,4],3),([4,10],[10,10],3)]),
        ("cross-channel", [([4,7],[10,7],3.2),([7,4],[7,10],3.2)]),
        ("l-channel", [([4,4],[10,4],2.6),([4,4],[4,10],2.6)]),
        ("three-wells", [([4,4],[4,4],3.4),([10,4],[10,4],3.4),([7,10],[7,10],3.4)]),
        ("stepped-slots", [([4,4],[10,4],2.6),([4,10],[10,10],4)]),
        ("diagonal-channel", [([4,4],[10,10],3)]),
        ("tee-channel", [([4,10],[10,10],3.6),([7,4],[7,10],3.6)]),
        ("u-channel", [([4,4],[4,10],3.2),([4,4],[10,4],3.2),([10,4],[10,10],3.2)]),
    ]
    for i, (label, pockets) in enumerate(specs, 1):
        name = f'part-{i:02d}-{label}'
        dest = root / 'jobs' / name
        dest.mkdir(parents=True, exist_ok=True)
        radius = 1.6
        plan = json.loads((ROOT / 'examples/pocket.json').read_text())
        plan.update(stock=dict(type='box', min=[0, 0, 0], max=[14, 14, 6]), target=dict(type='mesh', path='target.stl'))
        plan['tools'] = {'T1': plan['tools']['T1']}
        plan['tools']['T1']['diameter_mm'] = 2 * radius
        plan['tools']['T1']['shaft_diameter_mm'] = 2 * radius
        plan['initial_position'] = [2, 2, 8]
        def moves(depth_offset, feed, dwell=0):
            result = []
            for a, b, floor in pockets:
                z = floor + depth_offset
                result.extend([dict(type='rapid', to=[*a, 8]),
                    dict(type='cut', to=[*a, z], feed_mm_per_min=feed),
                    dict(type='cut', to=[*b, z], feed_mm_per_min=feed),
                    dict(type='cut', to=[*b, 8], feed_mm_per_min=feed)])
            return result + [dict(type='dwell', seconds=dwell), dict(type='rapid', to=[2, 2, 8])]
        plan['moves'] = moves(-1.6, 120, 1)
        stock = trimesh.creation.box([14, 14, 6]); stock.apply_translation([7, 7, 3])
        removals = []
        features = []
        for a, b, floor in pockets:
            ends = []
            for xy in [a, b]:
                m = trimesh.creation.cylinder(radius=radius, height=8-floor, sections=128)
                m.apply_translation([*xy, (8+floor)/2]); ends.append(m)
            removals.append(trimesh.convex.convex_hull(np.vstack([m.vertices for m in ends])))
            features.append(dict(centerline_start=a, centerline_end=b, radius=radius, floor_z=floor, stock_top_z=6))
        removal = trimesh.boolean.union(removals, engine='manifold') if len(removals)>1 else removals[0]
        trimesh.boolean.difference([stock, removal], engine='manifold').export(dest / 'target.stl')
        save(dest / 'plan.json', plan)
        job = dict(id=name, plan='plan.json', family='capsule_pocket' if len(features)==1 else 'pocket_set',
                   feature=features[0] if len(features)==1 else dict(pockets=features),
                   feed_limits_mm_min={'T1': 240}, max_moves=100, final_position=[2, 2, 8])
        save(dest / 'job.json', job)
        baseline = copy.deepcopy(plan); baseline['moves'] = moves(0, 120)
        result = simulate(baseline, base_dir=dest)
        if result['validity'] != 'valid':
            raise ValueError(f'{name} reference unresolved: {result["validity"]}')
        save(dest / 'reference-plan.json', baseline)
        save(dest / 'reference-result.json', result)
        cases.append(dict(id=name, job=str(dest / 'job.json'), target_sha256=file_hash(dest / 'target.stl'),
                          reference_seconds=result['estimated_time_seconds'], features=features))
        print(f'Prepared {name}: verified reference {result["estimated_time_seconds"]:.3f}s', flush=True)
    index = dict(cases=cases, families=['capsule_pocket', 'pocket_set'], gate_parts=['part-a', 'part-c'],
                 description='Ten distinct parts: slots, circular wells, intersecting channels and multiple depths. Trusted analytic feature descriptions accompany frozen meshes.')
    save(root / 'benchmark.json', index)
    return index


def report(workspace):
    root = Path(workspace).resolve()
    index = json.loads((root / 'benchmark.json').read_text())
    rows = []
    for case in index['cases']:
        path = root / 'runs' / f'benchmark-{case["id"]}' / 'manifest.json'
        if not path.exists():
            continue
        m = json.loads(path.read_text())
        valid = [a for a in m['attempts'] if a.get('result') and a['result']['validity'] == 'valid']
        best = m['best']['seconds'] if m['best'] else None
        rows.append(dict(part=case['id'], status=m['status'], reason=m['reason'],
            budget_exhausted=any(e['type']=='attempt_limit' for e in m.get('events',[])),
            judge_review_after_budget=bool(m.get('final_timing_review')),
            reference_seconds=case['reference_seconds'], first_valid_seconds=valid[0]['result']['estimated_time_seconds'] if valid else None,
            best_valid_seconds=best, improvement_vs_reference_percent=100*(1-best/case['reference_seconds']) if best is not None else None,
            attempts=len(m['attempts']), simulated=sum(a.get('stage') == 'simulated' for a in m['attempts']),
            invalid=sum(a.get('result', {}).get('validity') == 'invalid' for a in m['attempts'] if a.get('result')),
            uncertain_failures=sum(a['result'].get('verification') == 'unresolved' or a['result']['validity'] == 'unknown' for a in m['attempts'] if a.get('result')),
            loaded_knowledge_version=m.get('loaded_knowledge', {}).get('version'),
            promoted=sum(bool(x['evaluation']['promoted']) for x in m['learning']),
            manifest=str(path), best_plan=str(path.parent / 'best-plan.json') if best is not None else None))
    result = dict(parts=rows, planned_parts=10, parts_with_valid_plan=sum(r['best_valid_seconds'] is not None for r in rows),
                  interpretation='Per-part improvements compare with verified 120 mm/min reference paths. Sequential inheritance alone is not causal evidence of learning. No raw-time comparison across different geometries.',
                  timing='Constant commanded speeds; no acceleration or controller dynamics. Only passing plans score; unresolved clearance is a failure.')
    save(root / 'results.json', result)
    text = '# Ten-part CAM evaluation\n\n' + result['interpretation'] + '\n\n' + result['timing'] + '\n\n'
    text += '| Part | Status | Reference s | First valid s | Best valid s | Gain vs reference | Failures / uncertain failures | Loaded knowledge |\n|---|---|---:|---:|---:|---:|---:|---:|\n'
    def f(v): return '—' if v is None else f'{v:.3f}'
    for r in rows:
        text += f'| {r["part"]} | {r["status"]} | {f(r["reference_seconds"])} | {f(r["first_valid_seconds"])} | {f(r["best_valid_seconds"])} | {f(r["improvement_vs_reference_percent"])}% | {r["invalid"]} / {r["uncertain_failures"]} | {r["loaded_knowledge_version"]} |\n'
    text += '\nAn attempt limit is recorded separately in results.json, including any later timing-judge review of the retained passing plan. No run proves global optimality.\n'
    text += '\nAll targets are different combinations of capsule/circular pockets; this does not establish arbitrary-part CAM capability. Full machine collision verification is outside these results.\n'
    (root / 'RESULTS.md').write_text(text)
    return result


def run_benchmark(workspace, attempts=6):
    root = Path(workspace).resolve()
    index = prepare_benchmark(root)
    for case in index['cases']:
        if file_hash(Path(case['job']).parent / 'target.stl') != case['target_sha256']:
            raise ValueError('Benchmark target changed')
        manifest = root / 'runs' / f'benchmark-{case["id"]}' / 'manifest.json'
        if manifest.exists():
            old = json.loads(manifest.read_text())
            if old['status'] == 'running':
                raise RuntimeError('Existing unfinished run; inspect before resuming')
        else:
            run_job(case['job'], root, f'benchmark-{case["id"]}', Astra,
                    max_attempts=attempts, guidance_evaluations=1)
        report(root)
    return report(root)


def evaluate_transfer(workspace):
    """Held-out paired one-shot audit. Results never feed the learning promotion gate."""
    from .common import candidate, cheap_checks
    from .learning import Knowledge, context_for
    root = Path(workspace).resolve()
    index = json.loads((root / 'benchmark.json').read_text())
    knowledge = Knowledge(root / 'knowledge', 'astra', root / 'corpus/index.json')
    state = copy.deepcopy(knowledge.state)
    audit = root / 'transfer-audit'
    audit.mkdir(exist_ok=True)
    roles = Astra(audit / 'evidence')
    rows = []
    for i, case in enumerate(index['cases']):
        path = audit / f'{case["id"]}.json'
        if path.exists():
            row = json.loads(path.read_text())
            if row['knowledge_version'] != state['version']:
                raise ValueError('Transfer audit knowledge version changed')
            rows.append(row); continue
        job = load_job(case['job'])
        row = dict(part=case['id'], knowledge_version=state['version'])
        # Alternate order to reduce systematic time/order effects. No claim of seeded determinism.
        variants = ['cold', 'learned'] if i % 2 == 0 else ['learned', 'cold']
        for variant in variants:
            rules = state['rules'] if variant == 'learned' else []
            guidance = state['guidance'] if variant == 'learned' else ''
            print(f'Transfer audit {case["id"]}: {variant}', flush=True)
            try:
                response, evidence = roles.ask('planner', context_for(job, job['plan'], {}, guidance, rules))
                plan = candidate(job, response)
                issues = cheap_checks(job, plan, rules)
                result = dict(validity='invalid', issues=issues, estimated_time_seconds=None) if issues else simulate(plan)
                row[variant] = dict(result=result, evidence=evidence, plan=plan)
            except Exception as error:
                row[variant] = dict(result=dict(validity='invalid', passed=False, verification='execution_error', estimated_time_seconds=None), error=str(error))
        save(path, row); rows.append(row)
    def valid(r): return r['result']['validity'] == 'valid'
    summary = dict(knowledge_version=state['version'], rows=rows,
        cold_valid=sum(valid(r['cold']) for r in rows), learned_valid=sum(valid(r['learned']) for r in rows),
        faster_learned=sum(valid(r['cold']) and valid(r['learned']) and r['learned']['result']['estimated_time_seconds'] < r['cold']['result']['estimated_time_seconds']-1e-9 for r in rows),
        slower_learned=sum(valid(r['cold']) and valid(r['learned']) and r['learned']['result']['estimated_time_seconds'] > r['cold']['result']['estimated_time_seconds']+1e-9 for r in rows),
        limitations='One unseeded pair per part. Same frozen job and prior plan, alternating order. Audit data is not used for promotion. The final guidance has already seen optimization runs on these parts, so this measures retained behavior, not unseen-part generalization.')
    save(root / 'transfer-results.json', summary)
    return summary
