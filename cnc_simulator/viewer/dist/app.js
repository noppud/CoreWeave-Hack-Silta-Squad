import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {PLYLoader} from 'three/addons/loaders/PLYLoader.js';
import {createMachineReference} from './machine.js';
const $=id=>document.getElementById(id);
const fmt=n=>Number.isFinite(n)?n.toFixed(2):'—';
let reference=null,referencePromise=null,referenceMode=null;
let runs=[],currentRun=null,selected=-1,data=null,initial=null,removal=null,time=0,playing=false,lastStock=-1,token=0,follow=true;
let stockMesh=null,toolGroup=null,targetMesh=null,fixtureGroup=null,pathGroup=null,machineGroup=null,activeTool=null;
const error=e=>{$('error').hidden=false;$('error').textContent=String(e.message||e);};
window.addEventListener('error',e=>error(e.error||e.message));
window.addEventListener('unhandledrejection',e=>error(e.reason));
const response=async url=>{const r=await fetch(url);if(!r.ok)throw Error(`Could not load ${url} (${r.status})`);return r;};
const json=async url=>(await response(url)).json();
const renderer=new THREE.WebGLRenderer({canvas:$('scene'),antialias:true,alpha:false});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0x151b1e);renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
const scene=new THREE.Scene();scene.fog=new THREE.Fog(0x151b1e,100,220);
const camera=new THREE.PerspectiveCamera(40,1,.05,500);camera.up.set(0,0,1);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.08;controls.maxPolarAngle=Math.PI*.49;
scene.add(new THREE.HemisphereLight(0xdaefff,0x3b4a47,2.3));
const light=new THREE.DirectionalLight(0xfff4e6,4);light.position.set(15,-20,45);light.castShadow=true;light.shadow.mapSize.set(2048,2048);
Object.assign(light.shadow.camera,{left:-35,right:45,top:40,bottom:-35,near:.1,far:110});light.shadow.normalBias=.04;light.shadow.camera.updateProjectionMatrix();scene.add(light);
const fill=new THREE.DirectionalLight(0x76becd,1.2);fill.position.set(-30,20,25);scene.add(fill);
const stockMaterial=new THREE.MeshStandardMaterial({vertexColors:true,metalness:.63,roughness:.38});
const machineMaterial=new THREE.MeshStandardMaterial({color:0x35434a,metalness:.55,roughness:.5});
const tableMaterial=new THREE.MeshStandardMaterial({color:0x65747b,metalness:.7,roughness:.42});
const darkMaterial=new THREE.MeshStandardMaterial({color:0x18232a,metalness:.55,roughness:.34});
const cutterMaterial=new THREE.MeshStandardMaterial({color:0xd6e1df,metalness:.85,roughness:.26});
const accentMaterial=new THREE.MeshStandardMaterial({color:0x68b59c,metalness:.5,roughness:.36});
const resizer=new ResizeObserver(()=>{const b=$('canvas-wrap').getBoundingClientRect();renderer.setSize(b.width,b.height,false);camera.aspect=b.width/b.height;camera.updateProjectionMatrix();});resizer.observe($('canvas-wrap'));
function clear(group){if(group){scene.remove(group);group.traverse(o=>{if(o.geometry)o.geometry.dispose();});}return null;}
function box(group,size,position,material){const m=new THREE.Mesh(new THREE.BoxGeometry(...size),material);m.position.set(...position);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
function cylinder(group,radius,length,z,material){const m=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,length,48),material);m.rotation.x=Math.PI/2;m.position.z=z+length/2;m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
function buildMachine(){
 machineGroup=clear(machineGroup);machineGroup=new THREE.Group();const [lo,hi]=data.stock_bounds,w=hi[0]-lo[0],d=hi[1]-lo[1],x=(lo[0]+hi[0])/2,y=(lo[1]+hi[1])/2;
 box(machineGroup,[w*2.6,d*2.3,1.2],[x,y,lo[2]-.9],tableMaterial);
 for(let j=-3;j<=3;j++)box(machineGroup,[w*2.5,.13,.025],[x,y+j*d*.28,lo[2]-.285],darkMaterial);
 box(machineGroup,[w*2.8,d*2.45,1.4],[x,y,lo[2]-2.2],machineMaterial);
 box(machineGroup,[w*.7,3,30],[x,y+d*1.7,lo[2]+12],machineMaterial);
 box(machineGroup,[w*.5,d*1.2,2],[x,y+d*.9,lo[2]+27],machineMaterial);
 // Schematic rigid machine geometry is context, not a collision model.
 const floor=new THREE.Mesh(new THREE.PlaneGeometry(300,300),new THREE.MeshStandardMaterial({color:0x182024,roughness:.9}));floor.position.set(x,y,lo[2]-3);floor.receiveShadow=true;machineGroup.add(floor);
 scene.add(machineGroup);
}
function buildTool(id){toolGroup=clear(toolGroup);toolGroup=new THREE.Group();const t=data.plan.tools[id];let z=0;
 const cutter=cylinder(toolGroup,t.diameter_mm/2,t.flute_length_mm,z,cutterMaterial);cutter.name='cutter';z+=t.flute_length_mm;
 // Thin flute accents illustrate rotation; cutting is computed by the simulator's cylinder.
 for(let n=0;n<3;n++){const pts=[];for(let j=0;j<=40;j++){let zz=j/40*t.flute_length_mm,a=zz/t.flute_length_mm*2.4+n*Math.PI*2/3;pts.push(new THREE.Vector3(Math.cos(a)*t.diameter_mm*.503,Math.sin(a)*t.diameter_mm*.503,zz));}const groove=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineBasicMaterial({color:0x52645f}));groove.name='flute';toolGroup.add(groove);}
 cylinder(toolGroup,t.shaft_diameter_mm/2,t.shaft_length_mm,z,cutterMaterial);z+=t.shaft_length_mm;
 cylinder(toolGroup,t.holder_diameter_mm/2,t.holder_length_mm,z,darkMaterial);z+=t.holder_length_mm;
 cylinder(toolGroup,t.holder_diameter_mm*.56,.45,z-.45,accentMaterial);
 box(toolGroup,[6.5,6.5,6],[0,0,z+3],machineMaterial);cylinder(toolGroup,2.5,1,z,darkMaterial);
 scene.add(toolGroup);activeTool=id;
}
function fit(machine=false){if(!data)return;const [lo,hi]=data.stock_bounds,x=(lo[0]+hi[0])/2,y=(lo[1]+hi[1])/2,w=Math.max(hi[0]-lo[0],hi[1]-lo[1]);controls.target.set(x,y,machine?10:4);camera.position.set(x+w*(machine?2.7:1.5),y-w*(machine?3.3:1.9),w*(machine?3.3:1.9));controls.update();$('close-view').classList.toggle('active',!machine);$('machine-view').classList.toggle('active',machine);}
const faces=[[[0,0,0],[0,0,1],[0,1,1],[0,1,0]],[[1,0,0],[1,1,0],[1,1,1],[1,0,1]],[[0,0,0],[1,0,0],[1,0,1],[0,0,1]],[[0,1,0],[0,1,1],[1,1,1],[1,1,0]],[[0,0,0],[0,1,0],[1,1,0],[1,0,0]],[[0,0,1],[1,0,1],[1,1,1],[0,1,1]]];
const normals=[[-1,0,0],[1,0,0],[0,-1,0],[0,1,0],[0,0,-1],[0,0,1]],tri=[0,1,2,0,2,3];
function rebuildStock(){
 if(!data||!initial)return;const [nx,ny,nz]=data.shape,origin=data.origin,p=data.pitch,vertices=[],ns=[],colors=[];
 const present=i=>i>=0&&i<initial.length&&initial[i]&&removal[i]>time+1e-5;
 const offsets=[-ny*nz,ny*nz,-nz,nz,-1,1];
 for(let x=0;x<nx;x++)for(let y=0;y<ny;y++)for(let z=0;z<nz;z++){
  const i=(x*ny+y)*nz+z;if(!present(i))continue;
  const edges=[x===0,x===nx-1,y===0,y===ny-1,z===0,z===nz-1];
  for(let face=0;face<6;face++){let neighbor=i+offsets[face];if(!edges[face]&&present(neighbor))continue;
   let fresh=!edges[face]&&initial[neighbor]&&Number.isFinite(removal[neighbor])&&removal[neighbor]<=time+1e-5;
   const color=fresh?[.64,.83,.77]:[.56,.64,.67];
   for(const k of tri){const c=faces[face][k];vertices.push(origin[0]+(x+c[0])*p,origin[1]+(y+c[1])*p,origin[2]+(z+c[2])*p);ns.push(...normals[face]);colors.push(...color);}
  }
 }
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setAttribute('normal',new THREE.Float32BufferAttribute(ns,3));g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
 if(!stockMesh){stockMesh=new THREE.Mesh(g,stockMaterial);stockMesh.castShadow=true;stockMesh.receiveShadow=true;scene.add(stockMesh);}else{stockMesh.geometry.dispose();stockMesh.geometry=g;}
 lastStock=time;
}
function pose(){if(!data)return;let prev=data.trajectory[0],row=prev;for(let i=1;i<data.trajectory.length;i++){row=data.trajectory[i];if(time<=row.elapsed_seconds)break;prev=row;}
 const dt=row.elapsed_seconds-prev.elapsed_seconds,f=dt>0?Math.max(0,Math.min(1,(time-prev.elapsed_seconds)/dt)):1;
 const pos=row.position.map((v,i)=>row.from[i]+(v-row.from[i])*f);
 if(activeTool!==row.tool)buildTool(row.tool);toolGroup.position.set(...pos);
 toolGroup.children.filter(x=>x.name==='flute').forEach(x=>x.rotation.z=row.type==='cut'?time*14:0);
 $('xyz').textContent=`X ${pos[0].toFixed(2)}  Y ${pos[1].toFixed(2)}  Z ${pos[2].toFixed(2)}`;
 $('motion').textContent=time===0?'Ready':`${row.type.replaceAll('_',' ')} · move ${row.move+1}`;
 $('tool-label').textContent=`${row.tool} · Ø${data.plan.tools[row.tool].diameter_mm} mm`;
 $('clock').textContent=`${time.toFixed(2)} / ${fmt(data.result.estimated_time_seconds)} s`;$('timeline').value=time;
}
function metrics(row){const r=row?.result;$('verdict').className='verdict '+(r?.validity||'');$('verdict').textContent=r?.validity?{valid:'Pass',invalid:'Fail',unknown:'Fail'}[r.validity]:'Planning';
 $('verdict-note').textContent=r?.validity==='valid'?'Geometry and collision checks passed.':r?.validity==='invalid'?'Excluded from time optimization.':r?.validity==='unknown'?'Failed: could not establish geometry and clearance.':'Waiting for an authoritative result.';
 $('seconds').textContent=fmt(r?.estimated_time_seconds);$('breakdown').replaceChildren();
 for(const [key,val] of Object.entries(r?.time_breakdown||{})){const outer=document.createElement('div');outer.className='bar-row';const label=document.createElement('div');label.className='bar-label';const name=document.createElement('span');name.textContent=key.replaceAll('_',' ');const v=document.createElement('span');v.textContent=fmt(val)+' s';label.append(name,v);const track=document.createElement('div');track.className='bar-track';const bar=document.createElement('div');bar.className='bar-fill';bar.style.width=`${Math.max(0,Math.min(100,100*val/(r.estimated_time_seconds||1)))}%`;track.append(bar);outer.append(label,track);$('breakdown').append(outer);}
 $('feedback').replaceChildren();for(const issue of r?.issues||[]){const el=document.createElement('div');el.className='feedback-item';el.textContent=issue.description||String(issue);const loc=document.createElement('small');loc.textContent=(issue.moves?.length?`Moves ${issue.moves.map(m=>m+1).join(', ')}`:'Final stock / plan')+(issue.certainty?` · ${issue.certainty}`:'');el.append(loc);$('feedback').append(el);}
 if(r?.validity==='valid'){$('feedback').textContent='No unresolved geometry or collision issues.';}
}
async function loadAttempt(index){leaveReference();selected=index;playing=false;$('play').textContent='▶ Play';const run=runs.find(r=>r.id===currentRun),row=run?.attempts[index];metrics(row);renderRun();const mine=++token;
 data=null;initial=null;removal=null;$('play').disabled=true;stockMesh=clear(stockMesh);toolGroup=clear(toolGroup);targetMesh=clear(targetMesh);pathGroup=clear(pathGroup);fixtureGroup=clear(fixtureGroup);machineGroup=clear(machineGroup);
 if(!row?.playback){$('empty').textContent=row?.stage==='check_failed'?'Rejected by cheap checks before simulation.':'Waiting for simulation output…';return;}
 $('empty').textContent='Loading simulated stock…';const base=`/runs/${encodeURIComponent(currentRun)}/${row.playback.replace('playback.json','')}`;
 try{const meta=await json(base+'playback.json');if(mine!==token)return;if(meta.shape.reduce((a,b)=>a*b,1)>2000000)throw Error('Playback grid is too large for this viewer.');
 const [a,b,target]=await Promise.all([response(base+'initial.bin').then(r=>r.arrayBuffer()),response(base+'removal.bin').then(r=>r.arrayBuffer()),new PLYLoader().loadAsync(base+'target.ply')]);if(mine!==token){target.dispose();return;}
 data=meta;initial=new Uint8Array(a);removal=new Float32Array(b);if(initial.length!==meta.shape.reduce((a,b)=>a*b,1)||removal.length!==initial.length)throw Error('Incomplete stock animation data.');
 time=0;lastStock=-1;activeTool=null;buildMachine();buildTool(data.plan.initial_tool);fit();rebuildStock();
 targetMesh=new THREE.LineSegments(new THREE.EdgesGeometry(target,15),new THREE.LineBasicMaterial({color:0x9be7cf,transparent:true,opacity:.65,depthTest:false}));target.dispose();targetMesh.visible=$('target-toggle').getAttribute('aria-pressed')==='true';scene.add(targetMesh);
 pathGroup=new THREE.Group();for(const row of data.trajectory){if(!['cut','rapid'].includes(row.type))continue;const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...row.from),new THREE.Vector3(...row.position)]),new THREE.LineBasicMaterial({color:row.type==='rapid'?0xecae75:0x9be7cf,transparent:true,opacity:.5,depthTest:false}));pathGroup.add(line);}scene.add(pathGroup);
 fixtureGroup=new THREE.Group();scene.add(fixtureGroup);for(const file of data.fixtures){const g=await new PLYLoader().loadAsync(base+file);if(mine!==token){g.dispose();return;}const mesh=new THREE.Mesh(g,tableMaterial);mesh.castShadow=true;fixtureGroup.add(mesh);}
 $('timeline').max=data.result.estimated_time_seconds;$('timeline').value=0;$('play').disabled=false;$('empty').textContent='';pose();
 }catch(e){if(mine===token){$('empty').textContent='Playback unavailable';error(e);}}
}
function renderRun(){if(referenceMode)return;const run=runs.find(r=>r.id===currentRun);if(!run)return;$('mode').textContent=run.mode==='astra'?'GPT-6 Astra · live run':'Scripted rehearsal · no model';$('run-status').textContent=run.status==='incomplete'?run.reason:run.stage.replaceAll('supervisor','timing judge').replaceAll('_',' ');$('part-title').textContent=`${run.job_id||'Part'} · machining`;$('attempt-count').textContent=run.attempts.length;$('best').textContent=run.best?`${fmt(run.best.seconds)} s · #${run.best.attempt+1}`:'None yet';$('attempts').replaceChildren();
 for(const row of run.attempts){const el=document.createElement('button');el.className='attempt'+(selected===row.index?' active':'');const top=document.createElement('div');top.className='attempt-top';const title=document.createElement('span');title.textContent=`${String(row.index+1).padStart(2,'0')}  ${row.source==='supplied_seed'?'Starting plan':'CAM revision'}`;const status=document.createElement('span');status.className=row.result?.validity||'';status.textContent=row.result?.estimated_time_seconds!=null?fmt(row.result.estimated_time_seconds)+' s':row.result?.validity||row.stage;top.append(title,status);const p=document.createElement('p');p.textContent=row.summary||'Astra is preparing this candidate.';el.append(top,p);el.onclick=()=>{follow=false;loadAttempt(row.index);};$('attempts').append(el);}
 const knowledge=run.final_knowledge||run.loaded_knowledge;$('knowledge').textContent=knowledge?`Knowledge version ${knowledge.version}`:'No evaluated learning yet';$('learning').replaceChildren();const loaded=run.loaded_knowledge;
 if(loaded?.version){const p=document.createElement('p');p.textContent=`Loaded version ${loaded.version} from earlier runs. ${loaded.rules.length} saved check(s).`;$('learning').append(p);}
 for(const item of run.learning){const p=document.createElement('p');p.className=item.evaluation.promoted?'promoted':'';p.textContent=`${item.evaluation.kind||'Check'} ${item.evaluation.promoted?'promoted after evaluation':'not promoted'}${item.evaluation.newly_caught_failures!=null?` · ${item.evaluation.newly_caught_failures} failures caught, ${item.evaluation.false_rejections} false rejections`:''}`;$('learning').append(p);}
 if(!run.learning.length&&!loaded?.version){$('learning').textContent='Check and planning changes must pass evaluation before reuse.';}
}
async function refresh(){if(referenceMode)return;try{const latest=await json('/api/runs');runs=latest;const previous=currentRun;$('runs').replaceChildren();for(const run of runs){const o=document.createElement('option');o.value=run.id;o.textContent=`${run.job_id||run.id} · ${run.mode} · ${run.status}`;$('runs').append(o);}if(!runs.length){$('empty').textContent='No simulations yet. Choose Part A and run Astra.';return;}
 if(!currentRun||!runs.some(r=>r.id===currentRun))currentRun=runs[0].id;$('runs').value=currentRun;renderRun();const r=runs.find(r=>r.id===currentRun);const next=r.attempts.length-1;if(previous!==currentRun||(follow&&next!==selected)){await loadAttempt(next);}else if(selected>=0&&r.attempts[selected]?.playback&&!data){await loadAttempt(selected);}
 }catch(e){error(e);}}
$('runs').onchange=()=>{currentRun=$('runs').value;selected=-1;follow=true;refresh();};
$('play').onclick=()=>{if(!data)return;if(time>=data.result.estimated_time_seconds)time=0;playing=!playing;$('play').textContent=playing?'Ⅱ Pause':'▶ Play';};
$('reset').onclick=()=>{time=0;playing=false;lastStock=-1;$('play').textContent='▶ Play';pose();rebuildStock();};
$('timeline').oninput=()=>{time=+$('timeline').value;playing=false;$('play').textContent='▶ Play';pose();rebuildStock();};
$('close-view').onclick=()=>{leaveReference();renderRun();metrics(runs.find(r=>r.id===currentRun)?.attempts[selected]);fit(false);};
$('machine-view').onclick=()=>showReference('machine');$('setup-view').onclick=()=>showReference('setup');
$('reference-tool').onchange=()=>{if(reference){reference.selectTool(+$('reference-tool').value);showReference(referenceMode);}};
$('target-toggle').onclick=()=>{if(referenceMode)return;const on=$('target-toggle').getAttribute('aria-pressed')!=='true';$('target-toggle').setAttribute('aria-pressed',String(on));$('target-toggle').classList.toggle('active',on);if(targetMesh)targetMesh.visible=on;};
$('start').onclick=async()=>{try{$('start').disabled=true;$('error').hidden=true;const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job:$('job').value})});const result=await r.json();if(!r.ok)throw Error(result.error);currentRun=result.id;follow=true;selected=-1;setTimeout(refresh,500);}catch(e){error(e);}finally{$('start').disabled=false;}};
let last=performance.now();function frame(now){requestAnimationFrame(frame);const dt=Math.min((now-last)/1000,.1);last=now;if(playing&&data){time=Math.min(time+dt*+$('speed').value,data.result.estimated_time_seconds);if(time>=data.result.estimated_time_seconds){playing=false;$('play').textContent='▶ Play';}pose();if(Math.abs(time-lastStock)>.06||time===data.result.estimated_time_seconds)rebuildStock();}controls.update();renderer.render(scene,camera);}camera.position.set(25,-25,25);controls.target.set(6,5,4);requestAnimationFrame(frame);await refresh();setInterval(refresh,2500);
// Optional imperative access to the same inspection/playback controls.
if(document.modelContext?.registerTool){
 const lifecycle=new AbortController();window.addEventListener('pagehide',()=>lifecycle.abort(),{once:true});
 for(const tool of [
  {name:'inspect_machining_run',title:'Inspect machining run',description:'Read the selected run, simulator verdicts and best valid time. Does not launch a model.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute:()=>{const r=runs.find(r=>r.id===currentRun);return r?{id:r.id,mode:r.mode,status:r.status,best:r.best,attempts:r.attempts.map(a=>({index:a.index,result:a.result}))}:{status:'no_runs'};}},
  {name:'view_machining_attempt',title:'View machining attempt',description:'Select a completed attempt in the current run and seek its simulation playback. Does not launch a model.',inputSchema:{type:'object',properties:{attempt:{type:'integer',minimum:0},seconds:{type:'number',minimum:0}},required:['attempt','seconds'],additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:true},async execute(input){const r=runs.find(r=>r.id===currentRun);if(!Number.isInteger(input.attempt)||!r?.attempts[input.attempt]?.playback||!Number.isFinite(input.seconds)||input.seconds<0)throw Error('A simulated attempt and nonnegative time are required');follow=false;await loadAttempt(input.attempt);if(!data)throw Error('Playback unavailable');time=Math.min(input.seconds,data.result.estimated_time_seconds);pose();rebuildStock();return {run:currentRun,attempt:selected,seconds:time,validity:data.result.validity};}}
 ]){try{Promise.resolve(document.modelContext.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});}catch{ /* Ordinary browser controls remain available. */ }}
}

function leaveReference(){
 if(!referenceMode)return;referenceMode=null;if(reference)reference.root.visible=false;
 for(const group of [stockMesh,toolGroup,fixtureGroup,pathGroup,machineGroup])if(group)group.visible=true;
 if(targetMesh)targetMesh.visible=$('target-toggle').getAttribute('aria-pressed')==='true';
 $('reference-tool').hidden=true;$('setup-view').classList.remove('active');
 $('play').disabled=!data;$('timeline').disabled=false;$('speed').disabled=false;$('reset').disabled=false;
 $('target-toggle').disabled=false;document.querySelector('.scene-note').textContent='Nominal simulated stock · pocket test';
 camera.near=.05;camera.far=500;camera.updateProjectionMatrix();scene.fog.near=100;scene.fog.far=220;
 Object.assign(light.shadow.camera,{left:-35,right:45,top:40,bottom:-35,near:.1,far:110});light.shadow.camera.updateProjectionMatrix();
 light.position.set(15,-20,45);light.target.position.set(0,0,0);light.shadow.normalBias=.04;fill.position.set(-30,20,25);
}
async function showReference(mode){
 try{
  playing=false;$('play').textContent='▶ Play';referenceMode=mode;
  for(const group of [stockMesh,toolGroup,targetMesh,fixtureGroup,pathGroup,machineGroup])if(group)group.visible=false;
  $('empty').textContent='Loading downloaded Haas VF-2…';
  if(!referencePromise)referencePromise=json('/assets/haas-vf2.json').then(bundle=>{reference=createMachineReference(bundle);scene.add(reference.root);return reference;});
  await referencePromise;if(referenceMode!==mode)return;reference.root.visible=true;reference.enclosure(mode==='machine');
  $('empty').textContent='';$('reference-tool').hidden=false;
  $('play').disabled=true;$('timeline').disabled=true;$('speed').disabled=true;$('reset').disabled=true;$('target-toggle').disabled=true;
  $('close-view').classList.remove('active');$('machine-view').classList.toggle('active',mode==='machine');$('setup-view').classList.toggle('active',mode==='setup');
  camera.near=.5;camera.far=16000;camera.updateProjectionMatrix();scene.fog.near=8000;scene.fog.far=16000;
  if(mode==='machine'){controls.target.set(0,0,450);const distance=1800/Math.sin(Math.atan(Math.tan(camera.fov*Math.PI/360)*Math.min(camera.aspect,1)));camera.position.copy(controls.target).add(new THREE.Vector3(2900,-3900,1950).normalize().multiplyScalar(distance));}else{camera.position.set(500,-650,600);controls.target.set(0,0,110);}controls.update();
  light.position.set(800,-1400,2900);light.target.position.set(0,0,300);scene.add(light.target);fill.position.set(-1200,700,1900);
  Object.assign(light.shadow.camera,{left:-1600,right:1600,top:2000,bottom:-1400,near:10,far:6500});light.shadow.camera.updateProjectionMatrix();light.shadow.normalBias=.6;
  $('part-title').textContent=mode==='machine'?'Downloaded Haas VF-2':'Prepared vise, soft jaw & tools';
  document.querySelector('.scene-note').textContent='Actual exported assets · parked reference setup';
  $('motion').textContent='Reference pose · no machining playback';
  const p=reference.pose;$('xyz').textContent=`X ${p.axis.x.toFixed(2)} Y ${p.axis.y.toFixed(2)} Z ${p.axis.z.toFixed(2)}`;
  $('tool-label').textContent=`T${p.tool.number} · Ø${p.tool.diameter_mm.toFixed(2)} mm`;
  $('verdict').className='verdict';$('verdict').textContent='Reference';$('verdict-note').textContent='These assets are not covered by the pocket-demo collision verdict.';
  $('seconds').textContent='—';$('best').textContent='Reference setup';$('breakdown').replaceChildren();$('feedback').replaceChildren();
  for(const text of ['Haas VF-2 · 11 native machine bodies','Prepared vise and parallels · 19 bodies','Retained soft-jaw CAD · original millimetre scale',`T${p.tool.number}: ${p.tool.product_id} · ${p.tool.holder_description}`,`Gauge length ${p.tool.gauge_length_mm.toFixed(2)} mm · flute ${p.tool.flute_length_mm.toFixed(2)} mm`,'Machine, vise and library source hashes match the project configuration.']){const item=document.createElement('div');item.className='feedback-item';item.textContent=text;$('feedback').append(item);}
 }catch(e){$('empty').textContent='Machine asset loading failed';error(e);}
}

async function loadJobs(){try{const jobs=await json('/api/jobs');const select=document.querySelector('select#job');if(!select)return;select.replaceChildren();for(const job of jobs){const option=document.createElement('option');option.value=job.id;option.textContent=job.id;select.append(option);}}catch(e){error(e);}}
loadJobs();
