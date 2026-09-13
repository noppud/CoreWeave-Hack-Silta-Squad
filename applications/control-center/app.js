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
function drawer(kicker,title,html) { $('#drawer-kicker').textContent=kicker; $('#drawer-title').textContent=title; $('#drawer-body').innerHTML=html; if (!$('#drawer').open) $('#drawer').showModal(); $('#drawer').scrollTop=0; }
function partCard(p) {
  return `<button class="part-card ${p.id===S.job?'current':''}" data-part="${esc(p.id)}"><div class="part-image">${p.preview?`<img src="${esc(p.preview)}" alt="CAD preview of ${esc(p.label)}" loading="lazy">`:''}<span class="part-id">${esc(p.number)}</span>${p.media.length?`<span class="video-tag">▷ ${p.media.length} recordings</span>`:''}</div><div class="part-info"><h3>${esc(p.label)}</h3><div><span class="${p.verified?'passed':''}">${p.verified?'✓ Verified plan':esc(p.status)}</span><span>${seconds(p.summary.best_seconds)} min</span></div></div></button>`;
}
function eventRow(e, index, source='timeline') {
  const icons={learning:'✳',checks:'✓',judge:'↗',work:'↳'};
  return `<button class="event-row" data-event="${index}" data-event-source="${source}"><span class="event-icon ${esc(e.group)}">${icons[e.group]||'·'}</span><span><strong>${esc(e.title)}</strong><small>${esc(e.part)}${e.attempt?` · attempt ${e.attempt}`:''}${Number.isFinite(e.seconds)?` · ${seconds(e.seconds)} min estimate`:''}</small></span><time>${clock(e.at)}</time></button>`;
}
function changeView(view) {
  S.view=view; $$('.view').forEach(el=>el.hidden=el.id!==view+'-view');
  $$('.mainnav .nav').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
  $('#page-title').textContent=titles[view][0]; $('#page-subtitle').textContent=titles[view][1];
  if(view!=='overview'){clearTimeout(S.frameTimer);++S.mediaToken;$('#media video')?.pause();}else if(S.detail&&S.media==='live')renderMedia();
  if(view==='timeline') renderTimeline(); if(view==='parts') renderParts(); if(view==='learning') renderLearning();
  window.scrollTo({top:0,behavior:'instant'});
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
  $('#timeline-content').innerHTML=html||empty('No matching events.');
}
function memories() { return (S.data.learning.guidance||'').split(/\n\s*\n/).map(x=>x.replace(/\s+/g,' ').trim()).filter(Boolean).slice(1); }
function memoryCards(){return memories().map((m,i)=>`<details class="memory-card"><summary><span class="memory-number">${String(i+1).padStart(2,'0')}</span><span>${esc(m.split('. ')[0])}.</span><span class="orange">+</span></summary><p>${esc(m)}</p></details>`).join('');}
function renderLearning() {
  const l=S.data.learning;
  $('#learning-content').innerHTML=`<div class="sectionbar"><h2>Learned checks</h2>${link(l.active_checks,'Current Python')}</div><div class="lesson-grid">${l.checks.map(c=>`<button class="lesson" data-lesson="${c.id}"><p class="eyebrow orange">${esc(c.label)}</p><h2>${esc(c.title)}</h2><p>${esc(c.scope)}</p><div class="lesson-foot"><span>${esc(c.learned_on)}</span><span>Source & evidence ↗</span></div></button>`).join('')}</div><section class="learning-section"><div class="sectionbar"><h2>Planning memories</h2>${link(l.active_guidance,'Current prompt')}</div><div class="memory-list">${memoryCards()}</div></section><section class="learning-section"><details><summary>Saved changes · ${l.changes.length}</summary><div class="guidance-list">${l.changes.map(c=>`<button class="guidance-item" data-change="${esc(c.id)}"><small>${date(c.at)} · ${esc(c.kind==='checks'?'CHECK':'MEMORY')}</small><h3>${esc(c.job)}</h3><p>${esc(c.reason)}</p></button>`).join('')}</div></details></section>`;
}
async function openWorkbench(stage=S.stage) {
  S.stage=stage; S.media=stage==='input'?'drawing':stage==='cam'?'code':'model';
  $('#workbench-dialog').showModal();renderInspector();await renderMedia();
}
function lesson(id) {
  const c=S.data.learning.checks.find(c=>c.id===id); if(!c)return;
  const rejections=c.transfer?.observed_rejections||[];
  drawer(c.label,c.title,`<div class="drawer-copy">${esc(c.description)}</div><div class="mini-timeline"><div><small>FAILURE · ${esc(c.learned_on.split('→')[0])}</small><p>${esc(c.reason||'The recorded collision led to a fixture-envelope endpoint check.')}</p></div><div><small>NEW EXECUTABLE CHECK</small><p>${esc(c.scope)}</p></div>${rejections.map(r=>`<div><small>REUSED ON PART C · ${(r.runtime_s*1000).toFixed(0)} MS</small><p>${esc(r.issues.join('\n'))}</p><p>Simulation started for this rejected attempt: ${r.same_attempt_simulation_started?'yes':'no'}.</p></div>`).join('')}</div><div class="drawer-links">${link(c.source,'Saved check source')}${link(c.evidence,'Learning evidence')}<button class="text-button" data-inspect-job="${esc(c.job)}">Open source run ↗</button></div><details class="raw-details"><summary>Read the actual Python check</summary>${code(c.content)}</details>`);
}
async function selectPart(job, navigate=false) {
  const token=++S.requestToken;
  try {
    const d=await api('/api/jobs/'+encodeURIComponent(job));
    if(token!==S.requestToken)return;
    S.job=job;S.detail=d;S.video=0;S.modelKind='cad';S.sourceIndex=undefined;S.pdfPage=1;S.pdfZoom=false;
    if(navigate){changeView('overview');S.media='model';S.stage='fusion';}
    $('#selected-title').textContent=d.label;$('#selected-number').textContent=(d.number||'NEW DRAWING')+' / '+(S.data.worker.running&&S.data.worker.job===job?'LIVE JOB':'RETAINED JOB');
    $('#selected-status').textContent=d.verdict?.status==='passed'?'Verified plan':d.status||'Preparing';
    $('#selected-status').className='badge '+(d.verdict?.status==='passed'?'':d.status==='running'?'warn':'neutral');
    $('#part-select').value=job;$('#video-count').textContent=d.media?.length||'';
    $('[data-media="video"]').disabled=!d.media?.length;
    if(S.media==='video'&&!d.media?.length)S.media='model';
    const candidateCount=d.events.filter(e=>e.event==='candidate_created').length;$('#cam-count').textContent=`· ${candidateCount} ${candidateCount===1?'candidate':'candidates'}`;
    $('#fusion-foot').textContent=`${d.summary.passes} completed ${d.summary.passes===1?'pass':'passes'}`;
    $('#judge-foot').textContent=d.summary.last_action==='stop'?'Best verified plan selected':'Evidence → next decision';
    $('#canvas-job-title').textContent=d.label;$('#loop-part-name').textContent=d.label;renderInspector();if($('#workbench-dialog').open)await renderMedia();renderRecent();if(navigate&&!$('#workbench-dialog').open)await openWorkbench('fusion');
  } catch(e){notify(e.message);}
}
function renderRecent() {
  const e=S.data.timeline[0];$('#last-event').textContent=e?`· ${short(e.title,48)} ↗`:'↗';
  const m=memories();$('#memory-count').textContent=`${m.length} planning memories`;
  $('#memory-preview').textContent=m.length?'Ramp feed · stepdown · clearance':'Saved machining guidance';
}
function statusRow(label,status) {return `<div class="check-row"><span>${esc(label)}</span><span class="status">${esc(status)}</span></div>`;}
function renderInspector() {
  const d=S.detail;if(!d)return;
  const selected={input:['01 / INPUT','Drawing & setup'],cam:['02 / CAD + CAM','Generated code'],checks:['03 / CHECKS','Learned checks'],fusion:['04 / FUSION','Verification'],judge:['05 / JUDGE','Judge decisions']}[S.stage];
  $('#inspector-kicker').textContent=selected[0];$('#inspector-title').textContent=selected[1];
  $$('.node').forEach(n=>n.classList.toggle('selected',n.dataset.stage===S.stage));
  const rawLink=link(d.manifest,'Run evidence');
  let html='';
  if(S.stage==='fusion'){
    const v=d.verdict||{},summary=d.summary, feedback=v.feedback||{};
    const passed=v.status==='passed'&&v.completed;
    html=`<div class="verdict-title"><span class="checkmark">${passed?'✓':'·'}</span>${passed?'Selected plan passed verification':'Waiting for a verified plan'}</div><p class="inspector-copy">${passed?'Fusion machine verification and finished-stock comparison against the accepted CAD.':esc(d.reason||'The runner will publish the actual result here.')}</p><div class="metrics"><div><small>Best machining estimate</small><strong>${seconds(summary.best_seconds)}<span>min</span></strong></div><div><small>Verified passes · this run</small><strong>${summary.passes}<span>${summary.passes===1?'pass':'passes'}</span></strong></div></div><div class="checks-list">${statusRow('Fusion verification',passed?'✓ Complete':v.status||'Not yet recorded')}${statusRow('Finished stock → target',feedback.target_stock_comparison?.status==='passed'?'✓ Match within tolerance':feedback.target_stock_comparison?.status||'See evidence')}${statusRow('Accepted part geometry',passed?'✓ Preserved':'See evidence')}${statusRow('Result scope','CAM simulation')}</div>${Number.isFinite(summary.improvement_percent)&&summary.improvement_percent>0?`<p class="small-note"><span class="orange">${summary.improvement_percent.toFixed(2)}% lower estimate</span> than the first verified plan in this run.</p>`:''}<div class="inspector-links">${rawLink}${link(d.weave,'Weave trace')}</div>`;
  } else if(S.stage==='input'){
    html=`<div class="file-list">${d.drawings.filter(Boolean).map((u,i)=>link(u,`Drawing ${i+1} · PDF`)).join('')}</div>${statusRow('Accepted CAD',d.events.some(e=>e.event==='target_accepted')?'✓ Recorded':'Not yet accepted')}${statusRow('Input type','PDF drawing')}<div class="inspector-links"><button class="text-button" data-action="upload">Add another drawing →</button>${rawLink}</div>`;
  } else if(S.stage==='cam'){
    const candidates=d.events.filter(e=>e.event==='candidate_created');
    html=`<div class="metrics"><div><small>Candidate plans</small><strong>${candidates.length}</strong></div><div><small>Saved source files</small><strong>${d.sources.length}</strong></div></div><div class="file-list">${d.files.filter(f=>f.url).map(f=>link(f.url,f.name)).join('')}</div><button class="text-button" data-media="code">Inspect generated code →</button><p class="small-note">Python source appears when emitted. Retained jobs also expose their posted NC program.</p>`;
  } else if(S.stage==='checks'){
    const checks=d.events.filter(e=>e.event==='checks_completed');
    html=`${S.data.learning.checks.map(c=>`<button class="rule-link" data-lesson="${c.id}"><small>${esc(c.label)} · FROM ${esc(c.learned_on.toUpperCase())}</small><strong>${esc(c.title)} ↗</strong><span>${esc(c.status)}</span></button>`).join('')}<div class="checks-list">${statusRow('This run · check executions',String(checks.length))}${statusRow('Rejected before simulation',String(checks.filter(e=>e.raw.result?.passed===false).length))}</div><p class="small-note">Applicability is limited to the check’s recorded setup and supported NC modes.</p><div class="inspector-links">${link(S.data.learning.active_checks,'Current source')}</div>`;
  } else {
    const decisions=d.events.filter(e=>e.event==='supervisor_decision');
    html=`${[...decisions].reverse().map(e=>`<div class="judge-card"><small>${clock(e.at)} · ${esc(e.raw.decision?.action?.toUpperCase())}</small><p>${esc(e.detail)}</p><button class="text-button" data-detail-event="${d.events.indexOf(e)}">Evidence & full decision ↗</button></div>`).join('')||empty('The judge has not received a completed verification yet.')}<div class="inspector-links">${link(d.weave,'Weave trace')}${rawLink}</div>`;
  }
  $('#inspector-body').innerHTML=html;
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
    container.innerHTML=d.preview?`<img src="${esc(d.preview)}" alt="Retained CAD preview of ${esc(d.label)}">`:empty('The CAD preview appears when the drawing has been turned into a part.');
    $('#media-caption').textContent='CAD preview · retained target geometry';
    const meshUrl=S.modelKind==='stock'?d.stock_mesh:d.mesh;
    if(meshUrl){
      try{
        const {mountModel}=await import('/model.js');if(token!==S.mediaToken)return;
        container.innerHTML=`<div class="model-switcher"><button data-model-kind="cad" class="${S.modelKind==='cad'?'active':''}">Accepted CAD</button>${d.stock_mesh?`<button data-model-kind="stock" class="${S.modelKind==='stock'?'active':''}">Simulated result</button>`:''}</div><span class="model-help">DRAG TO ROTATE · SCROLL TO ZOOM</span>`;
        S.modelDispose=await mountModel(container,meshUrl,()=>token===S.mediaToken);
        if(token===S.mediaToken)$('#media-caption').textContent=S.modelKind==='stock'?'Simulated finished stock · exported from the verified Fusion candidate':'Interactive CAD · geometry from the retained STEP model';
      }catch(e){if(token===S.mediaToken){container.innerHTML=d.preview?`<img src="${esc(d.preview)}" alt="CAD preview">`:empty('3D view unavailable.');$('#media-caption').textContent='CAD preview · interactive renderer unavailable';}}
    }
  }else if(S.media==='video'){
    const list=d.media||[],v=list[S.video]||list[0];
    container.innerHTML=v?`<video controls playsinline preload="metadata" aria-label="${esc(v.scope)}" src="${esc(v.url)}"></video><div class="video-switcher">${list.map((v,i)=>`<button class="${i===S.video?'active':''}" data-video="${i}">${esc(v.label)}</button>`).join('')}</div>`:empty('No Fusion recording is attached to this part.');
    $('#media-caption').textContent=v?`${v.scope} · retained candidate`:'No recording attached';
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
  drawer(`${e.part} · ${date(e.at)} ${clock(e.at)}`,e.title,`<div class="drawer-copy">${esc(e.detail||'This stage is recorded in the job manifest.')}</div>${Number.isFinite(e.seconds)?`<div class="metrics"><div><small>Recorded machining estimate</small><strong>${seconds(e.seconds)}<span>min</span></strong></div></div>`:''}<div class="drawer-links"><button class="text-button" data-inspect-job="${esc(e.job)}">Open this run ↗</button></div><details class="raw-details"><summary>Exact recorded event</summary>${code(JSON.stringify(e.raw,null,2))}</details>`);
}
function showUpload() {
  $('#upload-result').innerHTML='';S.intake=null;
  $('#sample-drawings').innerHTML=S.data.parts.filter(p=>['UMC 08','UMC 11','UMC 12'].includes(p.number)).map(p=>`<button data-sample="${esc(p.id)}"><img src="${esc(p.preview)}" alt="${esc(p.label)}">${esc(p.label)} ↗</button>`).join('');
  $('#upload-dialog').showModal();
}
async function upload(data,name) {
  $('#upload-result').innerHTML='<p class="small-note">Receiving the PDF and attaching the shop context…</p>';
  try{
    const item=await api('/api/upload',{method:'POST',headers:{'Content-Type':'application/pdf','X-Filename':encodeURIComponent(name)},body:data});
    S.intake=item;
    $('#upload-result').innerHTML=`<div class="intake-result"><h3>${esc(item.filename)}</h3>${badge(item.profile?.known_drawing?'Drawing matched to its shop setup':'New drawing · Astra will read the PDF')}<p>${item.status==='ready'?esc(item.profile.machine):'Drawing received. This PDF needs its own machine, stock, material, tooling and fixture configuration before generation can start.'}</p>${item.status==='ready'?`<p><b>${esc(item.profile.material)} · ${esc(item.profile.stock?.join(' × '))} mm stock</b></p><details class="raw-details"><summary>Shop setup & assumptions</summary><p>${item.profile.assumptions.map(esc).join('<br><br>')}</p></details><p class="small-note">Up to 3 attempts · run-scoped learning</p><button class="primary" data-action="start-job" ${!S.data.enable_runs?'disabled':''}>${S.data.enable_runs?'Start in Fusion →':'Review-only server'}</button>`:''}<div class="drawer-links">${link(item.drawing,'View PDF')}</div></div>`;
    await refresh(false);
  }catch(e){$('#upload-result').innerHTML=`<div class="error-box">${esc(e.message)}</div>`;}
}
async function refresh(initial=false) {
  try{
    const d=await api('/api/state');S.data=d;
    $('#connection-label').textContent='Evidence synced';$('#connection-dot').classList.add('connected');
    $('#stat-parts').textContent=d.stats.verified;$('#nav-learning').textContent=d.stats.checks;
    $('#checks-foot').textContent=`${d.stats.checks} learned checks ↗`;
    const latest=d.intakes.find(x=>x.job===d.worker.job);
    $('#live-strip').hidden=!d.worker.running&&!latest;
    if(d.worker.running){
      $('#live-strip').innerHTML=`<span><i class="pulse"></i>Fusion worker · ${esc(latest?.filename||'New drawing')} · job in progress</span><button data-inspect-job="${esc(d.worker.job)}">Follow live job ↗</button>`;
    }else if(latest){
      $('#live-strip').innerHTML=`<span>Latest job · ${esc(latest.status)}${latest.worker_exit_code?` · worker exited (${latest.worker_exit_code})`:''}</span><button data-inspect-job="${esc(latest.job)}">Inspect result ↗</button>`;
    }
    const selected=$('#part-select').value;
    $('#part-select').innerHTML=d.parts.map(p=>`<option value="${esc(p.id)}">${esc(p.label)}</option>`).join('');$('#part-select').value=selected;
    renderRecent();
    if(initial)await selectPart(d.parts[0]?.id);
    else if(S.view==='timeline')renderTimeline();else if(S.view==='parts')renderParts();
    if(d.worker.running&&S.job===d.worker.job){
      const detail=await api('/api/jobs/'+S.job).catch(()=>null);
      if(detail){
        const changed=detail.events.length!==S.detail?.events.length||detail.sources.length!==S.detail?.sources.length;
        if(S.detail?.id!==detail.id){await selectPart(detail.id);}
        S.detail=detail;
        const ev=detail.events.at(-1)?.event||'';
        const stage=ev.startsWith('target')?'cam':ev.startsWith('candidate')||ev.startsWith('cam')?'cam':ev.startsWith('check')?'checks':ev.startsWith('verification')?'fusion':ev.startsWith('supervisor')?'judge':'cam';
        $$('.node').forEach(n=>n.classList.toggle('executing',n.dataset.stage===stage));
        $('#selected-status').textContent=detail.stage;
        if(changed){renderInspector();if(S.media==='code'||(S.media==='model'&&!$('#media canvas')))await renderMedia();}
      }
    }else $$('.node').forEach(n=>n.classList.remove('executing'));
  }catch(e){$('#connection-label').textContent='Connection lost';$('#connection-dot').classList.remove('connected');if(initial)notify(e.message);}
}

document.addEventListener('click',async event=>{
  const b=event.target.closest('button,[data-inspect-job]');if(!b)return;
  if(b.dataset.view){$('#workbench-dialog').close();$('#drawer').close();changeView(b.dataset.view);return;}
  if(b.dataset.part){await selectPart(b.dataset.part,true);return;}
  if(b.dataset.stage){await openWorkbench(b.dataset.stage);return;}
  if(b.dataset.modelKind){S.modelKind=b.dataset.modelKind;await renderMedia();return;}
  if(b.dataset.media){S.media=b.dataset.media;S.sourceIndex=undefined;await renderMedia();return;}
  if(b.dataset.pdfPage!==undefined){S.pdfPage=Number(b.dataset.pdfPage);await renderMedia();return;}
  if(b.dataset.video!==undefined){S.video=Number(b.dataset.video);await renderMedia();return;}
  if(b.dataset.lesson){lesson(b.dataset.lesson);return;}
  if(b.dataset.filter){S.filter=b.dataset.filter;S.limit=70;$$('#timeline-filters button').forEach(el=>el.classList.toggle('active',el===b));renderTimeline();return;}
  if(b.dataset.event!==undefined){openEvent(S.data.timeline[Number(b.dataset.event)]);return;}
  if(b.dataset.detailEvent!==undefined){openEvent(S.detail.events[Number(b.dataset.detailEvent)]);return;}
  if(b.dataset.inspectJob){$('#drawer').close();await selectPart(b.dataset.inspectJob,true);return;}
  if(b.dataset.change){const c=S.data.learning.changes.find(c=>c.id===b.dataset.change);drawer('SAVED PLANNING GUIDANCE',c.job,`<div class="drawer-copy">${esc(c.reason)}</div><div class="drawer-links">${link(c.source,'Saved guidance')}</div><details class="raw-details"><summary>Full saved prompt</summary>${code(c.content)}</details>`);return;}
  if(b.dataset.sample){const p=S.data.parts.find(p=>p.id===b.dataset.sample);try{const r=await fetch(p.drawings.find(Boolean));if(!r.ok)throw new Error('Drawing unavailable');await upload(await r.blob(),p.label+'.pdf');}catch(e){notify(e.message);}return;}
  const action=b.dataset.action;
  if(action==='open-part'){await openWorkbench('fusion');}
  else if(action==='close-workbench')$('#workbench-dialog').close();
  else if(action==='memories')drawer('SHARED PLANNING MEMORY','Planning lessons',`<div class="memory-list">${memoryCards()}</div><div class="drawer-links">${link(S.data.learning.active_guidance,'Current prompt')}<button class="text-button" data-view="learning">All learned checks & memories ↗</button></div>`);
  else if(action==='pdf-zoom'){S.pdfZoom=!S.pdfZoom;await renderMedia();}
  else if(action==='close')$('#drawer').close();
  else if(action==='close-upload')$('#upload-dialog').close();
  else if(action==='upload')showUpload();
  else if(action==='lesson-sides')lesson('sides');
  else if(action==='more-events'){S.limit+=70;renderTimeline();}
  else if(action==='active-guidance')drawer('CURRENT SHARED PLANNING GUIDANCE','Current planning memory',`<div class="drawer-links">${link(S.data.learning.active_guidance,'Source file')}</div>${code(S.data.learning.guidance)}`);
  else if(action==='slides')drawer('JOEL’S LOOP · REFERENCE & EXPLANATION','Two ways to learn.',`<p class="drawer-copy">The control center follows Joel’s input → agent → checks → simulation → judge layout. The original interactive slide uses scripted examples; the application uses actual run evidence.</p><div class="drawer-links"><a href="/reference" target="_blank" rel="noopener">Open Joel’s original interactive slide ↗</a></div><div class="slides">${S.data.slides.filter(Boolean).map(u=>`<img src="${esc(u)}" alt="Loop explanation slide">`).join('')}</div>`);
  else if(action==='aria')drawer('ARIA / RETAINED ARCHITECTURE REVIEW','ARIA review',`<div class="drawer-copy">ARIA reviewed the workflow and its evidence. This is a completed advisory review, separate from the machining judge.</div><div class="drawer-links">${link(S.data.learning.aria_source,'Actual ARIA response')}</div>${code(S.data.learning.aria||'No retained ARIA response found.')}`);
  else if(action==='expand-media'){
    const d=S.detail;
    if(S.media==='video'&&d.media?.length)drawer('RECORDED FUSION SIMULATION',d.label,`<video class="drawer-media" controls playsinline src="${esc(d.media[S.video].url)}"></video><p class="small-note">${esc(d.media[S.video].scope)}</p>`);
    else if(S.media==='drawing'&&d.drawings.find(Boolean))drawer('ORIGINAL DRAWING',d.label,`<div class="drawer-links">${link(d.drawings.find(Boolean),'Open original PDF')}</div>${S.pdf?`<img class="drawing-expanded" src="${esc(S.pdf.image)}" alt="Original drawing page ${S.pdf.page}">`:empty('Select the drawing tab to render the page.')}`);
    else if(S.media==='code')drawer('GENERATED FUSION PYTHON',d.label,code((d.sources[S.sourceIndex]||d.sources.at(-1))?.content||'No source yet.'));
    else drawer('RETAINED CAD PREVIEW',d.label,d.preview?`<img class="drawer-media" src="${esc(d.preview)}" alt="${esc(d.label)}">`:empty('No CAD preview yet.'));
  }else if(action==='worker'){
    drawer('LOCAL FUSION WORKER','Fusion worker',`<p class="drawer-copy">${esc(S.data.worker.label)}. The browser follows job events while the local Fusion worker generates and verifies the plan.</p><p class="small-note">Fusion needs an unlocked, dedicated desktop during verification. The Live Fusion tab uses the companion window feed when available, with viewport snapshots as fallback.</p><div class="drawer-links"><button class="primary" data-action="check-worker">Check Fusion connection</button></div><div id="worker-result"></div>`);
  }else if(action==='check-worker'){
    b.disabled=true;b.textContent='Checking…';try{const r=await api('/api/worker/check',{method:'POST',body:'{}'});$('#worker-result').textContent=r.label;await refresh();}catch(e){notify(e.message);}finally{b.disabled=false;b.textContent='Check Fusion connection';}
  }else if(action==='start-job'){
    b.disabled=true;b.textContent='Connecting to Fusion…';
    try{const r=await api('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:S.intake.id})});$('#upload-dialog').close();notify('Fusion job started. Follow its actual progress in the workspace.');await refresh();await selectPart(r.job,true);}
    catch(e){$('#upload-result').insertAdjacentHTML('beforeend',`<div class="error-box">${esc(e.message)}</div>`);b.disabled=false;b.textContent='Start in Fusion →';}
  }
});
$('#part-select').addEventListener('change',e=>selectPart(e.target.value));
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
await refresh(true);
setInterval(()=>refresh(false),5000);
