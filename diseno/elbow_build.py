"""Codo v2 - modelo 3D (hombro + servo J3 + manivela + biela + antebrazo) y planchas SVG de corte.

Uso:  python -I elbow_build.py [--no3d]
Salida: arm_{a,b,c}.sc/.png (3 poses), corte_mdf_3mm_codo.svg
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402
import elbow_geom as e      # noqa: E402
import scene as S           # noqa: E402
from shoulder_build import Sheet, part   # noqa: E402

RHO_REF, _ = g.find_phase()
POSES = (("a", 15.0, -60.0), ("b", 45.0, -20.0), ("c", 80.0, 30.0))      # (tag, theta, psi) dentro del rango permitido


def with_d(pose_fn, holes, *a):
    pts = pose_fn([(u, v) for (u, v, _) in holes], *a)
    return [(p[0], p[1], h[2]) for p, h in zip(pts, holes)]


def elbow(sc, theta, psi):
    qz = g.H
    # servo J3 (espejo del J2): orejas sobre la cara interior de la mejilla izq., cuerpo hacia afuera
    sc.box("servo_J3", g.BODY_X0, -(g.Y_C - g.SV_ABOVE) - g.SV_H, qz - g.SV_W / 2, g.SV_L, g.SV_H, g.SV_W, "#202428")
    sc.box("servo_J3_orejas", g.TAB_X0, -g.Y_C, qz - g.SV_W / 2, g.SV_TAB_L, g.SV_TAB_T, g.SV_W, "#202428")
    sc.cyl("servo_J3_eje", 4.8, -(g.Y_C - g.SV_ABOVE), -(g.Y_C - g.SV_ABOVE) + 3.5, 0.0, qz, "#b8bec6")
    sc.cyl("cuerno_J3", 19.0, e.Y_HORN[0], e.Y_HORN[1], 0.0, qz, "#f2f2f2")

    sc.plate("manivela", e.Y_CRANK[1], e.crank_pose(e.crank_ply(), psi), with_d(e.crank_pose, e.CRANK_HOLES, psi), color="#ff8a1f")
    sc.plate("biela", e.Y_ROD[1], e.rod_pose(e.rod_ply(), theta, psi), with_d(e.rod_pose, e.ROD_HOLES, theta, psi), color="#35c46a")
    fl = with_d(e.forearm_pose, e.FA_HOLES_L, theta, psi)
    fr = with_d(e.forearm_pose, e.FA_HOLES_R, theta, psi)
    sc.plate("antebrazo_izq", e.Y_FA_L[1], e.forearm_pose(e.forearm_left_ply(), theta, psi), fl, color="#b05cff")
    sc.plate("antebrazo_der", e.Y_FA_R[1], e.forearm_pose(e.forearm_right_ply(), theta, psi), fr, color="#b05cff")

    ex, ez = e.elbow_pt(theta)
    u = math.radians(psi + 180.0)
    sx = e.pt_forearm(theta, psi, e.SPACER_X)
    sc.cyl("pasador_codo", 3.0, -13.0, 16.5, ex, ez, "#b8bec6")
    sc.cyl("pasador_manivela", 3.0, -13.0, -5.2, e.RC * math.cos(u), g.H + e.RC * math.sin(u), "#b8bec6")
    sc.cyl("pasador_palanca", 3.0, -13.0, -5.2, ex + e.RC * math.cos(u), ez + e.RC * math.sin(u), "#b8bec6")
    sc.cyl("tubo_separador", 6.0, -9.0, 12.5, sx[0], sx[1], "#e0d0b0")
    sc.cyl("perno_separador", 3.0, -13.0, 16.5, sx[0], sx[1], "#b8bec6")


def run_3d():
    ok = True
    for tag, th, psi in POSES:
        sc = S.Scene()
        S.shoulder(sc, th, RHO_REF)
        elbow(sc, th, psi)
        ok &= sc.build("arm_" + tag, HERE, views=("iso", "right", "top"))
    return ok


def svg():
    s = Sheet("Codo v2 - MDF 3 mm")
    part(s, e.crank_ply(), e.CRANK_HOLES, 40, 40, "MANIVELA x1")
    part(s, e.rod_ply(), e.ROD_HOLES, 40, 80, "BIELA x1")
    part(s, e.forearm_left_ply(), e.FA_HOLES_L, 70, 130, "ANTEBRAZO IZQ x1 (con palanca)")
    part(s, e.forearm_right_ply(), e.FA_HOLES_R, 70, 170, "ANTEBRAZO DER x1")
    s.label(5, 8, "Rojo = corte. 1:1 mm. Tubo separador: 21.5 mm entre placas (anillos de MDF o tubo). Ranura 3.1 mm abierta al frente: puente de la pinza.", 3.0)
    s.save(os.path.join(HERE, "corte_mdf_3mm_codo.svg"))


if __name__ == "__main__":
    svg()
    print("svg ok")
    sys.exit(0 if ("--no3d" in sys.argv or run_3d()) else 1)
