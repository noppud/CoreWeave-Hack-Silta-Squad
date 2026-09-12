import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const scope = vm.createContext({setTimeout, clearTimeout, cancelAnimationFrame() {}});
vm.runInContext(readFileSync('silta/static/three.min.js', 'utf8'), scope);
const source = readFileSync('silta/static/viewer.js', 'utf8');
vm.runInContext(source.slice(source.indexOf('class OrbitController'), source.indexOf('function createTargetMesh')) + '\nthis.Controller = OrbitController;', scope);

class Canvas extends EventTarget {
  captured = new Set();
  setPointerCapture(id) { this.captured.add(id); }
  hasPointerCapture(id) { return this.captured.has(id); }
  releasePointerCapture(id) { this.captured.delete(id); }
  send(type, values) { const e = new Event(type, {cancelable:true}); Object.assign(e, values); this.dispatchEvent(e); }
}

test('paused orbit, pinch, Python preset and cleanup preserve the CAD frame', () => {
  const canvas = new Canvas(), camera = new scope.THREE.PerspectiveCamera();
  let renders = 0;
  const controller = new scope.Controller(camera, canvas, () => renders++, () => {});
  controller.focusOn(new scope.THREE.Vector3(40, 30, -10), 80);
  const center = controller.target.clone();
  canvas.send('pointerdown', {pointerId:1, clientX:0, clientY:0});
  canvas.send('pointermove', {pointerId:1, clientX:20, clientY:10});
  assert.ok(renders > 1, 'orbit must redraw even while playback is paused');
  assert.ok(controller.target.equals(center));
  const radius = controller.spherical.radius;
  canvas.send('pointerdown', {pointerId:2, clientX:40, clientY:10});
  canvas.send('pointermove', {pointerId:2, clientX:60, clientY:10});
  assert.ok(controller.spherical.radius < radius, 'spreading fingers zooms in');
  canvas.send('pointercancel', {pointerId:1});
  canvas.send('pointerup', {pointerId:2});
  assert.equal(controller.pointers.size, 0);
  controller.preset('top');
  assert.equal(controller.spherical.phi, 0.01);
  assert.ok(camera.up.equals(new scope.THREE.Vector3(0, 0, 1)));
  canvas.send('keydown', {key:'r'});
  assert.equal(controller.spherical.theta, Math.PI / 4);
  controller.dispose();
  const lastRenders = renders;
  canvas.send('keydown', {key:'ArrowLeft'});
  assert.equal(renders, lastRenders, 'disposed widgets must release input handlers');
});
