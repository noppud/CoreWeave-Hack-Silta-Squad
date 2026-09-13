// Replay derives every result from retained evidence; it never starts a job.
export function replaySteps(detail) {
  const stages = {target_generation_started:'input',target_accepted:'cam',candidate_created:'cam',checks_completed:'checks',verification_completed:'fusion',supervisor_decision:'judge',learning_change_saved:'learning',execution_interrupted:'judge'};
  let candidate=null, digest=null, retry=null;
  return detail.events.flatMap((e,index)=>{
    if(e.event==='checks_completed'&&e.raw.result?.passed===false)retry='checks';
    if(e.event==='verification_completed'&&e.raw.verification?.status==='failed')retry='simulation';
    if(e.event==='supervisor_decision'&&e.raw.decision?.action==='improve')retry='speed';
    if(e.event==='candidate_created'){candidate=e.raw.candidate;digest=e.raw.candidate_digest;}
    let stage=stages[e.event];if(!stage)return [];
    if(stage==='learning')stage=e.raw.change_kind==='checks'?'checks':'cam';
    const attempt=e.attempt||Number(candidate?.id?.match(/(\d+)$/)?.[1])||null;
    const folder=attempt?`cam-${String(attempt).padStart(4,'0')}/`:null;
    const source=['candidate_created','target_accepted'].includes(e.event)?(e.event==='target_accepted'?detail.sources.find(s=>s.name.includes('cad-attempt')):detail.sources.find(s=>s.name===folder+'cam-source.json')||detail.sources.find(s=>folder&&s.name.startsWith(folder)&&s.name.endsWith('.py'))):null;
    // A clip can only appear for the candidate explicitly named by its receipt.
    const video=stage==='fusion'?detail.media.find(v=>(candidate?.id&&v.candidate===candidate.id||digest&&v.digest===digest)&&v.kind==='machining'):null;
    const intent=e.event==='candidate_created'?(retry==='speed'?'Generating a faster plan':retry?'Regenerating code after failure':null):null;
    const step={stage,event:e,index,attempt,candidate:candidate?.id,source,video,intent};
    // An improvement decision really supplies instructions to the next CAM attempt.
    // Show that handoff inside the agent without claiming a shared-memory file was saved.
    if(e.event==='supervisor_decision'&&e.raw.decision?.action==='improve')return [step,{...step,stage:'cam',source:null,video:null,effect:'run-memory'}];
    return [step];
  });
}

export function addedParagraphs(change, changes) {
  const paragraphs=text=>(text||'').split(/\n\s*\n/).map(p=>p.replace(/\s+/g,' ').trim()).filter(Boolean);
  const previous=changes.filter(c=>c.kind===change.kind&&c.at<change.at).sort((a,b)=>b.at.localeCompare(a.at))[0];
  const old=new Set(paragraphs(previous?.content));
  // The first paragraph is the base agent instruction, not a learned memory.
  return paragraphs(change.content).slice(1).filter(p=>!old.has(p));
}
export function learningSteps(detail, mode, sourcePart) {
  const steps=replaySteps(detail);
  if(!sourcePart){
    if(mode==='check-learning'){
      const rejection=steps.find(s=>s.event.event==='checks_completed'&&s.event.raw.result?.passed===false);
      return rejection?steps.filter(s=>s===rejection||(s.stage==='cam'&&s.attempt===rejection.attempt)):[];
    }
    return steps.filter(s=>s.event.event==='candidate_created').slice(0,1);
  }
  const kind=mode==='check-learning'?'checks':'main_prompt';
  const save=steps.find(s=>s.event.event==='learning_change_saved'&&s.event.raw.change_kind===kind);
  if(!save)return [];
  const prior=steps.filter(s=>s.index<save.index);
  if(kind==='checks'){
    const failure=prior.findLast(s=>s.event.event==='verification_completed'&&s.event.raw.verification?.status==='failed');
    const check=failure&&prior.findLast(s=>s.stage==='checks'&&s.attempt===failure.attempt);
    return [check,failure,save].filter(Boolean);
  }
  const verdict=prior.findLast(s=>s.event.event==='verification_completed'&&s.event.raw.verification?.status==='passed');
  const decision=prior.findLast(s=>s.stage==='judge');
  return [verdict,decision,save].filter(Boolean);
}

export function replayTransition(step, next){
  const e=step.event,r=e.raw;
  if(step.effect==='run-memory')return 'Planning memory → new code for the same CAD';
  if(e.event==='checks_completed')return r.result?.passed?'Pass → Fusion simulation':'Fail → regenerate code';
  if(e.event==='verification_completed'){
    if(r.verification?.status==='passed')return 'Pass → judge review';
    if(r.verification?.status==='failed')return next?.event.event==='learning_change_saved'&&next.event.raw.change_kind==='checks'?'Fail → add a check → regenerate code':'Fail → regenerate code';
    return 'Verification incomplete';
  }
  if(e.event==='learning_change_saved')return r.change_kind==='checks'?'New check saved → retry with new code':'Memory saved for the next plan';
  if(e.event==='supervisor_decision')return r.decision?.action==='improve'?'Improve → CAD / CAM → checks → simulation':r.decision?.action==='stop'?'Accept → final part + NC':'';
  if(e.event==='candidate_created')return step.intent||'Generated code → checks';
  return '';
}
