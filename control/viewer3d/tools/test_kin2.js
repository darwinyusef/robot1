globalThis.window = globalThis;
require('../robot_data.js');
const K = require('../kin.js').init(window.ROBOT_DATA.meta);
const best = {};
for (let th = 5; th <= 85; th += 1) {
  const [lo, hi] = K.psiRange(th);
  for (let psi = lo; psi <= hi; psi += 1) {
    const p = K.pad(th, psi), b = Math.round(p[0] / 10) * 10;
    if (!best[b] || p[1] < best[b].z) best[b] = { z: p[1], th, psi };
  }
}
Object.keys(best).sort((a, b) => a - b).forEach(r => console.log('r=' + r, 'zmin=' + best[r].z.toFixed(1), 'th=' + best[r].th, 'psi=' + best[r].psi));
