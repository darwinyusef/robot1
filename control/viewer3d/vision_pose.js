/* Control por mano: MediaPipe HandLandmarker (CDN) -> HandPose -> sliders del visor (mueve el modelo 3D)
   y, si "enviar al brazo real" esta marcado, el espejo de esp32.js manda P a ~25 Hz al hub/ESP32. */
import { FilesetResolver, HandLandmarker } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.2/vision_bundle.mjs";

const el = (id) => document.getElementById(id);
const mapper = window.HandPose.create();
let lander = null, stream = null, raf = 0, lastT = -1, seen = false;

const status = (s) => { el("visionStatus").textContent = s; };

async function init() {
  const fs = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.2/wasm");
  const opts = (d) => ({ baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task", delegate: d }, runningMode: "VIDEO", numHands: 1 });
  try { lander = await HandLandmarker.createFromOptions(fs, opts("GPU")); }
  catch (e) { lander = await HandLandmarker.createFromOptions(fs, opts("CPU")); }
}

function setSlider(id, v) {
  const s = el(id);
  s.value = Math.round(v);
  s.dispatchEvent(new Event("input"));
}

function draw(lm) {
  const c = el("handLandmarks"), v = el("visionVideo");
  c.width = v.videoWidth; c.height = v.videoHeight;
  const g = c.getContext("2d");
  g.clearRect(0, 0, c.width, c.height);
  g.fillStyle = "#43d17a";
  lm.forEach((p) => { g.beginPath(); g.arc(p.x * c.width, p.y * c.height, 3, 0, 7); g.fill(); });
}

function loop() {
  const v = el("visionVideo");
  if (v.readyState >= 2 && v.currentTime !== lastT) {
    lastT = v.currentTime;
    const r = lander.detectForVideo(v, performance.now());
    if (r.landmarks.length) {
      const lm = r.landmarks[0];
      draw(lm);
      const p = mapper.update(lm, { aspect: v.videoWidth / v.videoHeight, mirror: true });
      setSlider("s_yaw", p.yaw); setSlider("s_th", p.th); setSlider("s_psi", p.psi); setSlider("s_phi", p.phi);
      status("mano detectada");
      seen = true;
    } else if (seen) {
      mapper.reset(); seen = false;
      el("handLandmarks").getContext("2d").clearRect(0, 0, 9999, 9999);
      status("sin mano: el brazo se queda donde estaba");
    }
  }
  raf = requestAnimationFrame(loop);
}

async function start() {
  el("visionStart").disabled = true;
  try {
    status("cargando modelo...");
    if (!lander) await init();
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    const v = el("visionVideo");
    v.srcObject = stream; await v.play();
    el("visionBox").style.display = "";
    el("visionStop").disabled = false;
    mapper.reset(); seen = false;
    status("muestra la mano a la camara");
    loop();
  } catch (e) {
    status("error: " + (e && e.message || e));
    el("visionStart").disabled = false;
  }
}

function stop() {
  cancelAnimationFrame(raf);
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  el("visionBox").style.display = "none";
  el("visionStart").disabled = false; el("visionStop").disabled = true;
  status("camara apagada");
}

el("visionStart").onclick = start;
el("visionStop").onclick = stop;
el("sendToRealRobot").onchange = function () {
  if (!window.ESP) return;
  if (this.checked && !window.ESP.connected()) { this.checked = false; status("conecta primero el brazo real (panel de arriba)"); return; }
  window.ESP.mirrorOn(this.checked);
};
