/* Cinematica del brazo v2 (plano del brazo XZ + guinada). Misma convencion que elbow_geom.py / shoulder_geom.py.
   S = (0, H) eje del hombro; codo E = S + L1*(cos th, sin th); el antebrazo toma el angulo ABSOLUTO psi (paralelogramo). */
(function (root) {
  var D2R = Math.PI / 180, R2D = 180 / Math.PI;
  var K = { m: null, padU: 38.0, padN: 12.5 };

  K.init = function (meta) {
    K.m = meta;
    // centro de las almohadillas respecto del codo: GOFF + padU a lo largo del antebrazo y padN "arriba" (capa de las mandibulas)
    K.LF = Math.hypot(meta.GOFF + K.padU, K.padN);
    K.DELTA = Math.atan2(K.padN, meta.GOFF + K.padU) * R2D;
    return K;
  };

  function interp(xs, ys, x) {
    if (x <= xs[0]) return ys[0];
    for (var i = 1; i < xs.length; i++) if (x <= xs[i]) return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    return ys[ys.length - 1];
  }
  // limites de psi segun theta (tabla de limites.h) y del paralelogramo (rel = psi - theta)
  K.psiRange = function (th) {
    var L = K.m.limits;
    var lo = interp(L.TH_LIM, L.PSI_LO, th), hi = interp(L.TH_LIM, L.PSI_HI, th);
    lo = Math.max(lo, th + K.m.REL_MIN); hi = Math.min(hi, th + K.m.REL_MAX);
    return [lo, hi];
  };
  K.clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
  K.clampTheta = function (th) { return K.clamp(th, K.m.THETA_MIN, K.m.THETA_MAX); };
  K.clampPsi = function (th, psi) { var r = K.psiRange(th); return K.clamp(psi, r[0], r[1]); };
  K.feasible = function (th, psi) {
    if (th < K.m.THETA_MIN - 1e-6 || th > K.m.THETA_MAX + 1e-6) return false;
    var r = K.psiRange(th);
    return psi >= r[0] - 1e-6 && psi <= r[1] + 1e-6;
  };

  K.elbow = function (th) { var t = th * D2R; return [K.m.L1 * Math.cos(t), K.m.H + K.m.L1 * Math.sin(t)]; };
  // punto local del antebrazo (lx adelante, lz "arriba" respecto del eje del antebrazo)
  K.fa = function (th, psi, lx, lz) {
    var e = K.elbow(th), p = psi * D2R, c = Math.cos(p), s = Math.sin(p);
    return [e[0] + lx * c - lz * s, e[1] + lx * s + lz * c];
  };
  K.pad = function (th, psi) { return K.fa(th, psi, K.m.GOFF + K.padU, K.padN); };

  // IK 2 eslabones: devuelve soluciones factibles [{th, psi}] para que el centro de las almohadillas llegue a (r, z)
  K.ik = function (r, z) {
    var S = [0, K.m.H], dx = r - S[0], dz = z - S[1], d = Math.hypot(dx, dz), L1 = K.m.L1, Lf = K.LF, out = [];
    if (d > L1 + Lf - 1e-6 || d < Math.abs(L1 - Lf) + 1e-6) return out;
    var A = Math.acos(K.clamp((L1 * L1 + d * d - Lf * Lf) / (2 * L1 * d), -1, 1)) * R2D, base = Math.atan2(dz, dx) * R2D;
    [base + A, base - A].forEach(function (th) {
      var t = th * D2R, ex = S[0] + L1 * Math.cos(t), ez = S[1] + L1 * Math.sin(t);
      var psi = Math.atan2(z - ez, r - ex) * R2D - K.DELTA;
      if (K.feasible(th, psi)) out.push({ th: th, psi: psi });
    });
    return out;
  };
  // la solucion mas cercana a una pose dada (o la de mayor theta si no se da)
  K.ikBest = function (r, z, near) {
    var s = K.ik(r, z);
    if (!s.length) return null;
    if (near) s.sort(function (a, b) { return Math.hypot(a.th - near.th, a.psi - near.psi) - Math.hypot(b.th - near.th, b.psi - near.psi); });
    else s.sort(function (a, b) { return b.th - a.th; });
    return s[0];
  };
  // apertura (separacion entre almohadillas, mm) a la altura del centro de las almohadillas, segun el giro phi de las mandibulas
  K.gap = function (phi) { return 8.3 + 1.34 * phi; };
  K.phiForGap = function (g) { return K.clamp((g - 8.3) / 1.34, 0, K.m.PHI_MAX); };

  root.Kin = K;
  if (typeof module !== 'undefined') module.exports = K;
})(typeof window !== 'undefined' ? window : globalThis);
