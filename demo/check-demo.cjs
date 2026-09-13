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

console.log('Passed: 54 inputs, eight distinct tests, one speed instruction per judge rejection, and rolling averages.');
