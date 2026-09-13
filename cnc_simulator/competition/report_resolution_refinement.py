"""Report every refinement outcome; never reinterpret old simulation artifacts."""
import json
from pathlib import Path
R=Path(__file__).parent/'resolution-refinement'
def main():
 rows=json.loads((R/'result.json').read_text());assert len(rows)==2
 lines=['# Resolution-only follow-up','','Two predeclared unresolved cases were rerun at 0.5 mm with a four-million-cell cap. Target, fixture, tool movements, feeds, and 3 mm tolerance were unchanged. Earlier runs stopped because their two-million-cell cap was too small.','', '| Case | 1 mm result | 0.5 mm result | Cells | Estimated machining seconds | Compute seconds |','| --- | --- | --- | --- | --- | --- |']
 for row in rows:
  old=row['original_result'];new=row['result']
  lines.append(f"| {row['case']} | {old['validity']} / {old['verification']} | {new['validity']} / {new['verification']} | {new.get('numerics',{}).get('cells','unavailable')} | {new['estimated_time_seconds']:.3f} | {row['wall_seconds']:.1f} |")
  assert abs(old['estimated_time_seconds']-new['estimated_time_seconds'])<1e-9
 lines+=['','## Interpretation','','A changed verdict from this experiment is a numerical-resolution result, not a CAM improvement or a physical measurement. The unchanged path has unchanged modeled machining time. Each original verdict still describes its original resolution; an unresolved result never becomes a pass without rerunning verification.','', 'The exact-failure memory includes the complete job contract and implementation hashes. A changed resolution is a different contract and must not inherit an old rejection as an unconditional physical-defect claim. No memory rules, production policy, or benchmark scores are updated by this report.','','The geometry backend uses floating-point signed distances, not exact arithmetic. This experiment retains the coarse 3 mm demonstration tolerance.']
 for row in rows:
  lines+=['',f"## {row['case']}",'',json.dumps(row['result']['issues'],indent=2)]
 (R/'REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines[:9]))
if __name__=='__main__':main()
