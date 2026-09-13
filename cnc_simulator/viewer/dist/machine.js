import * as THREE from 'three';

// One-time exported native geometry, expressed in millimetres. No Fusion runtime.
export function createMachineReference(bundle){
 const root=new THREE.Group();root.name='Downloaded Haas VF-2';
 const groups=new Map(),materials=new Set();
 function mesh(record){
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(record.positions,3));geometry.setIndex(record.indices);geometry.computeVertexNormals();
  const props=record.appearance.colors,c=props.opaque_albedo||props.metal_f0||props.transparent_color||[.6,.63,.65];
  const material=new THREE.MeshStandardMaterial({color:new THREE.Color().setRGB(...c,THREE.SRGBColorSpace),metalness:props.metal_f0 ? .6 : .12,roughness:.42,transparent:!!props.transparent_color,opacity:props.transparent_color ? .35 : 1,side:THREE.DoubleSide});
  materials.add(material);const object=new THREE.Mesh(geometry,material);object.name=record.path;object.castShadow=true;object.receiveShadow=true;return object;
 }
 for(const record of bundle.machine.meshes){if(!groups.has(record.group)){const g=new THREE.Group();g.name=record.group;groups.set(record.group,g);root.add(g);}groups.get(record.group).add(mesh(record));}
 const fixture=new THREE.Group();fixture.name='Prepared Haas vise and parallels';for(const record of bundle.fixture.meshes)fixture.add(mesh(record));root.add(fixture);
 const target=new THREE.Group();target.name='Retained soft-jaw CAD';for(const record of bundle.target.meshes){const object=mesh(record);object.material=new THREE.MeshStandardMaterial({color:0xb7cfd6,metalness:.7,roughness:.35});materials.add(object.material);target.add(object);}root.add(target);
 const toolGroup=new THREE.Group();root.add(toolGroup);
 const translation=bundle.g54_translation_mm,park=bundle.park_g54_mm;
 // The downloaded definition drives table X/Y opposite the programmed work coordinates.
 const tableOffset=[-translation[0]-park[0],-translation[1]-park[1],0];
 groups.get('X-Axis:1').position.set(tableOffset[0],tableOffset[1],0);
 groups.get('Y-Axis:1').position.set(0,tableOffset[1],0);
 fixture.position.set(translation[0]+tableOffset[0],translation[1]+tableOffset[1],translation[2]);target.position.copy(fixture.position);
 let pose;
 function addCylinder(r0,r1,height,z,material){const m=new THREE.Mesh(new THREE.CylinderGeometry(r1,r0,height,48),material);m.rotation.x=Math.PI/2;m.position.z=z+height/2;m.castShadow=true;toolGroup.add(m);}
 function selectTool(number){
  for(const object of [...toolGroup.children]){object.geometry.dispose();toolGroup.remove(object);}
  const t=bundle.tools.find(t=>t.number===number);if(!t)throw Error('Unknown reference tool');
  const cutter=new THREE.MeshStandardMaterial({color:0xc7c8b0,metalness:.8,roughness:.25}),holder=new THREE.MeshStandardMaterial({color:0x424a51,metalness:.7,roughness:.3});materials.add(cutter);materials.add(holder);
  addCylinder(t.diameter_mm/2,t.diameter_mm/2,t.flute_length_mm,0,cutter);
  addCylinder(t.shaft_diameter_mm/2,t.shaft_diameter_mm/2,t.stickout_mm-t.flute_length_mm,t.flute_length_mm,cutter);
  let z=t.stickout_mm;for(const segment of t.holder_segments){addCylinder(segment.lower_diameter/2,segment.upper_diameter/2,segment.height,z,holder);z+=segment.height;}
  const tipZ=translation[2]+park[2];const zTravel=tipZ+t.gauge_length_mm-610;
  if(zTravel < -508 || zTravel > 0 || Math.abs(tableOffset[0])>381 || Math.abs(tableOffset[1])>203)throw Error('Reference pose exceeds downloaded machine travel');
  groups.get('Z-Axis:1').position.z=zTravel;groups.get('Spindle:1').position.z=zTravel;toolGroup.position.set(0,0,tipZ);
  pose={tool:t,axis:{x:-tableOffset[0],y:-tableOffset[1],z:zTravel},tip:[0,0,tipZ]};return pose;
 }
 selectTool(bundle.tools[0].number);
 function enclosure(visible){groups.get('Static:1').children.forEach(o=>{if(o.name.endsWith('/Body2'))o.visible=visible;});}
 return {root,bundle,selectTool,enclosure,get pose(){return pose;},dispose(){root.traverse(o=>o.geometry?.dispose());for(const m of materials)m.dispose();}};
}
