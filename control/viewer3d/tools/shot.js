// Capturas de prueba del visor (Edge headless). Uso: node tools/shot.js <salida.png> '<json de opciones>'
// opciones: {anim:'tour', t:12.5, manual:{yaw,th,psi,phi}, cam:[az,el,d,tx,ty,tz], mdf:true, explode:0.5, w:1280, h:720}
const puppeteer = require('puppeteer-core');
const path = require('path');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
(async () => {
  const out = process.argv[2] || 'shot.png';
  const o = new Function('return (' + (process.argv[3] || '{}') + ')')();
  const w = o.w || 1280, h = o.h || 720;
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
  const page = await browser.newPage();
  await page.setViewport({ width: w, height: h });
  page.on('console', m => console.log('[console]', m.text()));
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  const url = 'file:///' + path.resolve(__dirname, '..', 'index.html').replace(/\\/g, '/') + `?video=1&w=${w}&h=${h}`;
  await page.goto(url);
  await page.waitForFunction('window.RV && window.RV.ready', { timeout: 60000 });
  const res = await page.evaluate((o) => {
    if (o.mdf) document.getElementById('mdf').checked = true;
    if (o.explode !== undefined) document.getElementById('explode').value = o.explode * 100;
    if (o.manual) RV.setManual(o.manual); else RV.load(o.anim || 'tour');
    if (o.t !== undefined) RV.renderAt(o.t); else if (!o.manual) RV.renderAt(0);
    if (o.cam) { RV.setCam(o.cam); RV.renderAt(o.t || 0); }
    return RV.info();
  }, o);
  console.log(JSON.stringify(res));
  await page.screenshot({ path: out });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
