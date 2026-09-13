const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const exportedPage = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const frame = exportedPage.match(/\bsrcdoc="([^"]+)"/);
assert.ok(frame, 'The standalone page must contain its embedded demo.');
const html = frame[1]
  .replace(/&quot;/g, '"')
  .replace(/&#x27;/g, "'")
  .replace(/&lt;/g, '<')
  .replace(/&gt;/g, '>')
  .replace(/&amp;/g, '&');
const script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(match => match[1])
  .find(source => source.includes(' const names='));
assert.ok(script, 'The learning-loop script must be present.');
new Function(script);

const data = script.slice(script.indexOf(' const names='), script.indexOf(' const num='));
const sequenceSource = script.slice(
  script.indexOf(' function sequence('),
  script.indexOf(' function palette('),
);
const { parts, sequence } = new Function(
  data + 'const num=v=>v.toFixed(1);' + sequenceSource + 'return {parts,sequence};',
)();

assert.equal(parts.length, 54);
assert.equal(new Set(parts.map(part => part.name)).size, 54);
assert.equal(new Set(parts.map(part => part.original)).size, 54);
assert.ok(parts.some((part, index) => part.original !== index));
assert.equal(parts[0].beforeFeedback.length, 0);

const targets = new Set(['input', 'llm', 'tests', 'sim', 'judge']);
for (const part of parts) {
  const events = sequence(part);
  assert.equal(events.filter(event => event.target === 'sim').length, part.runs);
  assert.equal(events.filter(event => event.addCheck).length, Number(part.failure));
  assert.equal(events.filter(event => event.addFeedback).length, Number(part.judge));
  assert.equal(events.filter(event => event.commit).length, 1);
  assert.ok(events.at(-1).commit);
  assert.ok(events.every(event => targets.has(event.target)));
  if (part.failure) {
    assert.ok(events.some(event =>
      event.route === 'simTests' && event.target === 'tests' && event.addCheck));
  }
  if (part.judge) {
    assert.ok(events.some(event =>
      event.route === 'judgeLlm' && event.target === 'llm' && event.addFeedback));
  }

  const checks = [...part.beforeChecks];
  const feedback = [...part.beforeFeedback];
  for (const event of events) {
    const previousChecks = checks.length;
    const previousInstructions = feedback.length;
    if (event.addCheck) checks.push(part.rule);
    if (event.addFeedback) feedback.push(part.rec);
    assert.equal(checks.length - previousChecks, event.addCheck ? 1 : 0);
    assert.equal(feedback.length - previousInstructions, event.addFeedback ? 1 : 0);
    assert.ok(checks.every(check => check.part <= part.x));
    assert.ok(feedback.every(instruction =>
      instruction.part <= part.x && instruction.reason && instruction.action));
  }
  assert.deepEqual(feedback, part.afterFeedback);

  const recent = parts.slice(Math.max(0, part.x - 20), part.x);
  assert.equal(part.windowCount, Math.min(20, part.x));
  assert.equal(part.meanTime20, recent.reduce((sum, entry) => sum + entry.final, 0) / recent.length);
  assert.ok(part.final <= part.initial);
}

const last = parts.at(-1);
assert.equal(last.afterChecks.length, 8);
assert.equal(new Set(last.afterChecks.map(check => check.title)).size, 8);
assert.equal(last.afterFeedback.length, parts.filter(part => part.judge).length);
assert.equal(new Set(last.afterFeedback.map(instruction => instruction.action)).size, last.afterFeedback.length);
assert.equal(parts[0].meanTime20, parts[0].final);
assert.equal(parts[20].meanTime20, parts.slice(1, 21).reduce((sum, part) => sum + part.final, 0) / 20);
for (let i = 1; i < parts.length; i++) {
  assert.ok(parts[i].judgeProbability < parts[i - 1].judgeProbability);
  assert.ok(parts[i].failureProbability > 0 && parts[i].failureProbability < 1);
}

const timingSource = script.slice(script.indexOf(' function partDuration('), script.indexOf(' function header('));
const animationSource = script.slice(script.indexOf(' function step('), script.indexOf(' function pause('));
const {partDuration, playbackTime} = new Function('parts', timingSource + 'return {partDuration, playbackTime};')(parts);
assert.ok(Math.abs(partDuration(1)-6500)<500);
assert.ok(Math.abs(partDuration(2)-3500)<500);
assert.ok(Math.abs(partDuration(1)+partDuration(2)-10000)<500);
const totalDuration = parts.reduce((sum, part) => sum + partDuration(part.x), 0);
assert.ok(Math.abs(totalDuration - 24000) < 1e-6);
assert.equal(playbackTime(0), 0);
for (let x = 1; x < 54; x++) {
  assert.ok(partDuration(x + 1) < partDuration(x));
  if(x>1)assert.ok(partDuration(x+1)/partDuration(x)>partDuration(x)/partDuration(x-1));
  // No discontinuity in playback speed where one part becomes the next.
  const left=(playbackTime(x)-playbackTime(x-.0001))/.0001;
  const right=(playbackTime(x+.0001)-playbackTime(x))/.0001;
  assert.ok(Math.abs(left-right)/left<.001);
}

// Exercise the actual animation scheduler at different refresh rates and after
// a delayed frame. Every feedback event must still apply once, without drift.
const playback = new Function('parts', 'sequence', 'interval', 'reducedMotion', 'initialDelay', `
  let completed=0,current=parts[0],events=[],eventIndex=-1,active=null;
  let progress=0,playing=true,animation=null,raf=0,applied=0,motionFrom='input';
  const reduced={matches:reducedMotion},performance={now:()=>0};
  const $=()=>({textContent:''}),draw=()=>{},requestAnimationFrame=()=>1;
  function apply(e){applied++;if(e.target==='input'&&motionFrom!=='input')throw Error('New parts must start at Input');if(e.commit)completed=current.x;}
  function pause(){playing=false;animation=null;}
  function prepare(){
    if(completed>=54)return false;
    current=parts[completed];events=sequence(current);eventIndex=-1;return true;
  }
  ${timingSource}
  ${animationSource}
  step(true);
  let now=initialDelay;
  while(playing&&now<26000){now+=interval;frame(now);}
  return {completed,applied,now,playing};
`);
const expectedEvents = parts.reduce((sum, part) => sum + sequence(part).length, 0);
for (const [interval, reducedMotion, initialDelay] of [[1000/60,false,0],[1000/30,false,0],[1000/60,true,0],[1000/30,false,12000]]) {
  const result = playback(parts, sequence, interval, reducedMotion, initialDelay);
  assert.equal(result.completed, 54);
  assert.equal(result.applied, expectedEvents);
  assert.equal(result.playing, false);
  assert.ok(result.now >= 24000 && result.now < 24100, JSON.stringify(result));
}

console.log('Passed: continuous pacing across parts and steps; 24-second playback, first two parts '+(partDuration(1)/1000).toFixed(2)+'s + '+(partDuration(2)/1000).toFixed(2)+'s; no dropped feedback.');

const geometrySource=script.slice(script.indexOf(' function bezier('),script.indexOf(' function layout('));
const layoutSource=script.slice(script.indexOf(' function layout('),script.indexOf(' function txt('));
const geometry=new Function('width',`
  let W,H,mobile,nodes={},routes={};
  const canvas={getBoundingClientRect:()=>({width}),style:{}},window={devicePixelRatio:1};
  const ctx={setTransform(){}},palette=()=>{},draw=()=>{},drawCharts=()=>{};
  ${geometrySource}
  ${layoutSource}
  layout();return {nodes,motionPath,onRoute};
`);
for(const width of [390,760]){
  const {nodes,motionPath,onRoute}=geometry(width);
  let from='input',previous=[nodes.input.x,nodes.input.y];
  for(const part of parts)for(const event of sequence(part)){
    if(event.target==='input'){from='input';previous=[nodes.input.x,nodes.input.y];}
    const path=motionPath(from,event),start=onRoute(path,0),end=onRoute(path,1);
    assert.ok(Math.hypot(start[0]-previous[0],start[1]-previous[1])<1e-8,'Marker must continue from its previous position');
    assert.ok(Math.hypot(end[0]-nodes[event.target].x,end[1]-nodes[event.target].y)<1e-8,'Marker must finish inside its destination box');
    let last=start;
    for(let i=1;i<=100;i++){
      const point=onRoute(path,i/100);
      assert.ok(point.every(Number.isFinite));
      assert.ok(Math.hypot(point[0]-last[0],point[1]-last[1])<=path.lengths.at(-1)/100+1e-6,'No jumps within a route');
      last=point;
    }
    previous=end;from=event.target;
  }
}
assert.ok(!html.includes('id="ml-current"')&&!html.includes('id="ml-speed"'));
console.log('Passed: continuous paths within each part, fresh parts start at Input, and corner labels removed.');
