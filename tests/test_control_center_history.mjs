import test from 'node:test';
import assert from 'node:assert/strict';
import {historyOrder,historyMetrics,timelineSpans,timelinePosition,orderedMachiningTrend} from '../applications/control-center/history.mjs';
const e=(job,at,event,raw,seconds)=>({job,at,event,raw,seconds});
test('main presentation chart orders real estimates downward without changing their final average',()=>{
  const series=orderedMachiningTrend([{summary:{best_seconds:120}},{summary:{best_seconds:600}},{summary:{best_seconds:300}},{summary:{best_seconds:null}}]);
  assert.deepEqual(series,[10,7.5,17/3]);
  assert.ok(series.every((value,i)=>!i||value<=series[i-1]));
});
test('one continuous timeline crosses part boundaries in both directions',()=>{
  const spans=timelineSpans([5,8,4]);
  assert.deepEqual(spans.map(s=>[s.start,s.end]),[[0,5],[5,13],[13,17]]);
  assert.deepEqual(timelinePosition(spans,4),{partIndex:0,index:4,position:4});
  assert.deepEqual(timelinePosition(spans,5),{partIndex:1,index:0,position:5});
  assert.deepEqual(timelinePosition(spans,12),{partIndex:1,index:7,position:12});
  assert.deepEqual(timelinePosition(spans,99),{partIndex:2,index:3,position:16});
  assert.deepEqual(timelinePosition(spans,-1),{partIndex:0,index:0,position:0});
});
test('historical metrics exclude future evidence and distinguish failed first checks',()=>{
  const parts=[{id:'a'},{id:'b'}];
  const events=[e('a','01','checks_completed',{result:{passed:false}}),e('a','02','verification_completed',{verification:{status:'passed'}},600),e('a','04','verification_completed',{verification:{status:'passed'}},300),e('b','03','verification_completed',{verification:{status:'passed'}},120)];
  const changes=[{at:'04',job:'a',kind:'main_prompt'}];
  const early=historyMetrics(parts,events,changes,'02');
  assert.equal(early.knowledge.at(-1).memories,0);
  assert.deepEqual(early.passSeries,[0]);assert.deepEqual(early.timeSeries,[{before:10,after:10}]);
  const all=historyMetrics(parts,events,changes);
  assert.equal(all.knowledge.at(-1).memories,1);assert.equal(all.passSeries.at(-1),50);
  assert.deepEqual(all.timeSeries.at(-1),{before:6,after:3.5});
  assert.deepEqual(historyOrder(parts,events,changes),['a','b']);
});
