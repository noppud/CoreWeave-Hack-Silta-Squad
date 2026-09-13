// Archived attempts retain their simulation → judge → repair ordering.
export function stagedSteps(detail,{presentation=false}={}){
  const source=name=>detail.sources.find(s=>s.name===name);
  const steps=[{stage:'input',title:'Drawing received',kind:'drawing'}];
  const finalVerification=detail.events.findLast(e=>e.event==='verification_completed'&&e.raw.verification?.status==='passed');
  let attempt=0;
  for(const event of detail.events){
    attempt=event.attempt||attempt;
    const base={event,attempt};
    if(event.event==='target_accepted')steps.push({...base,stage:'cad',title:'CAD target accepted',kind:'code',source:source('cad-attempt-01.py')});
    if(event.event==='candidate_generation_started')steps.push({...base,stage:'cam',title:attempt===1?'First machining plan':`Machining plan · attempt ${attempt}`,kind:'code',source:source(`cam-${String(attempt).padStart(4,'0')}/cam-source.json`)||source(`cam-${String(attempt).padStart(4,'0')}/cam-attempt-01.py`)});
    if(event.event==='cam_generation_failed')steps.push({...base,stage:'cam',title:'CAM generation rejected',kind:'failure',text:event.detail||'The first CAM generation failed. The next attempt repairs the source.'});
    if(event.event==='checks_completed')steps.push({...base,stage:'checks',title:event.raw.result?.passed?'Code checks passed':'Code checks failed',kind:'checks',passed:event.raw.result?.passed,issues:event.raw.result?.issues||[]});
    if(event.event==='verification_completed'){
      const verification=event.raw.verification;
      const video=(detail.media||[]).find(v=>v.kind==='machining'&&verification?.candidate_digest&&v.digest===verification.candidate_digest);
      if(event===finalVerification&&Number.isFinite(event.seconds))steps.push({...base,stage:'simulate',title:'Ready for live simulation',kind:'ready'});
      steps.push({...base,stage:'simulate',title:verification?.status==='passed'?'Fusion simulation passed':'Fusion simulation '+verification?.status,kind:'verification',passed:verification?.status==='passed',seconds:event.seconds,video:event===finalVerification?null:video});
    }
    if(event.event==='supervisor_decision')steps.push({...base,stage:'judge',title:event.raw.decision?.action==='improve'?'Judge: improve machining time':'Judge: retain best plan',kind:'instruction',text:event.raw.decision?.instructions});
  }
  if(presentation&&finalVerification){
    const failedIndex=steps.findIndex(s=>s.kind==='verification'&&!s.passed);
    if(failedIndex>=0){
      const firstFailureAttempt=steps[failedIndex].attempt;
      steps.splice(failedIndex+1,steps.length,
        ...steps.slice(failedIndex+1).filter(s=>s.attempt===finalVerification.attempt||s.kind==='result'));
      // Keep the repair cue once, then jump to the successful final attempt.
      steps.splice(failedIndex+1,0,{stage:'judge',title:'Judge: improve machining time',kind:'instruction',text:'Add the learned planning guidance and regenerate the same CAD.'});
    }
    const finalIndex=steps.findIndex(s=>s.event===finalVerification);
    if(finalIndex>=0&&!steps.some(s=>s.kind==='ready')){
      steps.splice(finalIndex,0,{...steps[finalIndex],stage:'simulate',title:'Starting Fusion simulation',kind:'ready'});
    }
  }
  const passes=steps.filter(s=>s.kind==='verification'&&s.passed&&Number.isFinite(s.seconds));
  if(passes.length)steps.push({stage:'output',title:'Final machining plan',kind:'result',before:passes[0].seconds,after:passes.at(-1).seconds});
  return steps;
}
export function stagedStepDuration(step){
  // Keep the source and checks legible, then reach the Fusion view quickly
  // enough for a live presentation.
  return ({drawing:3500,code:20000,failure:3500,checks:3500,verification:5000,instruction:10000,result:5000})[step.kind]||3500;
}
export function sourceBlocks(text,lines=18){
  const rows=(text||'').split('\n');
  return Array.from({length:Math.ceil(rows.length/lines)},(_,i)=>rows.slice(i*lines,(i+1)*lines).join('\n'));
}

// Presentation pacing only: the source and outcomes remain from the retained run.
export function streamedSource(source,elapsed,duration){
  const t=Math.max(0,Math.min(1,elapsed/duration));
  const progress=t-Math.sin(t*Math.PI*4)/(Math.PI*18);
  return source.slice(0,t===1?source.length:Math.floor(source.length*progress));
}
export function demoPlaybackAction({kind,status,live,requested,fallback}){
  if(kind!=='ready'||fallback)return 'none';
  if(status==='completed')return live?'review':'watch';
  if(status==='playing')return 'none';
  if(status==='ready'&&!requested)return 'start';
  return 'none';
}
