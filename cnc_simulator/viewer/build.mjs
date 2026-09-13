import {mkdir, copyFile} from 'node:fs/promises';
await mkdir('dist/vendor', {recursive:true});
for (const [source, destination] of [
 ['three/build/three.module.js','three.module.js'],
 ['three/build/three.core.js','three.core.js'],
 ['three/examples/jsm/controls/OrbitControls.js','OrbitControls.js'],
 ['three/examples/jsm/loaders/PLYLoader.js','PLYLoader.js'],
 ['three/examples/jsm/objects/MarchingCubes.js','MarchingCubes.js'],
 ['three/examples/jsm/environments/RoomEnvironment.js','RoomEnvironment.js'],
]) await copyFile(`node_modules/${source}`,`dist/vendor/${destination}`);
console.log('Local viewer assets ready.');
