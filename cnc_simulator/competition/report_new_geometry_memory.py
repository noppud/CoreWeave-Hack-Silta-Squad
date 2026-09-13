import json,statistics,hashlib
from pathlib import Path
R=Path(__file__).with_name('new-geometry-memory-study');data=json.loads((R/'result.json').read_text());assert len(data['rows'])==12
rows=[]
for part in data['protocol']['parts']:
 pairs=[p for p in data['pairs'] if p['part']==part];valid=[p for p in pairs if p['paired_coverage']];pct=[100*p['warm_minus_cold_seconds']/p['cold_seconds'] for p in valid]
 rows.append(dict(part=part,paired_passes=len(valid),median_warm_minus_cold_percent=statistics.median(pct) if pct else None,warm_only_failures=sum(p['cold_passed'] and not p['warm_passed'] for p in pairs),cold_unique_paths=len({r['movement_sha256'] for r in data['rows'] if r['part']==part and r['arm']=='cold'}),warm_unique_paths=len({r['movement_sha256'] for r in data['rows'] if r['part']==part and r['arm']=='warm'})))
checks=[]
for row in data['rows']:
 a=row['result'];plan=json.loads((Path(a['path'])/'plan.json').read_text());assert hashlib.sha256(Path(plan['target']['path']).read_bytes()).hexdigest()==row['target_sha256'];response=Path(a['evidence']);req=response.with_name(response.name.replace('.response.json','.request.json'));assert (R/'pre-registration.json').stat().st_mtime < req.stat().st_mtime
 config=json.loads(response.read_text());assert config['model']=='gpt-6-astra' and config['reasoning_effort']=='low' and config['requested_service_tier']=='fast';checks.append(row['case'])
(R/'summary.json').write_text(json.dumps(dict(parts=rows,integrity_checked=checks,conclusion='No robust cross-part speed benefit established. Shell warm slower in every repeat; plate ties twice with a negligible warm gain once. No memory rule promoted.'),indent=2)+'\n')
lines=['# Pre-registered new-geometry memory screen','','Definitions and comparison rules were saved before all twelve model requests. Frozen actuator-only memory; alternating arm order; no study feedback updates. The transport exposes no sampling seed.','', '| Part | Repeat | Cold seconds | Warm seconds | Warm minus cold |','|---|---:|---:|---:|---:|']
for p in data['pairs']:lines.append(f"| {p['part']} | {p['repetition']} | {p['cold_seconds']:.3f} | {p['warm_seconds']:.3f} | {p['warm_minus_cold_seconds']:+.3f} |")
lines+=['','All twelve plans passed the unchanged simulator. The shell warm plan is slower in all three repeats; the plate has two exact ties and a 0.005-second warm gain. This screen does not establish a useful general speed benefit from memory. No runtime memory-applicability rule is promoted.','', 'The first warm trial of each part has a derived stock-removal playback; this preselected trial is not labeled the best plan.']
(R/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,indent=2))
