// Muestrea cada animacion de anims.js y genera los datos del firmware del ESP32.
//   node tools/export_esp32.js            -> ../esp32/brazo_v2_esp32/{anims.h,limites.h}
const fs = require('fs');
const path = require('path');
globalThis.window = globalThis;
require('../robot_data.js');
require('../kin.js').init(window.ROBOT_DATA.meta);
const A = require('../anims.js');
const m = window.ROBOT_DATA.meta;

const HZ = 25;
const OUT = path.join(__dirname, '..', '..', 'esp32', 'brazo_v2_esp32');
const SKIP = new Set(['explode']);                 // solo mueve la camara y el despiece; el brazo no se mueve
const MAXV = { yaw: 240, th: 120, psi: 240, phi: 240 };   // deg/s del modelo (debe coincidir con MAX_VEL en el .ino)

// misma logica de psiLimits() del firmware, para medir cuanto recorta
const L = m.limits, SAFE = 2.0;
function fwPsi(th, p) {
  th = Math.min(Math.max(th, L.TH_LIM[0]), L.TH_LIM[L.TH_LIM.length - 1]);
  let i = 0; while (i < L.TH_LIM.length - 2 && th > L.TH_LIM[i + 1]) i++;
  let lo = Math.max(L.PSI_LO[i], L.PSI_LO[i + 1]) + SAFE, hi = Math.min(L.PSI_HI[i], L.PSI_HI[i + 1]) - SAFE;
  if (lo > hi) lo = hi = 0.5 * (lo + hi);
  lo = Math.max(lo, th + m.REL_MIN); hi = Math.min(hi, th + m.REL_MAX);
  if (lo > hi) lo = hi = 0.5 * (lo + hi);
  return Math.min(Math.max(p, lo), hi);
}

fs.mkdirSync(OUT, { recursive: true });
const list = A.LIST.filter(a => !SKIP.has(a.id));
let h = '// Generado por viewer3d/tools/export_esp32.js (no editar). Poses muestreadas de anims.js a ' + HZ + ' Hz.\n';
h += '// Cada fila: yaw, theta, psi, phi en decimas de grado.\n#pragma once\n#include <stdint.h>\n\n';
h += 'const int ANIM_HZ = ' + HZ + ';\n';
h += 'struct Anim { const char* id; const char* name; uint16_t n; const int16_t (*d)[4]; };\n\n';
const rows = [];
for (const a of list) {
  const tl = A.build(a.id);
  const n = Math.floor(tl.duration * HZ) + 1;
  const d = [];
  let clip = 0, vmax = { yaw: 0, th: 0, psi: 0, phi: 0 }, prev = null;
  for (let i = 0; i < n; i++) {
    const p = tl.poseAt(i / HZ);
    clip = Math.max(clip, Math.abs(fwPsi(p.th, p.psi) - p.psi));
    if (prev) for (const k of ['yaw', 'th', 'psi', 'phi']) vmax[k] = Math.max(vmax[k], Math.abs(p[k] - prev[k]) * HZ);
    prev = p;
    d.push([p.yaw, p.th, p.psi, p.phi].map(v => Math.round(v * 10)));
  }
  h += 'const int16_t ANIM_' + a.id + '[' + n + '][4] = {\n' + d.map(r => '{' + r.join(',') + '}').join(',') + '\n};\n\n';
  rows.push({ id: a.id, name: a.name, n });
  const over = Object.keys(MAXV).filter(k => vmax[k] > MAXV[k]);
  console.log(a.id.padEnd(8), (n / HZ).toFixed(1) + 's', String(n).padStart(5) + ' filas', ' recorte J3 firmware max ' + clip.toFixed(1) + ' deg',
    ' vel max', Object.keys(vmax).map(k => k + ' ' + vmax[k].toFixed(0)).join(' '), over.length ? ' <-- el firmware las limitara: ' + over.join(',') : '');
}
h += 'const Anim ANIMS[] = {\n' + rows.map(r => '  {"' + r.id + '", "' + r.name + '", ' + r.n + ', ANIM_' + r.id + '}').join(',\n') + '\n};\n';
h += 'const int N_ANIMS = ' + rows.length + ';\n';
fs.writeFileSync(path.join(OUT, 'anims.h'), h);

let lim = '// Generado por viewer3d/tools/export_esp32.js desde robot_data.js (mismos valores que ../../brazo_v2/limites.h; origen: diseno/output_build.py).\n#pragma once\n';
lim += 'const int N_LIM = ' + L.TH_LIM.length + ';\n';
lim += 'const int TH_LIM[N_LIM]  = {' + L.TH_LIM.join(', ') + '};\n';
lim += 'const int PSI_LO[N_LIM]  = {' + L.PSI_LO.join(', ') + '};\n';
lim += 'const int PSI_HI[N_LIM]  = {' + L.PSI_HI.join(', ') + '};\n';
fs.writeFileSync(path.join(OUT, 'limites.h'), lim);
console.log('escrito en', OUT, '(' + (h.length / 1024).toFixed(0) + ' KB de texto)');
