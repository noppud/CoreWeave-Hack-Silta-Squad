/**
 * Silta CNC Viewer - Three.js ESM module for anywidget
 *
 * Loads vendored Three.js and renders CNC machining workbench.
 * Python owns authoritative data; browser owns camera, time and interaction.
 */

let THREE = null;
let threeLoading = null;

// The vendored Three.js UMD bundle is prepended to this module as
// `__SILTA_THREE_SRC` by silta/viewer.py, so the widget never fetches it over the
// network and never depends on how the host serves widget assets.
async function loadThree() {
  if (THREE) return THREE;
  if (threeLoading) return threeLoading;

  threeLoading = (async () => {
    if (globalThis.THREE) {
      THREE = globalThis.THREE;
      return THREE;
    }
    if (typeof __SILTA_THREE_SRC !== 'string' || !__SILTA_THREE_SRC.length) {
      throw new Error('Silta viewer: vendored Three.js source was not injected.');
    }
    // Indirect eval runs the UMD bundle in global, non-strict scope, which is what
    // its `(this)` factory argument needs. A bare `import()` of a UMD file would not
    // produce a module namespace.
    (0, eval)(__SILTA_THREE_SRC);
    THREE = globalThis.THREE;
    if (!THREE) throw new Error('Silta viewer: Three.js did not register a global.');
    return THREE;
  })();

  return threeLoading;
}

class OrbitController {
  constructor(camera, canvas, onChange, onCommit) {
    this.camera = camera;
    this.canvas = canvas;
    this.onChange = onChange;
    this.onCommit = onCommit;
    this.target = new THREE.Vector3();
    this.spherical = { radius: 10, theta: Math.PI / 4, phi: Math.PI * 0.30 };
    this.defaultSpherical = { ...this.spherical };
    this.defaultTarget = this.target.clone();
    this.pointers = new Map();
    this.disposed = false;
    this.focusAnimation = null;
    this.handlers = {
      pointerdown: e => {
        this.pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
        canvas.setPointerCapture(e.pointerId);
      },
      pointermove: e => {
        const previous = this.pointers.get(e.pointerId);
        if (!previous) return;
        const next = {x: e.clientX, y: e.clientY};
        if (this.pointers.size === 2) {
          const other = [...this.pointers.entries()].find(([id]) => id !== e.pointerId)[1];
          const before = Math.hypot(previous.x - other.x, previous.y - other.y);
          const after = Math.hypot(next.x - other.x, next.y - other.y);
          if (after > 2) this.spherical.radius *= before / after;
        } else {
          this.spherical.theta -= (next.x - previous.x) * 0.01;
          this.spherical.phi -= (next.y - previous.y) * 0.01;
        }
        this.pointers.set(e.pointerId, next);
        this.update();
      },
      pointerup: e => this.endPointer(e),
      pointercancel: e => this.endPointer(e),
      lostpointercapture: e => this.endPointer(e),
      wheel: e => {
        e.preventDefault();
        this.zoom(Math.exp(e.deltaY * 0.001));
        clearTimeout(this.wheelTimer);
        this.wheelTimer = setTimeout(() => this.commit(), 150);
      },
      keydown: e => {
        const steps = {ArrowLeft: [-0.12, 0], ArrowRight: [0.12, 0],
          ArrowUp: [0, -0.12], ArrowDown: [0, 0.12]};
        if (steps[e.key]) {
          e.preventDefault();
          this.spherical.theta += steps[e.key][0];
          this.spherical.phi += steps[e.key][1];
          this.update(); this.commit();
        } else if (e.key === '+' || e.key === '=') { e.preventDefault(); this.zoom(0.85); this.commit(); }
        else if (e.key === '-') { e.preventDefault(); this.zoom(1.18); this.commit(); }
        else if (e.key.toLowerCase() === 'r') { e.preventDefault(); this.reset(); }
      }
    };
    for (const [type, handler] of Object.entries(this.handlers)) {
      canvas.addEventListener(type, handler, type === 'wheel' ? {passive: false} : undefined);
    }
  }
  endPointer(e) {
    if (!this.pointers.has(e.pointerId)) return;
    this.pointers.delete(e.pointerId);
    if (this.canvas.hasPointerCapture(e.pointerId)) this.canvas.releasePointerCapture(e.pointerId);
    this.commit();
  }
  commit() {
    if (!this.disposed) this.onCommit({ ...this.spherical, target: this.target.toArray() });
  }
  zoom(factor) { this.spherical.radius *= factor; this.update(); }
  update() {
    if (this.disposed) return;
    this.spherical.radius = Math.max(5, Math.min(800, this.spherical.radius));
    this.spherical.phi = Math.max(0.01, Math.min(Math.PI - 0.01, this.spherical.phi));
    this.camera.up.set(0, 0, 1);
    const {radius, theta, phi} = this.spherical;
    this.camera.position.set(this.target.x + radius * Math.sin(phi) * Math.sin(theta),
      this.target.y + radius * Math.sin(phi) * Math.cos(theta),
      this.target.z + radius * Math.cos(phi));
    this.camera.lookAt(this.target);
    this.onChange();
  }
  focusOn(center, size) {
    this.target.copy(center);
    this.spherical = {radius: size * 1.8, theta: Math.PI / 4, phi: Math.PI * 0.30};
    this.defaultSpherical = {...this.spherical};
    this.defaultTarget = this.target.clone();
    this.update();
  }
  preset(name) {
    const angles = {isometric: [Math.PI / 4, Math.PI * 0.30], top: [0, 0.01],
      front: [Math.PI, Math.PI / 2], side: [Math.PI / 2, Math.PI / 2]};
    if (!angles[name]) return;
    cancelAnimationFrame(this.focusAnimation);
    this.target.copy(this.defaultTarget);
    this.spherical = {...this.defaultSpherical, theta: angles[name][0], phi: angles[name][1]};
    this.update(); this.commit();
  }
  reset() { this.preset('isometric'); }
  easeToPoint(point, duration = 500) {
    cancelAnimationFrame(this.focusAnimation);
    const start = this.target.clone(), time = performance.now();
    const tick = () => {
      if (this.disposed) return;
      const t = Math.min((performance.now() - time) / duration, 1);
      this.target.lerpVectors(start, point, t); this.update();
      if (t < 1) this.focusAnimation = requestAnimationFrame(tick);
      else this.commit();
    };
    tick();
  }
  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.focusAnimation);
    clearTimeout(this.wheelTimer);
    for (const [type, handler] of Object.entries(this.handlers)) this.canvas.removeEventListener(type, handler);
    this.pointers.clear();
  }
}

function createTargetMesh(positions) {
  const geometry = new THREE.BufferGeometry();
  const posArray = new Float32Array(positions);
  geometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
  geometry.computeVertexNormals();

  // The requested shape, shown as a translucent ghost of the goal
  const material = new THREE.MeshStandardMaterial({
    color: 0x5E90B2,
    metalness: 0.2,
    roughness: 0.6,
    transparent: true,
    opacity: 0.4,
  });

  const mesh = new THREE.Mesh(geometry, material);

  // Add edge outline for crisp silhouette
  const edges = new THREE.EdgesGeometry(geometry, 25);
  const edgeMat = new THREE.LineBasicMaterial({ color: 0x6FA3C2, linewidth: 1 });
  const edgeMesh = new THREE.LineSegments(edges, edgeMat);
  mesh.add(edgeMesh);

  return mesh;
}

function createStockHeightfield(frame, stockDims) {
  const { nx, ny, grid_mm, height } = frame;
  const geometry = new THREE.BufferGeometry();

  const vertices = [];
  const indices = [];

  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < ny; j++) {
      const x = (frame.origin_mm ?? grid_mm / 2) + i * grid_mm;
      const y = (frame.origin_mm ?? grid_mm / 2) + j * grid_mm;
      const z = height[i * ny + j];
      vertices.push(x, y, z);
    }
  }

  for (let i = 0; i < nx - 1; i++) {
    for (let j = 0; j < ny - 1; j++) {
      const a = i * ny + j;
      const b = (i + 1) * ny + j;
      const c = (i + 1) * ny + (j + 1);
      const d = i * ny + (j + 1);

      indices.push(a, b, d);
      indices.push(b, c, d);
    }
  }

  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  // Opaque machined-metal surface
  const material = new THREE.MeshStandardMaterial({
    color: 0xC7DCE8,
    metalness: 0.45,
    roughness: 0.35,
  });

  return new THREE.Mesh(geometry, material);
}

function createFixtureBox(fixture) {
  const sx = fixture.x_max - fixture.x_min;
  const sy = fixture.y_max - fixture.y_min;
  const sz = fixture.z_max - fixture.z_min;

  const geometry = new THREE.BoxGeometry(sx, sy, sz);
  // Dark anodised blocks
  const material = new THREE.MeshStandardMaterial({
    color: 0x1B4E70,
    metalness: 0.35,
    roughness: 0.5,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(
    (fixture.x_min + fixture.x_max) / 2,
    (fixture.y_min + fixture.y_max) / 2,
    (fixture.z_min + fixture.z_max) / 2
  );

  // Add visible edge outline
  const edges = new THREE.EdgesGeometry(geometry);
  const edgeMat = new THREE.LineBasicMaterial({ color: 0x6FA3C2, linewidth: 1 });
  const edgeMesh = new THREE.LineSegments(edges, edgeMat);
  mesh.add(edgeMesh);

  return mesh;
}

function createGroundPlane(stockDims) {
  const size = Math.max(stockDims.x_mm, stockDims.y_mm) * 2;
  const geometry = new THREE.PlaneGeometry(size, size);
  const material = new THREE.ShadowMaterial({ opacity: 0.15 });

  const plane = new THREE.Mesh(geometry, material);
  plane.position.set(stockDims.x_mm / 2, stockDims.y_mm / 2, -stockDims.z_mm - 0.1);
  plane.receiveShadow = true;

  return plane;
}

function createGrid(stockDims) {
  const size = Math.max(stockDims.x_mm, stockDims.y_mm) * 1.5;
  const divisions = Math.floor(size / 10);
  const grid = new THREE.GridHelper(size, divisions, 0x24567A, 0x24567A);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(stockDims.x_mm / 2, stockDims.y_mm / 2, -stockDims.z_mm - 0.2);
  grid.material.opacity = 0.3;
  grid.material.transparent = true;

  return grid;
}

function createTrajectoryLines(segments, currentSegmentIndex = -1) {
  const rapidPoints = [];
  const feedPointsCompleted = [];
  const feedPointsPending = [];

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const completed = i <= currentSegmentIndex;
    const points = seg.cutting ? (completed ? feedPointsCompleted : feedPointsPending) : rapidPoints;
    points.push(...seg.start, ...seg.end);
  }

  const group = new THREE.Group();

  // Rapids: dim, thin, dashed, 25% opacity
  if (rapidPoints.length > 0) {
    const rapidGeom = new THREE.BufferGeometry();
    rapidGeom.setAttribute('position', new THREE.Float32BufferAttribute(rapidPoints, 3));
    const rapidMat = new THREE.LineDashedMaterial({
      color: 0x5E90B2,
      linewidth: 1,
      transparent: true,
      opacity: 0.25,
      dashSize: 2,
      gapSize: 1,
    });
    const rapidLine = new THREE.LineSegments(rapidGeom, rapidMat);
    rapidLine.computeLineDistances();
    group.add(rapidLine);
  }

  // Cutting moves completed: layout blue, thick, fully opaque
  if (feedPointsCompleted.length > 0) {
    const feedGeom = new THREE.BufferGeometry();
    feedGeom.setAttribute('position', new THREE.Float32BufferAttribute(feedPointsCompleted, 3));
    const feedMat = new THREE.LineBasicMaterial({ color: 0xEFF6FA, linewidth: 2 });
    group.add(new THREE.LineSegments(feedGeom, feedMat));
  }

  // Cutting moves pending: layout blue, dimmer
  if (feedPointsPending.length > 0) {
    const feedGeom = new THREE.BufferGeometry();
    feedGeom.setAttribute('position', new THREE.Float32BufferAttribute(feedPointsPending, 3));
    const feedMat = new THREE.LineBasicMaterial({
      color: 0xEFF6FA,
      linewidth: 1,
      transparent: true,
      opacity: 0.4,
    });
    group.add(new THREE.LineSegments(feedGeom, feedMat));
  }

  return group;
}

function createCollisionPath(segments, collisions) {
  const group = new THREE.Group();

  for (const collision of collisions) {
    const seg = segments.find(s => s.id === collision.segment_id);
    if (!seg) continue;

    // The struck segment, in inspection red
    const points = [...seg.start, ...seg.end];
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
    const mat = new THREE.LineBasicMaterial({ color: 0xF2634B, linewidth: 3 });
    const line = new THREE.LineSegments(geom, mat);
    line.userData.isPulsing = true;
    group.add(line);
  }

  return group;
}

function createCollisionMarkers(collisions) {
  const group = new THREE.Group();

  for (const collision of collisions) {
    // Marker sphere
    const sphereGeom = new THREE.SphereGeometry(1, 16, 16);
    const sphereMat = new THREE.MeshBasicMaterial({ color: 0xF2634B });
    const sphere = new THREE.Mesh(sphereGeom, sphereMat);
    sphere.position.set(collision.x, collision.y, collision.z);
    sphere.userData.isPulsing = true;
    group.add(sphere);

    // Radiating ring
    const ringGeom = new THREE.RingGeometry(2, 3, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xF2634B,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.5,
    });
    const ring = new THREE.Mesh(ringGeom, ringMat);
    ring.position.set(collision.x, collision.y, collision.z);
    ring.lookAt(0, 0, 1);
    ring.userData.isPulsing = true;
    group.add(ring);
  }

  return group;
}

function createToolEnvelope(toolData) {
  const geometry = new THREE.CylinderGeometry(
    toolData.diameter / 2,
    toolData.diameter / 2,
    toolData.cutting_length,
    16
  );
  const material = new THREE.MeshStandardMaterial({
    color: 0xEFF6FA,
    transparent: true,
    opacity: 0.7,
    metalness: 0.8,
    roughness: 0.2,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.rotation.x = Math.PI / 2;
  return mesh;
}

export function render({ model, el }) {
  let scene, camera, renderer, controls;
  let targetMesh, stockMesh, fixtureGroup, trajectoryGroup, collisionPathGroup, collisionMarkerGroup, toolEnvelope;
  let groundPlane, grid;
  let animationId = null;
  let isPlaying = false;
  let playbackSpeed = 1.0;
  let disposed = false;
  let cleanup = () => {};
  let resizeObserver;
  let playhead = Math.max(0, Math.min(1, model.get('playhead') || 0));
  let loopEnabled = true;
  let collisionFocused = false;
  let drawnSegment = -1, drawnTool = null, drawnFrame = null;

  const container = document.createElement('div');
  container.className = 'silta-viewer';

  const loading = document.createElement('div');
  loading.className = 'silta-viewer-loading';
  loading.textContent = 'Loading the replay';
  container.appendChild(loading);

  el.appendChild(container);

  loadThree().then(() => { if (!disposed) init(); }).catch(error => {
    loading.textContent = '3D unavailable on this device. The checks and downloads remain inspectable.';
    console.error(error);
  });

  function init() {
    loading.remove();

    const canvas = document.createElement('canvas');
    canvas.tabIndex = 0;
    canvas.setAttribute('aria-label', 'Interactive CAD model. Drag to rotate, pinch to zoom, or use arrow keys.');
    container.appendChild(canvas);

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0A2B41); // --scope

    camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 1000);

    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // Three-point lighting with one warm key
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xDCEAF4, 1.0);
    keyLight.position.set(30, 40, 40);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 2048;
    keyLight.shadow.mapSize.height = 2048;
    keyLight.shadow.camera.near = 0.1;
    keyLight.shadow.camera.far = 200;
    keyLight.shadow.camera.left = -100;
    keyLight.shadow.camera.right = 100;
    keyLight.shadow.camera.top = 100;
    keyLight.shadow.camera.bottom = -100;
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
    fillLight.position.set(-20, 20, 30);
    scene.add(fillLight);

    const backLight = new THREE.DirectionalLight(0xffffff, 0.3);
    backLight.position.set(0, -30, -20);
    scene.add(backLight);

    // The second callback is deliberately inert: camera state is browser-owned and
    // must never be synced back, or every orbit would re-upload the whole scene.
    controls = new OrbitController(camera, canvas, renderFrame, () => {});

    fixtureGroup = new THREE.Group();
    scene.add(fixtureGroup);

    // Corner registration ticks

    const controlsDiv = document.createElement('div');
    controlsDiv.className = 'silta-viewer-controls';
    controlsDiv.innerHTML = `
      <div class="silta-viewer-top-controls">
        <button class="silta-viewer-button silta-viewer-button-small" id="resetBtn" aria-label="Reset view">Reset view</button>
        <div class="silta-viewer-speed-controls">
          <label class="silta-viewer-label">Speed</label>
          <button class="silta-viewer-speed-btn" data-speed="0.5" aria-label="0.5x speed">0.5×</button>
          <button class="silta-viewer-speed-btn silta-viewer-speed-active" data-speed="1" aria-label="1x speed">1×</button>
          <button class="silta-viewer-speed-btn" data-speed="4" aria-label="4x speed">4×</button>
        </div>
      </div>
      <div class="silta-viewer-scrubber">
        <div class="silta-viewer-scrubber-track" id="scrubberTrack">
          <div class="silta-viewer-scrubber-fill" id="scrubberFill"></div>
        </div>
        <input type="range" class="silta-viewer-slider" id="playheadSlider"
               min="0" max="1" step="0.001" value="0" aria-label="Playback position">
      </div>
      <div class="silta-viewer-playback">
        <button class="silta-viewer-button" id="playBtn" aria-label="Play/Pause">Play</button>
        <div class="silta-viewer-readout">
          <div class="silta-viewer-readout-item">
            <span class="silta-viewer-label">Segment</span>
            <span class="silta-viewer-value" id="segmentValue">—</span>
          </div>
          <div class="silta-viewer-readout-item">
            <span class="silta-viewer-label">Operation</span>
            <span class="silta-viewer-value" id="opValue">—</span>
          </div>
          <div class="silta-viewer-readout-item">
            <span class="silta-viewer-label">Tool</span>
            <span class="silta-viewer-value" id="toolValue">—</span>
          </div>
          <div class="silta-viewer-readout-item">
            <span class="silta-viewer-label">Z</span>
            <span class="silta-viewer-value" id="zValue">—</span>
          </div>
        </div>
        <div class="silta-viewer-status-chip" id="statusChip">—</div>
      </div>
      <div class="silta-viewer-collision-banner" id="collisionBanner" style="display: none;"></div>
    `;
    container.appendChild(controlsDiv);

    const playBtn = controlsDiv.querySelector('#playBtn');
    const resetBtn = controlsDiv.querySelector('#resetBtn');
    const slider = controlsDiv.querySelector('#playheadSlider');
    const speedBtns = controlsDiv.querySelectorAll('.silta-viewer-speed-btn');

    playBtn.addEventListener('click', () => {
      isPlaying = !isPlaying;
      playBtn.textContent = isPlaying ? 'Pause' : 'Play';
      if (isPlaying) { cancelAnimationFrame(animationId); animate(); }
      else { cancelAnimationFrame(animationId); commitPlayhead(); }
    });

    resetBtn.addEventListener('click', () => {
      controls.reset();
    });

    slider.addEventListener('input', (e) => {
      isPlaying = false; playBtn.textContent = 'Play';
      cancelAnimationFrame(animationId);
      playhead = parseFloat(e.target.value); updatePlayhead();
    });

    slider.addEventListener('change', commitPlayhead);

    speedBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        speedBtns.forEach(b => b.classList.remove('silta-viewer-speed-active'));
        btn.classList.add('silta-viewer-speed-active');
        playbackSpeed = parseFloat(btn.dataset.speed);
      });
    });

    model.on('change:scene', updateScene);
    const receivePlayhead = () => {
      playhead = Math.max(0, Math.min(1, model.get('playhead') || 0)); updatePlayhead();
    };
    const receiveCamera = () => controls.preset(model.get('camera_command')?.preset || 'isometric');
    model.on('change:playhead', receivePlayhead);
    model.on('change:camera_command', receiveCamera);
    model.on('change:view_mode', updateVisibility);
    cleanup = () => {
      model.off('change:scene', updateScene);
      model.off('change:playhead', receivePlayhead);
      model.off('change:camera_command', receiveCamera);
      model.off('change:view_mode', updateVisibility);
    };

    updateScene();

    resizeObserver = new ResizeObserver(() => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height || disposed) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderFrame();
    });
    resizeObserver.observe(container);

    function animate() {
      if (!isPlaying || disposed) return;

      const sceneData = model.get('scene');
      const segments = sceneData?.trajectory?.segments || [];
      const segmentCount = segments.length;

      // Derive rate to complete in 12-18 seconds
      const targetDuration = 15; // seconds
      const frameRate = 1000 / 60; // ~60fps
      const increment = segmentCount > 0 ? (playbackSpeed / (targetDuration * 1000 / frameRate)) : 0.002;

      const currentPlayhead = playhead;
      let newPlayhead = currentPlayhead + increment;

      if (newPlayhead >= 1) {
        if (loopEnabled) {
          newPlayhead = 0;
        } else {
          newPlayhead = 1;
          isPlaying = false;
          playBtn.textContent = 'Play';
        }
      }

      playhead = newPlayhead;
      updatePlayhead();

      if (isPlaying) {
        animationId = requestAnimationFrame(animate);
      }
    }

    function renderFrame() {
      // Pulse collision elements
      const time = Date.now() * 0.001;
      scene.traverse(obj => {
        if (obj.userData.isPulsing) {
          obj.material.opacity = 0.5 + 0.3 * Math.sin(time * 4);
        }
      });

      renderer.render(scene, camera);
    }

    function updateScene() {
      const sceneData = model.get('scene');
      if (!sceneData || Object.keys(sceneData).length === 0) return;

      disposeScene();
      drawnSegment = -1; drawnTool = null; drawnFrame = null;

      let bounds = null;

      // Ground plane and grid
      if (sceneData.stock) {
        groundPlane = createGroundPlane(sceneData.stock);
        scene.add(groundPlane);

        grid = createGrid(sceneData.stock);
        scene.add(grid);
      }

      // Target mesh
      if (sceneData.target_mesh && sceneData.target_mesh.positions.length > 0) {
        targetMesh = createTargetMesh(sceneData.target_mesh.positions);
        scene.add(targetMesh);
        targetMesh.geometry.computeBoundingBox();
        bounds = targetMesh.geometry.boundingBox;
      }

      // Fixtures
      if (sceneData.fixtures) {
        for (const fixture of sceneData.fixtures) {
          const box = createFixtureBox(fixture);
          fixtureGroup.add(box);
        }
      }

      // Trajectory
      if (sceneData.trajectory && sceneData.trajectory.segments.length > 0) {
        trajectoryGroup = createTrajectoryLines(sceneData.trajectory.segments);
        scene.add(trajectoryGroup);

        // Collision path
        if (sceneData.collisions && sceneData.collisions.length > 0) {
          collisionPathGroup = createCollisionPath(sceneData.trajectory.segments, sceneData.collisions);
          scene.add(collisionPathGroup);

          collisionMarkerGroup = createCollisionMarkers(sceneData.collisions);
          scene.add(collisionMarkerGroup);
        }
      }

      updateStatusChip(sceneData);

      // Frame camera
      if (bounds) {
        const center = new THREE.Vector3();
        bounds.getCenter(center);
        const size = bounds.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        controls.focusOn(center, maxDim);
      } else if (sceneData.stock) {
        const center = new THREE.Vector3(
          sceneData.stock.x_mm / 2,
          sceneData.stock.y_mm / 2,
          -sceneData.stock.z_mm / 2
        );
        const size = Math.max(sceneData.stock.x_mm, sceneData.stock.y_mm, sceneData.stock.z_mm);
        controls.focusOn(center, size);
      }

      controls.preset(model.get('camera_command')?.preset || 'isometric');
      updatePlayhead();
      renderFrame();
    }

    function commitPlayhead() {
      // Intentionally local. Playback position is browser state; Python never reads
      // it, and syncing it would re-upload the entire scene payload on every pause.
    }

    function updateVisibility() {
      const mode = model.get('view_mode') || 'all';
      if (targetMesh) targetMesh.visible = mode !== 'stock';
      if (stockMesh) stockMesh.visible = mode !== 'target';
      for (const group of [fixtureGroup, trajectoryGroup, toolEnvelope, collisionPathGroup, collisionMarkerGroup]) {
        if (group) group.visible = mode !== 'target';
      }
      renderFrame();
    }

    function updatePlayhead() {
      const sceneData = model.get('scene');

      const slider = container.querySelector('#playheadSlider');
      if (slider) slider.value = playhead;

      const scrubberFill = container.querySelector('#scrubberFill');
      if (scrubberFill) scrubberFill.style.width = `${playhead * 100}%`;

      if (!sceneData || !sceneData.trajectory) {
        renderFrame();
        return;
      }

      const segments = sceneData.trajectory.segments;
      const segmentIndex = Math.floor(playhead * Math.max(0, segments.length - 1));
      const segment = segments[segmentIndex];

      // Update readouts
      const segmentValue = container.querySelector('#segmentValue');
      const opValue = container.querySelector('#opValue');
      const toolValue = container.querySelector('#toolValue');
      const zValue = container.querySelector('#zValue');

      if (segment) {
        if (segmentValue) segmentValue.textContent = segment.id || '—';
        if (opValue) opValue.textContent = segment.op || '—';
        if (toolValue) toolValue.textContent = segment.tool || '—';

        const t = (playhead * Math.max(0, segments.length - 1)) - segmentIndex;
        const z = segment.start[2] + (segment.end[2] - segment.start[2]) * t;
        if (zValue) zValue.textContent = z.toFixed(2);
      }

      // Rebuild only when crossing a segment, not every animation frame.
      if (drawnSegment !== segmentIndex) {
      if (trajectoryGroup) {
        scene.remove(trajectoryGroup);
        trajectoryGroup.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) obj.material.dispose();
        });
      }
      trajectoryGroup = createTrajectoryLines(segments, segmentIndex);
      scene.add(trajectoryGroup);
      drawnSegment = segmentIndex;
      }

      // Update tool position
      if (toolEnvelope && drawnTool !== segment?.tool) {
        scene.remove(toolEnvelope);
        toolEnvelope.geometry.dispose();
        toolEnvelope.material.dispose();
        toolEnvelope = null;
      }

      if (segment && segment.tool && sceneData.tools && sceneData.tools[segment.tool]) {
        const toolData = sceneData.tools[segment.tool];
        if (!toolEnvelope) {
          toolEnvelope = createToolEnvelope(toolData);
          drawnTool = segment.tool;
          scene.add(toolEnvelope);
        }

        const t = (playhead * Math.max(0, segments.length - 1)) - segmentIndex;
        const x = segment.start[0] + (segment.end[0] - segment.start[0]) * t;
        const y = segment.start[1] + (segment.end[1] - segment.start[1]) * t;
        const z = segment.start[2] + (segment.end[2] - segment.start[2]) * t;

        toolEnvelope.position.set(x, y, z);
      }

      // A simulator keyframe is static until its segment boundary is reached.
      const frame = sceneData.replay_frames?.findLast(f => f.segment_index <= segmentIndex);
      if (frame !== drawnFrame) {
        if (stockMesh) {
          scene.remove(stockMesh);
          stockMesh.geometry.dispose();
          stockMesh.material.dispose();
          stockMesh = null;
        }
        if (frame && sceneData.stock) {
          stockMesh = createStockHeightfield(frame, sceneData.stock);
          scene.add(stockMesh);
        }
        drawnFrame = frame;
      }

      updateVisibility();

      // Collision visibility and focus
      if (sceneData.collisions && sceneData.collisions.length > 0 && collisionMarkerGroup) {
        for (let i = 0; i < sceneData.collisions.length; i++) {
          const collision = sceneData.collisions[i];
          const collisionSegmentIndex = segments.findIndex(s => s.id === collision.segment_id);

          if (segmentIndex >= collisionSegmentIndex && !collisionFocused) {
            // Just reached collision
            collisionFocused = true;
            isPlaying = false;
            playBtn.textContent = 'Play';

            // Ease camera to collision point
            const collisionPoint = new THREE.Vector3(collision.x, collision.y, collision.z);
            controls.easeToPoint(collisionPoint);

            // Show collision banner
            const banner = container.querySelector('#collisionBanner');
            if (banner) {
              const part = collision.part || 'unknown';
              const obstacleKind = collision.obstacle_kind || 'obstacle';
              const obstacleId = collision.obstacle_id || '';
              banner.textContent = `Collision on segment ${collision.segment_id}: the ${part} struck ${obstacleKind} ${obstacleId}.`;
              banner.style.display = 'block';
            }
          }

          if (collisionMarkerGroup.children[i * 2]) {
            collisionMarkerGroup.children[i * 2].visible = segmentIndex >= collisionSegmentIndex;
          }
          if (collisionMarkerGroup.children[i * 2 + 1]) {
            collisionMarkerGroup.children[i * 2 + 1].visible = segmentIndex >= collisionSegmentIndex;
          }
        }
      }

      renderFrame();
    }

    function updateStatusChip(sceneData) {
      const chip = container.querySelector('#statusChip');
      if (!chip) return;

      if (sceneData.simulation_status) {
        const status = sceneData.simulation_status.status;
        chip.textContent = status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' ');
        chip.className = 'silta-viewer-status-chip';

        if (status === 'pass') {
          chip.classList.add('silta-viewer-status-pass');
        } else if (status === 'collision') {
          chip.classList.add('silta-viewer-status-collision');
        }
      } else {
        chip.textContent = '—';
        chip.className = 'silta-viewer-status-chip';
      }
    }

    function disposeScene() {
      if (targetMesh) {
        scene.remove(targetMesh);
        targetMesh.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) obj.material.dispose();
        });
        targetMesh = null;
      }

      if (stockMesh) {
        scene.remove(stockMesh);
        stockMesh.geometry.dispose();
        stockMesh.material.dispose();
        stockMesh = null;
      }

      if (trajectoryGroup) {
        scene.remove(trajectoryGroup);
        trajectoryGroup.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) obj.material.dispose();
        });
        trajectoryGroup = null;
      }

      if (collisionPathGroup) {
        scene.remove(collisionPathGroup);
        collisionPathGroup.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) obj.material.dispose();
        });
        collisionPathGroup = null;
      }

      if (collisionMarkerGroup) {
        scene.remove(collisionMarkerGroup);
        collisionMarkerGroup.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) obj.material.dispose();
        });
        collisionMarkerGroup = null;
      }

      if (toolEnvelope) {
        scene.remove(toolEnvelope);
        toolEnvelope.geometry.dispose();
        toolEnvelope.material.dispose();
        toolEnvelope = null;
      }

      if (groundPlane) {
        scene.remove(groundPlane);
        groundPlane.geometry.dispose();
        groundPlane.material.dispose();
        groundPlane = null;
      }

      if (grid) {
        scene.remove(grid);
        grid.geometry.dispose();
        grid.material.dispose();
        grid = null;
      }

      fixtureGroup.clear();

      collisionFocused = false;
      const banner = container.querySelector('#collisionBanner');
      if (banner) banner.style.display = 'none';
    }
  }

  return () => {
    disposed = true;
    isPlaying = false;
    cleanup();
    if (resizeObserver) resizeObserver.disconnect();
    if (animationId) cancelAnimationFrame(animationId);
    if (controls) controls.dispose();
    if (renderer) renderer.dispose();
    if (scene) {
      scene.traverse(obj => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach(m => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      });
    }
  };
}
