// Prueba de la cinematica inversa: node tools/test_kin.js
globalThis.window = globalThis;
require('../robot_data.js');
const K = require('../kin.js').init(window.ROBOT_DATA.meta);
const zt = K.m.TABLE_Z + 12;
console.log('LF', K.LF.toFixed(1), 'delta', K.DELTA.toFixed(2), 'mesa z', K.m.TABLE_Z);
let line = '';
for (let r = 80; r <= 300; r += 10) {
  const s = K.ik(r, zt);
  line += r + ':' + s.map(x => x.th.toFixed(0) + '/' + x.psi.toFixed(0)).join('|') + '  ';
}
console.log('objeto en la mesa (z=' + zt + ')\n' + line);
for (const z of [-10, 0, 20, 40, 60, 80, 100]) {
  let l = 'z=' + z + ': ';
  for (let r = 80; r <= 300; r += 20) { const s = K.ikBest(r, z); l += (s ? '#' : '.'); }
  console.log(l);
}
