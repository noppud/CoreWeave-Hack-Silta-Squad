import test from 'node:test';
import assert from 'node:assert/strict';
import {buildAriaPrompt,ARIA_URL} from '../applications/control-center/aria.mjs';
test('ARIA handoff uses recorded context and excludes display and private fields',()=>{
  const prompt=buildAriaPrompt('Why did this fail?',{id:'run-1',label:'Bracket',status:'incomplete',weave:'https://wandb.ai/silta/project/r/call/123',summary:{passes:0,best_seconds:null,supervisor_decisions:['private extra']},demo:{pass_rate:100},sources:[{content:'not context'}],events:[{event:'verification_completed',detail:'Fixture collision',attempt:1}],verdict:{status:'unknown',completed:false}}, {evaluation:{dataset:{case_count:6},variants:[{name:'learned',caught_invalid:2}]},checks:[],changes:[]});
  assert.match(prompt,/Fixture collision/);assert.match(prompt,/"completed": false/);assert.match(prompt,/"caught_invalid": 2/);
  assert.doesNotMatch(prompt,/private extra|not context|pass_rate/);
  assert.equal(ARIA_URL,'https://wandb.ai/silta/coreweave-hack-silta-squad/weave/agents');
});
test('ARIA handoff remains usable before a new run has evidence',()=>{
  const prompt=buildAriaPrompt('What next?',{id:'new-pdf',label:'New drawing'},{});
  assert.match(prompt,/What next/);assert.match(prompt,/new-pdf/);assert.match(prompt,/Do not launch jobs/);
});
