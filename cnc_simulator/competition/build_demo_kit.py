"""Bundle verified presentation artifacts using an explicit allowlist."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];C=ROOT/'competition';DEST=C/'release/demo-kit'
FILES={
 'film.mp4':C/'film/silta-demo.mp4',
 'judge-questions.md':C/'JUDGE_QA.md',
 'organizer-refresh.md':C/'ORGANIZER_REFRESH.md',
 'film-captions.srt':C/'film/silta-demo.srt',
 'film-narration.md':C/'film/NARRATION.md',
 'complex-machining.mp4':ROOT/'workspace-complex-three/videos/three-complex-parts.mp4',
 'source/simulator-source.tar.gz':C/'release/simulator-source.tar.gz',
 'source/source-manifest.json':C/'release/source-manifest.json',
 'source/README.md':C/'release/README.md',
 'source/live_terminal.py':C/'live_terminal.py',
 'evidence/complex-results.json':ROOT/'workspace-complex-three/summary.json',
 'evidence/complex-iterations.json':ROOT/'workspace-complex-three/iteration-audit.json',
 'evidence/complex-weave.json':ROOT/'workspace-complex-three/weave-publication.json',
 'evidence/film-receipt.json':C/'film/receipt.json',
 'evidence/reel-receipt.json':ROOT/'workspace-complex-three/videos/reel-verification.json',
 'evidence/memory-persistence.md':C/'memory-chain-audit.md',
 'evidence/memory-persistence.json':C/'memory-chain-audit.json',
 'evidence/repeated-memory-study.md':C/'repeated-memory-study/REPORT.md',
 'evidence/new-geometry-study.md':C/'new-geometry-memory-study/REPORT.md',
 'evidence/resolution-refinement.md':C/'resolution-refinement/REPORT.md',
 'evidence/failure-memory-eval.json':C/'failure-memory-eval/result.json',
 'evidence/hosted-checks.json':C/'hosted-checks.json',
 'evidence/aria-ablation.json':C/'aria-ablation/result.json',
 'evidence/aria-ablation-weave.json':C/'aria-ablation-publication.json',
 'evidence/aria-followup.txt':C/'aria-followup-response.txt',
 'evidence/current-preflight.json':C/'rehearsal-05/current-preflight.json',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 DEST.mkdir(parents=True,exist_ok=True)
 film=json.loads(FILES['evidence/film-receipt.json'].read_text());assert sha(FILES['film.mp4'])==film['sha256'] and film['decode_check']=='passed' and film['seconds']<120
 reel=json.loads(FILES['evidence/reel-receipt.json'].read_text());assert sha(FILES['complex-machining.mp4'])==reel['sha256'] and reel['full_decode_passed']
 rows=json.loads(FILES['evidence/complex-results.json'].read_text());assert len(rows)==3 and all(r['reference']['passed'] and r['best']['passed'] for r in rows)
 manifest=[]
 for name,source in FILES.items():
  path=DEST/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,path)
  manifest.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
 guide='''# SILTA demo kit

Start with [the 116-second film](film.mp4). It is a silent edited recording with selectable English captions; [narration](film-narration.md) is included. The longer [complex machining reel](complex-machining.mp4) shows three actual movement-driven stock-removal replays. Neither video is live execution.

## Evidence to explain

| Claim | Supporting artifact | Boundary |
| --- | --- | --- |
| Three complex parts improve over fixed references | [Raw results](evidence/complex-results.json) | Constant-speed estimates; 1 mm cells / 3 mm tolerance |
| Timing feedback can yield a better next proposal | [Iteration audit](evidence/complex-iterations.json) | Carrier improves; manifold ties; drum gets slower and retains earlier best |
| Memory reaches later requests | [Persistence audit](evidence/memory-persistence.md) | Persistence is not causal speed improvement |
| Transfer was actually measured | [Repeated parts](evidence/repeated-memory-study.md), [new geometries](evidence/new-geometry-study.md) | No useful general memory-speed benefit established |
| ARIA advice was tested | [ARIA follow-up](evidence/aria-followup.txt), [12-case results](evidence/aria-ablation.json) | Advisory, not simulation authority |
| Hosted sandbox executes exact-failure checks | [Hosted receipt](evidence/hosted-checks.json) | This is check execution, not full stock simulation in the sandbox |
| Weave scores the three complex outcomes | [Completed evaluation links](evidence/complex-weave.json) | Network/account access required to inspect hosted records |

See [judge questions](judge-questions.md) for evidence-specific answers and [organizer refresh](organizer-refresh.md) for the latest public schedule. Source paths in the Q&A refer to the original workspace; the evidence table above provides portable copies.

## Live sequence

1. Start a fresh PDF job after reviewing its extracted dimensions.
2. While it runs, explain the fixed-target loop and show measured results.
3. Return to the actual generated CAM, checks, stock simulation, timing and saved memory. If still running, say so; use a labeled completed replay as fallback.
4. Explain that failed geometry never earns a qualifying time score. Show the actual carrier improvement and retained slower drum trial.

On the original demo computer, use `http://127.0.0.1:2744/workspace.html`. Run the included `source/live_terminal.py JOB_ID` using Python to observe its actual events. This read-only monitor does not approve a drawing or start/restart a job. `--port` can select another local server.

For a new computer, follow [source installation and complex-part commands](source/README.md). Account/model access is required for fresh Astra proposals. The source archive does not contain existing run history. The recorded results started with memory version 14; a fresh unseeded run starts at 0 and may differ.

## Scope

Indexed 3+2, flat-end mills. No simultaneous-five-axis, controller, cutting-force or production-certification claim. Native Weave Signals are not configured. Hosted checks and ARIA/Weave records are distinct from the geometric simulator. Some raw evidence retains original machine-local artifact paths for provenance; these are not portable links or bundled full run directories. This kit is local and has not been submitted or publicly hosted.
'''
 (DEST/'START.md').write_text(guide)
 manifest.append(dict(path='START.md',bytes=(DEST/'START.md').stat().st_size,sha256=sha(DEST/'START.md')))
 (DEST/'manifest.json').write_text(json.dumps(dict(files=manifest,scope='Portable selected evidence and source, not full histories or installed runtime'),indent=2)+'\n')
 archive=C/'release/silta-demo-kit.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for name in [x['path'] for x in manifest]+['manifest.json']:z.write(DEST/name,'silta-demo-kit/'+name)
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for row in manifest:assert hashlib.sha256(z.read('silta-demo-kit/'+row['path'])).hexdigest()==row['sha256']
 receipt=dict(files=len(manifest)+1,bytes=archive.stat().st_size,sha256=sha(archive),all_archive_hashes_verified=True,film_seconds=film['seconds'])
 (C/'release/demo-kit-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
