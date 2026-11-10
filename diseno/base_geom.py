"""Base v2 - geometria: caja de MDF con el servo J1 vertical, torreta circular y puente de la pinza.

Ejes: z hacia arriba, J1 en el eje z (x=y=0), la tapa de la torreta es z=0 (mismo origen que el hombro).
Pila en z (mm):
  torreta [-3,0] | cuerno J1 [-4,-3] | cuerpo servo hasta z=-4.2 y 22.7 hacia abajo (-26.9)
  placa superior [-14,-11] con ventana del servo (orejas encima, [-11,-8.5]) | paredes [-30,-14] | placa inferior [-33,-30]
La torreta se apoya ademas en 4 patines (tornillo M3 + espaciador de nylon de 8 mm) que ruedan sobre la placa superior.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402
import elbow_geom as e      # noqa: E402
import gripper as gr        # noqa: E402

T, SLOT = g.T, g.SLOT
TURRET_R = 60.0
Z_TURRET = (-3.0, 0.0)
Z_HORN = (-4.0, -3.0)
Z_TOP = (-14.0, -11.0)
Z_WALL = (-30.0, -14.0)
Z_BOT = (-33.0, -30.0)
Z_BODY_TOP = -4.2
Z_TABS = (-11.0, -8.5)
TABLE_Z = Z_BOT[0]

HB = 70.0                       # media anchura de la base (placas 140 x 140)
WALL_IN = 3.0                   # las paredes quedan 3 mm hacia adentro del borde de las placas
FRONT_TABS = (-45.0, 0.0, 45.0)     # centros de lenguetas de las paredes frontal/trasera (largo 20)
SIDE_TABS = (-40.0, 0.0, 40.0)      # idem paredes laterales
TAB_LEN = 20.0
SKIDS = [(sx * 35.0, sy * 35.0, 3.2) for sx in (-1, 1) for sy in (-1, 1)]
CORNER = 60.0


def j1_window():
    return (g.WIN_DX[0], g.WIN_DZ[0], g.WIN_DX[1], g.WIN_DZ[1])        # (x0, y0, x1, y1)


def j1_tab_holes():
    return [(g.TAB_X0 + g.TAB_INSET, 0.0, 2.2), (g.TAB_X1 - g.TAB_INSET, 0.0, 2.2)]


def square(h):
    return [(-h, -h), (h, -h), (h, h), (-h, h)]


# ---- paredes: ranuras en las placas
def wall_slots():
    """rectangulos (x0,y0,x1,y1) de las ranuras de paredes, iguales en la placa superior e inferior."""
    r = []
    yo, yi = HB - WALL_IN, HB - WALL_IN - T
    for c in FRONT_TABS:
        r.append((c - TAB_LEN / 2, -yo, c + TAB_LEN / 2 + SLOT, -yi + SLOT))       # frontal (y<0)
        r.append((c - TAB_LEN / 2, yi - SLOT, c + TAB_LEN / 2 + SLOT, yo))         # trasera (y>0)
    for c in SIDE_TABS:
        r.append((-yo, c - TAB_LEN / 2, -yi + SLOT, c + TAB_LEN / 2 + SLOT))       # izquierda (x<0)
        r.append((yi - SLOT, c - TAB_LEN / 2, yo, c + TAB_LEN / 2 + SLOT))         # derecha (x>0)
    return r


CABLE_PASS = (-28.0, 0.0, 10.0)      # paso de los cables de J2/J3/pinza: mismo punto en la placa superior y en la torreta (alineados con guinada 0)


def top_plate():
    return square(HB), [(g.TAB_X0 + g.TAB_INSET, 0.0, 2.2), (g.TAB_X1 - g.TAB_INSET, 0.0, 2.2), CABLE_PASS] + \
        [(sx * CORNER, sy * CORNER, 9.0) for sx in (-1, 1) for sy in (-1, 1)], [j1_window()] + wall_slots()


def bottom_plate():
    return square(HB), [(sx * CORNER, sy * CORNER, 4.0) for sx in (-1, 1) for sy in (-1, 1)], wall_slots()


def wall_panel(length_half, centers):
    """pared en coordenadas (s, z): cuerpo z in Z_WALL y lenguetas de T a cada lado."""
    pts = [(-length_half, Z_WALL[0])]
    for c in centers:
        a, b = c - TAB_LEN / 2, c + TAB_LEN / 2
        pts += [(a, Z_WALL[0]), (a, Z_BOT[0]), (b, Z_BOT[0]), (b, Z_WALL[0])]
    pts += [(length_half, Z_WALL[0]), (length_half, Z_WALL[1])]
    for c in reversed(centers):
        a, b = c - TAB_LEN / 2, c + TAB_LEN / 2
        pts += [(b, Z_WALL[1]), (b, Z_TOP[1]), (a, Z_TOP[1]), (a, Z_WALL[1])]
    pts += [(-length_half, Z_WALL[1])]
    return pts


WALL_HALF_FRONT = HB - WALL_IN              # paredes frontal/trasera: de -67 a 67 (toda la anchura menos 3 mm)
WALL_HALF_SIDE = HB - WALL_IN - T           # laterales: entre las caras internas de frontal y trasera
CABLE_HOLE = [(0.0, -22.0, 10.0)]           # pared trasera


# ---- torreta
def turret_disc():
    return [(TURRET_R * math.cos(2 * math.pi * k / 120), TURRET_R * math.sin(2 * math.pi * k / 120)) for k in range(120)]


def turret_holes():
    hs = [(0.0, 0.0, g.CENTER_A)]
    hs += [(g.HORN_R * math.cos(math.radians(45 + 90 * k)), g.HORN_R * math.sin(math.radians(45 + 90 * k)), g.HORN_D) for k in range(4)]
    return hs + SKIDS + [CABLE_PASS]


def turret_slots():
    r = []
    for (a, b) in g.CHEEK_TABS:
        r.append((a, g.Y_C, b + SLOT, g.Y_C + T + SLOT))                       # mejilla derecha (y>0)
        r.append((a, -g.Y_C - T - SLOT, b + SLOT, -g.Y_C))                     # mejilla izquierda
    return r


def brace_plate():
    """travesano en coordenadas (y, z): de la cara exterior de una mejilla a la otra."""
    h = g.Y_C + T
    return [(-h, g.BRACE["z0"]), (h, g.BRACE["z0"]), (h, g.BRACE["z1"]), (-h, g.BRACE["z1"])]


# ---- puente de la pinza (placa de la pinza con cuello que entra en las ranuras del antebrazo)
GOFF = e.L2 + 26.0                          # x del antebrazo = x de la pinza + GOFF
NECK_X0 = -(26.0 + 26.0)                    # el cuello cubre las ranuras (26 mm) + 0 sobre la punta
NECK_HW = 0.5 * (e.Y_FA_R[1] - e.Y_FA_L[0])  # 13.75: de cara exterior a cara exterior
PLATE_X0 = -24.0
GRIP_REACH = GOFF + 66.0 - e.L2             # desde el extremo del antebrazo hasta las puntas (~92)


def gripper_plate():
    h = gr.PLATE["y1"]
    return [(NECK_X0, -NECK_HW), (PLATE_X0, -NECK_HW), (PLATE_X0, -h), (gr.PLATE["x1"], -h), (gr.PLATE["x1"], h),
            (PLATE_X0, h), (PLATE_X0, NECK_HW), (NECK_X0, NECK_HW)]


def gripper_plate_holes():
    return gr.PLATE_HOLES[:2] + [gr.PLATE_HOLES[2]]         # orejas del servo y pivote B (sin los 2 agujeros provisionales)


def gripper_plate_window():
    """ventana del servo de la pinza como (x0, y0, x1, y1); gr.WIN viene ordenada (x0, x1, y0, y1)."""
    return (gr.WIN[0], gr.WIN[2], gr.WIN[1], gr.WIN[3])
