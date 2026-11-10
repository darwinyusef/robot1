// Compila cada animacion y comprueba que TODAS las poses muestreadas respetan los limites. node tools/test_anims.js
globalThis.window = globalThis;
require('../robot_data.js');
require('../kin.js').init(window.ROBOT_DATA.meta);
const A = require('../anims.js');
const K = window.Kin;
let bad = 0;
for (const id of ['tour'].concat(A.LIST.map(a => a.id))) {
  let tl;
  try { tl = A.build(id); } catch (e) { console.log(id, 'ERROR', e.message); bad++; continue; }
  let worst = 0, n = 0, minPadZ = 1e9, yawMax = 0;
  for (let t = 0; t <= tl.duration; t += 1 / 30) {
    const p = tl.poseAt(t);
    n++;
    const r = K.psiRange(p.th);
    const viol = Math.max(0, K.m.THETA_MIN - p.th, p.th - K.m.THETA_MAX, r[0] - p.psi, p.psi - r[1], -p.phi, p.phi - K.m.PHI_MAX);
    worst = Math.max(worst, viol); yawMax = Math.max(yawMax, Math.abs(p.yaw));
    minPadZ = Math.min(minPadZ, K.pad(p.th, p.psi)[1]);
  }
  console.log(id.padEnd(8), 'dur', tl.duration.toFixed(1) + 's', ' max violacion de limites', worst.toFixed(2), 'deg', ' yaw max', yawMax.toFixed(0), ' z min pad', minPadZ.toFixed(1));
  if (worst > 0.5) bad++;
}
process.exit(bad ? 1 : 0);
