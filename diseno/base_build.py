"""Base v2 (fase 4) - ensamble 3D completo (SolidCraft) y planchas SVG de corte (MDF 3 mm).

Uso:  python -I base_build.py [--no3d]
Salida: robot_{a,b,c}.sc/.png (3 poses), corte_mdf_3mm_base_1.svg (placas), _2.svg (paredes, travesano, pinza)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402
import elbow_geom as e      # noqa: E402
import gripper as gr        # noqa: E402
import base_geom as b       # noqa: E402
import scene as S           # noqa: E402
import elbow_build as eb    # noqa: E402
from shoulder_build import Sheet, part   # noqa: E402

RHO_REF, _ = g.find_phase()
POSES = (("a", 45.0, -30.0, 20.0), ("b", 20.0, -40.0, 40.0), ("c", 75.0, 20.0, 0.0))      # (tag, theta, psi, apertura mandibulas)
MDF = "#c8a165"


def disc(cx, cy, r, n=28):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def base(sc):
    """caja, servo J1 vertical, patines y torreta (el disco lleva las ranuras de las mejillas)."""
    sc.pplate("placa_inf", (0, 0, b.Z_BOT[0]), (1, 0, 0), (0, 1, 0), b.square(b.HB), *_hr(b.bottom_plate()), color=MDF)
    tp, th, tr = b.top_plate()
    sc.pplate("placa_sup", (0, 0, b.Z_TOP[0]), (1, 0, 0), (0, 1, 0), tp, th, tr, color=MDF)
    yo = b.HB - b.WALL_IN
    sc.plate("pared_frontal", -yo + g.T, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), color="#d9b27a")
    sc.plate("pared_trasera", yo, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), b.CABLE_HOLE, color="#d9b27a")
    for nm, x0 in (("pared_izq", -yo), ("pared_der", yo - g.T)):
        sc.pplate(nm, (x0, 0, 0), (0, 1, 0), (0, 0, 1), b.wall_panel(b.WALL_HALF_SIDE, b.SIDE_TABS), color="#d9b27a")
    # servo J1: orejas apoyadas en la placa superior, cuerpo por la ventana
    zb = b.Z_BODY_TOP - g.SV_H
    sc.box("servo_J1", g.BODY_X0, -g.SV_W / 2, zb, g.SV_L, g.SV_W, g.SV_H, "#202428")
    sc.box("servo_J1_orejas", g.TAB_X0, -g.SV_W / 2, b.Z_TABS[0], g.SV_TAB_L, g.SV_W, g.SV_TAB_T, "#202428")
    sc.zcyl("servo_J1_eje", 4.8, b.Z_BODY_TOP, b.Z_HORN[1], 0, 0, "#b8bec6")
    sc.zcyl("cuerno_J1", 19.0, b.Z_HORN[0], b.Z_HORN[1], 0, 0, "#f2f2f2")
    for i, (x, y, _) in enumerate(b.SKIDS):
        sc.zcyl("patin_%d" % i, 6.0, b.Z_TOP[1], b.Z_TURRET[0], x, y, "#f0f0f0")
        sc.zcyl("patin_tornillo_%d" % i, 3.0, b.Z_TOP[1], b.Z_TURRET[1] + 2, x, y, "#b8bec6")
    sc.pplate("torreta", (0, 0, b.Z_TURRET[0]), (1, 0, 0), (0, 1, 0), b.turret_disc(), b.turret_holes()[:5] + [b.CABLE_PASS], b.turret_slots(), color="#9a9a9a", opacity=0.55)
    sc.pplate("travesano", (g.BRACE["x0"], 0, 0), (0, 1, 0), (0, 0, 1), b.brace_plate(), color=MDF)


def _hr(plate):
    """(poly?, holes, rects) -> (holes, rects) cuando la funcion ya devolvio el contorno aparte."""
    return plate[1], plate[2]


def gripper_on_forearm(sc, theta, psi, phi):
    ex, ez = e.elbow_pt(theta)
    p = math.radians(psi)
    xd, n = (math.cos(p), 0.0, math.sin(p)), (-math.sin(p), 0.0, math.cos(p))
    yc = e.FA_YC
    x0 = b.GOFF

    def tp(name, poly, holes=(), rects=(), gz0=0.0, thick=g.T, color=MDF):
        o = (ex + x0 * xd[0] + (gz0 + 1.5) * n[0], 0.0, ez + x0 * xd[2] + (gz0 + 1.5) * n[2])
        sc.pplate(name, o, xd, (0, 1, 0), [(u, v + yc) for u, v in poly],
                  [(u, v + yc, d) for u, v, d in holes], [(a, c + yc, d_, f + yc) for a, c, d_, f in rects], color=color, thick=thick)

    tp("pinza_placa", b.gripper_plate(), b.gripper_plate_holes(), [b.gripper_plate_window()], -g.T, g.T)
    tp("pinza_servo", [(gr.BODY_X0, gr.PIV - gr.SV_W / 2), (gr.BODY_X1, gr.PIV - gr.SV_W / 2), (gr.BODY_X1, gr.PIV + gr.SV_W / 2), (gr.BODY_X0, gr.PIV + gr.SV_W / 2)],
       gz0=-gr.SV_BELOW, thick=gr.SV_H, color="#202428")
    tp("pinza_orejas", [(gr.TAB_X0, gr.PIV - gr.SV_W / 2), (gr.TAB_X1, gr.PIV - gr.SV_W / 2), (gr.TAB_X1, gr.PIV + gr.SV_W / 2), (gr.TAB_X0, gr.PIV + gr.SV_W / 2)],
       gz0=0.0, thick=gr.SV_TAB_T, color="#202428")
    tp("pinza_eje", disc(0, gr.PIV, 2.4), gz0=gr.SV_H - gr.SV_BELOW, thick=3.5, color="#b8bec6")
    tp("pinza_cuerno", disc(0, gr.PIV, 9.5), gz0=gr.GEAR_Z0 - 1.0, thick=1.0, color="#f2f2f2")
    tp("pinza_sep_B", disc(0, -gr.PIV, 3.0), gz0=0.0, thick=gr.GEAR_Z0, color="#e0d0b0")
    tp("pinza_tornillo_B", disc(0, -gr.PIV, 1.5), gz0=-g.T - 2.0, thick=gr.GEAR_Z0 + 3 * g.T + 4, color="#b8bec6")
    A, B = gr.pose(phi)
    hA, hB = gr.hole_abs(gr.holes_A(), "A", phi), gr.hole_abs(gr.holes_B(), "B", phi)
    for k in range(2):
        tp("mandibula_A_%d" % k, A, hA, gz0=gr.GEAR_Z0 + k * g.T, color="#ff8a1f")
        tp("mandibula_B_%d" % k, B, hB, gz0=gr.GEAR_Z0 + k * g.T, color="#ffc266")


def run_3d():
    ok = True
    for tag, th, psi, phi in POSES:
        sc = S.Scene()
        base(sc)
        S.shoulder(sc, th, RHO_REF, turret=False)
        eb.elbow(sc, th, psi)
        gripper_on_forearm(sc, th, psi, phi)
        ok &= sc.build("robot_" + tag, HERE, views=("iso", "right", "top"), size=(1600, 1100))
    return ok


def svgs():
    s1 = Sheet("Base v2 - placas - MDF 3 mm", 350, 350)
    tp, th, tr = b.top_plate()
    part(s1, tp, th, 80, 90, "PLACA SUPERIOR x1 (servo J1 + paredes)", rects=tr)
    bp, bh, br = b.bottom_plate()
    part(s1, bp, bh, 250, 90, "PLACA INFERIOR x1", rects=br)
    part(s1, b.turret_disc(), b.turret_holes(), 70, 235, "TORRETA x1 (disco r=60)", rects=b.turret_slots())
    part(s1, b.brace_plate(), [], 230, 215, "TRAVESANO x1 (une las mejillas, pasa por las ranuras)")
    part(s1, b.gripper_plate(), b.gripper_plate_holes(), 255, 300, "PLACA DE LA PINZA CON CUELLO x1", rects=[b.gripper_plate_window()])
    s1.label(5, 8, "Rojo = corte, azul = grabado. 1:1 mm. Ranuras de pared 20.1 x 3.1. Agujeros de la torreta: 4 patines M3, cuerno J1 (centro + 4).", 3.0)
    s1.save(os.path.join(HERE, "corte_mdf_3mm_base_1.svg"))
    s2 = Sheet("Base v2 - paredes - MDF 3 mm", 350, 200)
    part(s2, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), [], 90, 50, "PARED FRONTAL x1")
    part(s2, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), b.CABLE_HOLE, 90, 110, "PARED TRASERA x1 (agujero de cables)")
    part(s2, b.wall_panel(b.WALL_HALF_SIDE, b.SIDE_TABS), [], 255, 50, "PARED IZQUIERDA x1")
    part(s2, b.wall_panel(b.WALL_HALF_SIDE, b.SIDE_TABS), [], 255, 110, "PARED DERECHA x1")
    s2.label(5, 190, "Las paredes (z -30..-14) llevan lenguetas de 3 mm que cruzan ambas placas; la altura del dibujo es z.", 3.0)
    s2.save(os.path.join(HERE, "corte_mdf_3mm_base_2.svg"))


if __name__ == "__main__":
    svgs()
    print("svg ok")
    sys.exit(0 if ("--no3d" in sys.argv or run_3d()) else 1)
