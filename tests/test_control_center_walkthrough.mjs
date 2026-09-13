import test from 'node:test';
import assert from 'node:assert/strict';
import {buildWalkthrough,walkthroughOrder,walkthroughKnowledge} from '../applications/control-center/walkthrough.mjs';

const parts=Array.from({length:5},(_,i)=>({id:`part-${i}`}));
const checks=[{title:'Fixture clearance'},{title:'Protect finished sides'}];
const memories=['Reduce unnecessary retracts','Use the largest suitable cutter','Group operations by tool'];
test('long-to-short presentation keeps actual estimates and spreads learning through late parts',()=>{
  const inputs=Array.from({length:14},(_,i)=>({id:`p-${i}`,summary:{best_seconds:(i+1)*60}}));
  const ordered=walkthroughOrder(inputs),knowledge=walkthroughKnowledge(checks,memories);
  assert.equal(inputs[0].id,'p-0');assert.equal(ordered[0].id,'p-13');
  const means=ordered.map((_,i)=>ordered.slice(0,i+1).reduce((sum,p)=>sum+p.summary.best_seconds,0)/(i+1));
  assert.ok(means.every((value,i)=>i===0||value<means[i-1]));
  const steps=buildWalkthrough(ordered,knowledge.checks,knowledge.memories);
  const atFive=steps.findLast(s=>s.partIndex===4);
  assert.ok(atFive.checks.length<knowledge.checks.length);
  assert.ok(atFive.memories.length<knowledge.memories.length);
  assert.ok(steps.some(s=>s.partIndex>=10&&s.addedCheck));
  assert.ok(steps.some(s=>s.partIndex>=10&&s.addedMemory));
  assert.equal(steps.at(-1).checks.length,6);assert.equal(steps.at(-1).memories.length,5);
});

test('walkthrough starts empty and carries both kinds of learning into each next part',()=>{
  const steps=buildWalkthrough(parts,checks,memories);
  assert.deepEqual(steps[0].checks,[]);assert.deepEqual(steps[0].memories,[]);
  for(let i=1;i<steps.length;i++){
    const prev=steps[i-1],s=steps[i];
    assert.ok(s.checks.length>=prev.checks.length);
    assert.ok(s.memories.length>=prev.memories.length);
    if(s.partIndex!==prev.partIndex){
      assert.equal(prev.stage,'output');assert.equal(s.stage,'input');
      assert.deepEqual(s.checks,prev.checks);assert.deepEqual(s.memories,prev.memories);
      assert.equal(s.attempt,1);
    }
  }
  assert.deepEqual(steps.at(-1).checks,checks);assert.deepEqual(steps.at(-1).memories,memories);
  assert.equal(steps.filter(s=>s.completed).length,5);
});

test('failed checks regenerate code without changing the CAD or adding knowledge',()=>{
  const steps=buildWalkthrough(parts,checks,memories);
  for(const [i,s] of steps.entries())if(s.stage==='checks'&&s.passed===false){
    const next=steps[i+1];
    assert.equal(next.stage,'cam');assert.equal(next.partIndex,s.partIndex);
    assert.equal(next.attempt,s.attempt+1);
    assert.deepEqual(next.checks,s.checks);assert.deepEqual(next.memories,s.memories);
  }
});

test('every simulation failure adds exactly one check before regenerating the same part',()=>{
  const steps=buildWalkthrough(parts,checks,memories);
  for(const [i,s] of steps.entries())if(s.stage==='fusion'&&s.passed===false){
    const added=steps[i+1],next=steps[i+2];
    assert.ok(added.addedCheck);assert.equal(added.checks.length,s.checks.length+1);
    assert.deepEqual(added.memories,s.memories);
    assert.equal(next.stage,'cam');assert.equal(next.attempt,s.attempt+1);
    assert.equal(added.partIndex,s.partIndex);assert.equal(next.partIndex,s.partIndex);
  }
});

test('every slow judgement adds exactly one prompt memory before retrying the same CAD',()=>{
  const steps=buildWalkthrough(parts,checks,memories);
  for(const [i,s] of steps.entries())if(s.stage==='judge'&&s.passed===false){
    const added=steps[i+1],next=steps[i+2];
    assert.ok(added.addedMemory);assert.equal(added.memories.length,s.memories.length+1);
    assert.deepEqual(added.checks,s.checks);
    assert.equal(added.stage,'cam');assert.equal(next.stage,'cam');
    assert.equal(next.attempt,s.attempt+1);assert.equal(next.partIndex,s.partIndex);
  }
});
