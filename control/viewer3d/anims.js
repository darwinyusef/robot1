/* Linea de tiempo y animaciones del brazo v2. Sin dependencia de three.js (se prueba con node tools/test_anims.js).
   Una animacion es una funcion de t: pose(t) = {yaw, th, psi, phi} (grados), camara(t), efectos(t), objetos(t), estelas, textos.
   Todas las poses de las animaciones salen de la cinematica inversa con los limites reales de limites.h. */
(function (root) {
  var K = root.Kin;
  var D2R = Math.PI / 180;
  var HOME = { yaw: 0, th: 45, psi: -20, phi: 20 };

  // ---- plataformas y objetos (el modelo no llega a la mesa: las almohadillas solo bajan hasta z ~ 0, ver README)
  var OBJ_D = 24, OBJ_H = 24, PED_TOP = 0;
  var PEDS = { P1: { yaw: -40, r: 170 }, P2: { yaw: 40, r: 185 }, P3: { yaw: 0, r: 150 } };
  var OBJECTS = [
    { id: 'o1', color: '#ffd23f', ped: 'P1' },
    { id: 'o2', color: '#43d17a', ped: 'P2' }
  ];
  var OZ = PED_TOP + OBJ_H / 2;               // z del centro del objeto apoyado en la plataforma

  function smooth(u) { return u * u * (3 - 2 * u); }
  function sine(u) { return 0.5 - 0.5 * Math.cos(Math.PI * u); }
  var EASE = { s: smooth, l: function (u) { return u; }, c: sine };

  function padWorld(p) {
    var q = K.pad(p.th, p.psi), y = p.yaw * D2R;
    return [q[0] * Math.cos(y), q[0] * Math.sin(y), q[1]];
  }

  function TL() {
    this.segs = []; this.t = 0; this.cur = Object.assign({}, HOME);
    this.caps = []; this.titles = []; this.cams = []; this.fxs = []; this.events = []; this.trails = [];
    this.marks = [];
  }
  TL.prototype.to = function (p, dur, ease) {
    var from = Object.assign({}, this.cur), to = Object.assign({}, this.cur, p);
    this.segs.push({ t0: this.t, t1: this.t + dur, from: from, to: to, ease: ease || 's' });
    this.t += dur; this.cur = to; return this;
  };
  TL.prototype.hold = function (d) { return this.to({}, d); };
  TL.prototype.go = function (yaw, r, z, dur, phi, ease) {
    var s = K.ikBest(r, z, { th: this.cur.th, psi: this.cur.psi });
    if (!s) throw new Error('IK sin solucion: r=' + r + ' z=' + z);
    var p = { yaw: yaw, th: s.th, psi: s.psi };
    if (phi !== undefined) p.phi = phi;
    return this.to(p, dur, ease);
  };
  TL.prototype.cap = function (text) { this.caps.push({ t: this.t, text: text }); return this; };
  TL.prototype.title = function (text, sub) { this.titles.push({ t: this.t, text: text, sub: sub || '' }); return this; };
  TL.prototype.cam = function (az, el, d, tg) { this.cams.push({ t: this.t, v: [az, el, d, tg[0], tg[1], tg[2]] }); return this; };
  TL.prototype.fx = function (name, value, dur) {
    var prev = 0; this.fxs.forEach(function (f) { if (f.name === name) prev = f.v1; });
    this.fxs.push({ name: name, t0: this.t, t1: this.t + (dur || 0.0001), v0: prev, v1: value }); return this;
  };
  TL.prototype.grab = function (id) { this.events.push({ t: this.t, type: 'grab', id: id }); return this; };
  TL.prototype.release = function (id, ped) { this.events.push({ t: this.t, type: 'release', id: id, ped: ped }); return this; };
  TL.prototype.trailOn = function (color) { this.trails.push({ t0: this.t, t1: null, t2: null, color: color }); return this; };
  TL.prototype.trailOff = function (hideAfter) {
    var tr = this.trails[this.trails.length - 1]; tr.t1 = this.t; tr.t2 = this.t + (hideAfter === undefined ? 2.0 : hideAfter); return this;
  };
  TL.prototype.hideTrails = function () { var t = this.t; this.trails.forEach(function (tr) { if (tr.t2 === null || tr.t2 > t) tr.t2 = t; }); return this; };

  // ---- evaluacion
  TL.prototype.poseAt = function (t) {
    var s = this.segs;
    if (!s.length) return Object.assign({}, HOME);
    if (t >= s[s.length - 1].t1) return Object.assign({}, s[s.length - 1].to);
    if (t <= s[0].t0) return Object.assign({}, s[0].from);
    var lo = 0, hi = s.length - 1;
    while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (s[mid].t0 <= t) lo = mid; else hi = mid - 1; }
    var g = s[lo], u = g.t1 > g.t0 ? Math.min(1, Math.max(0, (t - g.t0) / (g.t1 - g.t0))) : 1, e = EASE[g.ease](u);
    var o = {}; ['yaw', 'th', 'psi', 'phi'].forEach(function (k) { o[k] = g.from[k] + (g.to[k] - g.from[k]) * e; });
    return o;
  };
  function last(arr, t, key) { var r = null; for (var i = 0; i < arr.length; i++) { if (arr[i][key || 't'] <= t) r = arr[i]; else break; } return r; }
  TL.prototype.capAt = function (t) { var c = last(this.caps, t); return c ? c.text : ''; };
  TL.prototype.titleAt = function (t) { var c = last(this.titles, t); return c ? c : { text: '', sub: '' }; };
  TL.prototype.fxAt = function (t, name) {
    var v = 0;
    for (var i = 0; i < this.fxs.length; i++) {
      var f = this.fxs[i]; if (f.name !== name || f.t0 > t) continue;
      var u = f.t1 > f.t0 ? Math.min(1, (t - f.t0) / (f.t1 - f.t0)) : 1; v = f.v0 + (f.v1 - f.v0) * smooth(u);
    }
    return v;
  };
  TL.prototype.camAt = function (t) {
    var c = this.cams; if (!c.length) return null;
    if (t <= c[0].t) return c[0].v.slice();
    if (t >= c[c.length - 1].t) return c[c.length - 1].v.slice();
    var i = 0; while (i < c.length - 2 && c[i + 1].t <= t) i++;
    var a = c[i], b = c[i + 1], h = b.t - a.t, u = (t - a.t) / h, out = [];
    for (var k = 0; k < 6; k++) {
      // Hermite cubico con tangentes de Catmull-Rom (en unidades por segundo)
      var p0 = c[Math.max(0, i - 1)], p3 = c[Math.min(c.length - 1, i + 2)];
      var m1 = (b.v[k] - p0.v[k]) / Math.max(1e-6, (b.t - p0.t)), m2 = (p3.v[k] - a.v[k]) / Math.max(1e-6, (p3.t - a.t));
      if (i === 0) m1 = 0; if (i + 1 === c.length - 1) m2 = 0;
      var u2 = u * u, u3 = u2 * u;
      out.push((2 * u3 - 3 * u2 + 1) * a.v[k] + (u3 - 2 * u2 + u) * h * m1 + (-2 * u3 + 3 * u2) * b.v[k] + (u3 - u2) * h * m2);
    }
    return out;
  };
  TL.prototype.finish = function () {
    var self = this;
    this.duration = this.t;
    // estelas: muestreo de la punta (centro de las almohadillas) en [t0, t1]
    this.trails.forEach(function (tr) {
      if (tr.t1 === null) { tr.t1 = self.t; tr.t2 = self.t; }
      tr.pts = [];
      var n = Math.max(2, Math.ceil((tr.t1 - tr.t0) * 30));
      for (var i = 0; i <= n; i++) { var tt = tr.t0 + (tr.t1 - tr.t0) * i / n; tr.pts.push([tt].concat(padWorld(self.poseAt(tt)))); }
    });
    // objetos: posicion en funcion del tiempo
    this.objState = function (id, t) {
      var o = OBJECTS.filter(function (x) { return x.id === id; })[0], P = PEDS[o.ped];
      var pos = [P.r * Math.cos(P.yaw * D2R), P.r * Math.sin(P.yaw * D2R), OZ], held = false;
      for (var i = 0; i < self.events.length; i++) {
        var ev = self.events[i]; if (ev.id !== id || ev.t > t) continue;
        if (ev.type === 'grab') held = true;
        else { held = false; var Q = PEDS[ev.ped]; pos = [Q.r * Math.cos(Q.yaw * D2R), Q.r * Math.sin(Q.yaw * D2R), OZ]; }
      }
      if (held) { var w = padWorld(self.poseAt(t)); return { pos: w, held: true }; }
      return { pos: pos, held: false };
    };
    return this;
  };

  // ---------------------------------------------------------------- animaciones (cada una agrega a la linea de tiempo)
  var GRIP = K.phiForGap(OBJ_D), OPEN = 32;
  function home(tl, dur) { tl.to(HOME, dur === undefined ? 1.6 : dur); }
  function ped(name) { return PEDS[name]; }

  function pick(tl, id, from, to) {
    var A = ped(from), B = ped(to), up = OZ + 42;
    tl.cap('Abre la pinza y se coloca sobre el objeto').to({ phi: OPEN }, 0.5);
    tl.go(A.yaw, A.r, up, 1.7, OPEN);
    tl.cap('Baja hasta rodear el objeto').go(A.yaw, A.r, OZ, 1.0);
    tl.cap('Cierra: un servo y dos engranes mueven las dos mandibulas').to({ phi: GRIP }, 0.8).grab(id).hold(0.25);
    tl.cap('Levanta y gira la base (J1)').go(A.yaw, A.r, up, 1.0);
    tl.go(B.yaw, B.r, up, 2.0);
    tl.cap('Baja y suelta').go(B.yaw, B.r, OZ, 1.0);
    tl.to({ phi: OPEN }, 0.6).release(id, to).hold(0.2);
    tl.go(B.yaw, B.r, up, 0.9);
  }
  function animPick(tl) {
    tl.title('Recoger y colocar', 'Dos piezas cambian de plataforma');
    tl.cam(-38, 24, 560, [100, 0, 20]);
    tl.fx('props', 1, 0.0001);
    home(tl, 1.2);
    pick(tl, 'o1', 'P1', 'P3');
    tl.cam(-20, 28, 540, [110, 10, 20]);
    pick(tl, 'o2', 'P2', 'P1');
    tl.cam(-48, 22, 600, [110, 0, 20]);
    tl.cap('').to({ phi: 20 }, 0.3); home(tl, 1.8); tl.hold(0.5);
    tl.fx('props', 0, 0.0001);
  }
  function animWave(tl) {
    tl.title('Saludo', 'Guinada J1 y pinza al ritmo');
    tl.cam(-30, 14, 560, [110, 0, 70]);
    home(tl, 1.0);
    tl.cap('El hombro (J2) y el codo (J3) levantan la pinza').go(0, 190, 100, 2.0, 22);
    tl.cap('Hola!');
    for (var i = 0; i < 3; i++) { tl.to({ yaw: 28, phi: 36 }, 0.55, 'c'); tl.to({ yaw: -28, phi: 4 }, 0.55, 'c'); }
    tl.to({ yaw: 0, phi: 22 }, 0.5, 'c');
    tl.cam(-52, 18, 600, [110, 0, 70]);
    tl.cap('').hold(0.3); home(tl, 1.6); tl.hold(0.3);
  }
  function animCircles(tl) {
    tl.title('Dibujar en el aire', 'La punta traza un circulo en cada plano');
    tl.cam(-70, 12, 520, [150, 0, 70]);
    home(tl, 1.0);
    var c = { r: 190, z: 80, R: 30 }, n = 72, i, a;
    tl.cap('Circulo vertical: J2 y J3 coordinados (cinematica inversa)').go(0, c.r + c.R, c.z, 1.6, 20);
    tl.trailOn('#ff5d73');
    for (i = 1; i <= n; i++) { a = 2 * Math.PI * i / n; tl.go(0, c.r + c.R * Math.cos(a), c.z + c.R * Math.sin(a), 5.2 / n, undefined, 'l'); }
    tl.trailOff(2.5);
    tl.cam(-20, 55, 520, [150, 0, 60]);
    tl.cap('Circulo horizontal: J1 gira mientras J2/J3 ajustan el alcance');
    var hc = { x: 190, R: 30 }, z = 80;
    tl.go(0, hc.x + hc.R, z, 1.4);
    tl.trailOn('#4dd6ff');
    for (i = 1; i <= n; i++) {
      a = 2 * Math.PI * i / n;
      var x = hc.x + hc.R * Math.cos(a), y = hc.R * Math.sin(a);
      tl.go(Math.atan2(y, x) / D2R, Math.hypot(x, y), z, 5.6 / n, undefined, 'l');
    }
    tl.trailOff(2.5);
    tl.cam(-35, 20, 560, [150, 0, 60]);
    tl.cap('').hold(2.4).hideTrails(); home(tl, 1.6);
  }
  function animScan(tl) {
    tl.title('Espacio de trabajo', 'Barrido con la punta: dos niveles de altura');
    tl.cam(-60, 40, 620, [130, 0, 50]);
    home(tl, 1.0);
    var rows = [[40, 130, '#43d17a'], [40, 170, '#43d17a'], [40, 210, '#43d17a'], [90, 210, '#ffd23f'], [90, 170, '#ffd23f']];
    var side = -1;
    tl.cap('J1 barre +-75 grados; cada pasada cambia el alcance');
    rows.forEach(function (rw, k) {
      tl.go(75 * side, rw[1], rw[0], k === 0 ? 1.8 : 0.9, 24);
      tl.trailOn(rw[2]);
      var n = 40;
      for (var i = 1; i <= n; i++) tl.go(75 * side - 150 * side * i / n, rw[1], rw[0], 2.6 / n, undefined, 'l');
      tl.trailOff(60);
      side = -side;
    });
    tl.cam(-110, 55, 640, [130, 0, 40]);
    tl.cap('Las franjas muestran hasta donde llegan las puntas').hold(3.0);
    tl.cam(-20, 20, 600, [130, 0, 40]);
    tl.hold(2.5).hideTrails(); home(tl, 1.8);
  }
  function animJoints(tl) {
    tl.title('Las 4 articulaciones', 'Un servo por movimiento');
    tl.cam(-40, 22, 520, [60, 0, 60]);
    home(tl, 1.0);
    tl.cap('J1 - Base: servo vertical, gira la torreta +-90 grados').to({ yaw: -85 }, 1.6).to({ yaw: 85 }, 2.8).to({ yaw: 0 }, 1.6);
    tl.cam(-95, 12, 520, [60, 0, 80]);
    tl.cap('J2 - Hombro: reduccion de engranes 2:1 (piñon 14 / sector 28)').to({ th: 80 }, 2.2).to({ th: 22 }, 2.4);
    tl.cap('Con J2 solo se mueve el brazo: el antebrazo conserva su angulo (paralelogramo)').to({ th: 50 }, 1.6);
    tl.cam(-95, 12, 520, [90, 0, 90]);
    tl.cap('J3 - Codo: servo junto al hombro, manivela y biela en paralelogramo').to({ psi: -58 }, 1.8).to({ psi: 12 }, 2.8).to({ psi: -25 }, 1.6);
    tl.cam(-30, 28, 420, [150, 0, 40]);
    tl.cap('Pinza: un servo y dos engranes 1:1, mandibulas contrarotantes').to({ phi: 0 }, 1.0).to({ phi: 40 }, 2.4).to({ phi: 12 }, 1.4);
    tl.cam(-45, 24, 560, [100, 0, 50]);
    tl.cap('').hold(0.4); home(tl, 1.6);
  }
  function animMech(tl) {
    tl.title('Mecanismos por dentro', 'MDF translucido');
    tl.cam(-40, 22, 540, [60, 0, 60]);
    home(tl, 0.8);
    tl.fx('mdf', 0.8, 1.6);
    tl.cam(70, 14, 330, [-5, 0, 55]);
    tl.cap('Lado derecho: el servo J2 mueve un piñon de 14 dientes que engrana con un sector de 28').hold(1.2);
    tl.to({ th: 78 }, 3.0).to({ th: 20 }, 3.4).to({ th: 45 }, 1.6);
    tl.cam(-70, 16, 330, [-5, 0, 55]);
    tl.cap('Lado izquierdo: la manivela del servo J3 y la biela forman el paralelogramo').hold(1.5);
    tl.to({ psi: -50 }, 2.0).to({ psi: -20 }, 2.0);
    tl.cap('Brazo (J2) y antebrazo (J3) se mueven de forma independiente').to({ th: 65 }, 2.2).to({ th: 30, psi: -35 }, 2.4).to({ th: 45, psi: -20 }, 1.6);
    tl.cam(-40, 22, 560, [60, 0, 60]);
    tl.fx('mdf', 0, 1.6);
    tl.cap('').hold(1.6);
  }
  function animExplode(tl) {
    tl.title('Despiece', 'Capas de MDF de 3 mm');
    tl.cam(-40, 22, 560, [50, 0, 40]);
    home(tl, 1.0);
    tl.cap('Todas las piezas se cortan de MDF de 3 mm: capas apiladas en Y y en Z');
    tl.fx('explode', 1, 3.0);
    tl.cam(-62, 22, 700, [30, 0, 30]);
    tl.hold(3.2);
    tl.cam(10, 30, 720, [30, 0, 30]);
    tl.hold(3.2);
    tl.cam(-62, 22, 700, [30, 0, 30]);
    tl.fx('explode', 0, 3.0);
    tl.cam(-40, 22, 560, [50, 0, 40]);
    tl.cap('').hold(3.2);
  }
  function animIntro(tl) {
    tl.title('Brazo robotico v2', '4 servos - MDF 3 mm - corte laser');
    tl.cam(-120, 20, 640, [60, 0, 50]);
    home(tl, 0.01);
    tl.cap('Base, hombro con engranes, codo con paralelogramo y pinza de 2 engranes');
    tl.cam(-75, 20, 600, [60, 0, 50]);
    tl.hold(3.0);
    tl.cam(-40, 22, 540, [60, 0, 50]);
    tl.hold(2.4);
    tl.cap('');
  }

  var LIST = [
    { id: 'joints', name: 'Las 4 articulaciones', build: animJoints },
    { id: 'pick', name: 'Recoger y colocar', build: animPick },
    { id: 'wave', name: 'Saludo', build: animWave },
    { id: 'circles', name: 'Dibujar circulos', build: animCircles },
    { id: 'scan', name: 'Barrido del espacio', build: animScan },
    { id: 'mech', name: 'Mecanismos por dentro', build: animMech },
    { id: 'explode', name: 'Despiece', build: animExplode }
  ];
  var TOUR = [animIntro, animJoints, animPick, animWave, animCircles, animScan, animMech, animExplode];

  function build(id) {
    var tl = new TL(), fns;
    if (id === 'tour') fns = TOUR;
    else fns = [LIST.filter(function (a) { return a.id === id; })[0].build];
    fns.forEach(function (f, i) {
      if (id === 'tour' && i > 0) { tl.hideTrails(); }
      f(tl);
    });
    return tl.finish();
  }

  root.Anims = { build: build, LIST: LIST, HOME: HOME, PEDS: PEDS, OBJECTS: OBJECTS, OBJ_D: OBJ_D, OBJ_H: OBJ_H, PED_TOP: PED_TOP, OZ: OZ, padWorld: padWorld };
  if (typeof module !== 'undefined') module.exports = root.Anims;
})(typeof window !== 'undefined' ? window : globalThis);
