(function () {
  'use strict';
  const C = { h2: 0x4dd8ff, fc: 0x5cff9d, bat: 0xffc24d, bus: 0xc79bff, hull: 0xbfd4ff, motor: 0xff7a45 };
  let renderer, scene, camera, controls, host, clock;
  let plane, hullMat, props = [], flows = [], grid, groundGroup;
  const lastPos = new THREE.Vector3();
  let data = null, geom = null, idx = 0, playing = false, speed = 60, simT = 0, onFrame = null, ready = false, peak = { shaft: 1, fc: 1, bat: 1, h2: 1 };

  function init(el) {
    host = el;
    if (!window.THREE) { el.innerHTML = '<div class="nogl">3D needs three.js – check the internet connection and reload.</div>'; return false; }
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    el.appendChild(renderer.domElement);
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b1226);
    scene.fog = new THREE.Fog(0x0b1226, 60, 260);
    camera = new THREE.PerspectiveCamera(48, 1, 0.05, 2000);
    camera.position.set(-13, 7, 15);
    if (THREE.OrbitControls) { controls = new THREE.OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.dampingFactor = 0.1; controls.minDistance = 4; controls.maxDistance = 90; }
    scene.add(new THREE.HemisphereLight(0x9fc4ff, 0x10142a, 0.75));
    const sun = new THREE.DirectionalLight(0xffffff, 0.9); sun.position.set(20, 40, 10); scene.add(sun);
    groundGroup = new THREE.Group(); scene.add(groundGroup);
    grid = new THREE.GridHelper(600, 120, 0x2b4d8a, 0x1a2c52); groundGroup.add(grid);
    const gnd = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshBasicMaterial({ color: 0x0a1630 })); gnd.rotation.x = -Math.PI / 2; gnd.position.y = -0.02; groundGroup.add(gnd);
    const stars = new THREE.BufferGeometry(); const sp = [];
    for (let i = 0; i < 900; i++) { const r = 500 + Math.random() * 300, a = Math.random() * Math.PI * 2, b = Math.random() * Math.PI * 0.45; sp.push(r * Math.cos(a) * Math.cos(b), 30 + r * Math.sin(b), r * Math.sin(a) * Math.cos(b)); }
    stars.setAttribute('position', new THREE.Float32BufferAttribute(sp, 3));
    scene.add(new THREE.Points(stars, new THREE.PointsMaterial({ color: 0x9fb8ff, size: 1.2, sizeAttenuation: false, fog: false })));
    clock = new THREE.Clock();
    resize(); window.addEventListener('resize', resize);
    (function loop() { requestAnimationFrame(loop); tick(clock.getDelta()); })();
    ready = true;
    return true;
  }

  function resize() { if (!renderer || !host) return; const w = host.clientWidth || 800, h = host.clientHeight || 520; renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); }

  function mat(color, opts) { return new THREE.MeshStandardMaterial(Object.assign({ color, metalness: 0.25, roughness: 0.45 }, opts || {})); }

  function build(g) {
    if (plane) { scene.remove(plane); plane.traverse(o => { if (o.geometry) o.geometry.dispose(); }); }
    flows.forEach(f => scene.remove(f.points)); flows = []; props = [];
    plane = new THREE.Group();
    const L = 10, R = 0.75, span = Math.min(26, Math.max(9, L * g.span_m / Math.max(8, g.span_m * 0.8)));
    hullMat = mat(C.hull, { transparent: true, opacity: 0.18, depthWrite: false, side: THREE.DoubleSide });
    const body = new THREE.Mesh(new THREE.CylinderGeometry(R, R * 0.92, L * 0.72, 32, 1, true), hullMat); body.rotation.z = Math.PI / 2; plane.add(body);
    const nose = new THREE.Mesh(new THREE.SphereGeometry(R, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), hullMat); nose.rotation.z = -Math.PI / 2; nose.position.x = L * 0.36; nose.scale.set(1, 1.6, 1); plane.add(nose);
    const tail = new THREE.Mesh(new THREE.ConeGeometry(R * 0.92, L * 0.3, 32, 1, true), hullMat); tail.rotation.z = Math.PI / 2; tail.position.x = -L * 0.51; plane.add(tail);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.CylinderGeometry(R, R * 0.92, L * 0.72, 16, 1)), new THREE.LineBasicMaterial({ color: 0x6f8fd8, transparent: true, opacity: 0.35 })); edge.rotation.z = Math.PI / 2; plane.add(edge);
    const wingMat = mat(0xdfe8ff, { metalness: 0.4, roughness: 0.35 });
    const wing = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.1, span), wingMat); wing.position.set(0.4, g.n_motors > 1 ? 0.55 : -0.25, 0); plane.add(wing);
    const ht = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.07, span * 0.33), wingMat); ht.position.set(-L * 0.6, 0.15, 0); plane.add(ht);
    const vt = new THREE.Mesh(new THREE.BoxGeometry(0.95, 1.7, 0.08), wingMat); vt.position.set(-L * 0.6, 0.95, 0); plane.add(vt);
    const cbrt = Math.cbrt;
    const bus = new THREE.Vector3(0.2, -0.15, 0);
    const busMesh = new THREE.Mesh(new THREE.OctahedronGeometry(0.22), mat(C.bus, { emissive: C.bus, emissiveIntensity: 0.6 })); busMesh.position.copy(bus); plane.add(busMesh);
    let tankPos = null, fcPos = null, batPos = null;
    if (g.h2_kg > 0) {
      const tl = Math.min(3.4, 1.2 + cbrt(g.tank_volume_m3) * 1.4), tr = Math.min(R * 0.78, 0.35 + cbrt(g.tank_volume_m3) * 0.18);
      const tank = new THREE.Group();
      const cyl = new THREE.Mesh(new THREE.CylinderGeometry(tr, tr, tl, 28), mat(C.h2, { emissive: C.h2, emissiveIntensity: 0.25, metalness: 0.6 })); cyl.rotation.z = Math.PI / 2; tank.add(cyl);
      [-1, 1].forEach(s => { const cap = new THREE.Mesh(new THREE.SphereGeometry(tr, 24, 12), cyl.material); cap.position.x = s * tl / 2; tank.add(cap); });
      tank.position.set(-L * 0.24, 0, 0); plane.add(tank); tankPos = new THREE.Vector3(-L * 0.24 + tl / 2, 0, 0);
    }
    if (g.fc_kw > 0) {
      const s = Math.min(1.1, 0.35 + cbrt(g.fc_kg) * 0.07);
      const fc = new THREE.Mesh(new THREE.BoxGeometry(s * 1.4, s, s), mat(C.fc, { emissive: C.fc, emissiveIntensity: 0.3 })); fc.position.set(L * 0.06, 0.05, 0); plane.add(fc);
      const fins = new THREE.Group(); for (let k = -3; k <= 3; k++) { const f = new THREE.Mesh(new THREE.BoxGeometry(s * 1.42, s * 1.02, 0.02), mat(0x1e5a3a)); f.position.z = k * s * 0.13; fins.add(f); } fins.position.copy(fc.position); plane.add(fins);
      fcPos = fc.position.clone();
    }
    if (g.battery_kwh > 0) {
      const s = Math.min(1.1, 0.3 + cbrt(g.battery_kg) * 0.08);
      const bat = new THREE.Mesh(new THREE.BoxGeometry(s * 1.8, s * 0.55, s * 1.1), mat(C.bat, { emissive: C.bat, emissiveIntensity: 0.3 })); bat.position.set(L * 0.2, -0.42, 0); plane.add(bat);
      batPos = bat.position.clone();
    }
    const motors = [];
    const nm = Math.max(1, g.n_motors || 1);
    const motorPts = nm === 1 ? [new THREE.Vector3(L * 0.5, 0, 0)] : Array.from({ length: nm }, (_, i) => new THREE.Vector3(L * 0.12 + 0.6, 0.45, (i - (nm - 1) / 2) * span * 0.62 / Math.max(1, nm - 1) * (nm === 2 ? 0.9 : 1)));
    motorPts.forEach(p => {
      const nac = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.22, 1.5, 20), mat(0x9fb0d6, { metalness: 0.6 })); nac.rotation.z = Math.PI / 2; nac.position.copy(p).add(new THREE.Vector3(-0.3, 0, 0)); if (nm > 1) plane.add(nac);
      const mot = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.45, 20), mat(C.motor, { emissive: C.motor, emissiveIntensity: 0.5 })); mot.rotation.z = Math.PI / 2; mot.position.copy(p); plane.add(mot);
      const hub = new THREE.Group(); hub.position.copy(p).add(new THREE.Vector3(0.55, 0, 0));
      for (let b = 0; b < 4; b++) { const bl = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.25, 0.16), mat(0x2b2f3a, { metalness: 0.3 })); bl.position.y = 0.62; const arm = new THREE.Group(); arm.rotation.x = b * Math.PI / 2; arm.add(bl); hub.add(arm); }
      const sp = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.35, 16), mat(0xe0e6f5)); sp.rotation.z = -Math.PI / 2; sp.position.x = 0.12; hub.add(sp);
      const disc = new THREE.Mesh(new THREE.CircleGeometry(1.27, 40), new THREE.MeshBasicMaterial({ color: 0x9fc0ff, transparent: true, opacity: 0.0, side: THREE.DoubleSide, depthWrite: false })); disc.rotation.y = Math.PI / 2; hub.add(disc);
      plane.add(hub); props.push({ hub, disc }); motors.push(p.clone());
    });
    const mk = (pts, color, kind, n) => {
      const curve = new THREE.CatmullRomCurve3(pts);
      const geo = new THREE.BufferGeometry(); const pos = new Float32Array(n * 3); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      const pm = new THREE.PointsMaterial({ color, size: 0.16, transparent: true, opacity: 0.9, depthWrite: false, blending: THREE.AdditiveBlending });
      const points = new THREE.Points(geo, pm); plane.add(points);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, 0.025, 6, false), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.18 })); plane.add(tube);
      flows.push({ curve, points, n, kind, phase: Math.random(), tube });
    };
    if (tankPos && fcPos) mk([tankPos, new THREE.Vector3((tankPos.x + fcPos.x) / 2, 0.35, 0.15), fcPos], C.h2, 'h2', 60);
    if (fcPos) mk([fcPos, new THREE.Vector3((fcPos.x + bus.x) / 2, 0.1, -0.2), bus], C.fc, 'fc', 50);
    if (batPos) mk([batPos, new THREE.Vector3((batPos.x + bus.x) / 2, -0.4, 0.25), bus], C.bat, 'bat', 50);
    motors.forEach(p => mk([bus, new THREE.Vector3(bus.x, 0.25, p.z * 0.35), new THREE.Vector3(p.x - 0.4, p.y, p.z * 0.85), p], C.bus, 'shaft', 70));
    scene.add(plane);
    lastPos.copy(plane.position);
  }

  function load(result) {
    if (!ready) return;
    data = result.series; geom = result.geometry;
    build(geom);
    const mx = a => Math.max(1e-6, ...a.map(Math.abs));
    peak = { shaft: mx(data.p_shaft_kw), fc: mx(data.p_fc_kw), bat: mx(data.p_bat_kw), h2: mx(data.p_fc_kw) };
    simT = 0; idx = 0;
    camera.position.set(-13, 7, 15); if (controls) controls.target.set(0, 1.6, 0); lastPos.set(0, 1.6, 0); plane.position.set(0, 1.6, 0);
    update(true);
  }

  function sample(t) {
    const T = data.t; if (!T.length) return null;
    if (t <= T[0]) return 0; if (t >= T[T.length - 1]) return T.length - 1;
    let lo = 0, hi = T.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (T[m] <= t) lo = m; else hi = m; }
    return lo;
  }

  function update(force) {
    if (!data || !plane) return;
    idx = sample(simT);
    const i = idx;
    const alt = data.alt_m[i], x = data.x_km[i];
    plane.position.y = 1.6 + alt * 0.0025;
    const d = plane.position.clone().sub(lastPos);
    camera.position.add(d); if (controls) controls.target.add(d);
    lastPos.copy(plane.position);
    const i2 = Math.min(i + 1, data.t.length - 1), i0 = Math.max(i - 1, 0);
    const dz = (data.alt_m[i2] - data.alt_m[i0]), dx = (data.x_km[i2] - data.x_km[i0]) * 1000;
    const pitch = dx > 1 ? Math.atan2(dz, dx) : 0;
    plane.rotation.z += (pitch * 2.2 - plane.rotation.z) * 0.08;
    grid.position.x = -((x * 6) % 5);
    if (onFrame) onFrame(i, simT);
  }

  function tick(dt) {
    if (!renderer) return;
    if (data && playing) { simT += dt * speed; if (simT >= data.t[data.t.length - 1]) { simT = data.t[data.t.length - 1]; playing = false; if (window.H2Scene.onEnd) window.H2Scene.onEnd(); } update(); }
    if (data && plane) {
      const i = idx;
      const ps = Math.max(0, data.p_shaft_kw[i]) / peak.shaft;
      const pfc = Math.max(0, data.p_fc_kw[i]) / peak.fc;
      const pbat = data.p_bat_kw[i] / peak.bat;
      props.forEach(p => { p.hub.rotation.x += dt * (2 + 60 * ps) * (playing ? 1 : 0.15); p.disc.material.opacity = 0.05 + 0.18 * ps; });
      flows.forEach(f => {
        let lvl = 0, dir = 1;
        if (f.kind === 'h2') lvl = pfc; else if (f.kind === 'fc') lvl = pfc; else if (f.kind === 'bat') { lvl = Math.abs(pbat); dir = pbat >= 0 ? 1 : -1; } else lvl = ps;
        f.phase = (f.phase + dt * (0.15 + 1.4 * lvl) * dir * (playing ? 1 : 0.35) + 1) % 1;
        const pos = f.points.geometry.attributes.position.array;
        const vis = Math.round(f.n * Math.min(1, lvl * 1.15));
        for (let k = 0; k < f.n; k++) {
          const u = (k / f.n + f.phase) % 1; const p = f.curve.getPointAt(u);
          if (k < vis) { pos[3 * k] = p.x; pos[3 * k + 1] = p.y; pos[3 * k + 2] = p.z; } else { pos[3 * k] = pos[3 * k + 1] = pos[3 * k + 2] = 9999; }
        }
        f.points.geometry.attributes.position.needsUpdate = true;
        f.tube.material.opacity = 0.08 + 0.3 * Math.min(1, lvl);
      });
    }
    if (controls) controls.update();
    renderer.render(scene, camera);
  }

  window.H2Scene = {
    init, load, resize,
    play() { if (!data) return; if (simT >= data.t[data.t.length - 1]) simT = 0; playing = true; },
    pause() { playing = false; },
    isPlaying() { return playing; },
    setSpeed(s) { speed = s; },
    seek(frac) { if (!data) return; simT = frac * data.t[data.t.length - 1]; update(true); },
    progress() { return data ? simT / data.t[data.t.length - 1] : 0; },
    set onFrame(cb) { onFrame = cb; },
    onEnd: null
  };
})();
