"""Hombro v2 - geometria (piezas planas en el plano XZ; x = adelante, z = arriba; S = eje del hombro).

Reduccion 2:1: pinon z=14 en el servo J2, sector z=28 en el brazo (m=2). MDF 3 mm.
Pila de capas en Y (mm), mejillas de la torreta en |y| in [20, 23]:
  mejilla izq  [-23,-20] | cuerno J3 [-13,-12] + manivela [-12,-9] | biela [-8.5,-5.5] | placa izq. del brazo [-5,-2]
  placa der. del brazo [9,12] + capa de sector [6,9] | mejilla der. [20,23] | servo J2 por fuera (cuerpo y>13.2)
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                       # python -I no agrega la carpeta del script
from gripper import rot, shift, area, inside, overlap_area, min_dist, inv   # noqa: E402

T = 3.0
M, Z1, Z2 = 2.0, 14, 28
PA, BACKLASH = 20.0, 0.10
ADD, DED = 0.85 * M, 1.25 * M
RP1, RP2 = M * Z1 / 2, M * Z2 / 2
CD = RP1 + RP2                                  # 42 mm entre ejes
RATIO = Z2 / Z1

H = 60.0                                        # altura del eje S sobre la torreta (z=0)
L1 = 90.0                                       # brazo (S -> codo)
L2 = 90.0                                       # antebrazo (provisional, fase 3)
RL = 12.0                                       # radio del eslabon y del cubo
BETA = -135.0                                   # direccion S -> servo (grados)
THETA_MIN, THETA_MAX = 5.0, 85.0                # recorrido del brazo (servo: 0..160 deg)
S_MARGIN = 20.0
Q = (CD * math.cos(math.radians(BETA)), H + CD * math.sin(math.radians(BETA)))   # eje del servo J2

Y_C = 20.0                                      # cara interior de las mejillas
Y_ARM_R = (9.0, 12.0)
Y_SECT = (6.0, 9.0)
Y_ARM_L = (-5.0, -2.0)                          # (fase 3: se corrio 3 mm para dejar paso a la biela en [-8.5,-5.5])

# servo SG90 / MG90S (mismas cotas que gripper.py; verificar con calibre)
SV_L, SV_W, SV_H = 22.8, 12.2, 22.7
SV_TAB_L, SV_TAB_T, SV_SHAFT_FROM_END, SV_ABOVE = 32.5, 2.5, 6.0, 6.8
TAB_INSET, GEAR_GAP = 2.4, 8.0
HORN_R, HORN_D, CENTER_A = 8.0, 1.8, 7.6


def gear_teeth(m, z, centers, wrap=False, nfl=7):
    rp = m * z / 2.0
    rb = rp * math.cos(math.radians(PA))
    ra, rr = rp + ADD, rp - DED
    ap = math.radians(PA)
    half_p = (math.pi * m / 2 - BACKLASH) / (2 * rp)
    half = lambda r: half_p + inv(ap) - inv(math.acos(min(1.0, rb / r)))
    rs = np.linspace(max(rb, rr + 1e-9), ra, nfl)
    pol = lambda r, a: (r * math.cos(a), r * math.sin(a))
    pts, prev = [], None
    hb = half(rs[0])
    for c in centers:
        if prev is not None:
            pts.append(pol(rr, 0.5 * (prev + c - hb)))
        pts.append(pol(rr, c - hb))
        pts += [pol(r, c - half(r)) for r in rs]
        pts += [pol(r, c + half(r)) for r in rs[::-1]]
        pts.append(pol(rr, c + hb))
        prev = c + hb
    if wrap:
        pts.append(pol(rr, 0.5 * (prev + centers[0] + 2 * math.pi - hb)))
    return pts


def _arc(r, a0, a1, n=24):
    return [(r * math.cos(a), r * math.sin(a)) for a in np.linspace(a0, a1, n)]


def sector_teeth():
    p = 2 * math.pi / Z2
    lo = math.radians((BETA - THETA_MAX - S_MARGIN) % 360)
    hi = math.radians((BETA - THETA_MIN + S_MARGIN) % 360)
    ks = range(math.ceil(lo / p), math.floor(hi / p) + 1)
    return gear_teeth(M, Z2, [k * p for k in ks])


def arm_link_ply():
    """placa del brazo con eslabon y sector dentado; S en el origen, codo E en (L1, 0)."""
    teeth = sector_teeth()
    a_s = math.atan2(teeth[0][1], teeth[0][0]) % (2 * math.pi)
    a_e = math.atan2(teeth[-1][1], teeth[-1][0]) % (2 * math.pi)
    poly = [(0.0, -RL), (L1, -RL)]
    poly += [(L1 + RL * math.cos(a), RL * math.sin(a)) for a in np.linspace(-math.pi / 2, math.pi / 2, 24)][1:-1]
    poly += [(L1, RL), (0.0, RL)]
    poly += _arc(RL, math.pi / 2, a_s)[1:]
    poly += teeth
    poly += _arc(RL, a_e, 1.5 * math.pi)[:-1]
    return poly


def arm_sector_ply():
    """capa extra solo del cubo + sector (sin eslabon), misma dentadura."""
    teeth = sector_teeth()
    a_s = math.atan2(teeth[0][1], teeth[0][0]) % (2 * math.pi)
    a_e = math.atan2(teeth[-1][1], teeth[-1][0]) % (2 * math.pi)
    return teeth + _arc(RL, a_e, a_s + 2 * math.pi)[:-1]


def arm_left_plate():
    p = [(0.0, -RL), (L1, -RL)]
    p += [(L1 + RL * math.cos(a), RL * math.sin(a)) for a in np.linspace(-math.pi / 2, math.pi / 2, 24)][1:-1]
    p += [(L1, RL), (0.0, RL)]
    p += [(RL * math.cos(a), RL * math.sin(a)) for a in np.linspace(math.pi / 2, 1.5 * math.pi, 24)][1:-1]
    return p


ARM_HOLES = [(0.0, 0.0, 3.2), (L1, 0.0, 3.2)]


def pinion():
    p = 2 * math.pi / Z1
    return gear_teeth(M, Z1, [k * p for k in range(Z1)], wrap=True)


def pinion_holes():
    hs = [(0.0, 0.0, CENTER_A)]
    for k in range(4):
        a = math.radians(45 + 90 * k)
        hs.append((HORN_R * math.cos(a), HORN_R * math.sin(a), HORN_D))
    return hs


def arm_pose(poly, theta):
    return shift(rot(poly, math.radians(theta)), 0.0, H)


def pinion_pose(poly, rho):
    return shift(rot(poly, rho), Q[0], Q[1])


def find_phase(theta_ref=45.0):
    """giro del pinon (rad) que engrana con el sector en theta_ref: centro del intervalo sin solape."""
    sec = arm_pose(arm_link_ply(), theta_ref)
    pin = pinion()
    p = 2 * math.pi / Z1
    zero = []
    for d in np.arange(0.0, 360.0 / Z1, 0.25):
        if overlap_area(sec, pinion_pose(pin, math.radians(d)), 0.15) < 0.05:
            zero.append(d)
    if not zero:
        raise RuntimeError("sin fase de engrane")
    return math.radians(float(np.median(zero))), zero


def rho_at(theta, rho_ref, theta_ref=45.0):
    return rho_ref - RATIO * math.radians(theta - theta_ref)


# ------------------------------------------------------------------ mejillas de la torreta (plano XZ)
BODY_X0, BODY_X1 = -(SV_L - SV_SHAFT_FROM_END), SV_SHAFT_FROM_END
WIN_DX = (BODY_X0 - 0.3, BODY_X1 + 0.3)
WIN_DZ = (-SV_W / 2 - 0.3, SV_W / 2 + 0.3)
TAB_X0 = 0.5 * (BODY_X0 + BODY_X1) - SV_TAB_L / 2
TAB_X1 = TAB_X0 + SV_TAB_L


CHEEK_TABS = ((-44.0, -28.0), (2.0, 18.0))      # lenguetas inferiores (x) que entran en la torreta (z in [-T, 0])
BRACE = dict(x0=20.0, x1=20.0 + T, z0=12.0, z1=32.0)   # travesano entre mejillas (placa en plano YZ)
SLOT = 0.1                                      # holgura de ranuras (MDF 3 mm: ranura 3.1)


def cheek_outline():
    pts = [(-50.0, 0.0)]
    for (a, b) in CHEEK_TABS:
        pts += [(a, 0.0), (a, -T), (b, -T), (b, 0.0)]
    return pts + [(26.0, 0.0), (26.0, H - 10), (14.0, H + 16), (-14.0, H + 16), (-58.0, H - 10)]


def brace_slot():
    return (BRACE["x0"], BRACE["z0"], BRACE["x1"] + SLOT, BRACE["z1"])


def cheek_right_holes():
    return [(0.0, H, 3.2), (Q[0] + TAB_X0 + TAB_INSET, Q[1], 2.2), (Q[0] + TAB_X1 - TAB_INSET, Q[1], 2.2)]


def cheek_rects_right():
    return [cheek_right_window(), brace_slot()]


def cheek_rects_left():
    return [cheek_left_window(), brace_slot()]


def cheek_right_window():
    return (Q[0] + WIN_DX[0], Q[1] + WIN_DZ[0], Q[0] + WIN_DX[1], Q[1] + WIN_DZ[1])


def cheek_left_holes():
    """servo J3 coaxial con S, espejo del J2: tornillos de las orejas (la ventana va aparte)."""
    return [(TAB_X0 + TAB_INSET, H, 2.2), (TAB_X1 - TAB_INSET, H, 2.2)]


def cheek_left_window():
    return (WIN_DX[0], H + WIN_DZ[0], WIN_DX[1], H + WIN_DZ[1])
