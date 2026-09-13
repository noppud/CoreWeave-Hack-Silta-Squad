import test from 'node:test';
import assert from 'node:assert/strict';
import {replaySteps, replayTransition} from '../applications/control-center/replay.mjs';
const event=(name,raw={},attempt=null)=>({event:name,raw,attempt});
test('replay preserves failure, repair, and judge ordering from recorded events',()=>{
  const events=[event('candidate_created',{candidate:{id:'candidate-0001'},candidate_digest:'one'},1),event('checks_completed',{result:{passed:false,issues:['collision']}},1),event('candidate_created',{candidate:{id:'candidate-0002'},candidate_digest:'two'},2),event('checks_completed',{result:{passed:true}},2),event('verification_completed',{verification:{status:'failed'}},2),event('supervisor_decision',{decision:{action:'stop'}})];
  const steps=replaySteps({events,sources:[],media:[]});
  assert.deepEqual(steps.map(s=>s.stage),['cam','checks','cam','checks','fusion','judge']);
  assert.equal(steps[1].event.raw.result.passed,false);
  assert.equal(steps[4].event.raw.verification.status,'failed');
  assert.equal(steps.length,events.length);
});
test('code and recordings cannot leak backward from the final candidate',()=>{
  const sources=[{name:'cam-0001/cam-source.json',content:'first'},{name:'cam-0002/cam-source.json',content:'second'}];
  const clip={candidate:'candidate-0002',digest:'two',kind:'machining'};
  const events=[event('candidate_created',{candidate:{id:'candidate-0001'},candidate_digest:'one'},1),event('verification_completed'),event('candidate_created',{candidate:{id:'candidate-0002'},candidate_digest:'two'},2),event('verification_completed')];
  const steps=replaySteps({events,sources,media:[clip]});
  assert.equal(steps[0].source.content,'first');
  assert.equal(steps[1].video,undefined);
  assert.equal(steps[2].source.content,'second');
  assert.equal(steps[3].video,clip);
});
test('missing evidence stays missing and does not invent a successful stage',()=>{
  const steps=replaySteps({events:[event('verification_completed',{verification:{status:'unknown'}})],sources:[],media:[{kind:'machining'}]});
  assert.equal(steps.length,1);assert.equal(steps[0].video,undefined);assert.equal(steps[0].source,null);
  assert.equal(steps[0].event.raw.verification.status,'unknown');
});

test('three feedback paths preserve distinct repair and optimization semantics',()=>{
  const events=[event('candidate_created',{candidate:{id:'candidate-0001'}},1),event('checks_completed',{result:{passed:false}},1),event('candidate_created',{candidate:{id:'candidate-0002'}},2),event('verification_completed',{verification:{status:'failed'}},2),event('learning_change_saved',{change_kind:'checks'}),event('candidate_created',{candidate:{id:'candidate-0003'}},3),event('verification_completed',{verification:{status:'passed'}},3),event('supervisor_decision',{decision:{action:'improve'}}),event('candidate_created',{candidate:{id:'candidate-0004'}},4)];
  const steps=replaySteps({events,sources:[],media:[]});
  assert.equal(replayTransition(steps[1],steps[2]),'Fail → regenerate code');
  assert.equal(replayTransition(steps[3],steps[4]),'Fail → add a check → regenerate code');
  assert.equal(steps[4].stage,'checks');
  assert.equal(steps[5].stage,'cam');
  assert.equal(steps[8].effect,'run-memory');
  assert.equal(steps[9].intent,'Generating a faster plan');
  assert.equal(steps[8].candidate,steps[7].candidate);
  assert.equal(steps[0].intent,null);
  assert.equal(steps[4].source,null);
});
