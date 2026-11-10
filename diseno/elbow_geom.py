"""Codo v2 - geometria. Servo J3 coaxial con S (eje del hombro), manivela + biela en paralelogramo.

Plano XZ, S = (0, H), E = codo = S + L1*(cos th, sin th).
El antebrazo toma el angulo ABSOLUTO psi de la manivela:  manivela = psi + 180  (la palanca del antebrazo apunta hacia atras).
  manivela: S -> S + RC*u,  u = -(cos psi, sin psi)
  biela   : de S + RC*u a E + RC*u  (paralela al brazo, largo L1)
  palanca : de E a E + RC*u  (cola de la placa izq. del antebrazo)
Capas en Y: manivela y placa izq. del antebrazo [-12,-9]; biela [-8.5,-5.5]; placa der. del antebrazo [12.5,15.5].
Zona sin control: rel = psi - th = 0 o 180 (alineado con el brazo) -> el paralelogramo se hace plano. Se limita rel a REL_MIN..REL_MAX.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402
from gripper import rot, shift   # noqa: E402

RC = 16.0                       # radio de la manivela / palanca
ROD_R = 4.5                     # radio de los extremos de la biela y manivela (ancho 9)
HUB_R = 11.5                    # cubo de la manivela (cuerno redondo r=9.5)
E_HUB = 8.0
FA_HW = 7.0                     # semiancho del antebrazo
PIN_D = 3.2

Y_CRANK = (-12.0, -9.0)
Y_ROD = (-8.5, -5.5)
Y_FA_L = (-12.0, -9.0)
Y_FA_R = (12.5, 15.5)
Y_HORN = (-13.0, -12.0)
FA_YC = 0.5 * (Y_FA_L[0] + Y_FA_R[1])           # centro del antebrazo en y (1.75)

L2 = g.L2
SPACER_X = 40.0                 # separador entre placas (en el sistema del antebrazo)
SLOT_X0 = L2 - 26.0             # ranura abierta al frente para el puente de la pinza
SLOT_H = 3.1
NOTCH_BOT = [(L2, -FA_HW), (L2, -SLOT_H / 2), (SLOT_X0, -SLOT_H / 2)]
NOTCH_TOP = [(SLOT_X0, SLOT_H / 2), (L2, SLOT_H / 2), (L2, FA_HW)]

REL_MIN, REL_MAX = -135.0, -35.0                # psi - theta permitido (grados)


def arc(cx, cy, r, a0, a1, n=20):
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in np.linspace(a0, a1, n)]


def crank_ply():
    """manivela en su sistema local: S en el origen, perno en (RC, 0)."""
    a = math.degrees(math.asin(ROD_R / HUB_R))
    x0 = math.sqrt(HUB_R ** 2 - ROD_R ** 2)
    pts = [(x0, -ROD_R), (RC, -ROD_R)]
    pts += arc(RC, 0.0, ROD_R, -90, 90)[1:-1]
    pts += [(RC, ROD_R), (x0, ROD_R)]
    pts += arc(0.0, 0.0, HUB_R, a, 360 - a)[1:-1]
    return pts


CRANK_HOLES = [(0.0, 0.0, g.CENTER_A)] + [(g.HORN_R * math.cos(math.radians(45 + 90 * k)), g.HORN_R * math.sin(math.radians(45 + 90 * k)), g.HORN_D) for k in range(4)] + [(RC, 0.0, PIN_D)]


def rod_ply():
    """biela: del perno de la manivela (0,0) al de la palanca (L1,0)."""
    pts = [(0.0, -ROD_R), (g.L1, -ROD_R)] + arc(g.L1, 0.0, ROD_R, -90, 90)[1:-1] + [(g.L1, ROD_R), (0.0, ROD_R)]
    pts += arc(0.0, 0.0, ROD_R, 90, 270)[1:-1]
    return pts


ROD_HOLES = [(0.0, 0.0, PIN_D), (g.L1, 0.0, PIN_D)]


def forearm_left_ply():
    """placa izquierda del antebrazo (con cola-palanca); E en el origen, antebrazo hacia +x."""
    ab = math.degrees(math.asin(FA_HW / E_HUB))
    at = math.degrees(math.asin(ROD_R / E_HUB))
    pts = arc(-RC, 0.0, ROD_R, 90, 270)                             # cola, de arriba hacia abajo por la izquierda
    pts += arc(0.0, 0.0, E_HUB, 180 + at, 360 - ab)                 # cubo por abajo
    pts += NOTCH_BOT + NOTCH_TOP
    pts += arc(0.0, 0.0, E_HUB, ab, 180 - at)                       # cubo por arriba
    return pts


def forearm_right_ply():
    ab = math.degrees(math.asin(FA_HW / E_HUB))
    return arc(0.0, 0.0, E_HUB, ab, 360 - ab) + NOTCH_BOT + NOTCH_TOP

FA_HOLES_L = [(0.0, 0.0, PIN_D), (-RC, 0.0, PIN_D), (SPACER_X, 0.0, PIN_D)]
FA_HOLES_R = [(0.0, 0.0, PIN_D), (SPACER_X, 0.0, PIN_D)]


# ------------------------------------------------------------------ poses
def elbow_pt(theta):
    t = math.radians(theta)
    return (g.L1 * math.cos(t), g.H + g.L1 * math.sin(t))


def crank_pose(poly, psi):
    return shift(rot(poly, math.radians(psi + 180.0)), 0.0, g.H)


def rod_pose(poly, theta, psi):
    u = math.radians(psi + 180.0)
    return shift(rot(poly, math.radians(theta)), RC * math.cos(u), g.H + RC * math.sin(u))


def forearm_pose(poly, theta, psi):
    ex, ez = elbow_pt(theta)
    return shift(rot(poly, math.radians(psi)), ex, ez)


def pt_forearm(theta, psi, lx, lz=0.0):
    """punto local del antebrazo (lx, lz) en coordenadas absolutas."""
    ex, ez = elbow_pt(theta)
    p = math.radians(psi)
    return (ex + lx * math.cos(p) - lz * math.sin(p), ez + lx * math.sin(p) + lz * math.cos(p))

