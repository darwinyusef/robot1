"""Pinza v2: 1 servo SG90/MG90S + 2 engranajes involutos (mandibulas contra-rotantes). MDF 3 mm.

Uso:  python -I gripper.py
Salida (en esta carpeta):
  gripper_report.txt                      verificacion numerica (engrane, apertura, contacto de puntas)
  gripper_script.json / gripper_*.sc      modelo 3D (SolidCraft) en 3 poses: cerrada, media, abierta
  gripper_*.png                           capturas
  corte_mdf_3mm_pinza.svg                 plancha de corte laser (1:1, mm)

Sistema de coordenadas (vista superior, eje de la pinza = +X):
  pivote A (servo)  = (0, +PIV)      pivote B (libre) = (0, -PIV)      PIV = radio primitivo (engranes 1:1)
  Z = 0 es la cara superior de la placa base; la placa ocupa Z in [-T, 0].
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = r"I:\SolidCraft\solidcraft-cli.exe"

# ------------------------------------------------------------------ parametros
T = 3.0                       # espesor MDF
M, Z = 2.0, 16                # modulo y dientes (1:1)
PA = 20.0                     # angulo de presion
BACKLASH = 0.10               # holgura de diseno (el kerf del laser anade ~0.2 mm mas)
RP = M * Z / 2.0              # radio primitivo = 16
PIV = RP                      # pivotes a +-16 mm del eje (distancia entre centros = 32)
ADD, DED = 0.85 * M, 1.25 * M  # addendum / dedendum

PHI_MAX = 40.0                # giro maximo de cada mandibula (= recorrido del servo, 1:1)
PHI_MID = 20.0                # pose en la que las almohadillas quedan paralelas
TIP_GAP = 0.6                 # separacion entre puntas con la pinza cerrada
S_MARGIN = 22.0               # margen angular del sector dentado (grados)

RH = 11.5                     # radio del cubo
W0, W1, W2 = 10.0, 9.0, 7.0   # ancho del dedo: base, codo, punta
L1, LP = 26.0, 26.0           # tramo recto y almohadilla
C0 = 0.0                      # fase de dientes (mandibula A, rad)

# servo SG90 / MG90S (verificar con calibre)
SV_L, SV_W, SV_H = 22.8, 12.2, 22.7
SV_TAB_L, SV_TAB_T = 32.5, 2.5
SV_SHAFT_FROM_END = 6.0
SV_BELOW = 15.9               # cuerpo por debajo de la cara inferior de las orejas
SV_TAB_HOLE_INSET = 2.4
GEAR_Z0 = 8.0                 # cara inferior de los engranes sobre la placa (cuerpo servo sobresale 6.8 + holgura de cuerno)
HORN_HOLE_R, HORN_HOLE_D = 8.0, 1.8
CENTER_HOLE_A, CENTER_HOLE_B = 7.6, 3.2


# ------------------------------------------------------------------ geometria basica
def inv(a):
    return math.tan(a) - a


def rot(pts, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def shift(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def mirror_y(pts):
    return [(x, -y) for x, y in reversed(pts)]     # invertir orden para seguir en sentido antihorario


def area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def inside(P, poly):
    """P: Nx2 array; poly: lista de puntos. Devuelve mascara booleana (rayo hacia +x)."""
    x, y = P[:, 0], P[:, 1]
    res = np.zeros(len(P), bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if y1 == y2:
            continue
        cond = (y1 > y) != (y2 > y)
        xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        res ^= cond & (x < xin)
    return res


def overlap_area(a, b, step=0.1):
    ax0, ax1 = min(p[0] for p in a), max(p[0] for p in a)
    ay0, ay1 = min(p[1] for p in a), max(p[1] for p in a)
    bx0, bx1 = min(p[0] for p in b), max(p[0] for p in b)
    by0, by1 = min(p[1] for p in b), max(p[1] for p in b)
    x0, x1, y0, y1 = max(ax0, bx0), min(ax1, bx1), max(ay0, by0), min(ay1, by1)
    if x0 >= x1 or y0 >= y1:
        return 0.0
    xs = np.arange(x0, x1, step)
    ys = np.arange(y0, y1, step)
    G = np.array([(x, y) for x in xs for y in ys])
    both = inside(G, a) & inside(G, b)
    return float(both.sum()) * step * step


def y_at_x(poly, x):
    """valores de y donde la vertical x=cte corta el contorno."""
    ys = []
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (x1 - x) * (x2 - x) < 0:
            ys.append(y1 + (y2 - y1) * (x - x1) / (x2 - x1))
    return ys


def min_dist(a, b):
    """distancia minima vertice-a-arista entre dos poligonos (aprox. suficiente, puntos densificados)."""
    def dense(p, d=0.25):
        out = []
        for i in range(len(p)):
            x1, y1 = p[i]
            x2, y2 = p[(i + 1) % len(p)]
            n = max(1, int(math.hypot(x2 - x1, y2 - y1) / d))
            for k in range(n):
                out.append((x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n))
        return np.array(out)
    A, B = dense(a), dense(b)
    d = np.sqrt(((A[:, None, :] - B[None, :, :]) ** 2).sum(-1))
    return float(d.min())


# ------------------------------------------------------------------ dientes involutos
def gear_teeth(centers, nfl=7):
    """contorno (antihorario) de los dientes cuyos centros angulares (rad) se dan; del pie inicial al pie final."""
    rp = RP
    rb = rp * math.cos(math.radians(PA))
    ra, rr = rp + ADD, rp - DED
    ap = math.radians(PA)
    half_p = (math.pi * M / 2 - BACKLASH) / (2 * rp)

    def half(r):
        return half_p + inv(ap) - inv(math.acos(min(1.0, rb / r)))

    rs = np.linspace(max(rb, rr + 1e-9), ra, nfl)
    pol = lambda r, a: (r * math.cos(a), r * math.sin(a))
    pts, prev = [], None
    for c in centers:
        hb = half(rs[0])
        if prev is not None:
            pts.append(pol(rr, 0.5 * (prev + c - hb)))
        pts.append(pol(rr, c - hb))
        for r in rs:
            pts.append(pol(r, c - half(r)))
        for r in rs[::-1]:
            pts.append(pol(r, c + half(r)))
        pts.append(pol(rr, c + hb))
        prev = c + hb
    return pts


def jaw_geometry(psi0, c0):
    """mandibula tipo A en su marco local (pivote en el origen, dedo hacia +x, cara interior = -y).
    Devuelve contorno antihorario, el punto interior de la punta y los angulos."""
    p = 2 * math.pi / Z
    a_lo = math.radians(-90 + math.degrees(psi0) - PHI_MAX - S_MARGIN)
    a_hi = math.radians(-90 + math.degrees(psi0) + S_MARGIN)
    k0 = math.ceil((a_lo - c0) / p)
    k1 = math.floor((a_hi - c0) / p)
    centers = [c0 + k * p for k in range(k0, k1 + 1)]
    teeth = gear_teeth(centers)

    delta = psi0 - math.radians(PHI_MID)
    n1 = (0.0, 1.0)
    n2 = (-math.sin(delta), math.cos(delta))
    P1 = (L1, 0.0)
    P2 = (L1 + LP * math.cos(delta), LP * math.sin(delta))
    h0, h1, h2 = W0 / 2, W1 / 2, W2 / 2
    x0 = math.sqrt(RH ** 2 - h0 ** 2)
    k = 1.0 / (1.0 + (n1[0] * n2[0] + n1[1] * n2[1]))
    mit = ((n1[0] + n2[0]) * k, (n1[1] + n2[1]) * k)
    bot0, top0 = (x0, -h0), (x0, h0)
    botB = (P1[0] - h1 * mit[0], P1[1] - h1 * mit[1])
    topB = (P1[0] + h1 * mit[0], P1[1] + h1 * mit[1])
    # cara interior (la que agarra) con ancho constante h1 -> paralela al tramo; el afinado va por la cara exterior
    botT = (P2[0] - h1 * n2[0], P2[1] - h1 * n2[1])
    topT = (P2[0] + (W2 - h1) * n2[0], P2[1] + (W2 - h1) * n2[1])

    th_t = math.atan2(h0, x0)
    th_s = math.atan2(teeth[0][1], teeth[0][0]) % (2 * math.pi)
    arc = [(RH * math.cos(a), RH * math.sin(a)) for a in np.linspace(th_t, th_s, 40)][1:]   # [0] == top0
    poly = [bot0, botB, botT, topT, topB, top0] + arc + teeth
    return poly, botT


def solve_psi0():
    """angulo de reposo del dedo para que, con la pinza cerrada, las puntas queden a TIP_GAP."""
    lo, hi = 0.0, math.radians(40)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        _, botT = jaw_geometry(mid, C0)
        x, y = botT
        y_abs = PIV - x * math.sin(mid) + y * math.cos(mid)
        if y_abs > TIP_GAP / 2:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


PSI0 = solve_psi0()
PA_, _ = jaw_geometry(PSI0, C0)                                     # mandibula A (local)
PB_ = mirror_y(jaw_geometry(PSI0, C0 + math.pi / Z)[0])             # mandibula B: espejo con dientes a media paso


def holes_A():
    hs = [(0.0, 0.0, CENTER_HOLE_A)]
    for k in range(4):
        a = math.radians(45 + 90 * k)
        hs.append((HORN_HOLE_R * math.cos(a), HORN_HOLE_R * math.sin(a), HORN_HOLE_D))
    return hs


def holes_B():
    return [(0.0, 0.0, CENTER_HOLE_B)]


def pose(phi_deg):
    """contornos absolutos de A y B para un giro phi (grados, 0 = cerrada)."""
    phi = math.radians(phi_deg)
    A = shift(rot(PA_, -PSI0 + phi), 0.0, PIV)
    B = shift(rot(PB_, PSI0 - phi), 0.0, -PIV)
    return A, B


def hole_abs(hs, which, phi_deg):
    phi = math.radians(phi_deg)
    out = []
    for (u, v, d) in hs:
        if which == "A":
            (x, y), = shift(rot([(u, v)], -PSI0 + phi), 0.0, PIV)
        else:
            (x, y), = shift(rot([(u, -v)], PSI0 - phi), 0.0, -PIV)
        out.append((x, y, d))
    return out


# ------------------------------------------------------------------ placa base
PLATE = dict(x0=-30.0, x1=24.0, y0=-26.0, y1=26.0)
BODY_X0, BODY_X1 = -(SV_L - SV_SHAFT_FROM_END), SV_SHAFT_FROM_END        # cuerpo del servo en X
WIN = (BODY_X0 - 0.3, BODY_X1 + 0.3, PIV - SV_W / 2 - 0.3, PIV + SV_W / 2 + 0.3)
TAB_X0 = 0.5 * (BODY_X0 + BODY_X1) - SV_TAB_L / 2
TAB_X1 = TAB_X0 + SV_TAB_L
PLATE_HOLES = ([(TAB_X0 + SV_TAB_HOLE_INSET, PIV, 2.2), (TAB_X1 - SV_TAB_HOLE_INSET, PIV, 2.2),
                (0.0, -PIV, 3.2)]
               + [(-26.0, 20.0, 3.2), (-26.0, -20.0, 3.2)])


# ------------------------------------------------------------------ verificacion
def verify():
    lines = []
    ok = True

    def log(s):
        lines.append(s)
        print(s)

    log("PINZA v2  m=%.1f z=%d  entre centros=%.1f mm  psi0=%.2f deg  backlash=%.2f mm" % (M, Z, 2 * PIV, math.degrees(PSI0), BACKLASH))
    log("area A=%.1f  area B=%.1f mm2 (positivas = antihorario)" % (area(PA_), area(PB_)))
    for nm, poly in (("A", PA_), ("B", PB_)):
        if area(poly) <= 0:
            ok = False
            log("ERROR: contorno %s no es antihorario/simple" % nm)

    # agujeros dentro del contorno
    for nm, poly, hs in (("A", PA_, holes_A()), ("B", PB_, holes_B())):
        P = np.array([(u, v) for (u, v, d) in hs])
        # B esta en marco espejo -> los agujeros (0,0) no cambian
        if not inside(P, poly).all():
            ok = False
            log("ERROR: agujero de %s fuera del contorno" % nm)

    log("")
    log(" phi   solape A/B (mm2)   dist.min A-B (mm)   apertura entre puntas (mm)   ancho almohadilla (mm)")
    worst = 0.0
    tip_closed = None
    for phi in range(0, int(PHI_MAX) + 1, 5):
        A, B = pose(phi)
        ov = overlap_area(A, B, 0.1)
        dm = min_dist(A, B)
        tipA = min(p[1] for p in A if p[0] > L1 + 10)
        tipB = max(p[1] for p in B if p[0] > L1 + 10)
        # ancho de almohadilla: separacion de las caras interiores a la altura x = L1+LP/2
        xs_pad = L1 + LP * 0.5
        ya, yb = y_at_x(A, xs_pad), y_at_x(B, xs_pad)
        pw = (min(ya) - max(yb)) if ya and yb else float("nan")
        log("%4d   %14.2f   %17.2f   %24.2f   %20.2f" % (phi, ov, dm, tipA - tipB, pw))
        worst = max(worst, ov)
        if phi == 0:
            tip_closed = tipA - tipB
    if worst > 0.5:
        ok = False
        log("ERROR: los engranes interfieren (solape > 0.5 mm2)")
    if tip_closed is not None and tip_closed < 0:
        ok = False
        log("ERROR: las puntas se cruzan con la pinza cerrada")
    log("")
    log("servo: eje en (0, %.1f); ventana de placa x[%.1f, %.1f] y[%.1f, %.1f]; orejas x[%.2f, %.2f]"
        % (PIV, WIN[0], WIN[1], WIN[2], WIN[3], TAB_X0, TAB_X1))
    log("alzado: engranes z=[%.1f, %.1f] sobre la placa; separador del pivote B = %.1f mm" % (GEAR_Z0, GEAR_Z0 + 2 * T, GEAR_Z0))
    log("RESULTADO: %s" % ("OK" if ok else "FALLA"))
    with open(os.path.join(HERE, "gripper_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return ok


# ------------------------------------------------------------------ modelo 3D
def build_steps(phi_deg):
    steps = []

    def cmd(c, **p):
        steps.append({"command": c, "params": p})

    def plane(z):
        return {"origin": [0, 0, z], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}

    def r4(p):
        return [round(p[0], 4), round(p[1], 4)]

    def extrude_poly(name, z, polys, holes, thickness, rects=()):
        cmd("sketch.create", plane=plane(z))
        for poly in polys:
            cmd("sketch.line", points=[r4(p) for p in poly], closed=True)
        for (x0, y0, x1, y1) in rects:
            cmd("sketch.rectangle.two_point", p0=[x0, y0], p1=[x1, y1])
        for (x, y, d) in holes:
            cmd("sketch.circle.center", center=[round(x, 4), round(y, 4)], diameter=d)
        cmd("sketch.finish")
        cmd("solid.extrude", distance=thickness, body_name=name, operation="new")

    colors = {}
    MDF, JA, JB, SERVO, STEEL = "#c8a165", "#ff8a1f", "#ffc266", "#202428", "#b8bec6"

    # placa base
    extrude_poly("placa_base", -T, [[(PLATE["x0"], PLATE["y0"]), (PLATE["x1"], PLATE["y0"]),
                                     (PLATE["x1"], PLATE["y1"]), (PLATE["x0"], PLATE["y1"])]],
                 PLATE_HOLES, T, rects=[(WIN[0], WIN[2], WIN[1], WIN[3])])
    colors["placa_base"] = (MDF, 1.0)

    # servo
    cmd("solid.box", length=SV_L, width=SV_W, height=SV_H, corner=[BODY_X0, PIV - SV_W / 2, -SV_BELOW], body_name="servo_cuerpo")
    cmd("solid.box", length=SV_TAB_L, width=SV_W, height=SV_TAB_T, corner=[TAB_X0, PIV - SV_W / 2, 0.0], body_name="servo_orejas")
    cmd("solid.cylinder", diameter=4.8, height=3.5, base=[0, PIV, SV_H - SV_BELOW], axis="Z", body_name="servo_eje")
    cmd("solid.cylinder", diameter=19.0, height=1.0, base=[0, PIV, GEAR_Z0 - 1.0], axis="Z", body_name="cuerno")
    cmd("solid.cylinder", diameter=7.0, height=4.0, base=[0, PIV, GEAR_Z0], axis="Z", body_name="cuerno_cubo")
    for n in ("servo_cuerpo", "servo_orejas", "servo_eje"):
        colors[n] = (SERVO, 1.0)
    colors["cuerno"] = ("#f2f2f2", 1.0)
    colors["cuerno_cubo"] = ("#f2f2f2", 1.0)

    # separador + tornillo del pivote B
    cmd("solid.cylinder", diameter=6.0, height=GEAR_Z0, base=[0, -PIV, 0.0], axis="Z", body_name="separador_B")
    cmd("solid.cylinder", diameter=3.0, height=GEAR_Z0 + 2 * T + 4 + T, base=[0, -PIV, -T - 2.0], axis="Z", body_name="tornillo_B")
    colors["separador_B"] = (STEEL, 1.0)
    colors["tornillo_B"] = (STEEL, 1.0)

    # mandibulas: 2 capas de 3 mm cada una
    A, B = pose(phi_deg)
    hA, hB = hole_abs(holes_A(), "A", phi_deg), hole_abs(holes_B(), "B", phi_deg)
    for k in range(2):
        z = GEAR_Z0 + k * T
        extrude_poly("mandibula_A_%d" % (k + 1), z, [A], hA, T)
        extrude_poly("mandibula_B_%d" % (k + 1), z, [B], hB, T)
        colors["mandibula_A_%d" % (k + 1)] = (JA, 1.0)
        colors["mandibula_B_%d" % (k + 1)] = (JB, 1.0)

    for n, (c, o) in colors.items():
        cmd("appearance.assign", bodies=[n], color=c, opacity=o)
    return steps


def run_3d():
    ok = True
    for phi, tag in ((0, "cerrada"), (PHI_MID, "media"), (PHI_MAX, "abierta")):
        script = os.path.join(HERE, "gripper_script_%s.json" % tag)
        with open(script, "w", encoding="utf-8") as f:
            json.dump({"commands": build_steps(phi)}, f)
        sc = os.path.join(HERE, "gripper_%s.sc" % tag)
        r = subprocess.run([CLI, "run", script, "--save", sc, "--quiet"], capture_output=True, text=True)
        print(tag, r.returncode, r.stderr[-1200:])
        if r.returncode != 0:
            ok = False
            continue
        for view in (("iso", "iso"), ("top", "top")):
            r = subprocess.run([CLI, "snapshot", "--in", sc, "--out", os.path.join(HERE, "gripper_%s_%s.png" % (tag, view[1])),
                                "--view", view[0], "--width", "1400", "--height", "1000"], capture_output=True, text=True)
            if r.returncode != 0:
                print("snapshot", tag, view, r.stderr[-300:])
    return ok


# ------------------------------------------------------------------ SVG de corte (MDF 3 mm)
def svg_sheet(fname, w=300, h=200):
    cut, eng = [], []

    def path_poly(pts, ox, oy):
        d = "M" + "L".join("%.3f %.3f" % (ox + x, oy - y) for x, y in pts) + "Z"
        cut.append('<path d="%s"/>' % d)

    def circle(x, y, d, ox, oy):
        cut.append('<circle cx="%.3f" cy="%.3f" r="%.3f"/>' % (ox + x, oy - y, d / 2))

    def rect(x0, y0, x1, y1, ox, oy):
        cut.append('<path d="M%.3f %.3fH%.3fV%.3fH%.3fZ"/>' % (ox + x0, oy - y0, ox + x1, oy - y1, ox + x0))

    def label(x, y, s, size=3.5):
        eng.append('<text x="%.2f" y="%.2f" font-size="%.1f" font-family="monospace">%s</text>' % (x, y, size, s))

    # placa base, en reposo (marco del modelo), origen en (ox, oy)
    ox, oy = 40.0, 60.0
    path_poly([(PLATE["x0"], PLATE["y0"]), (PLATE["x1"], PLATE["y0"]), (PLATE["x1"], PLATE["y1"]), (PLATE["x0"], PLATE["y1"])], ox, oy)
    rect(WIN[0], WIN[2], WIN[1], WIN[3], ox, oy)
    for (x, y, d) in PLATE_HOLES:
        circle(x, y, d, ox, oy)
    label(ox + PLATE["x0"], oy - PLATE["y1"] - 3, "PLACA BASE x1")

    # mandibulas en pose cerrada: 2 capas de A y 2 de B
    A0, B0 = pose(0.0)
    hA0, hB0 = hole_abs(holes_A(), "A", 0.0), hole_abs(holes_B(), "B", 0.0)

    def bbox(p):
        return min(q[0] for q in p), min(q[1] for q in p), max(q[0] for q in p), max(q[1] for q in p)

    slots = [(150.0, 60.0), (150.0, 140.0), (230.0, 60.0), (230.0, 140.0)]
    names = [("MANDIBULA A (cuerno) 1/2", A0, hA0), ("MANDIBULA A (cuerno) 2/2", A0, hA0),
             ("MANDIBULA B 1/2", B0, hB0), ("MANDIBULA B 2/2", B0, hB0)]
    for (sx, sy), (nm, poly, hs) in zip(slots, names):
        x0, y0, x1, y1 = bbox(poly)
        ox2, oy2 = sx - x0 - 8, sy + (y0 + y1) / 2          # centra en vertical
        path_poly(poly, ox2, oy2)
        for (x, y, d) in hs:
            circle(x, y, d, ox2, oy2)
        label(sx - 8, sy - (y1 - y0) / 2 - 3, nm)
    label(5, 8, "Pinza v2 - MDF 3 mm - hoja %dx%d. Rojo = corte (0.1 mm), azul = grabado. Escala 1:1 mm." % (w, h), 3.2)
    label(5, 13, "Engranes m=%.1f z=%d. Pegar las 2 capas de cada mandibula con los dientes alineados." % (M, Z), 3.2)

    svg = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" width="%dmm" height="%dmm" viewBox="0 0 %d %d">' % (w, h, w, h),
           "<title>Pinza v2 - MDF 3 mm</title>",
           '<rect id="PLANCHA" x="0" y="0" width="%d" height="%d" fill="none" stroke="#888" stroke-width="0.2" stroke-dasharray="2 2"/>' % (w, h),
           '<g id="CORTE" fill="none" stroke="#ff0000" stroke-width="0.1">'] + cut + ["</g>",
           '<g id="GRABADO" fill="#0000ff" stroke="none">'] + eng + ["</g>", "</svg>"]
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))


if __name__ == "__main__":
    good = verify()
    svg_sheet(os.path.join(HERE, "corte_mdf_3mm_pinza.svg"))
    print("svg ok")
    if "--no3d" not in sys.argv:
        good = run_3d() and good
    sys.exit(0 if good else 1)
