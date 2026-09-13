import test from 'node:test';
import assert from 'node:assert/strict';
import {stagedSteps,sourceBlocks,stagedStepDuration} from '../applications/control-center/staged-replay.mjs';
test('staged replay preserves generation failure, source attempt and measured verification ordering',()=>{
 const event=(event,attempt,raw={},seconds)=>({event,attempt,raw,seconds});
 const sources=[{name:'cam-0001/cam-attempt-01.py',content:'bad'},{name:'cam-0002/cam-attempt-01.py',content:'repair'}];
 const steps=stagedSteps({sources,events:[event('candidate_generation_started',1),event('cam_generation_failed',1),event('candidate_generation_started',2),event('checks_completed',2,{result:{passed:true}}),event('verification_completed',2,{verification:{status:'passed'}},944.09)]});
 assert.deepEqual(steps.map(s=>s.kind),['drawing','code','failure','code','checks','ready','verification','result']);
 assert.equal(steps[1].source.content,'bad');assert.equal(steps[3].source.content,'repair');
 assert.equal(steps.at(-1).after,944.09);
 assert.equal(steps.some(s=>s.addedMemory||s.addedCheck),false);
});
test('no successful verification means no ready-to-simulate claim',()=>{
 const steps=stagedSteps({sources:[],events:[{event:'verification_completed',raw:{verification:{status:'unknown'}}}]});
 assert.equal(steps.some(s=>s.kind==='ready'),false);
 assert.deepEqual(sourceBlocks('a\nb\nc',2),['a\nb','c']);
});
test('code replay uses the decoded source instead of the escaped execution wrapper',()=>{
 const steps=stagedSteps({sources:[{name:'cam-0001/cam-attempt-01.py',content:'exec(compile(...))'},{name:'cam-0001/cam-source.json',content:'def plan():\n    return tools[1]'}],events:[{event:'candidate_generation_started',attempt:1,raw:{}}]});
 assert.equal(steps[1].source.content,'def plan():\n    return tools[1]');
});

test('each simulation precedes its judge and the live gate precedes final judging',()=>{
 const event=(event,attempt,raw={},seconds)=>({event,attempt,raw,seconds});
 const steps=stagedSteps({sources:[],events:[
  event('verification_completed',2,{verification:{status:'passed'}},944),
  event('supervisor_decision',2,{decision:{action:'improve',instructions:'Reduce air cutting'}}),
  event('candidate_generation_started',3),
  event('checks_completed',3,{result:{passed:true}}),
  event('verification_completed',3,{verification:{status:'passed'}},908),
  event('supervisor_decision',3,{decision:{action:'stop',instructions:'Keep this plan'}}),
 ]});
 assert.deepEqual(steps.map(s=>s.stage),['input','simulate','judge','cam','checks','simulate','simulate','judge','output']);
 assert.equal(steps[5].kind,'ready');
 assert.equal(steps[5].after,undefined,'Do not expose the final estimate before live simulation');
 assert.equal(steps.at(-1).after,908);
 assert.ok(stagedStepDuration({kind:'code'})>=20000);
 assert.ok(stagedStepDuration({kind:'instruction'})>=10000);
});

test('streaming reveals saved source monotonically and completely without changing it',async()=>{
 const {streamedSource}=await import('../applications/control-center/staged-replay.mjs');
 const source='def plan():\n    return "fixed CAD"\n'.repeat(100);
 let previous='';
 for(let elapsed=0;elapsed<=20000;elapsed+=100){const next=streamedSource(source,elapsed,20000);assert.ok(next.startsWith(previous));assert.ok(source.startsWith(next));previous=next;}
 assert.equal(previous,source);
 assert.equal(streamedSource(source,0,20000),'');
});
test('live playback starts once at its gate and judging waits for actual completion',async()=>{
 const {demoPlaybackAction:action}=await import('../applications/control-center/staged-replay.mjs');
 assert.equal(action({kind:'code',status:'ready'}),'none');
 assert.equal(action({kind:'ready',status:'preparing'}),'none');
 assert.equal(action({kind:'ready',status:'ready',requested:false}),'start');
 assert.equal(action({kind:'ready',status:'ready',requested:true}),'none');
 assert.equal(action({kind:'ready',status:'playing',live:true}),'none');
 assert.equal(action({kind:'ready',status:'completed',live:true}),'review');
 assert.equal(action({kind:'ready',status:'completed',live:false}),'watch');
 assert.equal(action({kind:'ready',status:'completed',live:true,fallback:true}),'none');
});
test('uploaded-run controls cannot skip source, checks, or simulation',async()=>{
 const {readFile}=await import('node:fs/promises');
 const html=await readFile(new URL('../applications/control-center/index.html',import.meta.url),'utf8');
 const dialog=html.split('<dialog id="demo-dialog"')[1].split('</dialog>')[0];
 for(const control of ['demo-next','demo-prev','demo-toggle','demo-play'])assert.equal(dialog.includes(control),false);
 assert.ok(dialog.includes('demo-reset'));
});
