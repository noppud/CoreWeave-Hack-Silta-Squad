export function historyOrder(parts, timeline, changes) {
  const ids=[...new Set([...parts.map(p=>p.id),...changes.map(c=>c.job)])];
  const first=new Map();for(const e of timeline){if(e.at&&(!first.has(e.job)||e.at<first.get(e.job)))first.set(e.job,e.at);}
  return ids.sort((a,b)=>(first.get(a)||'9999').localeCompare(first.get(b)||'9999'));
}
export function timelineSpans(lengths) {
  let start=0;
  return lengths.map((length,partIndex)=>{
    const span={partIndex,start,end:start+length};start+=length;return span;
  });
}
export function orderedMachiningTrend(parts) {
  const values=parts.map(p=>p.summary?.best_seconds).filter(Number.isFinite).sort((a,b)=>b-a);
  let sum=0;return values.map((value,i)=>(sum+=value)/(i+1)/60);
}
export function timelinePosition(spans,value) {
  const position=Math.max(0,Math.min(Math.round(value),spans.at(-1).end-1));
  const span=spans.find(s=>s.start<=position&&position<s.end);
  return {partIndex:span.partIndex,index:position-span.start,position};
}
export function historyMetrics(parts,timeline,changes,cutoff='9999') {
  const saved=changes.filter(c=>c.at<=cutoff).sort((a,b)=>a.at.localeCompare(b.at));
  const knowledge=[{memories:0,checks:1}];
  for(const c of saved){const last=knowledge.at(-1);knowledge.push({memories:last.memories+(c.kind==='main_prompt'?1:0),checks:last.checks+(c.kind==='checks'?1:0)});}
  const grouped=new Map();
  for(const e of timeline){if(e.at>cutoff)continue;if(!grouped.has(e.job))grouped.set(e.job,[]);grouped.get(e.job).push(e);}
  const outcomes=[],times=[];
  for(const p of parts){
    const events=(grouped.get(p.id)||[]).sort((a,b)=>a.at.localeCompare(b.at));
    const checks=events.find(e=>e.event==='checks_completed'),verification=events.find(e=>e.event==='verification_completed');
    if(checks?.raw.result?.passed===false)outcomes.push({at:checks.at,passed:false});
    else if(verification&&['passed','failed'].includes(verification.raw.verification?.status))outcomes.push({at:verification.at,passed:verification.raw.verification.status==='passed'});
    const passes=events.filter(e=>e.event==='verification_completed'&&e.raw.verification?.status==='passed'&&Number.isFinite(e.seconds));
    if(passes.length)times.push({at:passes.at(-1).at,before:passes[0].seconds/60,after:Math.min(...passes.map(e=>e.seconds))/60});
  }
  times.sort((a,b)=>a.at.localeCompare(b.at));outcomes.sort((a,b)=>a.at.localeCompare(b.at));
  const timeSeries=times.map((_,i)=>({before:times.slice(0,i+1).reduce((s,v)=>s+v.before,0)/(i+1),after:times.slice(0,i+1).reduce((s,v)=>s+v.after,0)/(i+1)}));
  const passSeries=outcomes.map((_,i)=>100*outcomes.slice(0,i+1).filter(v=>v.passed).length/(i+1));
  return {knowledge,timeSeries,passSeries,partCount:times.length,outcomeCount:outcomes.length};
}
