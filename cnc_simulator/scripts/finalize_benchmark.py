"""Verify and package actual benchmark artifacts; never creates simulation verdicts."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
import argparse

import imageio_ffmpeg
from camloop.benchmark import report
from render_benchmark import render


def finalize(workspace):
    root=Path(workspace).resolve()
    results=report(root)
    if len(results['parts'])!=10 or any(r['status']=='running' for r in results['parts']):
        raise ValueError('Ten finished runs are required')
    render(root)
    package=root/'delivery';package.mkdir(exist_ok=True)
    checks=[]
    for row in results['parts']:
        manifest_path=Path(row['manifest']);m=json.loads(manifest_path.read_text())
        if not m['best']:
            checks.append(dict(part=row['part'],passed=False,reason='No passing plan'));continue
        sim=manifest_path.parent/f'attempt-{m["best"]["attempt"]:03d}'/'simulation'
        result=json.loads((sim/'result.json').read_text())
        assert result['passed'] is True and result['validity']=='valid' and not result['issues']
        assert result['estimated_time_seconds']==m['best']['seconds']
        plan=json.loads((manifest_path.parent/'best-plan.json').read_text())
        target=Path(plan['target']['path'])
        assert hashlib.sha256(target.read_bytes()).hexdigest()==m['target_hash']==result['target_sha256']
        part=package/row['part'];part.mkdir(exist_ok=True)
        shutil.copyfile(target,part/'target.stl');plan['target']['path']='target.stl'
        (part/'best-plan.json').write_text(json.dumps(plan,indent=2))
        shutil.copyfile(sim/'final_stock.ply',part/'final_stock.ply')
        shutil.copyfile(sim/'result.json',part/'simulation-result.json')
        video=root/'videos'/f'{row["part"]}.mp4';receipt=json.loads(video.with_suffix('.json').read_text())
        assert receipt['passed'] is True
        assert receipt['source_sha256']==hashlib.sha256((sim/'playback.json').read_bytes()).hexdigest()
        frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(video))
        assert frames==receipt['frames'] and abs(seconds-receipt['video_seconds'])<.1
        shutil.copyfile(video,part/'machining.mp4')
        checks.append(dict(part=row['part'],passed=True,video_frames=frames,video_seconds=seconds,target_sha256=m['target_hash']))
    for name in ['results.json','RESULTS.md','experiment.json','transfer-results.json']:
        path=root/name
        if path.exists():shutil.copyfile(path,package/name)
    for path in (root/'report').glob('*'):
        if path.is_file():shutil.copyfile(path,package/path.name)
    reel=root/'videos/ten-part-machining-reel.mp4'
    if reel.exists():shutil.copyfile(reel,package/reel.name)
    (package/'artifact-checks.json').write_text(json.dumps(checks,indent=2))
    valid=[r for r in results['parts'] if r['best_valid_seconds'] is not None]
    ref=sum(r['reference_seconds'] for r in valid);best=sum(r['best_valid_seconds'] for r in valid)
    summary=f'''# Silta: ten-part CAM results

{len(valid)}/10 parts have passing plans. Combined same-part reference time: {ref:.3f} s.
Combined best passing time: {best:.3f} s ({100*(1-best/ref):.2f}% lower).

CAM generates movements, checks run, simulation returns pass/fail, and the timing-only
judge accepts the best verified time or requests another CAM attempt. Unresolved
geometry fails verification; it never scores. Target geometry stays fixed.

See RESULTS.md for each part and run completion status. Reaching an attempt limit
retains any passing plan but is not a judge acceptance or proof of optimality.
Time gains versus fixed 120 mm/min reference paths include feed changes up to the
frozen 240 mm/min limit. They must not all be attributed to cross-part learning.
The separate transfer-results.json/transfer-summary.md records the one-pair learning
audit and its limitations. No performance gain is fabricated if learning regresses.

Each part folder contains the frozen target, a runnable best plan (only its target
file path is made relative), final machined stock, the actual simulation result and
an MP4 from the recorded nominal stock-removal timeline. Source manifests, every
candidate and model-role evidence remain in the experiment workspace.

Videos show simulated workpiece/tool motion; they do not show a physical machine run
or establish full-machine collision safety. The downloaded Haas remains a separate
reference visual. These ten parts use accepted capsule/circular pocket unions,
including disconnected features, intersections and different depths. This is not
arbitrary CAD feature recognition. Timing assumes constant commanded speeds.

Reproduce a plan after installing the local simulator:
`python -m cncsim <part-folder>/best-plan.json --output <new-output-folder>`.
'''
    (package/'README.md').write_text(summary)
    archive=root/'ten-part-results.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(package.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(package))
    print(json.dumps(dict(parts_passed=len(valid),reference_seconds=ref,best_seconds=best,reduction_percent=100*(1-best/ref),package=str(archive)),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace');finalize(p.parse_args().workspace)
