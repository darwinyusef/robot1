// Renderiza una animacion a MP4, cuadro a cuadro (Edge headless + ffmpeg por pipe).
// Uso: node tools/render_video.js <salida.mp4> [anim=tour] [fps=30] [w=1280] [h=720] [tmax=duracion]
const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const path = require('path');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
(async () => {
  const out = path.resolve(process.argv[2] || 'brazo_v2_tour.mp4');
  const anim = process.argv[3] || 'tour';
  const fps = +(process.argv[4] || 30), w = +(process.argv[5] || 1280), h = +(process.argv[6] || 720);
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
  const page = await browser.newPage();
  await page.setViewport({ width: w, height: h });
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  await page.goto('file:///' + path.resolve(__dirname, '..', 'index.html').replace(/\\/g, '/') + `?video=1&w=${w}&h=${h}`);
  await page.waitForFunction('window.RV && window.RV.ready', { timeout: 60000 });
  const dur = await page.evaluate(a => RV.load(a), anim);
  const tmax = +(process.argv[7] || dur);
  const n = Math.floor(tmax * fps);
  console.log(`anim=${anim} dur=${dur.toFixed(1)}s frames=${n} @${fps}fps ${w}x${h}`);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise(r => ff.on('close', r));
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => RV.renderAt(t), i / fps);
    const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 150 === 0) console.log(`${i}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end(); await done; await browser.close();
  console.log('listo', out, ((Date.now() - t0) / 1000).toFixed(0) + 's');
})().catch(e => { console.error(e); process.exit(1); });
