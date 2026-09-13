"""Summarize every pre-specified pair without treating missing/failed runs as speedups."""
import json,statistics
from pathlib import Path

def summarize(pairs):
 valid=[p for p in pairs if p['paired_coverage']]
 deltas=[p['warm_minus_cold_seconds'] for p in valid]
 return dict(total_pairs=len(pairs),passing_pairs=len(valid),warm_faster=sum(d< -1e-6 for d in deltas),cold_faster=sum(d>1e-6 for d in deltas),ties=sum(abs(d)<=1e-6 for d in deltas),median_warm_minus_cold_seconds=statistics.median(deltas) if deltas else None,cold_total_seconds=sum(p['cold_seconds'] for p in valid),warm_total_seconds=sum(p['warm_seconds'] for p in valid))

def main():
 root=Path(__file__).with_name('repeated-memory-study');data=json.loads((root/'result.json').read_text());assert len(data['rows'])==12 and len(data['pairs'])==6
 s=summarize(data['pairs']);(root/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
 lines=['# Repeated cold/warm CAM comparison','',data['protocol']['scope'],'','Frozen memory contains only the actuator episode. Both arms receive the same reference result, fixed target, compiler, and verifier. No study results update memory. Order alternates within pairs; runs are not seeded or blinded.','', '| Part | Repeat | Cold seconds | Warm seconds | Warm minus cold |','|---|---:|---:|---:|---:|']
 fmt=lambda v:'not passing' if v is None else f'{v:.3f}'
 for p in data['pairs']:lines.append(f"| {p['part']} | {p['repetition']} | {fmt(p['cold_seconds'])} | {fmt(p['warm_seconds'])} | {fmt(p['warm_minus_cold_seconds'])} |")
 lines+=['',f"{s['passing_pairs']}/{s['total_pairs']} paired passes. Warm faster: {s['warm_faster']}; cold faster: {s['cold_faster']}; ties: {s['ties']}.",'','These selected repeated comparisons test the effect of this frozen memory on these parts. They do not establish generalization to unseen CAD or physical machining. Timing is the fixed simulator estimate. Failures and inference errors remain in result.json and never receive a passing time score.']
 (root/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(s,indent=2))
if __name__=='__main__':main()
