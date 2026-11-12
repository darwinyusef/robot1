/* Mano (21 landmarks de MediaPipe) -> pose del brazo { yaw, th, psi, phi } en grados del modelo.
   Mismo calculo que control/vision/cv/pose_map.py: si cambias una constante, cambia la otra (test_pose_map.py las compara).
   - posicion horizontal de la palma -> guinada J1 (mano a la derecha de la imagen = giro a la derecha = yaw negativo)
   - posicion vertical de la palma   -> hombro J2 (arriba = theta mayor)
   - tamano de la mano (muneca-nudillo medio): cerca de la camara = codo mas extendido (rel = psi - theta)
   - apertura pulgar-indice / ancho de palma -> pinza J3 de la pinza (pellizco = cerrada)
   Las distancias se miden en unidades de alto de imagen (x se escala por aspect = ancho/alto). */
(function (root) {
  var C = {
    margin: 0.10,                 // zona activa: el 80 % central de la imagen
    yawSign: -1, yawMax: 90,
    thMin: 5, thMax: 85,
    relMin: -135, relMax: -35,    // psi - theta
    sizeFar: 0.12, sizeNear: 0.30,
    pinchClosed: 0.35, pinchOpen: 0.55,   // mismos umbrales que el clic de vision.js
    phiMin: 0, phiMax: 40,
    alpha: 0.35                   // suavizado exponencial
  };
  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function lerp01(v, a, b) { return clamp((v - a) / (b - a), 0, 1); }

  function create() {
    var s = null;
    return {
      reset: function () { s = null; },
      /* lm: landmarks; mirror: true si la imagen se ve en espejo (webcam del navegador: los landmarks vienen sin espejar) */
      update: function (lm, opt) {
        opt = opt || {};
        var asp = opt.aspect || 1;
        var d = function (a, b) { return Math.hypot((a.x - b.x) * asp, a.y - b.y); };
        var ids = [0, 5, 9, 13, 17], cx = 0, cy = 0;
        ids.forEach(function (i) { cx += lm[i].x; cy += lm[i].y; });
        cx /= ids.length; cy /= ids.length;
        if (opt.mirror) cx = 1 - cx;
        var u = lerp01(cx, C.margin, 1 - C.margin), v = lerp01(cy, C.margin, 1 - C.margin);
        var size = d(lm[0], lm[9]), palm = d(lm[5], lm[17]) || 1e-3;
        var k = lerp01(size, C.sizeFar, C.sizeNear);
        var open = lerp01(d(lm[4], lm[8]) / palm, C.pinchClosed, C.pinchOpen);
        var yaw = C.yawSign * (u - 0.5) * 2 * C.yawMax;
        var th = C.thMax - v * (C.thMax - C.thMin);
        var psi = th + C.relMin + k * (C.relMax - C.relMin);
        var phi = C.phiMin + open * (C.phiMax - C.phiMin);
        var raw = [yaw, th, psi, phi];
        s = s ? s.map(function (x, i) { return x + (raw[i] - x) * C.alpha; }) : raw;
        return { yaw: s[0], th: s[1], psi: s[2], phi: s[3], pinch: open < 0.5 };
      }
    };
  }
  root.HandPose = { C: C, create: create };
  if (typeof module !== 'undefined') module.exports = root.HandPose;
})(typeof window !== 'undefined' ? window : globalThis);
