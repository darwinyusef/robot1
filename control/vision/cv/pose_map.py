"""Mano (21 landmarks de MediaPipe) -> pose del brazo (yaw, th, psi, phi) en grados del modelo.

Mismo calculo que control/viewer3d/handpose.js (ver ese archivo para el significado): si cambias una constante, cambia la otra.
Los landmarks deben venir ya en espejo (el pipeline hace cv2.flip antes de detectar). Distancias en unidades de alto de imagen.
"""
import math

C = dict(margin=0.10, yaw_sign=-1, yaw_max=90, th_min=5, th_max=85, rel_min=-135, rel_max=-35,
         size_far=0.12, size_near=0.30, pinch_closed=0.35, pinch_open=0.55, phi_min=0, phi_max=40, alpha=0.35)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _lerp01(v, a, b):
    return _clamp((v - a) / (b - a), 0.0, 1.0)


class PoseMapper:
    def __init__(self):
        self._s = None

    def reset(self):
        self._s = None

    def update(self, lm, aspect=1.0):
        d = lambda a, b: math.hypot((lm[a].x - lm[b].x) * aspect, lm[a].y - lm[b].y)
        ids = (0, 5, 9, 13, 17)
        cx = sum(lm[i].x for i in ids) / len(ids)
        cy = sum(lm[i].y for i in ids) / len(ids)
        u, v = _lerp01(cx, C["margin"], 1 - C["margin"]), _lerp01(cy, C["margin"], 1 - C["margin"])
        k = _lerp01(d(0, 9), C["size_far"], C["size_near"])
        palm = d(5, 17) or 1e-3
        opened = _lerp01(d(4, 8) / palm, C["pinch_closed"], C["pinch_open"])
        yaw = C["yaw_sign"] * (u - 0.5) * 2 * C["yaw_max"]
        th = C["th_max"] - v * (C["th_max"] - C["th_min"])
        psi = th + C["rel_min"] + k * (C["rel_max"] - C["rel_min"])
        phi = C["phi_min"] + opened * (C["phi_max"] - C["phi_min"])
        raw = (yaw, th, psi, phi)
        a = C["alpha"]
        self._s = raw if self._s is None else tuple(x + (r - x) * a for x, r in zip(self._s, raw))
        return dict(zip(("yaw", "th", "psi", "phi"), self._s))
