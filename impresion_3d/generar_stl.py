"""Version para IMPRESION 3D (FDM) del brazo v2: genera un STL por pieza con solidcraft-cli.

  python3 generar_stl.py            -> stl/*.stl  (usa la geometria de ../diseno en solo lectura: no modifica nada de la version MDF)
  python3 generar_stl.py base       -> solo las piezas cuyo nombre contiene "base"
  python3 generar_stl.py --ver      -> ademas guarda vistas/*.png (iso y planta) con solidcraft-cli snapshot

Misma cinematica, mismos engranes, mismo alcance y mismos limites que la version MDF; cambia como se hacen las piezas:
  - las capas que en MDF eran 2 piezas pegadas (sector, piñon, mandibulas) salen en una sola pieza de 6 mm
  - caja de la base: placa inferior + 4 paredes + 4 postes con rosca en una pieza (sin ranuras ni lengüetas); tapa = placa superior
  - torreta: las 8 orejas de rueda van fundidas al disco (se imprime boca abajo, sin soportes)
  - pinza con el servo ARRIBA: las orejas se apoyan sobre la placa, el cuerpo queda arriba y las mandibulas cuelgan por debajo
  - holguras FDM: agujeros +0.2 mm, ranuras +0.25 mm, juego de engrane 0.30 mm (MDF: 0.10)
Cada pieza se genera ya en su orientacion de impresion (cara de apoyo en z=0).
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DISENO = os.path.join(os.path.dirname(HERE), "diseno")
sys.path.insert(0, DISENO)
import shoulder_geom as g   # noqa: E402
import elbow_geom as e      # noqa: E402
import gripper as gr        # noqa: E402
import base_geom as b       # noqa: E402

CLI = os.environ.get("SOLIDCRAFT_CLI") or shutil.which("solidcraft-cli") or "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli"
OUT = os.path.join(HERE, "stl")
VISTAS = os.path.join(HERE, "vistas")

# ---------------------------------------------------------------- tolerancias FDM
HOLE_ADD = 0.2          # a todos los agujeros
SLOT_FDM = 0.25         # ranuras de lengüeta (MDF: 0.10)
BACKLASH_FDM = 0.30     # juego de los dientes (MDF: 0.10, el laser quitaba otros ~0.2)
g.SLOT = b.SLOT = SLOT_FDM
g.BACKLASH = BACKLASH_FDM
gr.BACKLASH = BACKLASH_FDM
gr.PA_, _ = gr.jaw_geometry(gr.PSI0, gr.C0)
gr.PB_ = gr.mirror_y(gr.jaw_geometry(gr.PSI0, gr.C0 + math.pi / gr.Z)[0])

T = g.T
# pinza con el servo arriba (z=0: cara superior de la placa de la pinza, la placa ocupa [-3, 0])
JAW_TOP = -6.0          # cara superior de las mandibulas: 1 mm de cuerno entre el cuerpo del servo (z -5) y la mandibula
JAW_T = 2 * T           # mandibulas de una sola pieza de 6 mm
SPACER_H = -JAW_TOP - T  # separador del pivote B: de la cara inferior de la placa (-3) a la mandibula (-6) = 3 mm


# ---------------------------------------------------------------- comandos
def cmd(c, **p):
    return {"command": c, "params": p}


def plane(origin, x_dir, y_dir):
    return {"origin": list(origin), "x_dir": list(x_dir), "y_dir": list(y_dir)}


def xy(z):
    return plane((0, 0, z), (1, 0, 0), (0, 1, 0))


def r4(p):
    return [round(p[0], 4), round(p[1], 4)]


def clean(poly):
    out = []
    for p in poly:
        q = r4(p)
        if not out or abs(q[0] - out[-1][0]) > 1e-3 or abs(q[1] - out[-1][1]) > 1e-3:
            out.append(q)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-3 and abs(out[0][1] - out[-1][1]) < 1e-3:
        out.pop()
    return out


def rect(r):
    x0, y0, x1, y1 = r
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def extrude(name, pl, outlines, holes, voids, dist, op="new", hole_add=HOLE_ADD):
    """sketch en el plano pl con contornos, agujeros (x,y,d) y huecos poligonales; los lazos interiores son huecos."""
    s = [cmd("sketch.create", plane=pl)]
    for o in outlines:
        s.append(cmd("sketch.line", points=clean(o), closed=True))
    for v in voids:
        s.append(cmd("sketch.line", points=clean(v), closed=True))
    for (x, y, d) in holes:
        s.append(cmd("sketch.circle.center", center=r4((x, y)), diameter=round(d + hole_add, 3)))
    s.append(cmd("sketch.finish"))
    p = dict(distance=dist, operation=op)
    if op == "new":
        p["body_name"] = name
    s.append(cmd("solid.extrude", **p))
    return s


def flat(name, outline, holes, voids=(), t=T):
    return extrude(name, xy(0), [outline], holes, voids, t)


def circle_ext(name, pl, centers, d, dist, op="join"):
    s = [cmd("sketch.create", plane=pl)]
    for (x, y) in centers:
        s.append(cmd("sketch.circle.center", center=r4((x, y)), diameter=d))
    s.append(cmd("sketch.finish"))
    p = dict(distance=dist, operation=op)
    if op == "new":
        p["body_name"] = name
    s.append(cmd("solid.extrude", **p))
    return s


# ---------------------------------------------------------------- piezas planas del brazo
def pieza_brazo_der():
    """placa derecha del brazo (3 mm) + capa de sector fundida (3 mm): sector y cubo de 6 mm."""
    s = flat("brazo_der_sector", g.arm_link_ply(), g.ARM_HOLES)
    s += extrude("", xy(T - 0.01), [g.arm_sector_ply()], g.ARM_HOLES[:1], [], T + 0.01, op="join")
    return s


def pieza_pinon():
    return flat("pinon", g.pinion(), g.pinion_holes(), t=2 * T)


# ---------------------------------------------------------------- torreta (se imprime boca abajo: la cara superior de la torreta en z=0)
EAR_T = T
EAR_X = b.EAR_GAP / 2 + EAR_T / 2         # centro de cada oreja respecto del eje de la rueda


def pieza_torreta():
    holes = b.turret_holes()
    voids = [rect(r) for r in b.turret_slots()]
    # hueco sobre cada rodamiento: el borde superior del rodamiento queda libre (z -3)
    for (x, y, ax) in b.WHEELS:
        h = b.EAR_GAP / 2
        voids.append(rect((x - h, y - 5.0, x + h, y + 5.0)) if ax == "x" else rect((x - 5.0, y - h, x + 5.0, y + h)))
    s = [cmd("sketch.create", plane=xy(0)),
         cmd("sketch.circle.center", center=[0, 0], diameter=2 * b.TURRET_R)]
    for v in voids:
        s.append(cmd("sketch.line", points=clean(v), closed=True))
    for (x, y, d) in holes:
        s.append(cmd("sketch.circle.center", center=r4((x, y)), diameter=round(d + HOLE_ADD, 3)))
    s += [cmd("sketch.finish"), cmd("solid.extrude", distance=T, operation="new", body_name="torreta")]
    # orejas de rueda: 2 por rueda, planas perpendiculares al eje (que es radial); suben desde la cara de impresion del disco
    wz = T + (b.Z_TURRET[0] - b.WHEEL_Z)       # altura (z impresion) del eje de la rueda: 3 + 4 = 7
    top = T + (b.Z_TURRET[0] - b.EAR_Z0)       # 3 + 7.5 = 10.5
    for (x, y, ax) in b.WHEELS:
        for sgn in (-1, 1):
            if ax == "x":
                pl = plane((x + sgn * EAR_X - EAR_T / 2, 0, 0), (0, 1, 0), (0, 0, 1))   # normal +x
                u0 = y
            else:
                pl = plane((0, y + sgn * EAR_X + EAR_T / 2, 0), (1, 0, 0), (0, 0, 1))   # normal -y
                u0 = x
            s += extrude("", pl, [[(u0 - b.EAR_HALF, T - 0.5), (u0 + b.EAR_HALF, T - 0.5), (u0 + b.EAR_HALF, top), (u0 - b.EAR_HALF, top)]],
                         [(u0, wz, 3.2)], [], EAR_T, op="join")
    return s


# ---------------------------------------------------------------- caja de la base (z=0 = cara de apoyo en la mesa; z de diseño + 33)
ZO = -b.Z_BOT[0]          # 33: z diseño -> z impresion
POST_D, PILOT_D, PILOT_DEEP = 9.0, 2.6, 12.0


def pieza_caja():
    top = b.Z_WALL[1] + ZO                  # 19: borde superior de las paredes (apoyo de la placa superior)
    zb = b.Z_BOT[1] + ZO                    # 3: cara superior de la placa inferior
    s = extrude("caja_base", xy(0), [b.square(b.HB)], [], [], T)
    yo, yi = b.HB - b.WALL_IN, b.HB - b.WALL_IN - T
    # paredes frontal/trasera: plano (x, z) con normal -y
    for y0 in (-yi, yo):
        pl = plane((0, y0, 0), (1, 0, 0), (0, 0, 1))
        s += extrude("", pl, [rect((-b.WALL_HALF_FRONT, zb - 0.5, b.WALL_HALF_FRONT, top))], [], [], T, op="join")
    # laterales: plano (y, z) con normal +x
    for x0 in (-yo, yi):
        pl = plane((x0, 0, 0), (0, 1, 0), (0, 0, 1))
        h = b.WALL_HALF_SIDE + 0.5
        s += extrude("", pl, [rect((-h, zb - 0.5, h, top))], [], [], T, op="join")
    # postes de esquina con piloto M3 (tornillo M3 x 8 de la placa superior)
    corners = [(sx * b.CORNER, sy * b.CORNER) for sx in (-1, 1) for sy in (-1, 1)]
    s += circle_ext("", xy(zb - 0.5), corners, POST_D, top - zb + 0.5)
    s += circle_ext("", xy(top - PILOT_DEEP), corners, PILOT_D, PILOT_DEEP + 1.0, op="cut")
    # paso de cables en la pared trasera (y>0): s=0, z diseño -22
    zc = b.CABLE_HOLE[0][1] + ZO
    s += [cmd("sketch.create", plane=plane((0, yo + 3, 0), (1, 0, 0), (0, 0, 1))),
          cmd("sketch.circle.center", center=[0, round(zc, 3)], diameter=b.CABLE_HOLE[0][2] + HOLE_ADD),
          cmd("sketch.finish"), cmd("solid.extrude", distance=T + 6, operation="cut")]
    return s


def pieza_placa_superior():
    outline, holes, voids = b.top_plate()
    holes = [h for h in holes if h[2] != 9.0] + [(sx * b.CORNER, sy * b.CORNER, 3.2) for sx in (-1, 1) for sy in (-1, 1)]
    return flat("placa_superior", outline, holes, [rect(voids[0])])         # sin las ranuras de las paredes


# ---------------------------------------------------------------- pinza con el servo arriba
def pieza_placa_pinza():
    return flat("placa_pinza", b.gripper_plate(), b.gripper_plate_holes(), [rect(b.gripper_plate_window())])


def pieza_mandibula(which):
    A0, B0 = gr.pose(0.0)
    poly = A0 if which == "A" else B0
    holes = gr.hole_abs(gr.holes_A() if which == "A" else gr.holes_B(), which, 0.0)
    return flat("mandibula_" + which, poly, holes, t=JAW_T)


def pieza_separador():
    s = circle_ext("separador_pinza", xy(0), [(0, 0)], 6.0, SPACER_H, op="new")
    return s + [cmd("sketch.create", plane=xy(-1)), cmd("sketch.circle.center", center=[0, 0], diameter=3.4),
                cmd("sketch.finish"), cmd("solid.extrude", distance=SPACER_H + 2, operation="cut")]


# ---------------------------------------------------------------- seguros (identicos a los de ../diseno/impresion_3d)
def hexpocket(af, z0, depth):
    r = af / math.sqrt(3)
    pts = [[round(r * math.cos(math.radians(60 * k)), 4), round(r * math.sin(math.radians(60 * k)), 4)] for k in range(6)]
    return [cmd("sketch.create", plane=xy(z0)), cmd("sketch.line", points=pts, closed=True), cmd("sketch.finish"),
            cmd("solid.extrude", distance=depth, operation="cut")]


def pieza_seguro():
    s = circle_ext("seguro", xy(0), [(0, 0)], b.CAP_OD, b.CAP_T, op="new")
    s += [cmd("sketch.create", plane=xy(-1)), cmd("sketch.circle.center", center=[0, 0], diameter=g.CAP_HOLE),
          cmd("sketch.finish"), cmd("solid.extrude", distance=b.CAP_T + 2, operation="cut")]
    return s + hexpocket(g.CAP_AF, g.CAP_FLOOR, 3)


def pieza_calzo():
    s = circle_ext("calzo_rodamiento", xy(0), [(0, 0)], b.SHIM_OD, b.SHIM_T, op="new")
    return s + [cmd("sketch.create", plane=xy(-1)), cmd("sketch.circle.center", center=[0, 0], diameter=b.SHIM_ID),
                cmd("sketch.finish"), cmd("solid.extrude", distance=b.SHIM_T + 2, operation="cut")]


PIEZAS = [
    # (archivo, cantidad, funcion, nota de impresion)
    ("01_brazo_der_sector", 1, pieza_brazo_der, "plana, sector hacia arriba"),
    ("02_brazo_izq", 1, lambda: flat("brazo_izq", g.arm_left_plate(), g.ARM_HOLES), "plana"),
    ("03_pinon_J2", 1, pieza_pinon, "plana (6 mm), va en el cuerno del servo J2"),
    ("04_mejilla_der_J2", 1, lambda: flat("mejilla_der", g.cheek_outline(), g.cheek_right_holes(), [rect(r) for r in g.cheek_rects_right()]), "plana, 4 perimetros"),
    ("05_mejilla_izq_J3", 1, lambda: flat("mejilla_izq", g.cheek_outline(), g.cheek_left_holes(), [rect(r) for r in g.cheek_rects_left()]), "plana, 4 perimetros"),
    ("06_travesano", 1, lambda: flat("travesano", b.brace_plate(), []), "plana"),
    ("07_manivela", 1, lambda: flat("manivela", e.crank_ply(), e.CRANK_HOLES), "plana"),
    ("08_biela", 1, lambda: flat("biela", e.rod_ply(), e.ROD_HOLES), "plana"),
    ("09_antebrazo_izq", 1, lambda: flat("antebrazo_izq", e.forearm_left_ply(), e.FA_HOLES_L), "plana"),
    ("10_antebrazo_der", 1, lambda: flat("antebrazo_der", e.forearm_right_ply(), e.FA_HOLES_R), "plana"),
    ("11_torreta", 1, pieza_torreta, "BOCA ABAJO tal como sale en el STL (las orejas de rueda suben); sin soportes"),
    ("12_caja_base", 1, pieza_caja, "tal cual: placa en la cama, paredes y postes hacia arriba; sin soportes"),
    ("13_placa_superior", 1, pieza_placa_superior, "plana"),
    ("14_placa_pinza", 1, pieza_placa_pinza, "plana"),
    ("15_mandibula_A", 1, lambda: pieza_mandibula("A"), "plana (6 mm), va en el cuerno del servo de la pinza"),
    ("16_mandibula_B", 1, lambda: pieza_mandibula("B"), "plana (6 mm)"),
    ("17_separador_pinza", 1, pieza_separador, "plana"),
    ("18_seguro", 20, pieza_seguro, "bolsillo hexagonal hacia arriba, 100 % de relleno"),
    ("19_calzo_rodamiento", 8, pieza_calzo, "plana, 100 % de relleno"),
]


def run(item):
    name, qty, fn, note = item
    steps = fn()
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix=name + "_")
    with os.fdopen(fd, "w") as f:
        json.dump({"commands": steps}, f)
    stl = os.path.join(OUT, name + ".stl")
    r = subprocess.run([CLI, "run", tmp, "--out", stl, "--quiet"], capture_output=True, text=True)
    msg = r.stdout + r.stderr
    if r.returncode == 0 and VER:
        for vista in ("iso", "top"):
            v = subprocess.run([CLI, "snapshot", tmp, "--out", os.path.join(VISTAS, "%s_%s.png" % (name, vista)), "--view", vista,
                                "--width", "900", "--height", "700"], capture_output=True, text=True)
            msg += v.stdout + v.stderr
    os.remove(tmp)
    ok = r.returncode == 0 and os.path.exists(stl)
    return name, ok, msg[-400:]


VER = False


def main(argv):
    global VER
    VER = "--ver" in argv
    argv = [a for a in argv if a != "--ver"]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(VISTAS, exist_ok=True)
    sel = [p for p in PIEZAS if not argv or any(a in p[0] for a in argv)]
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(run, sel))
    bad = 0
    for name, ok, msg in res:
        print(("OK   " if ok else "FALLA"), name, "" if ok else msg)
        bad += not ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
