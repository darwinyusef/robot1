"""Base v2 (fase 4) - verificacion: encaje de lenguetas/ranuras, huecos del servo J1, y colisiones 3D del antebrazo+pinza
contra base, torreta, mejillas, travesano y servos, barriendo J1 (guinada), theta y psi.

Uso:  python -I base_check.py   (escribe base_report.txt)
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
import base_geom as b       # noqa: E402

MARGIN = 2.0
YAWS = (0, 15, 30, 45, 60, 75, 90)          # |guinada|; la base es simetrica en x e y
STEP = 4.0


def grid(x0, x1, y0, y1, z0, z1, step=STEP):
    ax = lambda a, c: np.linspace(a, c, max(2, int(math.ceil((c - a) / step)) + 1))
    X, Y, Z = np.meshgrid(ax(x0, x1), ax(y0, y1), ax(z0, z1), indexing="ij")
    return np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)


def body_points():
    """puntos (lx, ly, lz) del antebrazo y la pinza en el marco del antebrazo (lx adelante, lz perpendicular en el plano, ly lateral)."""
    fa = grid(0, e.L2, e.Y_FA_L[0] - 0.0, e.Y_FA_R[1], -e.FA_HW, e.FA_HW)
    cy = e.FA_YC
    body = grid(e.L2 - 4, e.L2 + 50, cy - 26, cy + 26, -18, 13)
    jaws = grid(e.L2 + 50, e.L2 + b.GRIP_REACH, cy - 36, cy + 36, -4, 4)
    return np.vstack([fa, body, jaws])


def inpoly(pts, poly):
    """pts (N,2) dentro del poligono (ray casting)."""
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if y1 == y2:
            continue
        cond = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1)
        inside ^= cond
    return inside


CHEEK = g.cheek_outline()


def hits(theta, psi, yaw_deg, P):
    """devuelve el conjunto de nombres de piezas que chocan (puntos de P en el marco local del antebrazo)."""
    ex, ez = e.elbow_pt(theta)
    p = math.radians(psi)
    xp = ex + P[:, 0] * math.cos(p) - P[:, 2] * math.sin(p)          # radial en el plano del brazo
    zz = ez + P[:, 0] * math.sin(p) + P[:, 2] * math.cos(p)
    yy = P[:, 1]
    a = math.radians(yaw_deg)
    X = xp * math.cos(a) - yy * math.sin(a)
    Y = xp * math.sin(a) + yy * math.cos(a)
    r = np.hypot(X, Y)
    bad = set()
    if (zz < b.TABLE_Z + MARGIN * 0).any():
        bad.add("mesa")
    # torreta (disco r=60, z -3..0) y cuerpo de la base (|x|,|y|<=70, z<=-8.5): todo lo que quede bajo z=0 dentro de ellos
    if ((zz < MARGIN) & (r < b.TURRET_R + MARGIN)).any():
        bad.add("torreta")
    if ((zz < b.Z_TABS[1] + MARGIN) & (np.abs(X) < b.HB + MARGIN) & (np.abs(Y) < b.HB + MARGIN)).any():
        bad.add("base")
    # piezas fijas a la torreta (se evaluan en el plano del brazo, guinada 0)
    if yaw_deg == 0:
        q = np.stack([xp, zz], 1)
        for nm, sgn in (("mejilla_der", 1), ("mejilla_izq", -1)):
            ys = (yy >= g.Y_C - MARGIN) & (yy <= g.Y_C + g.T + MARGIN) if sgn > 0 else (yy <= -g.Y_C + MARGIN) & (yy >= -g.Y_C - g.T - MARGIN)
            if ys.any() and inpoly(q[ys], CHEEK).any():
                bad.add(nm)
        br = (xp > g.BRACE["x0"] - MARGIN) & (xp < g.BRACE["x1"] + MARGIN) & (zz > g.BRACE["z0"] - MARGIN) & (zz < g.BRACE["z1"] + MARGIN) & (np.abs(yy) < g.Y_C + g.T)
        if br.any():
            bad.add("travesano")
        qx, qz = g.Q
        s2 = (yy > 13.2) & (yy < 35.9) & (xp > qx + g.BODY_X0 - MARGIN) & (xp < qx + g.BODY_X1 + MARGIN) & (np.abs(zz - qz) < g.SV_W / 2 + MARGIN)
        s3 = (yy < -13.2) & (yy > -35.9) & (xp > g.BODY_X0 - MARGIN) & (xp < g.BODY_X1 + MARGIN) & (np.abs(zz - g.H) < g.SV_W / 2 + MARGIN)
        if s2.any():
            bad.add("servo_J2")
        if s3.any():
            bad.add("servo_J3")
    return bad


def main():
    out, ok = [], True

    def log(s=""):
        out.append(s)
        print(s)

    log("BASE v2 (fase 4)   placas %.0fx%.0f  torreta r=%.0f  mesa z=%.0f (tapa de la torreta z=0)" % (2 * b.HB, 2 * b.HB, b.TURRET_R, b.TABLE_Z))

    # --- 1. contornos
    from shoulder_check import simple
    for nm, poly in (("placa sup.", b.top_plate()[0]), ("placa inf.", b.bottom_plate()[0]), ("torreta", b.turret_disc()),
                     ("pared fr/tr", b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS)), ("pared lat.", b.wall_panel(b.WALL_HALF_SIDE, b.SIDE_TABS)),
                     ("travesano", b.brace_plate()), ("placa pinza", b.gripper_plate())):
        s = simple(poly)
        ok &= s and g.area(poly) > 0
        log("  contorno %-12s puntos=%3d area=%8.1f mm2 simple=%s" % (nm, len(poly), g.area(poly), s))

    # --- 2. servo J1
    x0, y0, x1, y1 = b.j1_window()
    log("")
    log("servo J1 vertical: ventana %.1f..%.1f x %.1f..%.1f mm, cuerpo z %.1f..%.1f, orejas z %.1f..%.1f sobre la placa superior (z tope %.1f)"
        % (x0, x1, y0, y1, -4.2 - g.SV_H, b.Z_BODY_TOP, b.Z_TABS[0], b.Z_TABS[1], b.Z_TOP[1]))
    inner = b.HB - b.WALL_IN - g.T
    for nm, v in (("ventana en caja", max(abs(x0), abs(x1), abs(y0), abs(y1)) < inner - 4), ):
        ok &= v
        log("  %s: %s" % (nm, v))
    clr_bot = b.Z_BOT[1] - (b.Z_BODY_TOP - g.SV_H)
    log("  holgura cuerpo-placa inferior: %.1f mm   cuerno apoyado bajo la torreta (z %.0f..%.0f), eje del servo asoma %.1f mm sobre el cuerpo"
        % (-clr_bot, b.Z_HORN[0], b.Z_HORN[1], b.Z_HORN[0] - b.Z_BODY_TOP))
    ok &= -clr_bot > 1.0
    # lenguetas de la oreja en la placa y agujeros de la torreta
    th = b.turret_holes()
    for nm, (u, v, d) in (("patin", (35, 35, 6.4)), ):
        pass
    dmin = 1e9
    for (hx, hy, hd) in b.SKIDS:
        for (a0, b0, a1, b1) in [b.j1_window()]:
            dx = max(a0 - hx, 0, hx - a1); dy = max(b0 - hy, 0, hy - b1)
            dmin = min(dmin, math.hypot(dx, dy) - hd / 2)
    log("  patines: distancia minima a la ventana %.1f mm (los patines ruedan sobre la placa superior)" % dmin)
    ok &= dmin > 3

    # --- 3. encaje de lenguetas
    slots = b.wall_slots()
    log("")
    log("ranuras de pared: %d por placa; lenguetas %.0f mm de largo, ranura %.1f x %.1f mm (holgura %.1f)" % (len(slots), b.TAB_LEN, b.TAB_LEN + b.SLOT, g.T + b.SLOT, b.SLOT))
    for (a0, b0, a1, b1) in slots:
        w, h = a1 - a0, b1 - b0
        if not (abs(min(w, h) - (g.T + b.SLOT)) < 1e-6 and abs(max(w, h) - (b.TAB_LEN + b.SLOT)) < 1e-6):
            ok = False
            log("  ERROR ranura mal dimensionada %s" % ((a0, b0, a1, b1),))
        if max(abs(a0), abs(a1), abs(b0), abs(b1)) > b.HB:
            ok = False
            log("  ERROR ranura fuera de la placa")
    # ranuras de mejilla en la torreta y su separacion a otros agujeros
    ts = b.turret_slots()
    hx_min = 1e9
    for (a0, b0, a1, b1) in ts:
        for (hx, hy, hd) in b.turret_holes():
            dx = max(a0 - hx, 0, hx - a1); dy = max(b0 - hy, 0, hy - b1)
            hx_min = min(hx_min, math.hypot(dx, dy) - hd / 2)
    log("ranuras de mejilla en la torreta: %d, separacion minima a otros agujeros %.1f mm" % (len(ts), hx_min))
    ok &= hx_min > 3
    log("travesano: %.0f x %.0f mm, en x %.0f..%.0f, atraviesa ranuras de ambas mejillas" % (2 * (g.Y_C + g.T), g.BRACE["z1"] - g.BRACE["z0"], g.BRACE["x0"], g.BRACE["x1"]))

    # --- 4. puente de la pinza
    pl = b.gripper_plate()
    log("")
    log("puente de la pinza: cuello x %.0f..%.0f mm y +-%.2f mm (ranura del antebrazo %.1f mm abierta al frente) -> placa de la pinza x %.0f..%.0f"
        % (b.NECK_X0, b.PLATE_X0, b.NECK_HW, e.SLOT_H, b.PLATE_X0, gr.PLATE["x1"]))
    slot_len = 26.0
    log("  cuello se inserta %.0f mm en las ranuras del antebrazo; alcance total desde el codo = L2 + %.0f = %.0f mm" % (slot_len, b.GRIP_REACH, e.L2 + b.GRIP_REACH))

    # --- 5. colisiones 3D
    P = body_points()
    log("")
    log("colisiones 3D (%d puntos de muestreo): antebrazo + pinza contra mesa/torreta/base (todas las guinadas) y mejillas/travesano/servos (plano del brazo)" % len(P))
    thetas = list(range(int(g.THETA_MIN), int(g.THETA_MAX) + 1, 10))
    rels = list(range(int(e.REL_MIN), int(e.REL_MAX) + 1, 5))
    log("theta  psi permitido (min..max) en el peor caso de guinada; piezas que limitan")
    lo_all, hi_all = 1e9, -1e9
    lim = {}
    for th in thetas:
        okp, why = [], {}
        for r in rels:
            psi = th + r
            bad = set()
            for yw in YAWS:
                bad |= hits(th, psi, yw, P)
            if bad:
                why[psi] = bad
            else:
                okp.append(psi)
        if not okp:
            ok = False
            log("%5d  SIN POSE LIBRE" % th)
            continue
        # el rango debe ser contiguo
        lo, hi = min(okp), max(okp)
        gaps = [p for p in range(int(lo), int(hi) + 1, 5) if p not in okp]
        lim[th] = (lo, hi)
        lo_all, hi_all = min(lo_all, lo), max(hi_all, hi)
        who = sorted({n for bset in why.values() for n in bset})
        log("%5d  %4.0f .. %4.0f   (rel %4.0f .. %4.0f)  %s%s" % (th, lo, hi, lo - th, hi - th, ",".join(who) or "-", "   HUECOS" if gaps else ""))
        if gaps:
            ok = False
    log("psi absoluto total: %.0f..%.0f = %.0f deg de servo J3 (disponibles 180)" % (lo_all, hi_all, hi_all - lo_all))
    ok &= hi_all - lo_all <= 180
    # el mismo barrido sin guinada: cuanto se gana si solo se trabaja de frente
    lo0 = min(min(p for p in range(int(th + e.REL_MIN), int(th + e.REL_MAX) + 1, 5) if not hits(th, p, 0, P)) for th in thetas
              if any(not hits(th, p, 0, P) for p in range(int(th + e.REL_MIN), int(th + e.REL_MAX) + 1, 5)))
    log("(con guinada 0 el psi minimo seria %.0f; con la base cuadrada la guinada de 45 deg es la mas restrictiva por la diagonal)" % lo0)
    log("limite por software: psi en [psi_min(theta), psi_max(theta)] de la tabla (interpolar), tambien rel en [%.0f, %.0f]" % (e.REL_MIN, e.REL_MAX))

    # --- 6. J1 ---
    log("")
    log("J1: servo vertical directo, recorrido util 180 deg = guinada -90..+90 (cable por el agujero trasero de %.0f mm)" % b.CABLE_HOLE[0][2])
    log("")
    log("RESULTADO: %s" % ("OK" if ok else "FALLA"))
    with open(os.path.join(HERE, "base_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
