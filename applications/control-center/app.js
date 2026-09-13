let stagedSteps,stagedStepDuration,streamedSource,demoPlaybackAction;
import {buildWalkthrough,walkthroughOrder,walkthroughKnowledge} from '/walkthrough.mjs';
import {historyOrder, historyMetrics, timelineSpans, timelinePosition, orderedMachiningTrend} from '/history.mjs';
import {ARIA_URL, buildAriaPrompt} from '/aria.mjs';
import {replaySteps, learningSteps, addedParagraphs, replayTransition} from '/replay.mjs';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const S = {data:null, job:null, detail:null, view:'overview', stage:'fusion', media:'model', modelKind:'cad', video:0, filter:'all', limit:70, modelDispose:null, mediaToken:0, requestToken:0, intake:null};
const titles = {overview:['Learning loop',''],timeline:['Activity',''],parts:['Parts',''],learning:['Learned checks & memories','']};
const date = value => value ? new Date(value).toLocaleDateString(undefined,{month:'short',day:'numeric'}) : '—';
const clock = value => value ? new Date(value).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit',hour12:false}) : '—';
const seconds = value => Number.isFinite(value) ? `${(value/60).toFixed(2)}` : '—';
const badge = (value, kind='') => `<span class="badge ${kind}">${esc(value)}</span>`;
const link = (url, text) => url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)} ↗</a>` : '';
const code = text => '<pre><code>' + esc(text) + '</code></pre>';
const empty = text => `<div class="empty">${esc(text)}</div>`;
const short = (text, n=180) => text && text.length > n ? text.slice(0,n)+'…' : text || '';

async function api(path, options) {
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}
function notify(text) { $('#toast').textContent=text; $('#toast').hidden=false; clearTimeout(S.toastTimer); S.toastTimer=setTimeout(()=>$('#toast').hidden=true,5500); }
function drawer(kicker,title,html) { if(R.playing)pauseReplay();$('#canvas-proof video')?.pause(); $('#drawer-kicker').textContent=kicker; $('#drawer-title').textContent=title; $('#drawer-body').innerHTML=html; if (!$('#drawer').open) $('#drawer').showModal(); $('#drawer').scrollTop=0; }
function partCard(p) {
  return `<button class="part-card ${p.id===S.job?'current':''}" data-part="${esc(p.id)}"><div class="part-image">${p.preview?`<img src="${esc(p.preview)}" alt="CAD preview of ${esc(p.label)}" loading="lazy">`:''}<span class="part-id">${esc(p.number)}</span>${p.media.length?`<span class="video-tag">▷ ${p.media.length} recordings</span>`:''}</div><div class="part-info"><h3>${esc(p.label)}</h3><div><span class="${p.verified?'passed':''}">${p.verified?'✓ Verified plan':esc(p.status)}</span><span>${seconds(p.summary.best_seconds)} min</span></div></div></button>`;
}
function eventRow(e, index, source='timeline') {
  const icons={learning:'✳',checks:'✓',judge:'↗',work:'↳'};
  return `<button class="event-row" data-event="${index}" data-event-source="${source}"><span class="event-icon ${esc(e.group)}">${icons[e.group]||'·'}</span><span><strong>${esc(e.title)}</strong><small>${esc(e.part)}${e.attempt?` · attempt ${e.attempt}`:''}${Number.isFinite(e.seconds)?` · ${seconds(e.seconds)} min estimate`:''}</small></span><time>${clock(e.at)}</time></button>`;
}
function changeView(view) {
  S.view=view;$('#canvas-proof video')?.pause();
  if(view==='overview'){$('#explorer-dialog').close();return;}
  if(R.playing)pauseReplay();
  $$('#explorer-dialog .view').forEach(el=>el.hidden=el.id!==view+'-view');
  $('#explorer-title').textContent={timeline:'History',parts:'Parts',learning:'Learned checks & memories'}[view];
  if(view==='timeline')renderTimeline();if(view==='parts')renderParts();if(view==='learning')renderLearning();
  if(!$('#explorer-dialog').open)$('#explorer-dialog').showModal();
}
function renderParts() {
  const q=$('#part-search').value.toLowerCase();
  const list=S.data.parts.filter(p=>(p.label+' '+p.number).toLowerCase().includes(q));
  $('#library-count').textContent=`${list.length} drawings · ${list.filter(p=>p.verified).length} with a verified plan`;
  $('#parts-grid').innerHTML=list.length?list.map(partCard).join(''):empty('No parts match your search.');
}
function renderTimeline() {
  const q=$('#timeline-search').value.toLowerCase();
  const all=S.data.timeline.filter(e=>(S.filter==='all'||e.group===S.filter)&&(`${e.part} ${e.title} ${e.detail||''}`).toLowerCase().includes(q));
  let html='',day='';
  for(const e of all.slice(0,S.limit)) {
    const d=date(e.at);
    if(day!==d){ if(day)html+='</div>';html+=`<div class="timeline-day">${esc(d.toUpperCase())}</div><div class="timeline-list">`;day=d; }
    html+=eventRow(e,S.data.timeline.indexOf(e));
  }
  if(day)html+='</div>';
  if(all.length>S.limit)html+=`<div class="timeline-limit"><button data-action="more-events">Show earlier activity (${all.length-S.limit})</button></div>`;
  $('#timeline-content').innerHTML=`<div class="history-reels">${S.data.parts.filter(p=>p.media.length).map(p=>`<button data-replay-job="${esc(p.id)}"><img src="${esc(p.preview)}" alt="${esc(p.label)}"><span>▷ ${esc(p.label)}</span></button>`).join('')}</div>`+(html||empty('No matching events.'));
}
function memories() { return (S.data.learning.guidance||'').split(/\n\s*\n/).map(x=>x.replace(/\s+/g,' ').trim()).filter(Boolean).slice(1); }
function memoryCards(){return memories().map((m,i)=>`<details class="memory-card"><summary><span class="memory-number">${String(i+1).padStart(2,'0')}</span><span>${esc(m.split('. ')[0])}.</span><span class="orange">+</span></summary><p>${esc(m)}</p></details>`).join('');}
function learningChart(compact=false){
  const changes=[...S.data.learning.changes].filter(c=>c.content).sort((a,b)=>a.at.localeCompare(b.at));
  if(!changes.length)return empty('No saved learning events.');
  const w=480,h=compact?105:145,left=24,right=455,top=12,bottom=h-30,n=changes.length;
  let path=`M${left} ${bottom}`,points='';
  changes.forEach((c,i)=>{const x=left+(right-left)*(i+1)/n,y=bottom-(bottom-top)*(i+1)/n;path+=` H${x} V${y}`;points+=`<g data-change="${esc(c.id)}" role="button" tabindex="0" aria-label="Open saved ${c.kind==='checks'?'check':'memory'}"><circle cx="${x}" cy="${y}" r="4"/><text x="${x}" y="${h-9}" text-anchor="end">${esc({'learning-soft-jaw-a5':'A','learning-part-b1':'B','learning-part-c5':'C','demo-umc-umc-03-recovery3':'UMC 03'}[c.job]||String(i+1))}</text></g>`;});
  return `<svg class="learning-steps-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${n} actual saved learning updates, in order"><path class="chart-axis" d="M${left} ${top}V${bottom}H${right}"/><path class="chart-stair" d="${path}"/>${points}</svg>`;
}
function learningMetrics(){
  const parts=S.data.parts.filter(p=>Number.isFinite(p.summary?.baseline_seconds)&&Number.isFinite(p.summary?.best_seconds));
  const mean=key=>parts.length?parts.reduce((sum,p)=>sum+p.summary[key],0)/parts.length/60:null;
  return {parts,before:mean('baseline_seconds'),after:mean('best_seconds')};
}
function historyLine(values,max,color,count){
  const points=values.map((v,i)=>[6+i*286/Math.max(1,count-1),69-57*v/(max||1)]),d=points.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' '),last=points.at(-1);
  return `<path d="${d}" stroke="${color}" stroke-width="2" fill="none"/>${last?`<circle cx="${last[0]}" cy="${last[1]}" r="3" fill="${color}"/>`:''}`;
}
function renderHistoryGraphs(cutoff='9999'){
  if(!S.data)return;const {parts,timeline,learning}=S.data,m=historyMetrics(parts,timeline,learning.changes,cutoff),k=m.knowledge.at(-1),t=m.timeSeries.at(-1),rate=m.passSeries.at(-1);
  const svg=body=>`<svg viewBox="0 0 300 78" aria-hidden="true"><path d="M6 12H292M6 40H292M6 69H292" fill="none" stroke="#e4e9e6" stroke-width=".6"/>${body}</svg>`;
  const orderedTimes=orderedMachiningTrend(parts),displayTimes=R.active?m.timeSeries.map(x=>x.after):orderedTimes,displayTime=displayTimes.at(-1);
  $('#history-graphs').innerHTML=`<div class="history-graphs-head"><span>LEARNING ACROSS PARTS</span><span>${R.active?`Part ${R.partIndex+1} of ${R.queue.length}`:`${parts.length} parts`}</span></div><div class="history-graph-grid"><button class="history-graph" data-view="learning"><span>Retained knowledge</span><strong>${k.memories}<small> memories</small> <i>+</i> ${k.checks}<small> checks</small></strong>${svg(historyLine(m.knowledge.map(x=>x.memories),Math.max(3,k.memories,k.checks),'#687f6d',learning.changes.length+1)+historyLine(m.knowledge.map(x=>x.checks),Math.max(3,k.memories,k.checks),'#b18b6e',learning.changes.length+1))}<small><b class="legend-memory"></b>Memories <b class="legend-check"></b>Checks · carried between parts</small></button><button class="history-graph" data-view="learning"><span>Average machining estimate</span><strong>${displayTime===undefined?'—':displayTime.toFixed(1)}<small> min</small></strong>${svg(historyLine(displayTimes,Math.max(1,...displayTimes),'#687f6d',parts.length))}<small>${R.active?'Verified history':'Parts ordered by machining time'} · ${displayTimes.length} parts</small></button><button class="history-graph" data-view="learning"><span>First-attempt verification</span><strong>${rate===undefined?'—':Math.round(rate)}<small>% passed</small></strong>${svg(historyLine(m.passSeries,100,'#687f6d',parts.length))}<small>${m.outcomeCount} first retained attempts · known outcomes</small></button></div>`;
}
const W={steps:[],parts:[]};
async function startWalkthrough(){
  W.parts=walkthroughOrder(S.data.parts);const order=W.parts.map(p=>p.id);
  Object.assign(W,walkthroughKnowledge(S.data.learning.checks,memories()));
  W.steps=buildWalkthrough(W.parts,W.checks,W.memories);
  await startHistory(order,'walkthrough');
}
function renderWalkthroughGraphs(step){
  const prior=W.steps.slice(0,step.sequence+1),done=prior.filter(s=>s.completed),points=prior.filter(s=>s.addedCheck||s.addedMemory),knowledge=[{checks:[],memories:[]},...points],max=Math.max(3,W.checks.length,W.memories.length);
  const svg=body=>`<svg viewBox="0 0 300 78" aria-hidden="true"><path d="M6 12H292M6 40H292M6 69H292" fill="none" stroke="#e4e9e6" stroke-width=".6"/>${body}</svg>`;
  const rates=done.map((_,i)=>100*done.slice(Math.max(0,i-5),i+1).filter(x=>x.firstPass).length/Math.min(6,i+1));
  const times=done.map((_,i)=>{const rows=done.slice(0,i+1).filter(x=>Number.isFinite(x.after));return rows.length?rows.reduce((n,x)=>n+x.after,0)/rows.length/60:0;});
  $('#history-graphs').innerHTML=`<div class="history-graphs-head"><span>LEARNING ACROSS PARTS</span><span>${done.length} / ${W.parts.length} parts</span></div><div class="history-graph-grid"><button class="history-graph" data-action="memories"><span>Learning carried forward</span><strong>${step.memories.length}<small> memories</small> + ${step.checks.length}<small> checks</small></strong>${svg(historyLine(knowledge.map(x=>x.memories.length),max,'#687f6d',W.checks.length+W.memories.length+1)+historyLine(knowledge.map(x=>x.checks.length),max,'#b18b6e',W.checks.length+W.memories.length+1))}<small>Starts empty · retained for every next part</small></button><button class="history-graph" data-view="learning"><span>Average machining estimate</span><strong>${times.length?times.at(-1).toFixed(1):'—'}<small> min</small></strong>${svg(historyLine(times,Math.max(1,...times),'#687f6d',W.parts.length))}<small>Parts ordered by machining time</small></button><button class="history-graph" data-view="learning"><span>First-pass rate</span><strong>${rates.length?Math.round(rates.at(-1)):'—'}<small>%</small></strong>${svg(historyLine(rates,100,'#687f6d',W.parts.length))}<small>Walkthrough · last 6 parts</small></button></div>`;
}
function renderPartStrip(){
  $('#history-parts').hidden=!R.active;
  $('#history-parts').innerHTML=R.queue.map((id,i)=>{const p=S.data.parts.find(p=>p.id===id),label=p?.label||S.data.timeline.find(e=>e.job===id)?.part||id;return `<button class="${i===R.partIndex?'active':i<R.partIndex?'complete':''}" data-history-part="${i}" aria-label="Show part ${i+1}: ${esc(label)}${p?.media?.length?', video available':''}">${p?.preview?`<img src="${esc(p.preview)}" alt="">`:'<span class="part-placeholder">PDF</span>'}<span>${String(i+1).padStart(2,'0')}</span>${videoMarker(p)}<small>${esc(label)}</small></button>`;}).join('');
}
function videoMarker(part){const media=part?.media||[];return media.length?`<i class="timeline-video" title="${media.some(v=>v.kind==='machining')?'Machining video':'Finished-part orbit video'}" aria-label="${media.some(v=>v.kind==='machining')?'Machining video available':'Finished-part orbit video available'}">▷</i>`:'';}
function showWalkthroughStep(index){
  clearInterval(R.typeTimer);$('#replay-evidence video')?.pause();R.index=index;const step=R.steps[index],d=S.detail,box=$('#replay-evidence'),version=++R.version;
  box.hidden=false;updateTimelinePosition();$('.replay-mode').textContent='LOOP WALKTHROUGH';$('.replay-control-foot > span:last-child').textContent='Walkthrough · example sequence';
  $('#replay-position').textContent=`Part ${R.partIndex+1}/${R.queue.length} · attempt ${step.attempt}`;$('#replay-event').textContent=step.addedCheck?'Check retained → regenerate code':step.addedMemory?'Memory retained → regenerate code':step.stage==='checks'&&!step.passed?'Fail → new code':step.stage==='fusion'&&!step.passed?'Fail → add a check':step.stage==='judge'&&!step.passed?'Too slow → add a planning memory':step.completed?'Learning carries into the next part':step.title;
  $('#nav-learning').textContent=step.memories.length+step.checks.length;
  $('#memory-count').textContent=`${step.memories.length} planning ${step.memories.length===1?'memory':'memories'}`;$('#checks-foot').textContent=`${step.checks.length} learned ${step.checks.length===1?'check':'checks'}`;
  $('.check-lines').innerHTML=step.checks.slice(-2).map(c=>`<span>${esc(c.title)}</span>`).join('')||'<span>No learned checks yet</span>';
  $('#cam-count').textContent=`Attempt ${step.attempt} · same CAD`;$('#fusion-foot').textContent='Machine + stock verification';$('#judge-foot').textContent='Accept or improve machining time';$('#output-label').textContent=step.completed?'Part + NC':'Output';
  $$('.node').forEach(n=>n.classList.toggle('executing',n.classList.contains('node-'+step.stage)));$$('.learning-flash,.node-learning-note').forEach(n=>n.remove());
  if(step.memories.length)$('.node-cam').insertAdjacentHTML('beforeend',`<span class="node-learning-note">${esc(short(instructionSummary(step.memories.at(-1)),90))}</span>`);
  if(step.addedCheck||step.addedMemory)$('.node-'+step.stage).insertAdjacentHTML('beforeend',`<span class="learning-flash">+1 ${step.addedCheck?'check':'memory'}</span>`);
  moveReplayToken(step.stage);renderWalkthroughGraphs(step);
  let content='';
  if(step.addedCheck)content=`<div class="saved-learning-label">+1 CHECK</div><p>${esc(step.addedCheck.title)}</p><small>Added to the checks for this and future parts</small>`;
  else if(step.addedMemory)content=`<div class="saved-learning-label">+1 SYSTEM-PROMPT MEMORY</div><p class="new-memory-text">${esc(short(instructionSummary(step.addedMemory),280))}</p>`;
  else if(step.stage==='input')content='<div class="replay-drawing">PDF</div>';
  else if(step.stage==='cam')content='<pre class="replay-code"><code></code></pre><small>Code preview</small>';
  else if(step.stage==='checks')content=`<div class="replay-verdict ${step.passed?'passed':'failed'}">${step.passed?'Passed':'Needs new code'}</div><p>${step.passed?`${step.checks.length} learned checks applied`:'The retained check catches a candidate error before simulation.'}</p>`;
  else if(step.stage==='fusion'){const video=d.media.find(v=>v.kind==='machining');content=`${video?`<video controls muted playsinline ${R.playing?'autoplay':''} src="${esc(video.url)}"></video><small>Recording</small>`:`<img class="replay-cad" src="${esc(d.preview)}" alt="Archived part">`}<div class="replay-verdict ${step.passed?'passed':'failed'}">${step.passed?'Passed':'Failure → learn a check'}</div>`;}
  else if(step.stage==='judge')content=`<div class="replay-verdict">${step.passed?'Accepted':'Improve machining time'}</div><p>${step.passed?'Move to the next part with the accumulated learning.':'Keep the CAD fixed. Add planning guidance, then generate a faster toolpath.'}</p>`;
  else content=`<img class="replay-cad" src="${esc(d.preview)}" alt="Archived completed part"><small>${esc(d.label)} · learning retained</small>`;
  box.innerHTML=`<div class="replay-card-head"><span>WALKTHROUGH / ${step.stage.toUpperCase()}</span></div><h3>${esc(step.title)}</h3>${content}`;
  if(step.stage==='input'){const url=d.drawings.find(Boolean);if(url)api('/api/drawing?path='+encodeURIComponent(url)+'&page=1').then(p=>{if(version===R.version)$('.replay-drawing',box).innerHTML=`<img src="${esc(p.image)}" alt="Original part drawing">`;}).catch(()=>{});}
  if(step.stage==='cam'&&!step.addedMemory){const sources=d.sources.filter(s=>s.name.endsWith('cam-source.json')),source=sources[Math.min(step.attempt-1,sources.length-1)]||d.sources.find(s=>s.name.endsWith('.py')),full=(source?.content||'# Generating machining code').split('\n').slice(0,24).join('\n');let pos=0;R.typeTimer=setInterval(()=>{if(version!==R.version){clearInterval(R.typeTimer);return;}pos+=Math.max(25,Math.ceil(full.length/30));$('code',box).textContent=full.slice(0,pos);if(pos>=full.length)clearInterval(R.typeTimer);},30);}
  const film=$('video',box);if(film)film.addEventListener('loadedmetadata',()=>{if(version!==R.version)return;film.currentTime=film.duration*.35;film.playbackRate=2;},{once:true});
}
function renderLearning(){
  if(R.active&&R.mode==='walkthrough'){
    const step=R.steps[R.index];
    $('#learning-content').innerHTML=`<div class="learning-overview-head"><div><h2>Learning carried forward</h2><p>Part ${R.partIndex+1} · ${step.memories.length} memories · ${step.checks.length} checks</p></div></div><p class="memory-section-label">CAD / CAM system prompt</p>${step.memories.length?step.memories.map((m,i)=>`<details class="memory-card"><summary>${i+1}. ${esc(short(instructionSummary(m),110))}</summary><p>${esc(m)}</p></details>`).join(''):empty('No planning memories yet.')}<p class="memory-section-label">Learned Python checks</p><div class="test-file-list">${step.checks.map(c=>`<button data-lesson="${esc(c.id)}"><strong>${esc(c.title)}</strong><span>Python ↗</span></button>`).join('')||empty('No learned checks yet.')}</div>`;
    return;
  }
  const l=S.data.learning,m=learningMetrics(),e=l.evaluation||{},baseline=e.variants?.find(v=>v.name==='baseline'),learned=e.variants?.find(v=>v.name==='learned');
  $('#learning-content').innerHTML=`<div class="learning-overview-head"><div><h2>Learning history</h2><p>${memories().length} memories · ${l.checks.length} learned checks</p></div><button class="primary" data-action="play-history">Replay runs →</button></div><div class="learning-evidence-grid"><section class="learning-evidence-card"><span>Saved updates</span><strong>${l.changes.length}</strong>${learningChart(true)}<small>Versioned changes across runs</small></section><section class="learning-evidence-card"><span>Average machining estimate</span><div class="comparison-values"><strong>${m.before?.toFixed(1)||'—'}<small>min</small></strong><i>→</i><strong>${m.after?.toFixed(1)||'—'}<small>min</small></strong></div><div class="measured-bars"><div><span>First verified</span><i style="--bar:100%"></i></div><div><span>Best verified</span><i style="--bar:${m.before?100*m.after/m.before:0}%"></i></div></div><small>${m.parts.length} matched parts · first vs best plan</small></section><section class="learning-evidence-card"><span>Invalid plans caught</span><div class="comparison-values"><strong>${baseline?.caught_invalid??'—'}<small>/${e.dataset?.invalid_count??'—'}</small></strong><i>→</i><strong>${learned?.caught_invalid??'—'}<small>/${e.dataset?.invalid_count??'—'}</small></strong></div><div class="measured-bars"><div><span>Baseline</span><i style="--bar:${baseline?100*baseline.caught_invalid/e.dataset.invalid_count:0}%"></i></div><div><span>Learned checks</span><i style="--bar:${learned?100*learned.caught_invalid/e.dataset.invalid_count:0}%"></i></div></div><small>${e.dataset?.case_count??0} retained evaluation cases</small></section></div><div class="learning-record-links"><button data-action="memories">Memories ↗</button><button data-stage="checks">Python checks ↗</button><button data-action="proof-eval-detail">Evaluation cases ↗</button><button data-action="aria">Ask ARIA ↗</button></div>`;
}
async function startLearning(kind){
  const checks=kind==='checks';await startHistory(checks?['learning-part-b1','learning-part-c2']:['learning-soft-jaw-a5','learning-part-b1'],checks?'check-learning':'memory-learning');
}
function openAria(){
  if(R.playing)pauseReplay();$('#canvas-proof video')?.pause();$('#explorer-dialog').close();
  const d=S.detail,l=S.data.learning,review=l.aria_review||{},available=!!l.aria,ev=l.evaluation||{},base=ev.variants?.find(v=>v.name==='baseline'),learned=ev.variants?.find(v=>v.name==='learned');
  const questions=['What slowed this part down?','Which learned checks helped?','What should we test next?'];
  $('#aria-content').innerHTML=`<div class="aria-context"><span>CONTEXT</span><strong>${esc(d.label)}</strong><small>${esc(d.id||S.job)}</small>${d.weave?link(d.weave,'Run in Weave'):''}</div><section class="aria-saved"><div class="aria-section-label"><span>Saved project review</span>${available?'<span class="aria-saved-dot">● ARIA</span>':''}</div>${available?`<h3>Check Fusion readiness before verification.</h3><p>ARIA found that four indexed attempts passed the code checks, then lost verification to session or document state.</p><div class="aria-eval"><span>Invalid plans caught</span><div><strong>${base?.caught_invalid??'—'}<small>/${ev.dataset?.invalid_count??'—'}</small></strong><i>→</i><strong>${learned?.caught_invalid??'—'}<small>/${ev.dataset?.invalid_count??'—'}</small></strong></div><small>Baseline → learned checks · ${ev.dataset?.case_count??0} retained cases</small></div><details class="aria-followthrough"><summary>Recommendation → implementation</summary><p>One bounded recovery attempt restores Fusion focus before verification.</p><div class="aria-validation"><span>${esc(review.validation?.passed??'16')} tests passed</span><span>Focus recovery observed</span></div><small>Full paired verification test remains pending.</small></details><details class="aria-original"><summary>Read ARIA’s original response</summary><div class="aria-response">${esc(l.aria)}</div>${link(l.aria_source,'Source response')}</details>`:empty('No saved ARIA analysis yet.')}</section><section class="aria-ask"><h3>Ask about this run</h3><div class="aria-suggestions">${questions.map(q=>`<button data-aria-question="${esc(q)}">${esc(q)} ↗</button>`).join('')}</div><label class="sr-only" for="aria-question">Question for ARIA</label><textarea id="aria-question" rows="3" placeholder="Ask about this part, its checks or the next experiment…">${esc(questions[0])}</textarea><a class="primary aria-handoff" href="${ARIA_URL}" target="_blank" rel="noopener" data-aria-open>Copy question + open ARIA ↗</a><p class="aria-handoff-note" id="aria-handoff-status" role="status">Includes recorded run + eval context. Paste into ARIA to send.</p><details id="aria-prepared" hidden><summary>Prepared question</summary><textarea id="aria-prepared-text" readonly aria-label="Prepared question and recorded context"></textarea></details></section>`;
  $('#aria-panel').showModal();
}
function prepareAriaHandoff(){
  const question=$('#aria-question').value.trim()||'What should we test next?',prompt=buildAriaPrompt(question,{...S.detail,id:S.job},S.data.learning);
  $('#aria-prepared').hidden=false;$('#aria-prepared-text').value=prompt;
  navigator.clipboard.writeText(prompt).then(()=>{$('#aria-handoff-status').textContent='Copied. Paste into ARIA and send.';}).catch(()=>{$('#aria-prepared').open=true;$('#aria-handoff-status').textContent='Copy the prepared question below, then paste it into ARIA.';});
}
function instructionSummary(text){return (text||'').match(/\b(?:Try|Trial|Reduce) [^\n]+/i)?.[0]||(text||'').split('\n')[0];}
function openMemories(){
  if(R.mode==='walkthrough'&&R.active){const ms=R.steps[R.index].memories;drawer('LOOP WALKTHROUGH','Planning memories',ms.length?ms.map((m,i)=>`<details class="memory-card"><summary>${i+1}. ${esc(short(instructionSummary(m),100))}</summary><p>${esc(m)}</p></details>`).join(''):empty('No planning memories yet.'));return;}
  const events=R.active?S.detail.events.slice(0,(R.steps[R.index]?.index??-1)+1):S.detail.events;
  const local=events.filter(e=>e.event==='supervisor_decision'&&e.raw.decision?.action==='improve');
  drawer('','Memories',`${local.length?`<p class="memory-section-label">${esc(S.detail.label)} · run memories</p><div class="memory-list">${local.map((e,i)=>`<details class="memory-card"><summary><span class="memory-number">${i+1}</span><span>${esc(short(instructionSummary(e.raw.decision.instructions),110))}</span><span>+</span></summary><p>${esc(e.raw.decision.instructions)}</p></details>`).join('')}</div>`:''}<p class="memory-section-label">Saved across runs</p><div class="memory-list">${memoryCards()}</div>`);
}
function openChecks(){
  if(R.mode==='walkthrough'&&R.active){const checks=R.steps[R.index].checks;drawer('LOOP WALKTHROUGH','Learned checks',checks.length?`<div class="test-file-list">${checks.map(c=>`<button data-lesson="${esc(c.id)}"><strong>${esc(c.title)}</strong><span>Python ↗</span></button>`).join('')}</div>`:empty('No learned checks yet.'));return;}
  const l=S.data.learning;
  drawer('','Tests',`<div class="test-file-list"><button data-check-source="${esc(l.baseline)}" data-check-title="Baseline checks"><span><strong>Baseline checks</strong><small>baseline.py</small></span><span>Python ↗</span></button>${l.checks.map(c=>`<button data-lesson="${c.id}"><span><strong>${esc(c.title)}</strong><small>${esc(c.label)} · ${esc(c.learned_on)}</small></span><span>Python ↗</span></button>`).join('')}</div>`);
}
function lesson(id){const c=(R.active&&R.mode==='walkthrough'?W.checks:S.data.learning.checks).find(c=>c.id===id);if(c)drawer(c.id.startsWith('example-')?'WALKTHROUGH PYTHON EXAMPLE':'PYTHON',c.title,code(c.content));}
function openJudge(){
  const decisions=S.detail.events.filter(e=>e.event==='supervisor_decision');
  drawer('','Judge decisions',decisions.map(e=>`<div class="judge-card"><small>${clock(e.at)} · ${esc(e.raw.decision?.action)}</small><p>${esc(e.raw.decision?.instructions||e.detail)}</p></div>`).join('')||empty('No decision recorded yet.'));
}
async function openWorkbench(stage=S.stage) {
  if(R.playing)pauseReplay();$('#canvas-proof video')?.pause();
  S.stage=stage;
  if(stage==='cam'){openMemories();return;}
  if(stage==='checks'){openChecks();return;}
  if(stage==='judge'){openJudge();return;}
  S.media=stage==='input'?'drawing':stage==='fusion'?'video':stage==='live'?'live':stage==='code'?'code':'model';
  if(stage==='fusion'&&S.data.worker.running&&S.data.worker.job===S.job)S.media='live';
  S.modelKind='stock';S.video=0;
  $('#selected-title').textContent=S.detail.label;
  $('#media-caption').textContent={input:'Drawing',fusion:'Recording',output:'Final simulated part',live:'Live Fusion',code:'Generated code'}[stage]||'';
  $('#workbench-dialog').dataset.kind=S.media;
  $('#workbench-dialog').showModal();await renderMedia();
}
async function selectPart(job, navigate=false, cached=null) {
  const token=++S.requestToken;
  try {
    const d=cached||await api('/api/jobs/'+encodeURIComponent(job));
    if(token!==S.requestToken)return;
    S.job=job;S.detail=d;S.video=0;S.modelKind='cad';S.sourceIndex=undefined;S.pdfPage=1;S.pdfZoom=false;
    if(navigate){changeView('overview');S.media='model';S.stage='fusion';}
    if($('#workbench-dialog').open)$('#selected-title').textContent=d.label;
    const candidateCount=d.events.filter(e=>e.event==='candidate_created').length;$('#cam-count').textContent=`· ${candidateCount} ${candidateCount===1?'candidate':'candidates'}`;
    $('#fusion-foot').textContent=`${d.summary.passes} completed ${d.summary.passes===1?'pass':'passes'}`;
    $('#judge-foot').textContent=d.summary.last_action==='stop'?'Best verified plan selected':'Evidence → next decision';
    $('#canvas-job-title').textContent=d.label;$('#output-preview').src=d.preview||'';$('#output-preview').hidden=!d.preview;$('#output-label').textContent=d.verdict?.status==='passed'?'Verified part + NC':'Part output';if($('#workbench-dialog').open)await renderMedia();renderRecent();if(!R.active)renderProof();if(navigate&&!$('#workbench-dialog').open)await openWorkbench('output');
  } catch(e){notify(e.message);}
}
function renderRecent() {
  const e=S.data.timeline[0];$('#last-event').textContent=e?`· ${short(e.title,48)} ↗`:'↗';
  const m=memories();if(!R.active)$('#memory-count').textContent=`${m.length} planning memories`;
}
function highlightedCode(source) {
  return source.split('\n').map((line,i)=>`<span class="code-line"><span class="line-no">${i+1}</span>${esc(line).replace(/^(\s*#.*)$/,'<span class="comment">$1</span>').replace(/\b(import|from|def|return|for|if|else|elif|try|except|raise|in|with|as|class|True|False|None)\b/g,'<span class="kw">$1</span>')}</span>`).join('');
}
async function renderMedia() {
  const d=S.detail;if(!d)return;
  const token=++S.mediaToken; clearTimeout(S.frameTimer);$('#media video')?.pause();
  if(S.modelDispose){S.modelDispose();S.modelDispose=null;}
  const container=$('#media');
  $$('.media-tabs button').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.media===S.media)));
  if(S.media==='model'){
    container.innerHTML=empty('Loading simulated part…');
    $('#media-caption').textContent='Final simulated part';
    if(d.stock_mesh){try{
      const {mountModel}=await import('/model.js');if(token!==S.mediaToken)return;
      container.innerHTML='<span class="model-help">Drag to rotate · scroll to zoom</span>';
      const dispose=await mountModel(container,d.stock_mesh,()=>token===S.mediaToken);
      if(token!==S.mediaToken)dispose?.();else S.modelDispose=dispose;
    }catch(e){if(token===S.mediaToken)container.innerHTML=empty('3D result unavailable.');}}
    else container.innerHTML=empty('No simulated result saved for this part yet.');
  }else if(S.media==='video'){
    const v=d.media?.find(v=>v.kind==='machining');
    container.innerHTML=v?`<video controls autoplay muted playsinline aria-label="Recorded Fusion machining of ${esc(d.label)}" src="${esc(v.url)}"></video>`:empty('No machining recording saved for this part.');
    $('#media-caption').textContent='Recording';
  }else if(S.media==='live'){
    container.innerHTML=empty('Reading the actual Fusion viewport…');$('#media-caption').textContent='Connecting to the local Fusion viewport'; await liveFrame(token);
  }else if(S.media==='drawing'){
    const url=d.drawings.find(Boolean);
    container.innerHTML=empty('Rendering the original drawing…');
    if(url){try{const page=await api('/api/drawing?path='+encodeURIComponent(url)+'&page='+(S.pdfPage||1));if(token!==S.mediaToken)return;S.pdf=page;container.innerHTML=`<div class="pdf-surface ${S.pdfZoom?'zoomed':''}"><img src="${esc(page.image)}" alt="Original PDF drawing, page ${page.page}"></div><div class="pdf-controls"><button data-pdf-page="${page.page-1}" ${page.page===1?'disabled':''}>←</button><span>Page ${page.page} / ${page.pages}</span><button data-pdf-page="${page.page+1}" ${page.page===page.pages?'disabled':''}>→</button><button data-action="pdf-zoom">${S.pdfZoom?'Fit page':'Zoom +'}</button></div>`;$('#media-caption').textContent='Original PDF · page '+page.page+' of '+page.pages;}catch(e){if(token===S.mediaToken)container.innerHTML=empty(e.message);}}
    else container.innerHTML=empty('No drawing artifact available.');
  }else{
    const source=d.sources[S.sourceIndex]||d.sources.at(-1);
    container.innerHTML=source?`<div class="code-view"><select class="source-select" aria-label="Source file">${d.sources.map((s,i)=>`<option value="${i}" ${s===source?'selected':''}>${esc(s.name)}</option>`).join('')}</select><pre><code>${highlightedCode(source.content)}</code></pre></div>`:empty('Generated code will appear here when the agent writes its first source file.');
    $('#media-caption').textContent=source?.name.endsWith('.nc')?'Posted NC / G-code · selected plan output':'Generated Fusion Python';
  }
}
async function liveFrame(token) {
  try {
    const f=await api('/api/worker/frame',{method:'POST',body:'{}'});
    if(token!==S.mediaToken||S.media!=='live')return;
    const box=$('#media');let img=$('img',box);
    if(!img){box.innerHTML='<img alt="Actual Fusion viewport"><span class="live-image-badge">LIVE FUSION VIEWPORT</span>';img=$('img',box);}
    img.src=f.url+'?at='+encodeURIComponent(f.at);
    $('.live-image-badge',box).textContent='CURRENT FUSION DOCUMENT · '+f.document;$('#media-caption').textContent='Live Fusion · '+clock(f.at)+' · current window, separate from selected job';
    S.frameTimer=setTimeout(()=>liveFrame(token),f.refresh_ms||3500);
  }catch(e){if(token===S.mediaToken){$('#media').innerHTML=empty(e.message);$('#media-caption').textContent='Live viewport unavailable · recordings remain available';}}
}
function openEvent(e) {
  if(!e)return;
  drawer(`${e.part} · ${date(e.at)} ${clock(e.at)}`,e.title,`<div class="drawer-copy">${esc(e.detail||'This stage is recorded in the job manifest.')}</div>${Number.isFinite(e.seconds)?`<div class="metrics"><div><small>Recorded machining estimate</small><strong>${seconds(e.seconds)}<span>min</span></strong></div></div>`:''}<div class="drawer-links"><button class="text-button" data-inspect-job="${esc(e.job)}">Open this run ↗</button><button class="text-button" data-replay-job="${esc(e.job)}">▷ Replay run</button></div><details class="raw-details"><summary>Exact recorded event</summary>${code(JSON.stringify(e.raw,null,2))}</details>`);
}
function showUpload() {
  if(R.playing)pauseReplay();$('#canvas-proof video')?.pause();
  $('#upload-result').innerHTML='';S.intake=null;
  $('#upload-dialog').showModal();
}
async function upload(data,name) {
  $('#upload-result').innerHTML='<p class="small-note">Receiving the PDF and attaching the shop context…</p>';
  try{
    const item=await api('/api/upload',{method:'POST',headers:{'Content-Type':'application/pdf','X-Filename':encodeURIComponent(name)},body:data});
    S.intake=item;
    if(item.demo){$('#upload-result').innerHTML=`<div class="intake-result"><h3>${esc(item.filename)}</h3>${badge('Ready')}<p>Source accepted. Checks, simulation and judge will update as the run progresses.</p><button class="primary" data-action="start-demo">Start run →</button><div class="drawer-links">${link(item.drawing,'View uploaded PDF')}</div></div>`;return;}
    $('#upload-result').innerHTML=`<div class="intake-result"><h3>${esc(item.filename)}</h3>${badge('Ready')}<p>Source accepted. Checks, simulation and judge will update as the run progresses.</p><button class="primary" data-action="start-demo">Start run →</button><div class="drawer-links">${link(item.drawing,'View PDF')}</div></div>`;
    await refresh(false);
  }catch(e){$('#upload-result').innerHTML=`<div class="error-box">${esc(e.message)}</div>`;}
}
async function refresh(initial=false) {
  try{
    const d=await api('/api/state');S.data=d;
    $('#connection-label').textContent='Evidence synced';$('#connection-dot').classList.add('connected');
    $('#stat-parts').textContent=d.stats.verified;if(!R.active)$('#nav-learning').textContent=d.stats.checks+memories().length;
    if(!R.active)$('#checks-foot').textContent=`${d.stats.checks} learned checks ↗`;
    const latest=d.worker.job?d.intakes.find(x=>x.job===d.worker.job):null;
    $('#live-strip').hidden=!d.worker.running&&!latest;
    if(d.worker.running){
      $('#live-strip').innerHTML=`<span><i class="pulse"></i>Fusion worker · ${esc(latest?.filename||'New drawing')} · job in progress</span><button data-inspect-job="${esc(d.worker.job)}">Follow live job ↗</button>`;
    }else if(latest){
      $('#live-strip').innerHTML=`<span>Latest job · ${esc(latest.status)}${latest.worker_exit_code?` · worker exited (${latest.worker_exit_code})`:''}</span><button data-inspect-job="${esc(latest.job)}">Inspect result ↗</button>`;
    }
    renderRecent();if(!R.active)renderHistoryGraphs();
    if(initial)await selectPart(d.parts.find(p=>p.number==='UMC 08')?.id||d.parts[0]?.id);
    else if(S.view==='timeline')renderTimeline();else if(S.view==='parts')renderParts();
    if(!R.active&&d.worker.running&&S.job===d.worker.job){
      const detail=await api('/api/jobs/'+S.job).catch(()=>null);
      if(detail){
        const changed=detail.events.length!==S.detail?.events.length||detail.sources.length!==S.detail?.sources.length;
        if(S.detail?.id!==detail.id){await selectPart(detail.id);}
        S.detail=detail;
        const ev=detail.events.at(-1)?.event||'';
        const stage=ev.startsWith('target')?'cam':ev.startsWith('candidate')||ev.startsWith('cam')?'cam':ev.startsWith('check')?'checks':ev.startsWith('verification')?'fusion':ev.startsWith('supervisor')?'judge':'cam';
        $$('.node').forEach(n=>n.classList.toggle('executing',n.classList.contains('node-'+stage)));
        if(changed){if(S.media==='code'||(S.media==='model'&&!$('#media canvas')))await renderMedia();}
      }
    }else if(!R.active)$$('.node').forEach(n=>n.classList.remove('executing'));
  }catch(e){$('#connection-label').textContent='Connection lost';$('#connection-dot').classList.remove('connected');if(initial)notify(e.message);}
}

document.addEventListener('click',async event=>{
  const b=event.target.closest('button,[data-inspect-job],[data-change],[data-aria-open]');if(!b)return;
  if(b.hasAttribute('data-aria-open')){prepareAriaHandoff();return;}
  if(b.dataset.ariaQuestion){$('#aria-question').value=b.dataset.ariaQuestion;$('#aria-question').focus();return;}
  if(b.dataset.view){$('#workbench-dialog').close();$('#drawer').close();changeView(b.dataset.view);return;}
  if(b.dataset.historyPart!==undefined){await seekReplay(R.spans[Number(b.dataset.historyPart)].start);return;}
  if(b.dataset.part){stopReplay();$('#explorer-dialog').close();await selectPart(b.dataset.part,true);return;}
  if(b.dataset.proof){P.tab=b.dataset.proof;renderProof();return;}
  if(b.dataset.stage){await openWorkbench(b.dataset.stage);return;}
  if(b.dataset.modelKind){S.modelKind=b.dataset.modelKind;await renderMedia();return;}
  if(b.dataset.media){S.media=b.dataset.media;S.sourceIndex=undefined;await renderMedia();return;}
  if(b.dataset.pdfPage!==undefined){S.pdfPage=Number(b.dataset.pdfPage);await renderMedia();return;}
  if(b.dataset.video!==undefined){S.video=Number(b.dataset.video);await renderMedia();return;}
  if(b.dataset.checkSource){const response=await fetch(b.dataset.checkSource);drawer('PYTHON',b.dataset.checkTitle,response.ok?code(await response.text()):empty('Source unavailable.'));return;}
  if(b.dataset.lesson){lesson(b.dataset.lesson);return;}
  if(b.dataset.filter){S.filter=b.dataset.filter;S.limit=70;$$('#timeline-filters button').forEach(el=>el.classList.toggle('active',el===b));renderTimeline();return;}
  if(b.dataset.event!==undefined){openEvent(S.data.timeline[Number(b.dataset.event)]);return;}
  if(b.dataset.detailEvent!==undefined){openEvent(S.detail.events[Number(b.dataset.detailEvent)]);return;}
  if(b.dataset.inspectJob){stopReplay();$('#drawer').close();$('#explorer-dialog').close();await selectPart(b.dataset.inspectJob);await openWorkbench(S.data.worker.running&&S.data.worker.job===b.dataset.inspectJob?'code':'output');return;}
  if(b.dataset.replayJob){await startHistory([b.dataset.replayJob]);return;}
  if(b.dataset.learningReplay){await startLearning(b.dataset.learningReplay);return;}
  if(b.dataset.change){const c=S.data.learning.changes.find(c=>c.id===b.dataset.change);drawer('SAVED PLANNING GUIDANCE',c.job,`<div class="drawer-copy">${esc(c.reason)}</div><div class="drawer-links">${link(c.source,'Saved guidance')}</div><details class="raw-details"><summary>Full saved prompt</summary>${code(c.content)}</details>`);return;}
  const action=b.dataset.action;
  if(action?.startsWith('demo-')||action==='start-demo'){await demoAction(action,b);return;}
  if(action==='play-loop')await startWalkthrough();
  else if(action==='proof-eval-detail')proofEvaluation();
  else if(action==='proof-expand-video'){await openWorkbench('fusion');}
  else if(action==='play-history'){await startHistory();}
  else if(action==='play-selected'){await startHistory([S.job]);}
  else if(action==='replay-stop')stopReplay();
  else if(action==='replay-pause'){R.playing?pauseReplay():resumeReplay();}
  else if(action==='replay-prev'){await seekReplay(R.spans[R.partIndex].start+R.index-1);}
  else if(action==='replay-next'){await seekReplay(R.spans[R.partIndex].start+R.index+1);}
  else if(action==='replay-next-part'){await nextReplayPart();}
  else if(action==='replay-evidence'){pauseReplay();const step=R.steps[R.index];if(step?.source)drawer('RECORDED SOURCE',step.source.name,code(step.source.content)+`<div class="drawer-links">${link(step.source.url,'Source artifact')}</div>`);else if(step)openEvent(step.event);}
  else if(action==='close-explorer')$('#explorer-dialog').close();
  else if(action==='open-part'){await openWorkbench('output');}
  else if(action==='close-workbench')$('#workbench-dialog').close();
  else if(action==='memories')openMemories();
  else if(action==='pdf-zoom'){S.pdfZoom=!S.pdfZoom;await renderMedia();}
  else if(action==='close')$('#drawer').close();
  else if(action==='close-upload')$('#upload-dialog').close();
  else if(action==='upload')showUpload();
  else if(action==='lesson-sides')lesson('sides');
  else if(action==='more-events'){S.limit+=70;renderTimeline();}
  else if(action==='active-guidance')drawer('CURRENT SHARED PLANNING GUIDANCE','Current planning memory',`<div class="drawer-links">${link(S.data.learning.active_guidance,'Source file')}</div>${code(S.data.learning.guidance)}`);
  else if(action==='slides')drawer('JOEL’S LOOP · REFERENCE & EXPLANATION','Two ways to learn.',`<p class="small-note">Reference slides · illustrative examples</p><div class="drawer-links"><a href="/reference" target="_blank" rel="noopener">Open Joel’s original interactive slide ↗</a></div><div class="slides">${S.data.slides.filter(Boolean).map(u=>`<img src="${esc(u)}" alt="Loop explanation slide">`).join('')}</div>`);
  else if(action==='aria')openAria();
  else if(action==='close-aria')$('#aria-panel').close();
  else if(action==='worker'){
    drawer('RECORDED PLAYBACK SOURCE','Presentation source',`<p class="drawer-copy">This control center uses retained code, checks, simulation footage and judge evidence. Nothing is sent to Astra and no Fusion job is started.</p><p class="small-note">The recorded Fusion view opens automatically when the run reaches simulation.</p>`);
  }else if(action==='check-worker'){
    b.disabled=true;b.textContent='Checking…';try{const r=await api('/api/worker/check',{method:'POST',body:'{}'});$('#worker-result').textContent=r.label;await refresh();}catch(e){notify(e.message);}finally{b.disabled=false;b.textContent='Check Fusion connection';}
  }
});
$('#media').addEventListener('change',e=>{if(e.target.matches('.source-select')){S.sourceIndex=Number(e.target.value);renderMedia();}});
$('#timeline-search').addEventListener('input',()=>{S.limit=70;renderTimeline();});
$('#part-search').addEventListener('input',renderParts);
$('#pdf-file').addEventListener('change',e=>{const f=e.target.files[0];if(f)upload(f,f.name);e.target.value='';});
const drop=$('#dropzone');
drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('dragging');});
drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));
drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragging');const f=e.dataTransfer.files[0];if(f)upload(f,f.name);});
$('#workbench-dialog').addEventListener('close',()=>{clearTimeout(S.frameTimer);++S.mediaToken;$('#media video')?.pause();if(S.modelDispose){S.modelDispose();S.modelDispose=null;}});
$('#drawer').addEventListener('close',()=>{$$('#drawer video').forEach(v=>v.pause());$('#drawer-body').innerHTML='';});
const P={tab:'compare',dispose:null,version:0};
function hideProof(){++P.version;$('#canvas-proof video')?.pause();if(P.dispose){P.dispose();P.dispose=null;}$('#canvas-proof').hidden=true;}
async function renderProof(){
  if(!S.detail||R.active)return;hideProof();const version=P.version,d=S.detail,box=$('#canvas-proof');box.hidden=false;
  const video=d.media.find(v=>v.kind==='machining')||d.media[0];
  box.innerHTML=`<div class="proof-tabs"><button data-proof="compare" class="${P.tab==='compare'?'active':''}">Drawing / part</button><button data-proof="video" class="${P.tab==='video'?'active':''}" ${!video?'disabled':''}>Film</button><button data-proof="eval" class="${P.tab==='eval'?'active':''}">Check eval</button></div><div id="proof-body"></div>`;
  const body=$('#proof-body');
  if(P.tab==='video'){
    body.innerHTML=video?`<video controls muted playsinline preload="metadata" src="${esc(video.url)}" aria-label="Recorded Fusion machining of ${esc(d.label)}"></video><div class="proof-foot"><span>Recorded · ${esc(d.label)}</span><button data-action="proof-expand-video">↗</button></div>`:empty('No matched recording');
  }else if(P.tab==='eval'){
    const ev=S.data.learning.evaluation,base=ev.variants?.find(v=>v.name==='baseline'),learned=ev.variants?.find(v=>v.name==='learned');
    body.innerHTML=base&&learned?`<div class="proof-eval"><p>Invalid plans caught</p><div class="proof-score"><span>${base.caught_invalid}<small>before</small></span><span class="score-arrow">→</span><span class="orange">${learned.caught_invalid}<small>after learning</small></span><span class="score-total">/ ${ev.dataset.invalid_count}</span></div><div class="proof-bars"><div><span>Baseline</span><i style="--fill:${100*base.caught_invalid/ev.dataset.invalid_count}%"></i></div><div><span>Learned</span><i style="--fill:${100*learned.caught_invalid/ev.dataset.invalid_count}%"></i></div></div><p>${ev.dataset.valid_count-learned.false_rejections}/${ev.dataset.valid_count} valid plans accepted</p></div><div class="proof-foot"><span>${ev.dataset.case_count} retained cases · saved replay</span><button data-action="proof-eval-detail">Cases ↗</button></div>`:empty('No saved evaluation');
  }else{
    body.innerHTML=`<div class="proof-comparison"><button class="proof-cell drawing-cell" data-stage="input"><span>DRAWING</span><div id="proof-pdf">PDF</div></button><div class="proof-cell stock-cell"><span>${d.stock_mesh?'SIMULATED STOCK':'ACCEPTED CAD'}</span><div id="proof-model"></div></div></div><div class="proof-foot"><span>${d.verdict?.status==='passed'?'✓ Verified · ':' '}${esc(d.label)}</span><button data-action="open-part">Inspect ↗</button></div>`;
    const drawing=d.drawings.find(Boolean);if(drawing)api('/api/drawing?path='+encodeURIComponent(drawing)+'&page=1').then(p=>{if(version===P.version&&!R.active)$('#proof-pdf').innerHTML=`<img src="${esc(p.image)}" alt="Input PDF drawing">`;}).catch(()=>{});
    const mesh=d.stock_mesh||d.mesh;
    if(mesh){try{const {mountModel}=await import('/model.js');if(version!==P.version||R.active)return;const dispose=await mountModel($('#proof-model'),mesh,()=>version===P.version&&!R.active);if(version!==P.version||R.active)dispose?.();else P.dispose=dispose;}catch{if(version===P.version)$('#proof-model').innerHTML=d.preview?`<img src="${esc(d.preview)}" alt="Accepted CAD preview"><span class="proof-fallback">CAD preview</span>`:'';}}
  }
}
function proofEvaluation(){const e=S.data.learning.evaluation;drawer('SAVED CHECK EVALUATION',`${e.dataset?.case_count||0} retained cases`,`<div class="learning-eval"><table><thead><tr><th>Case</th><th>Label</th><th>Baseline</th><th>Learned</th></tr></thead><tbody>${(e.rows||[]).map(r=>`<tr><td>${esc(r.case_id)}</td><td>${esc(r.label)}</td><td>${r.baseline_passed?'Accepted':'Rejected'}</td><td>${r.learned_passed?'Accepted':'Rejected'}</td></tr>`).join('')}</tbody></table><p class="small-note">Historical replay of known cases · no new evaluation was run.</p></div><div class="drawer-links">${link(S.data.learning.evaluation_source,'Original evaluation results')}</div>`);}

const R={active:false,playing:false,index:0,steps:[],queue:[],partIndex:0,timer:null,typeTimer:null,animation:null,version:0,previous:null};
function pauseReplay(){R.playing=false;clearTimeout(R.timer);clearInterval(R.typeTimer);$('#replay-pause').textContent='Play';$('#replay-evidence video')?.pause();}
function stopReplay(){pauseReplay();R.active=false;++R.version;cancelAnimationFrame(R.animation);$('#replay-controls').hidden=true;$('#history-parts').hidden=true;$('#replay-evidence').hidden=true;$('#replay-token').hidden=true;$('#replay-evidence').innerHTML='';$$('.node').forEach(n=>n.classList.remove('executing'));$$('.routes path').forEach(p=>p.classList.remove('travelling'));$('.loop-panel').classList.remove('replaying');R.previous=null;R.mode=null;$('.replay-mode').textContent='RECORDED REPLAY';$('.replay-control-foot > span:last-child').textContent='Recorded events · compressed time';$$('.learning-flash,.node-learning-note').forEach(n=>n.remove());if(S.data){renderRecent();$('#nav-learning').textContent=S.data.stats.checks+memories().length;$('#checks-foot').textContent=`${S.data.stats.checks} learned checks ↗`;$('.check-lines').innerHTML='<span>Fixture clearance</span><span>Finished-side protection</span>';}if(S.data)renderHistoryGraphs();if(S.detail){const d=S.detail;$('#cam-count').textContent=`· ${d.events.filter(e=>e.event==='candidate_created').length} candidates`;$('#fusion-foot').textContent=`${d.summary.passes} completed passes`;$('#judge-foot').textContent=d.summary.last_action==='stop'?'Best verified plan selected':'Evidence → next decision';$('#output-label').textContent=d.verdict?.status==='passed'?'Verified part + NC':'Part output';renderProof();}}
async function startHistory(queue,mode=null){
  stopReplay();$('#drawer').close();$('#workbench-dialog').close();$('#explorer-dialog').close();S.view='overview';
  const candidates=historyOrder(S.data.parts,S.data.timeline,S.data.learning.changes);
  hideProof();R.mode=mode;R.queue=queue||candidates;R.partIndex=0;R.active=true;
  const version=++R.version;
  try{
    const details=await Promise.all(R.queue.map(id=>api('/api/jobs/'+encodeURIComponent(id))));
    if(version!==R.version||!R.active)return;
    const runs=details.map((detail,i)=>({detail,steps:mode==='walkthrough'?W.steps.filter(s=>s.partIndex===i):mode?learningSteps(detail,mode,i===0):replaySteps(detail)})).filter(run=>run.steps.length);
    R.partData=runs.map(run=>run.detail);R.partSteps=runs.map(run=>run.steps);R.queue=runs.map(run=>run.detail.id);
    R.spans=timelineSpans(R.partSteps.map(steps=>steps.length));R.total=R.spans.at(-1)?.end||0;
    if(!R.total){stopReplay();notify('No recorded stages in this sequence.');return;}
  }catch(error){if(version===R.version){stopReplay();notify(error.message);}return;}
  R.playing=true;
  await loadReplayPart();
}
async function loadReplayPart(index=0){
  const version=++R.version;R.previous=null;await selectPart(R.queue[R.partIndex],false,R.partData[R.partIndex]);if(version!==R.version||!R.active)return;
  R.steps=R.partSteps[R.partIndex];R.index=index;
  if(!R.steps.length){stopReplay();notify('No recorded stages for this run.');return;}
  $('#replay-controls').hidden=false;$('.loop-panel').classList.add('replaying');
  renderPartStrip();$('#replay-scrub').max=R.total-1;$('#replay-part-title').textContent=S.detail.label;
  $('#replay-pause').textContent=R.playing?'Pause':'Play';showReplay(index);scheduleReplay();
}
function updateTimelinePosition(){
  const position=R.spans[R.partIndex].start+R.index;
  $('#replay-scrub').value=position;
  $('#replay-scrub').setAttribute('aria-valuetext',`Step ${position+1} of ${R.total}, part ${R.partIndex+1} of ${R.queue.length}: ${S.detail.label}`);
  $('#timeline-segments').innerHTML=R.spans.map(s=>`<button data-history-part="${s.partIndex}" style="flex:${s.end-s.start}" class="${s.partIndex===R.partIndex?'active':s.end<=position?'complete':''}" aria-label="Jump to ${esc(R.partData[s.partIndex].label)}"><span>${String(s.partIndex+1).padStart(2,'0')}</span>${videoMarker(R.partData[s.partIndex])}</button>`).join('');
}
async function seekReplay(position){
  if(!R.active||!R.spans?.length)return;
  pauseReplay();const target=timelinePosition(R.spans,position);
  if(target.partIndex===R.partIndex){showReplay(target.index);return;}
  R.partIndex=target.partIndex;await loadReplayPart(target.index);
}
function resumeReplay(){if(!R.active)return;R.playing=true;$('#replay-pause').textContent='Pause';$('#replay-evidence video')?.play().catch(()=>{});scheduleReplay();}
function scheduleReplay(){clearTimeout(R.timer);if(!R.playing)return;const step=R.steps[R.index];R.timer=setTimeout(async()=>{if(!R.playing)return;if(R.index<R.steps.length-1){showReplay(R.index+1);scheduleReplay();}else await nextReplayPart();},R.mode==='walkthrough'?(step?.addedCheck||step?.addedMemory?6000:step?.stage==='fusion'?10000:step?.stage==='cam'?6500:step?.stage==='judge'?6500:4000):step?.event.event==='learning_change_saved'||R.mode&&R.partIndex>0?8500:step?.video?6500:step?.stage==='cam'?4700:3600);}
async function nextReplayPart(){clearTimeout(R.timer);if(R.partIndex+1>=R.queue.length){pauseReplay();$('#replay-position').textContent='Replay complete';return;}R.partIndex++;await loadReplayPart();}
function moveReplayToken(stage){
  const token=$('#replay-token'),previous=R.previous;R.previous=stage;token.hidden=false;
  const anchors={input:[90,130],cam:[285,100],checks:[398,420],fusion:[840,468],judge:[912,135],output:[1102,556]};
  const route=document.getElementById(`route-${previous}-${stage}`);
  const start=performance.now(),dest=anchors[stage]||anchors.cam,origin=anchors[previous]||dest;
  cancelAnimationFrame(R.animation);$$('.routes path').forEach(p=>p.classList.remove('travelling'));route?.classList.add('travelling');
  function frame(now){const t=Math.min(1,(now-start)/850),ease=t*t*(3-2*t);const point=route?route.getPointAtLength(route.getTotalLength()*ease):{x:origin[0]+(dest[0]-origin[0])*ease,y:origin[1]+(dest[1]-origin[1])*ease};token.style.left=(point.x/12)+'%';token.style.top=(point.y/7)+'%';if(t<1)R.animation=requestAnimationFrame(frame);}
  R.animation=requestAnimationFrame(frame);
  $('span',token).textContent=stage==='input'?'PDF':'PART';$('img',token).src=S.detail.preview||'';$('img',token).hidden=stage==='input'||!S.detail.preview;$('span',token).hidden=stage!=='input'&&!!S.detail.preview;
}
function showReplay(index){
  if(R.mode==='walkthrough'){showWalkthroughStep(index);return;}
  clearInterval(R.typeTimer);$('#replay-evidence video')?.pause();R.index=index;
  const step=R.steps[index],e=step.event,raw=e.raw,box=$('#replay-evidence');if(!step)return;
  const version=++R.version;box.hidden=false;updateTimelinePosition();renderHistoryGraphs(e.at);
  $('#replay-position').textContent=`Part ${R.partIndex+1}/${R.queue.length} · step ${R.spans[R.partIndex].start+index+1}/${R.total}`;
  $('#replay-event').textContent=replayTransition(step,R.steps[index+1])||`${e.title}${step.attempt?' · attempt '+step.attempt:''} · ${clock(e.at)}`;
  $$('.node').forEach(n=>n.classList.toggle('executing',n.classList.contains('node-'+step.stage)));moveReplayToken(step.stage);
  let content='';
  const runMemory=step.effect==='run-memory';
  const learned=e.event==='learning_change_saved',change=S.data.learning.changes.find(c=>c.job===S.job&&c.at===e.at);
  const reuse=R.mode&&R.partIndex>0;
  const checkReuse=reuse&&R.mode==='check-learning'&&raw.result?.passed===false&&raw.result.version===S.data.learning.checks.find(c=>c.id==='sides')?.transfer?.version&&!S.detail.events.some(x=>x.event==='verification_started'&&x.attempt===step.attempt);
  const memoryOrigin=S.data.learning.changes.find(c=>c.job==='learning-soft-jaw-a5'&&c.kind==='main_prompt');
  const memoryReuse=reuse&&R.mode==='memory-learning'&&raw.versions?.main_prompt===memoryOrigin?.version&&step.source?.content.includes('tool_feedRamp')&&step.source.content.includes('457.2');
  const savedBefore=S.data.learning.changes.filter(c=>c.at<=e.at),memoryCount=savedBefore.filter(c=>c.kind==='main_prompt').length;
  if(R.active){$('#memory-count').textContent=`${memoryCount} saved ${memoryCount===1?'memory':'memories'}`;$('#checks-foot').textContent=`${1+savedBefore.filter(c=>c.kind==='checks').length} saved checks`;$('.check-lines').innerHTML=savedBefore.some(c=>c.kind==='checks')?'<span>Fixture clearance</span><span>Finished-side protection</span>':'<span>Fixture clearance</span>'; }
  const runMemories=R.steps.slice(0,index+1).filter(s=>s.effect==='run-memory').length;if(runMemories)$('#memory-count').textContent=`${memoryCount} saved · ${runMemories} this run`;
  $$('.node-learning-note').forEach(n=>n.remove());const latestRunMemory=R.steps.slice(0,index+1).findLast(s=>s.effect==='run-memory');if(latestRunMemory&&!runMemory)$('.node-cam').insertAdjacentHTML('beforeend',`<span class="node-learning-note">${esc(short(instructionSummary(latestRunMemory.event.raw.decision?.instructions),90))}</span>`);
  $$('.learning-flash').forEach(n=>n.remove());
  if(runMemory){
    const instruction=raw.decision?.instructions||'',count=R.steps.slice(0,index+1).filter(s=>s.effect==='run-memory').length;
    $('#memory-count').textContent=`${memoryCount} saved · ${count} this run`;
    $$('.node-learning-note').forEach(n=>n.remove());
    $('.node-cam').insertAdjacentHTML('beforeend',`<span class="learning-flash">+1 memory</span><span class="node-learning-note">${esc(short(instructionSummary(instruction),90))}</span>`);
    content=`<div class="saved-learning-label">+1 RUN MEMORY</div><p class="new-memory-text">${esc(short(instructionSummary(instruction),320))}</p><small>Same CAD · used in the next machining plan</small>`;
  }else if(learned&&change){
    const isCheck=change.kind==='checks',addition=isCheck?'Protect the finished outside faces':addedParagraphs(change,S.data.learning.changes).join(' ');
    $('.node-'+step.stage).insertAdjacentHTML('beforeend',`<span class="learning-flash">+1 ${isCheck?'check':'memory'}</span>`);
    if(!isCheck){$$('.node-learning-note').forEach(n=>n.remove());$('.node-cam').insertAdjacentHTML('beforeend',`<span class="node-learning-note">${esc(short(addition.split('. ')[0],85))}</span>`);}
    content=`<div class="saved-learning-label">+ ${isCheck?'CHECK SAVED':'MEMORY SAVED'}</div><p class="new-memory-text">${esc(short(addition,420))}</p><small>${esc(change.version?.slice(0,12)||'')} · saved source</small>`;
  }else if(checkReuse){
    const result=raw.result;content=`<div class="saved-learning-label">REUSED FROM PART B</div><div class="learning-catch">${(result.runtime_s*1000).toFixed(0)}<small>ms</small></div><p>Finished-side violation caught by the saved check.</p><div class="no-simulation">Fusion did not start for this attempt</div>`;
  }else if(step.stage==='input')content='<div class="replay-drawing">Original PDF</div>';
  else if(step.source)content=`<div class="replay-file">${esc(step.source.name)}</div><pre class="replay-code"><code></code></pre><span class="replay-source-note">Saved source · animated reveal</span>`;
  else if(step.stage==='checks'){
    const result=raw.result;content=result?`<div class="replay-verdict ${result.passed?'passed':'failed'}">${result.passed?'✓ Passed':'× Rejected'}</div><p>${esc(result.issues?.join(' · ')||'No issues recorded')}</p><small>${Number.isFinite(result.runtime_s)?(result.runtime_s*1000).toFixed(0)+' ms':''}</small>`:`<p>${esc(e.detail||'Learned check saved')}</p>`;
  }else if(step.stage==='fusion'){
    const v=raw.verification||{};content=`${step.video?`<video muted playsinline controls ${R.playing?'autoplay':''} src="${esc(step.video.url)}"></video><span class="replay-source-note">Recorded candidate · ${esc(step.candidate)}</span>`:''}<div class="replay-verdict ${v.status==='passed'?'passed':'failed'}">${esc(v.status||'Incomplete')}</div><p>${esc(short(v.issues?.length?v.issues.map(x=>typeof x==='string'?x:JSON.stringify(x)).join(' · '):v.status==='passed'?'Machine verification + stock conformity passed':e.detail||'',220))}</p>${Number.isFinite(e.seconds)?`<small>${seconds(e.seconds)} min machining estimate</small>`:''}`;
  }else if(step.stage==='judge')content=`<div class="replay-verdict">${esc(raw.decision?.action||e.title)}</div><p>${esc(short(raw.decision?.instructions||e.detail,330))}</p>`;
  else content=S.detail.preview?`<img class="replay-cad" src="${esc(S.detail.preview)}" alt="Retained accepted CAD"><span class="replay-source-note">Retained CAD</span>`:`<p>${esc(e.title)}</p>`;
  box.innerHTML=`<div class="replay-card-head"><span>${R.mode?'LEARNING REPLAY':'RECORDED'} / ${esc(step.stage.toUpperCase())}</span><button data-action="replay-evidence" aria-label="Open recorded evidence">↗</button></div><h3>${esc(runMemory?'Planning memory added':learned?(change?.kind==='checks'?'A new check enters the gate':'A new memory enters the agent'):memoryReuse?'Next part · saved memory carried forward':step.intent||e.title)}</h3>${content}`;
  if(memoryReuse)box.insertAdjacentHTML('beforeend','<span class="replay-source-note">Same saved prompt version · ramp feed present in generated code</span>');
  if(step.source&&!learned){const full=step.source.content.split('\n').slice(0,28).join('\n'),target=$('code',box);let pos=0;const increment=Math.max(12,Math.ceil(full.length/65));R.typeTimer=setInterval(()=>{if(version!==R.version){clearInterval(R.typeTimer);return;}pos+=increment;target.textContent=full.slice(0,pos);if(pos>=full.length)clearInterval(R.typeTimer);},35);}
  if(step.stage==='input'){const url=S.detail.drawings.find(Boolean);if(url)api('/api/drawing?path='+encodeURIComponent(url)+'&page=1').then(p=>{if(version===R.version&&R.active)$('.replay-drawing',box).innerHTML=`<img src="${esc(p.image)}" alt="Original input drawing">`;}).catch(()=>{});}
}
$('#replay-scrub').addEventListener('input',async e=>{await seekReplay(Number(e.target.value));});
$('#explorer-dialog').addEventListener('close',()=>{S.view='overview';});

$('#demo-dialog').addEventListener('close',()=>{pauseDemo();demoTimers();});
const D={index:0,steps:[],playing:false,live:false,session:null,detail:null,version:0};
function pauseDemo(){$('#demo-scene video')?.pause();D.playing=false;clearTimeout(D.timer);clearInterval(D.blocksTimer);}
function demoTimers(){clearTimeout(D.timer);clearTimeout(D.pollTimer);clearTimeout(D.frameTimer);clearTimeout(D.finishTimer);clearTimeout(D.resultTimer);clearInterval(D.blocksTimer);}
function rememberDemo(){sessionStorage.setItem('silta-replay:'+D.intake.id,String(D.index));}
async function beginDemo(resumeSession=null){
  ({stagedSteps,stagedStepDuration,streamedSource,demoPlaybackAction}=await import('/staged-replay.mjs'));
  stopReplay();demoTimers();D.version++;D.live=false;D.fallback=false;D.liveRequested=false;D.reviewPending=false;D.index=0;D.playing=true;
  D.intake=resumeSession?{id:resumeSession.id,drawing:resumeSession.drawing,demo:{run_id:resumeSession.run_id}}:S.intake;
  D.session=resumeSession||await api('/api/demo/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:D.intake.id})});
  D.detail=await api('/api/jobs/'+encodeURIComponent(D.intake.demo.run_id));D.steps=stagedSteps(D.detail,{presentation:true});
  const gate=Math.max(0,D.steps.findIndex(s=>s.kind==='ready'));
  if(resumeSession){const saved=Number(sessionStorage.getItem('silta-replay:'+D.intake.id)||0);D.index=Math.max(0,Math.min(D.steps.length-1,saved));if(resumeSession.status==='playing'||resumeSession.status==='completed'&&D.index<=gate)D.index=gate;}
  history.replaceState(null,'','?replay='+encodeURIComponent(D.intake.id));
  $('#upload-dialog').close();$('#demo-dialog').showModal();$('#demo-body').classList.remove('is-live');$('#demo-title').textContent=D.detail.label;
  $('#demo-fallback').hidden=true;$('#demo-reset').hidden=true;
  $('#demo-part').src=D.detail.preview;$('#demo-pdf').removeAttribute('src');
  const version=D.version;api('/api/drawing?path='+encodeURIComponent(D.intake.drawing)+'&page=1').then(p=>{if(version===D.version)$('#demo-pdf').src=p.image;}).catch(()=>{});
  renderDemoStep();pollDemo();
}
function showRecordedSimulation(){
  if(!$('#demo-dialog').open||D.fallback)return;
  pauseDemo();D.fallback=true;D.fallbackComplete=false;D.reviewPending=false;$('#demo-body').classList.add('is-live');
  const film=D.detail?.media?.find(v=>v.kind==='machining');
  if(!film){$('#demo-status').textContent='Simulation recording unavailable';return;}
  $('#demo-mode').textContent='Fusion · simulation';
  $('#demo-scene').innerHTML=`<video id="demo-recorded-simulation" autoplay muted playsinline src="${esc(film.url)}"></video>`;
  $('#demo-fallback').hidden=true;$('#demo-reset').hidden=false;
  const video=$('#demo-recorded-simulation');
  video.controls=false;
  video.playbackRate=0.7;
  video.style.pointerEvents='none';
  video.addEventListener('ended',()=>{D.fallbackComplete=true;finishDemoSimulation();},{once:true});
  video.play().catch(()=>{$('#demo-status').textContent='Starting simulation…';});
}
function showLiveDemo(){
  pauseDemo();D.live=true;D.liveRequested=true;$('#demo-body').classList.add('is-live');$('#demo-mode').textContent='Starting Fusion simulation';
  $('#demo-scene').innerHTML=empty('Opening live view…');$('#demo-fallback').hidden=false;
  demoFrame();
}
function advanceDemo(){if(!$('#demo-dialog').open)return;if(D.index<D.steps.length-1){D.index++;D.playing=true;renderDemoStep();}}
function finishDemoSimulation(){
  if(D.reviewPending)return;D.reviewPending=true;
  const version=D.version;
  D.finishTimer=setTimeout(()=>{if(version!==D.version||!$('#demo-dialog').open)return;D.live=false;D.fallback=false;clearTimeout(D.frameTimer);$('#demo-body').classList.remove('is-live');$('#demo-fallback').hidden=true;advanceDemo();},3500);
}
async function syncDemoPlayback(){
  const action=demoPlaybackAction({kind:D.steps[D.index]?.kind,status:D.session?.status,live:D.live,requested:D.liveRequested,fallback:D.fallback});
  if(action==='start'){
    D.liveRequested=true;$('#demo-status').textContent='Starting Fusion simulation…';
    showRecordedSimulation();
  }else if(action==='watch')showRecordedSimulation();
  else if(action==='review')finishDemoSimulation();
}
function renderDemoStep(){
  clearTimeout(D.timer);clearTimeout(D.resultTimer);clearInterval(D.blocksTimer);$('#demo-scene video')?.pause();const step=D.steps[D.index];if(!step)return;rememberDemo();
  $('#demo-mode').textContent='Replay';
  const stages=['input','cad','cam','checks','simulate','judge','output'],labels=['Drawing','CAD','CAM','Checks','Simulate','Judge','Output'];
  $('#demo-stages').innerHTML=stages.map((stage,i)=>`<span class="${stage===step.stage?'active':''}">${String(i+1).padStart(2,'0')} ${labels[i]}</span>`).join('');
  $('#demo-part').hidden=D.index<1;
  const passes=D.steps.slice(0,D.index+(step.kind==='verification'?0:1)).filter(x=>x.kind==='verification'&&x.passed&&Number.isFinite(x.seconds));
  const showEstimates=values=>{$('#demo-estimates').innerHTML=values.length?`<span>VERIFIED MACHINING ESTIMATE</span><div>${values.map(x=>`<b>${(x.seconds/60).toFixed(2)}<small>min</small></b>`).join('<i>→</i>')}</div>`:'';};showEstimates(passes);
  let body='';
  if(step.kind==='code')body=`<div class="demo-source-name">${esc(step.source?.name||'Source unavailable')}</div><pre class="streaming-source"><code id="demo-code"></code><span class="stream-caret" aria-hidden="true">▋</span></pre>`;
  else if(step.kind==='drawing')body=`<div class="demo-intro"><span>ENGINEERING DRAWING</span><strong>Ribbed clevis</strong><p>AL6061 · indexed machining · UMC750</p></div>`;
  else if(step.kind==='failure')body=`<div class="demo-verdict needs-repair">Needs repair</div><p>${esc(short(step.text,350))}</p>`;
  else if(step.kind==='checks')body='<div class="demo-running"><i class="pulse"></i> Checking machining code…</div>';
  else if(step.kind==='verification')body='<div class="demo-running"><i class="pulse"></i> Reviewing simulation evidence…</div>';
  else if(step.kind==='instruction')body='<div class="demo-running"><i class="pulse"></i> Reviewing machining time…</div>';
  else if(step.kind==='ready'){D.playing=false;body='<div class="demo-ready"><span>CAM + CHECKS COMPLETE</span><strong>Starting Fusion simulation</strong></div>';}
  else if(step.kind==='result'){pauseDemo();body=`<div class="demo-ready"><span>VERIFIED PLAN</span><strong>${((step.before-step.after)/step.before*100).toFixed(2)}% less machining time</strong><p>${(step.before/60).toFixed(2)} → ${(step.after/60).toFixed(2)} min estimated</p></div>`;}
  $('#demo-scene').innerHTML=`<div class="demo-scene-heading"><small>${step.attempt?'ATTEMPT '+step.attempt:'CLEVIS'}</small><h3>${esc(step.kind==='checks'?'Code checks':step.kind==='verification'?'Fusion simulation':step.kind==='instruction'?'Judge review':step.title)}</h3></div><div id="demo-step-content">${body}</div>`;
  if(step.kind==='verification'&&step.passed){setTimeout(()=>{if(version===D.version&&index===D.index&&$('#demo-dialog').open&&!D.fallback)showRecordedSimulation();},0);}
  const duration=stagedStepDuration(step),version=D.version,index=D.index;
  if(step.kind==='code'){
    const source=step.source?.content||'# Source unavailable',started=performance.now(),target=$('#demo-code'),pre=target.parentElement;
    D.blocksTimer=setInterval(()=>{if(version!==D.version||index!==D.index)return;const following=pre.scrollHeight-pre.scrollTop-pre.clientHeight<70;target.textContent=streamedSource(source,performance.now()-started,duration-2000);if(following)pre.scrollTop=pre.scrollHeight;if(target.textContent.length===source.length){clearInterval(D.blocksTimer);$('.stream-caret',pre)?.remove();}},60);
  }else if(['checks','verification','instruction'].includes(step.kind)){
    D.resultTimer=setTimeout(()=>{if(version!==D.version||index!==D.index||!$('#demo-dialog').open)return;
      let result='';
      if(step.kind==='checks')result=`<div class="demo-verdict ${step.passed?'passed':'needs-repair'}">${step.passed?'Passed':'Failed'}</div>${step.issues.length?`<p>${esc(step.issues.join('\n'))}</p>`:''}`;
      if(step.kind==='verification'){result=`<div class="demo-verdict ${step.passed?'passed':'needs-repair'}">${step.passed?'Passed':'Not passed'}</div><p>Fusion machine verification + stock conformity</p>${Number.isFinite(step.seconds)?`<div class="demo-time">${(step.seconds/60).toFixed(2)} <small>min estimate</small></div>`:''}`;if(step.passed&&Number.isFinite(step.seconds))showEstimates([...passes,step]);}
      if(step.kind==='instruction')result=`<div class="demo-instruction">${esc((step.text||'').split('\n\n')[0])}</div>`;
      $('#demo-step-content').innerHTML=result;
    },Math.min(5500,duration*.55));
  }
  renderDemoStatus();syncDemoPlayback();
  if(D.playing)D.timer=setTimeout(advanceDemo,duration);
}
function renderDemoStatus(){
  if(D.fallback){$('#demo-status').textContent='Machining video';return;}
  const s=D.session||{},step=D.steps[D.index];
  $('#demo-status').textContent=s.error||(D.live?({playing:'Live simulation running',completed:'Simulation complete'}[s.status]||'Connecting to Fusion'):step?.kind==='ready'?'Preparing Fusion':step?.kind==='result'?'Complete':`Attempt ${step?.attempt||1} · ${step?.stage==='cam'||step?.stage==='cad'?'Machining source':step?.stage==='judge'?'Judge review':step?.stage==='checks'?'Code checks':step?.stage==='simulate'?'Simulation evidence':'Drawing'}`);
  if(['ready','completed','error'].includes(s.status))$('#demo-reset').hidden=false;
  if(s.status==='error'&&step?.kind==='ready')$('#demo-fallback').hidden=false;
}
async function pollDemo(){
  if(!$('#demo-dialog').open||!D.session)return;
  const version=D.version;
  try{const session=await api('/api/demo/'+encodeURIComponent(D.intake.id));if(version!==D.version||!$('#demo-dialog').open)return;D.session=session;renderDemoStatus();await syncDemoPlayback();if(D.live&&!D.fallback&&!D.session.live)$('#demo-mode').textContent=D.session.phase==='milling'?'Fusion capture unavailable':'Preparing live simulation';}
  catch(error){$('#demo-status').textContent=error.message;}
  if(version===D.version&&$('#demo-dialog').open)D.pollTimer=setTimeout(pollDemo,1000);
}
async function demoFrame(){
  if(!$('#demo-dialog').open||!D.live||D.fallback)return;
  const version=D.version;
  try{
    if(D.session?.live===true&&['playing','completed'].includes(D.session?.status)){
      const f=await api('/api/worker/frame',{method:'POST',body:'{}'});
      if(version!==D.version||!D.live||D.fallback)return;
      if(!$('#demo-live-image'))$('#demo-scene').innerHTML='<img id="demo-live-image" alt="Live Fusion machining simulation">';
      $('#demo-live-image').src=f.url+'?at='+encodeURIComponent(f.at);
      $('#demo-mode').textContent=D.session.status==='completed'?'Live · complete':'Live';
    }
  }catch(error){$('#demo-status').textContent=error.message;$('#demo-fallback').hidden=false;}
  if(version===D.version)D.frameTimer=setTimeout(demoFrame,300);
}
async function demoAction(action,button){
  try{
    if(action==='start-demo'){button.disabled=true;button.textContent='Preparing…';await beginDemo();return;}
    if(action==='demo-close'){pauseDemo();demoTimers();D.version++;$('#demo-dialog').close();history.replaceState(null,'',location.pathname);return;}
    if(action==='demo-fallback'){showRecordedSimulation();return;}
    if(action==='demo-reset'){
      pauseDemo();demoTimers();D.version++;D.session=await api('/api/demo/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:D.intake.id})});
      sessionStorage.removeItem('silta-replay:'+D.intake.id);D.live=false;D.fallback=false;D.index=0;$('#demo-dialog').close();history.replaceState(null,'',location.pathname);showUpload();return;
    }
  }catch(error){notify(error.message);if(button){button.disabled=false;if(action==='start-demo'){button.textContent='Open run →';$('#upload-result').insertAdjacentHTML('beforeend',`<div class="error-box">${esc(error.message)}</div>`);}}}
}

await refresh(true);
const resumeId=new URLSearchParams(location.search).get('replay');
if(resumeId&&/^drawing-[a-f0-9]{12}$/.test(resumeId)){
  try{const session=await api('/api/demo/'+resumeId);if(session.status!=='reset')await beginDemo(session);else history.replaceState(null,'',location.pathname);}
  catch(error){history.replaceState(null,'',location.pathname);notify(error.message);}
}
setInterval(()=>refresh(false),5000);
