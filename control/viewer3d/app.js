/* Visor three.js del brazo v2. Marco CAD (Z arriba) dentro de un grupo rotado; las poses se calculan como
   M(pose) * M(pose_ref)^-1 aplicadas a mallas construidas en la pose de referencia (theta 45, psi -30, phi 20). */
(function () {
  'use strict';
  var D = window.ROBOT_DATA, M = D.meta, K = window.Kin, A = window.Anims;
  var D2R = Math.PI / 180;
  var q = new URLSearchParams(location.search);
  var VIDEO = q.get('video') === '1';
  if (VIDEO) document.body.classList.add('video');

  // ------------------------------------------------------------------ escena
  var stage = document.getElementById('stage');
  var W = VIDEO ? parseInt(q.get('w') || '1280', 10) : innerWidth, H = VIDEO ? parseInt(q.get('h') || '720', 10) : innerHeight;
  var renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: VIDEO });
  renderer.setPixelRatio(VIDEO ? 1 : Math.min(devicePixelRatio, 2));
  renderer.setSize(W, H);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  stage.appendChild(renderer.domElement);

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x14171c);
  scene.fog = new THREE.Fog(0x14171c, 900, 2200);
  var camera = new THREE.PerspectiveCamera(36, W / H, 5, 4000);
  var controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = !VIDEO; controls.dampingFactor = 0.12;

  scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x3a3430, 0.55));
  var sun = new THREE.DirectionalLight(0xfff1dd, 0.95);
  sun.position.set(260, 520, 300); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  var sc = sun.shadow.camera; sc.left = -380; sc.right = 380; sc.top = 380; sc.bottom = -380; sc.near = 100; sc.far = 1400;
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.6;
  scene.add(sun);
  var fill = new THREE.DirectionalLight(0x9db8ff, 0.3); fill.position.set(-300, 200, -250); scene.add(fill);

  // CAD (x,y,z) con z arriba -> three (x,z,-y)
  var world = new THREE.Group(); world.rotation.x = -Math.PI / 2; scene.add(world);
  function toThree(v) { return new THREE.Vector3(v[0], v[2], -v[1]); }

  // mesa y rejilla
  var table = new THREE.Mesh(new THREE.PlaneGeometry(1400, 1400), new THREE.MeshStandardMaterial({ color: 0x242a33, roughness: 0.95 }));
  table.position.z = M.TABLE_Z; table.receiveShadow = true; world.add(table);
  var grid = new THREE.GridHelper(1400, 56, 0x3a4350, 0x2c333d); grid.rotation.x = Math.PI / 2; grid.position.z = M.TABLE_Z + 0.2; world.add(grid);

  // ------------------------------------------------------------------ grupos articulados
  function G(parent) { var g = new THREE.Group(); g.matrixAutoUpdate = false; (parent || world).add(g); return g; }
  var grp = {};
  grp.static = G();
  grp.yaw = G();
  ['fixed', 'arm', 'pinion', 'crank', 'rod', 'fa'].forEach(function (n) { grp[n] = G(grp.yaw); });
  grp.jawA = G(grp.fa); grp.jawB = G(grp.fa);

  function groupFor(name) {
    if (/^(placa_inf|placa_sup|pared_|servo_J1$|servo_J1_orejas)/.test(name)) return 'static';
    if (/^(pinon_|cuerno_J2|servo_J2_eje)/.test(name)) return 'pinion';
    if (/^brazo_/.test(name)) return 'arm';
    if (/^(manivela|cuerno_J3|servo_J3_eje|pasador_manivela)/.test(name)) return 'crank';
    if (name === 'biela') return 'rod';
    if (/^mandibula_A/.test(name)) return 'jawA';
    if (/^mandibula_B/.test(name)) return 'jawB';
    if (/^(antebrazo_|pasador_codo|pasador_palanca|tubo_separador|perno_separador|pinza_)/.test(name)) return 'fa';
    return 'fixed';
  }
  var baseNames = /^(placa_|pared_|servo_J1|cuerno_J1|patin_|torreta|travesano)/;
  var mdfNames = /^(torreta|mejilla_|travesano|placa_sup|placa_inf|pared_)/;

  // ------------------------------------------------------------------ mallas
  function b64(s, Type) {
    var bin = atob(s), n = bin.length, u8 = new Uint8Array(n);
    for (var i = 0; i < n; i++) u8[i] = bin.charCodeAt(i);
    return new Type(u8.buffer);
  }
  var meshes = [];
  var unmapped = [];
  Object.keys(D.meshes).forEach(function (name) {
    var m = D.meshes[name];
    var pos = b64(m.p, Int16Array), idx = m.itype === 16 ? b64(m.i, Uint16Array) : b64(m.i, Uint32Array);
    var f = new Float32Array(pos.length);
    for (var i = 0; i < pos.length; i++) f[i] = pos[i] * m.s;
    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(f, 3));
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    try { geo = THREE.BufferGeometryUtils.toCreasedNormals(geo, 35 * D2R); } catch (e) { geo = geo.toNonIndexed(); geo.computeVertexNormals(); }
    var metal = /eje|perno|pasador|tornillo|tubo/.test(name), dark = /^servo/.test(name);
    var mat = new THREE.MeshStandardMaterial({
      color: m.color, roughness: metal ? 0.35 : (dark ? 0.55 : 0.78), metalness: metal ? 0.75 : 0.02,
      transparent: m.opacity < 1, opacity: m.opacity
    });
    var mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(m.c[0], m.c[1], m.c[2]);
    mesh.castShadow = true; mesh.receiveShadow = true;
    mesh.name = name;
    var gname = groupFor(name);
    if (!grp[gname]) { unmapped.push(name); gname = 'fixed'; }
    grp[gname].add(mesh);
    mesh.userData = { base: mesh.position.clone(), opacity: m.opacity, mdf: mdfNames.test(name), isBase: baseNames.test(name), group: gname, depthWrite0: mat.depthWrite };
    meshes.push(mesh);
  });
  if (unmapped.length) console.warn('cuerpos sin grupo:', unmapped);

  // plataformas y objetos
  var pedMeshes = {}, objMeshes = {};
  Object.keys(A.PEDS).forEach(function (k) {
    var P = A.PEDS[k], h = A.PED_TOP - M.TABLE_Z;
    var m = new THREE.Mesh(new THREE.CylinderGeometry(19, 19, h, 40), new THREE.MeshStandardMaterial({ color: 0x8a8f98, roughness: 0.6, metalness: 0.2 }));
    m.rotation.x = Math.PI / 2;      // eje del cilindro (Y) -> Z del marco CAD
    m.position.set(P.r * Math.cos(P.yaw * D2R), P.r * Math.sin(P.yaw * D2R), M.TABLE_Z + h / 2);
    m.castShadow = m.receiveShadow = true; world.add(m); pedMeshes[k] = m;
  });
  A.OBJECTS.forEach(function (o) {
    var m = new THREE.Mesh(new THREE.CylinderGeometry(A.OBJ_D / 2, A.OBJ_D / 2, A.OBJ_H, 36), new THREE.MeshStandardMaterial({ color: o.color, roughness: 0.5 }));
    m.rotation.x = Math.PI / 2; m.castShadow = m.receiveShadow = true; world.add(m); objMeshes[o.id] = m;
  });

  // ------------------------------------------------------------------ cinematica de las mallas
  var X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1);
  function mTrans(x, y, z) { return new THREE.Matrix4().makeTranslation(x, y, z); }
  function mRotY(a) { return new THREE.Matrix4().makeRotationY(a); }
  function rotAbout(p, axis, ang) {
    return mTrans(p.x, p.y, p.z).multiply(new THREE.Matrix4().makeRotationAxis(axis.clone().normalize(), ang)).multiply(mTrans(-p.x, -p.y, -p.z));
  }
  function Mrod(th, psi) { var u = (psi + 180) * D2R; return mTrans(M.RC * Math.cos(u), 0, M.H + M.RC * Math.sin(u)).multiply(mRotY(-th * D2R)); }
  function Mfa(th, psi) { var e = K.elbow(th); return mTrans(e[0], 0, e[1]).multiply(mRotY(-psi * D2R)); }
  var R0 = M.ref, MrodInv = Mrod(R0.theta, R0.psi).invert(), MfaInv = Mfa(R0.theta, R0.psi).invert();
  var S = new THREE.Vector3(0, 0, M.H), Q = new THREE.Vector3(M.Q[0], 0, M.Q[1]);
  var e0 = K.elbow(R0.theta), p0 = R0.psi * D2R;
  var pivA = new THREE.Vector3(e0[0] + M.GOFF * Math.cos(p0), M.YC + M.PIV, e0[1] + M.GOFF * Math.sin(p0));
  var pivB = new THREE.Vector3(e0[0] + M.GOFF * Math.cos(p0), M.YC - M.PIV, e0[1] + M.GOFF * Math.sin(p0));
  var nRef = new THREE.Vector3(-Math.sin(p0), 0, Math.cos(p0));
  var ID = new THREE.Matrix4();

  function setM(g, m) { g.matrix.copy(m); g.matrixWorldNeedsUpdate = true; }
  function applyPose(p) {
    setM(grp.static, ID); setM(grp.fixed, ID);
    setM(grp.yaw, new THREE.Matrix4().makeRotationZ(p.yaw * D2R));
    setM(grp.arm, rotAbout(S, Y, -(p.th - R0.theta) * D2R));
    setM(grp.pinion, rotAbout(Q, Y, M.RATIO * (p.th - R0.theta) * D2R));
    setM(grp.crank, rotAbout(S, Y, -(p.psi - R0.psi) * D2R));
    setM(grp.rod, Mrod(p.th, p.psi).multiply(MrodInv));
    setM(grp.fa, Mfa(p.th, p.psi).multiply(MfaInv));
    setM(grp.jawA, rotAbout(pivA, nRef, (p.phi - R0.phi) * D2R));
    setM(grp.jawB, rotAbout(pivB, nRef, -(p.phi - R0.phi) * D2R));
  }

  // despiece: cada malla se separa de su capa vecina segun su posicion
  function applyExplode(k) {
    meshes.forEach(function (m) {
      var b = m.userData.base, o = m.position;
      if (k <= 0) { o.copy(b); return; }
      var ng = m.userData.group;
      if (m.userData.isBase) o.set(b.x, b.y, b.z + k * (b.z + 16) * 2.4);
      else if (ng === 'fa' || ng === 'jawA' || ng === 'jawB') {
        var lz = (b.x - e0[0]) * nRef.x + (b.z - e0[1]) * nRef.z;
        o.set(b.x + nRef.x * k * lz * 1.2, b.y + k * (b.y - 1.75) * 2.6, b.z + nRef.z * k * lz * 1.2);
      } else o.set(b.x, b.y + k * b.y * 3.2, b.z);
    });
  }
  var mdfAlpha = 0;
  function applyMdf(a) {
    if (a === mdfAlpha) return; mdfAlpha = a;
    meshes.forEach(function (m) {
      var mat = m.material, base = m.userData.opacity;
      if (m.userData.mdf || /^(mejilla|brazo|antebrazo|biela|manivela|pinon|pinza_placa)/.test(m.name)) {
        var op = base * (1 - 0.8 * a); mat.opacity = op; mat.transparent = op < 0.999; mat.depthWrite = op > 0.6;
      }
      m.castShadow = a < 0.5;
    });
  }

  // ------------------------------------------------------------------ camara
  function setCam(v) {      // v = [az, el, dist, tx, ty, tz] (grados, mm; marco CAD)
    var az = v[0] * D2R, el = v[1] * D2R, d = v[2], tg = [v[3], v[4], v[5]];
    var pos = [tg[0] + d * Math.cos(el) * Math.cos(az), tg[1] + d * Math.cos(el) * Math.sin(az), tg[2] + d * Math.sin(el)];
    camera.position.copy(toThree(pos)); controls.target.copy(toThree(tg)); camera.lookAt(controls.target);
  }
  function viewPreset(az, el, d, tg) { setAuto(false); setCam([az, el, d, tg[0], tg[1], tg[2]]); }
  setCam([-40, 24, 560, 70, 0, 40]);

  // ------------------------------------------------------------------ estelas
  var trailLines = [];
  function rebuildTrails(tl) {
    trailLines.forEach(function (l) { world.remove(l); l.geometry.dispose(); }); trailLines = [];
    tl.trails.forEach(function (tr) {
      var geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(tr.pts.length * 3), 3));
      var line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: tr.color, linewidth: 2 }));
      line.frustumCulled = false; line.userData.tr = tr; world.add(line); trailLines.push(line);
    });
  }
  function updateTrails(t) {
    trailLines.forEach(function (l) {
      var tr = l.userData.tr, pa = l.geometry.attributes.position, n = 0;
      if (t >= tr.t0 && t < tr.t2) {
        for (var i = 0; i < tr.pts.length && tr.pts[i][0] <= t; i++) { pa.setXYZ(i, tr.pts[i][1], tr.pts[i][2], tr.pts[i][3]); n = i + 1; }
      }
      l.geometry.setDrawRange(0, n); pa.needsUpdate = true; l.visible = n > 1;
    });
  }

  // ------------------------------------------------------------------ estado / reproductor
  var tl = null, tlId = null, t = 0, playing = false, speed = 1, manual = { yaw: 0, th: 45, psi: -20, phi: 20 };
  var el = function (id) { return document.getElementById(id); };
  var autocam = el('autocam');
  function setAuto(v) { autocam.checked = v; }

  function fmt(s) { s = Math.max(0, s); return Math.floor(s / 60) + ':' + ('0' + Math.floor(s % 60)).slice(-2); }
  function updateUI(p) {
    el('v_yaw').textContent = p.yaw.toFixed(0) + '°'; el('v_th').textContent = p.th.toFixed(0) + '°';
    el('v_psi').textContent = p.psi.toFixed(0) + '°'; el('v_phi').textContent = p.phi.toFixed(0) + '°';
    if (document.activeElement.type !== 'range' || tl) {
      el('s_yaw').value = p.yaw; el('s_th').value = p.th; el('s_psi').value = p.psi; el('s_phi').value = p.phi;
    }
    var r = K.psiRange(p.th);
    el('lim').textContent = 'J3 permitido ahora: ' + r[0].toFixed(0) + '° a ' + r[1].toFixed(0) + '°   |   apertura ' + K.gap(p.phi).toFixed(0) + ' mm';
  }

  function showProps(v) {
    Object.keys(pedMeshes).forEach(function (k) { pedMeshes[k].visible = v; });
    Object.keys(objMeshes).forEach(function (k) { objMeshes[k].visible = v; });
  }
  function frame(tt) {
    var p;
    if (tl) {
      p = tl.poseAt(tt);
      var cv = tl.camAt(tt);
      if (cv && (autocam.checked || VIDEO)) setCam(cv);
      var ti = tl.titleAt(tt);
      document.querySelector('#ttl b').textContent = ti.text; document.querySelector('#ttl i').textContent = ti.sub;
      el('cap').textContent = tl.capAt(tt);
      applyExplode(Math.max(tl.fxAt(tt, 'explode'), el('explode').value / 100)); applyMdf(Math.max(tl.fxAt(tt, 'mdf'), el('mdf').checked ? 1 : 0));
      A.OBJECTS.forEach(function (o) { var s = tl.objState(o.id, tt); objMeshes[o.id].position.set(s.pos[0], s.pos[1], s.pos[2]); });
      showProps(tlId === 'pick' || tl.fxAt(tt, 'props') > 0.5);
      updateTrails(tt);
      el('seek').value = Math.round(1000 * tt / tl.duration); el('tt').textContent = fmt(tt) + ' / ' + fmt(tl.duration);
    } else {
      p = manual;
      applyExplode(el('explode').value / 100); applyMdf(el('mdf').checked ? 1 : 0);
      A.OBJECTS.forEach(function (o) { var P = A.PEDS[o.ped]; objMeshes[o.id].position.set(P.r * Math.cos(P.yaw * D2R), P.r * Math.sin(P.yaw * D2R), A.OZ); });
      showProps(true);
      updateTrails(-1);
    }
    applyPose(p); updateUI(p);
    if (window.ESP) window.ESP.pose(p);
  }

  function load(id) {
    tlId = id; tl = id ? A.build(id) : null; t = 0;
    document.querySelectorAll('#animList button').forEach(function (b) { b.classList.toggle('on', b.dataset.id === (id || '')); });
    if (tl) { rebuildTrails(tl); setAuto(true); } else { el('cap').textContent = ''; document.querySelector('#ttl b').textContent = ''; document.querySelector('#ttl i').textContent = ''; el('seek').value = 0; el('tt').textContent = '0:00 / 0:00'; updateTrails(-1); }
    play(!!tl);
  }
  function play(v) { playing = v; el('pp').innerHTML = v ? '&#10074;&#10074;' : '&#9654;'; }

  // UI
  var list = el('animList');
  [{ id: 'tour', name: 'Recorrido completo (' + fmt(A.build('tour').duration) + ')' }].concat(A.LIST).forEach(function (a) {
    var b = document.createElement('button'); b.textContent = a.name; b.dataset.id = a.id; b.onclick = function () { load(a.id); }; list.appendChild(b);
  });
  var bm = document.createElement('button'); bm.textContent = 'Control manual (sliders)'; bm.dataset.id = ''; bm.onclick = function () { load(null); play(false); }; list.appendChild(bm);

  el('pp').onclick = function () {
    if (!tl) { load('tour'); return; }
    if (!playing && t >= tl.duration - 0.01) t = 0;
    play(!playing);
  };
  el('seek').oninput = function () { if (tl) { t = tl.duration * this.value / 1000; play(false); } };
  el('speed').oninput = function () { speed = this.value / 100; el('speedv').textContent = speed.toFixed(speed < 1 ? 2 : 1).replace(/\.?0+$/, '') + 'x'; };
  ['yaw', 'th', 'psi', 'phi'].forEach(function (k) {
    el('s_' + k).oninput = function () {
      if (tl) { tl = null; tlId = null; document.querySelectorAll('#animList button').forEach(function (b) { b.classList.toggle('on', b.dataset.id === ''); }); updateTrails(-1); el('cap').textContent = ''; play(false); manual = tlPose(); }
      manual[k] = parseFloat(this.value);
      manual.th = K.clampTheta(manual.th); manual.psi = K.clampPsi(manual.th, manual.psi);
    };
  });
  function tlPose() { return { yaw: parseFloat(el('s_yaw').value), th: parseFloat(el('s_th').value), psi: parseFloat(el('s_psi').value), phi: parseFloat(el('s_phi').value) }; }
  el('mdf').onchange = function () { /* se aplica en frame() */ };
  el('explode').oninput = function () { if (tl) { /* el despiece manual aplica solo sin animacion */ } };
  el('vFront').onclick = function () { viewPreset(0, 5, 560, [60, 0, 40]); };
  el('vSide').onclick = function () { viewPreset(-90, 5, 560, [60, 0, 40]); };
  el('vTop').onclick = function () { viewPreset(-90, 89, 620, [60, 0, 0]); };
  el('vIso').onclick = function () { viewPreset(-40, 24, 560, [70, 0, 40]); };
  controls.addEventListener('start', function () { if (tl) setAuto(false); });

  // ------------------------------------------------------------------ bucle
  var last = performance.now();
  function loop(now) {
    var dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (playing && tl) {
      t += dt * speed;
      if (t >= tl.duration) { if (el('loop').checked) t = 0; else { t = tl.duration; play(false); } }
    }
    frame(t);
    controls.update();
    renderer.render(scene, camera);
    if (!VIDEO) requestAnimationFrame(loop);
  }
  addEventListener('resize', function () {
    if (VIDEO) return;
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight);
  });
  camera.aspect = W / H; camera.updateProjectionMatrix();

  // API para el video (headless): renderAt(t) deja la escena en el instante t y dibuja un cuadro
  window.RV = {
    ready: true,
    load: function (id) { load(id); play(false); return tl.duration; },
    renderAt: function (tt) { t = tt; frame(tt); renderer.render(scene, camera); return true; },
    setManual: function (p) { load(null); manual = Object.assign(manual, p); frame(0); renderer.render(scene, camera); },
    setCam: setCam,
    unmapped: unmapped,
    info: function () { return { meshes: meshes.length, tris: renderer.info.render.triangles }; }
  };

  if (VIDEO) { frame(0); renderer.render(scene, camera); }
  else {
    var start = q.get('anim');
    if (start === 'manual') load(null); else load(start || 'tour');
    requestAnimationFrame(loop);
  }
})();
