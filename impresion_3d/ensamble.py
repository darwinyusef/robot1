"""Robot completo ensamblado (version impresion 3D) con solidcraft-cli.

  python3 ensamble.py            -> ensamble/robot_{a,b,c}.sc + .png (iso, right, top, front) y robot_a.3mf
  python3 ensamble.py a          -> solo la pose a

Une en una sola escena: caja, tapa, torreta (las 3 con la geometria de generar_stl.py, ya movidas a su sitio),
pinza con el servo ARRIBA (placa + mandibulas de 6 mm + separador) y el resto de piezas planas del brazo, mas
servos, rodamientos y tornillos. No modifica nada de ../diseno.
"""
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True
import generar_stl as G   # noqa: E402  (fija las holguras FDM antes de importar los modulos de ../diseno)

g, e, gr, b = G.g, G.e, G.gr, G.b
import scene as S          # noqa: E402
import elbow_build as eb   # noqa: E402
import base_build as bb    # noqa: E402

S.CLI = G.CLI
OUT = os.path.join(G.HERE, "ensamble")
POSES = (("a", 45.0, -30.0, 20.0), ("b", 20.0, -40.0, 40.0), ("c", 75.0, 20.0, 0.0))
PLA = "#e8e4d8"
PLA2 = "#f2a33a"
SKIP = ("placa_inf", "placa_sup", "pared_frontal", "pared_trasera", "pared_izq", "pared_der", "torreta")


class PrintScene(S.Scene):
    """igual que Scene pero sin las piezas de MDF que aqui se reemplazan por las impresas."""

    def pplate(self, name, *a, **k):
        if name in SKIP or (name.startswith("rueda_") and "oreja" in name):
            return
        k["color"] = PLA
        super().pplate(name, *a, **k)

    def plate(self, name, *a, **k):
        if name in SKIP:
            return
        k["color"] = PLA
        super().plate(name, *a, **k)


def disc(cx, cy, r, n=28):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def printed_base(sc):
    sc.steps += G.pieza_caja() + [G.cmd("solid.move", bodies=["caja_base"], translate=[0, 0, -G.ZO])]
    sc.steps += G.pieza_placa_superior() + [G.cmd("solid.move", bodies=["placa_superior"], translate=[0, 0, b.Z_TOP[0]])]
    sc.steps += G.pieza_torreta() + [G.cmd("solid.move", bodies=["torreta"], axis=[1, 0, 0], angle="180 deg")]
    for n in ("caja_base", "placa_superior"):
        sc.colors[n] = (PLA, 1.0)
    sc.colors["torreta"] = ("#9aa0a8", 1.0)


def printed_gripper(sc, theta, psi, phi):
    """pinza con el servo arriba: orejas sobre la placa, cuerpo arriba, eje hacia abajo, mandibulas de 6 mm debajo."""
    ex, ez = e.elbow_pt(theta)
    p = math.radians(psi)
    xd, n = (math.cos(p), 0.0, math.sin(p)), (-math.sin(p), 0.0, math.cos(p))
    yc, x0 = e.FA_YC, b.GOFF

    def tp(name, poly, holes=(), rects=(), gz0=0.0, thick=g.T, color=PLA):
        o = (ex + x0 * xd[0] + (gz0 + 1.5) * n[0], 0.0, ez + x0 * xd[2] + (gz0 + 1.5) * n[2])
        sc.pplate(name, o, xd, (0, 1, 0), [(u, v + yc) for u, v in poly],
                  [(u, v + yc, d + G.HOLE_ADD) for u, v, d in holes], [(a, c + yc, d_, f + yc) for a, c, d_, f in rects],
                  color=color, thick=thick)

    box = lambda x0_, x1_: [(x0_, gr.PIV - gr.SV_W / 2), (x1_, gr.PIV - gr.SV_W / 2), (x1_, gr.PIV + gr.SV_W / 2), (x0_, gr.PIV + gr.SV_W / 2)]
    tp("pinza_placa", b.gripper_plate(), b.gripper_plate_holes(), [b.gripper_plate_window()], -g.T, g.T)
    tp("pinza_servo", box(gr.BODY_X0, gr.BODY_X1), gz0=-5.0, thick=gr.SV_H, color="#202428")
    tp("pinza_orejas", box(gr.TAB_X0, gr.TAB_X1), gz0=0.0, thick=gr.SV_TAB_T, color="#202428")
    tp("pinza_eje", disc(0, gr.PIV, 2.4), gz0=-8.5, thick=3.5, color="#b8bec6")
    tp("pinza_cuerno", disc(0, gr.PIV, 9.5), gz0=G.JAW_TOP - 1.0, thick=1.0, color="#f2f2f2")
    tp("pinza_separador", disc(0, -gr.PIV, 3.0), gz0=G.JAW_TOP, thick=G.SPACER_H, color="#e0d0b0")
    tp("pinza_tornillo_B", disc(0, -gr.PIV, 1.5), gz0=G.JAW_TOP - G.JAW_T - 1.0, thick=G.JAW_T + G.SPACER_H + 4.0, color="#b8bec6")
    A, B = gr.pose(phi)
    tp("mandibula_A", A, gr.hole_abs(gr.holes_A(), "A", phi), gz0=G.JAW_TOP - G.JAW_T, thick=G.JAW_T, color=PLA2)
    tp("mandibula_B", B, gr.hole_abs(gr.holes_B(), "B", phi), gz0=G.JAW_TOP - G.JAW_T, thick=G.JAW_T, color=PLA2)


def build(tag, theta, psi, phi):
    sc = PrintScene()
    bb.base(sc)
    printed_base(sc)
    S.shoulder(sc, theta, bb.RHO_REF, turret=False)
    eb.elbow(sc, theta, psi)
    printed_gripper(sc, theta, psi, phi)
    return sc.build("robot_" + tag, OUT, views=("iso", "right", "top", "front"), size=(1600, 1100))


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    ok = True
    for tag, th, psi, phi in POSES:
        if argv and tag not in argv:
            continue
        ok &= build(tag, th, psi, phi)
    sc = os.path.join(OUT, "robot_a.sc")
    if ok and os.path.exists(sc) and (not argv or "a" in argv):
        r = subprocess.run([G.CLI, "run", "--in", sc, "--out", os.path.join(OUT, "robot_a.3mf"), "--quiet"], capture_output=True, text=True)
        print("3mf", r.returncode, r.stderr[-200:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
