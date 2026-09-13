"""Evidence-derived benchmark summaries; failures and null comparisons remain visible."""
import html,json
from pathlib import Path
from ..common import save


def report(root):
    root=Path(root);catalog=json.loads((root/'catalog.json').read_text());rows=[];pairs=[]
    for part in catalog['parts']:
        path=root/'runs'/part['id']/'manifest.json'
        if not path.exists():continue
        m=json.loads(path.read_text());best=m.get('best');reference=m.get('reference')
        baseline=reference['result'].get('estimated_time_seconds') if reference and reference['result']['passed'] else None
        seconds=best['result']['estimated_time_seconds'] if best else None
        row=dict(id=m['id'],name=m['name'],split=m['split'],status=m['status'],reference_seconds=baseline,reference_passed=reference['result']['passed'] if reference else False,best_seconds=seconds,reduction_percent=100*(1-seconds/baseline) if seconds and baseline else None,attempts=len(m['attempts']),failed_attempts=sum(not a['result']['passed'] for a in m['attempts']),loaded_memory_version=m.get('loaded_memory_version',m.get('loaded_memory',{}).get('version',0) if m.get('loaded_memory') else 0),saved_memory_version=m.get('saved_memory_version'),target_sha256=m['target_sha256'],manifest=str(path.resolve()),error=m.get('error'))
        rows.append(row)
        if m.get('paired_audit'):
            pair=dict(id=m['id'])
            for arm in ['cold','warm']:
                r=m['paired_audit'][arm]['result'];pair[arm+'_passed']=r['passed'];pair[arm+'_seconds']=r.get('estimated_time_seconds') if r['passed'] else None
            pairs.append(pair)
    joint=[p for p in pairs if p['cold_passed'] and p['warm_passed']]
    audit=dict(pairs=pairs,cold_valid=sum(p['cold_passed'] for p in pairs),warm_valid=sum(p['warm_passed'] for p in pairs),warm_faster=sum(p['warm_seconds']<p['cold_seconds']-1e-5 for p in joint),warm_slower=sum(p['warm_seconds']>p['cold_seconds']+1e-5 for p in joint),tied=sum(abs(p['warm_seconds']-p['cold_seconds'])<=1e-5 for p in joint),interpretation='One unseeded cold/warm Astra proposal per later part, alternating arm order. Identical target, reference feedback, compiler and budgets; warm receives memory from earlier parts. Cold results are withheld from the warm optimizer. Small sample; persistence does not establish general learning effectiveness.')
    output=dict(parts=rows,held_out_audit=audit,objective='Machining seconds only among passing plans',scope='Indexed 3+2, flat-end tools; 1 mm stock cells and 3 mm demonstration tolerance. Configured tool/fixture collisions and travel limits; not whole-machine certification.')
    save(root/'results.json',output)
    md=['# Indexed five-axis CAM results','',output['scope'],'','| Part | Reference s | Best passing s | Reduction | Status |','|---|---:|---:|---:|---|']
    for r in rows:
        ref=f"{r['reference_seconds']:.2f}" if r['reference_seconds'] is not None else 'FAIL'
        best=f"{r['best_seconds']:.2f}" if r['best_seconds'] is not None else 'None'
        reduction=f"{r['reduction_percent']:.1f}%" if r['reduction_percent'] is not None else 'N/A'
        md.append(f"| {r['name']} | {ref} | {best} | {reduction} | {r['status']} |")
    md+=['','## Sequential learning evaluation','',f"Cold valid: {audit['cold_valid']}/{len(pairs)}. Warm valid: {audit['warm_valid']}/{len(pairs)}. Warm faster: {audit['warm_faster']}; slower: {audit['warm_slower']}; tied: {audit['tied']}.",'',audit['interpretation']]
    md+=['','## Artifacts','','- `videos/five-part-machining-reel.mp4`: accelerated machining replays; per-video receipts record pass/fail and source plan hashes.','- `memory/versions/`: persisted sequential episodes; `audit.json` verifies hashes and model settings.','- `runs/`: actual CAM attempts, geometry results, timing decisions and final stock exports.']
    if (root/'recovery').exists():md+=['- `recovery/`: additional repair attempts; original failed manifests remain preserved.']
    md+=['','Failed plans are excluded from timing scores. A failed reference is not a valid timing baseline. Within-part optimization is not proof of generally effective learning.']
    (root/'RESULTS.md').write_text('\n'.join(md)+'\n');return output
