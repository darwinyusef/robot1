"""Codo v2 - verificacion: colisiones por capas (y) en el barrido theta x psi, zona sin control del paralelogramo, par y biela.

Uso:  python -I elbow_check.py   (escribe elbow_report.txt)
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402
import elbow_geom as e      # noqa: E402

DENS = 0.75e-3
FLOOR_Z = -33.0         # mesa: 33 mm bajo la tapa de la torreta (base de la fase 4: placa inf. + paredes + placa sup.)
GRIP_LEN = 92.0         # alcance de la pinza desde el extremo del antebrazo (fase 4: puente + pinza)
SERVO_STALL = {"SG90": 1.8, "MG90S": 2.2}
RHO_REF, _ = g.find_phase()
SV_ZH = g.SV_W / 2


def circ(cx, cz, r, n=14):
    return [(cx + r * math.cos(2 * math.pi * k / n), cz + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def rect(x0, z0, x1, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def bbox_hit(a, b, pad=0.8):
    ax = [p[0] for p in a]; az = [p[1] for p in a]; bx = [p[0] for p in b]; bz = [p[1] for p in b]
    return not (max(ax) + pad < min(bx) or max(bx) + pad < min(ax) or max(az) + pad < min(bz) or max(bz) + pad < min(az))


def scene(theta, psi):
    """lista de (nombre, (y0,y1), poligono_abs, grupo). Los pernos llevan en 'grupo' las piezas que atraviesan."""
    qx, qz = g.Q
    ex, ez = e.elbow_pt(theta)
    u = math.radians(psi + 180.0)
    cx, cz = e.RC * math.cos(u), g.H + e.RC * math.sin(u)
    lx, lz = ex + e.RC * math.cos(u), ez + e.RC * math.sin(u)
    sx = e.pt_forearm(theta, psi, e.SPACER_X)
    rho = g.rho_at(theta, RHO_REF)
    P = []
    add = lambda n, y, poly, ok=(): P.append((n, y, poly, set(ok)))
    add("manivela", e.Y_CRANK, e.crank_pose(e.crank_ply(), psi))
    add("biela", e.Y_ROD, e.rod_pose(e.rod_ply(), theta, psi))
    add("anteb_izq", e.Y_FA_L, e.forearm_pose(e.forearm_left_ply(), theta, psi))
    add("anteb_der", e.Y_FA_R, e.forearm_pose(e.forearm_right_ply(), theta, psi))
    add("brazo_der", g.Y_ARM_R, g.arm_pose(g.arm_link_ply(), theta))
    add("sector", g.Y_SECT, g.arm_pose(g.arm_sector_ply(), theta))
    add("brazo_izq", g.Y_ARM_L, g.arm_pose(g.arm_left_plate(), theta))
    add("pinon", (6.0, 12.0), g.pinion_pose(g.pinion(), rho))
    add("cuerno_J2", (12.0, 13.0), circ(qx, qz, 9.5, 20))
    add("cuerno_J3", e.Y_HORN, circ(0.0, g.H, 9.5, 20))
    add("servo_J2", (13.2, 35.9), rect(qx + g.BODY_X0, qz - SV_ZH, qx + g.BODY_X1, qz + SV_ZH))
    add("servo_J3", (-35.9, -13.2), rect(g.BODY_X0, g.H - SV_ZH, g.BODY_X1, g.H + SV_ZH))
    add("pern_S", (-7.0, 26.0), circ(0.0, g.H, 1.5), ("brazo_der", "sector", "brazo_izq"))
    add("pern_E", (-13.0, 16.5), circ(ex, ez, 1.5), ("anteb_izq", "anteb_der", "brazo_der", "brazo_izq"))
    add("pern_manivela", (-13.0, -5.2), circ(cx, cz, 1.5), ("manivela", "biela"))
    add("pern_palanca", (-13.0, -5.2), circ(lx, lz, 1.5), ("biela", "anteb_izq"))
    add("pern_sep", (-13.0, 16.5), circ(sx[0], sx[1], 1.5), ("anteb_izq", "anteb_der"))
    add("tubo_sep", (-9.0, 12.5), circ(sx[0], sx[1], 3.0), ("anteb_izq", "anteb_der"))
    return P


# pares que se tocan a proposito (engrane o contacto en el mismo plano que se verifica aparte)
IGNORE = {frozenset(("pinon", "sector")), frozenset(("pinon", "brazo_der")), frozenset(("cuerno_J2", "pinon")),
          frozenset(("pern_sep", "tubo_sep")), frozenset(("pern_S", "cuerno_J3"))}


def collisions(theta, psi, near=0.6):
    P = scene(theta, psi)
    bad = []
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            n1, y1, p1, ok1 = P[i]; n2, y2, p2, ok2 = P[j]
            if frozenset((n1, n2)) in IGNORE or n2 in ok1 or n1 in ok2:
                continue
            if min(y1[1], y2[1]) - max(y1[0], y2[0]) <= 0.05:
                continue
            if not bbox_hit(p1, p2):
                continue
            if g.overlap_area(p1, p2, 0.25) > 0.1 or g.min_dist(p1, p2) < near:
                bad.append("%s-%s" % (n1, n2))
    tip = e.pt_forearm(theta, psi, e.L2 + GRIP_LEN)                # extremo de la pinza (fija al antebrazo)
    if min(tip[1], e.pt_forearm(theta, psi, e.L2, -e.FA_HW)[1], e.pt_forearm(theta, psi, e.L2, e.FA_HW)[1]) < FLOOR_Z:
        bad.append("suelo")
    return bad


def main():
    out, ok = [], True

    def log(s=""):
        out.append(s)
        print(s)

    log("CODO v2  manivela RC=%.0f  biela %.0f  antebrazo L2=%.0f  limites rel=psi-theta: %.0f..%.0f" % (e.RC, g.L1, e.L2, e.REL_MIN, e.REL_MAX))
    log("")
    log("mapa de colisiones: filas theta, columnas rel=psi-theta (grados).  . libre   X choque")
    rels = list(range(-150, -19, 10))
    log("theta " + " ".join("%5d" % r for r in rels))
    forb = {}
    for th in range(int(g.THETA_MIN), int(g.THETA_MAX) + 1, 10):
        row = []
        for r in rels:
            b = collisions(th, th + r)
            forb[(th, r)] = b
            row.append("    ." if not b else ("    F" if b == ["suelo"] else "    X"))
        log("%5d " % th + " ".join(row))
    log("(F = solo toca el plano del suelo con la pinza; se resuelve con un limite acoplado por software)")
    hard = [(th, r) for (th, r), b in forb.items() if [n for n in b if n != "suelo"] and e.REL_MIN <= r <= e.REL_MAX]
    if hard:
        ok = False
        log("ERROR: choques dentro de rel %.0f..%.0f: %s" % (e.REL_MIN, e.REL_MAX, [(k, forb[k]) for k in hard[:6]]))
    else:
        log("sin choques de piezas dentro de rel %.0f..%.0f" % (e.REL_MIN, e.REL_MAX))
    outside = sorted({n for (th, r), b in forb.items() if not (e.REL_MIN <= r <= e.REL_MAX) for n in b if n != "suelo"})
    log("choques de piezas fuera del rango (justifican el limite): %s" % (", ".join(outside) or "ninguno"))

    # envolvente de psi permitida por theta (suelo con pinza) y rango total del servo J3
    log("")
    log("theta  psi_min(suelo)  psi_max   rel permitido")
    lo_all, hi_all = 1e9, -1e9
    for th in range(int(g.THETA_MIN), int(g.THETA_MAX) + 1, 10):
        ex, ez = e.elbow_pt(th)
        s = max(-1.0, min(1.0, -(ez - FLOOR_Z) / (e.L2 + GRIP_LEN)))
        psi_lo = max(th + e.REL_MIN, math.degrees(math.asin(s)))
        psi_hi = th + e.REL_MAX
        if psi_lo > psi_hi:
            ok = False
        lo_all, hi_all = min(lo_all, psi_lo), max(hi_all, psi_hi)
        log("%5d  %13.0f  %7.0f   %.0f..%.0f" % (th, psi_lo, psi_hi, psi_lo - th, psi_hi - th))
    log("psi absoluto total: %.0f..%.0f deg = %.0f deg de servo J3 (el servo ofrece 180)" % (lo_all, hi_all, hi_all - lo_all))
    if hi_all - lo_all > 180:
        ok = False
        log("ERROR: el recorrido excede 180 deg")
    log("(comando: psi limitado a [max(theta%+.0f, psi_suelo(theta)), theta%+.0f])" % (e.REL_MIN, e.REL_MAX))

    # factor de par de la biela (cos del angulo entre biela y palanca)
    f_min = min(abs(math.sin(math.radians(r))) for r in (e.REL_MIN, e.REL_MAX))
    log("brazo de palanca util en los limites: |sin(rel)| >= %.2f" % f_min)

    # masas y par
    a1 = lambda poly, holes=(): (g.area(poly) - sum(math.pi * d * d / 4 for (_, _, d) in holes)) * g.T * DENS
    mL = a1(e.forearm_left_ply(), e.FA_HOLES_L)
    mR = a1(e.forearm_right_ply(), e.FA_HOLES_R)
    mRod = a1(e.rod_ply(), e.ROD_HOLES)
    mCr = a1(e.crank_ply(), e.CRANK_HOLES)
    m_spac = 3.0
    log("")
    log("masas (g): placa izq. antebrazo %.1f  placa der. %.1f  biela %.1f  manivela %.1f  separador+tornilleria %.1f" % (mL, mR, mRod, mCr, m_spac))
    m_fa = mL + mR + m_spac
    x_fa = (mL * 0.45 * e.L2 + mR * 0.5 * e.L2 + m_spac * e.SPACER_X) / m_fa
    GRIP, GRIP_X, PAYX = 25.0, e.L2 + 36.0, e.L2 + 80.0       # pinza centrada ~36 mm tras el extremo; carga en las puntas
    for pay in (20.0, 50.0):
        t_e = (m_fa * x_fa + GRIP * GRIP_X + pay * PAYX) / 10.0 / 1000.0                  # kg*cm a psi=0 (peor caso)
        w_f = m_fa + GRIP + pay + 0.5 * mRod
        m_arm = (4.0 * 0 + 15.4 * 0.5 * g.L1 + 0.5 * mRod * 0.0) / 10.0 / 1000.0
        t2 = (m_arm * 1000 * 10 + w_f * g.L1 * math.cos(math.radians(g.THETA_MIN)) + 0.5 * mRod * 0) / 10.0 / 1000.0 / g.RATIO / 0.9
        parts = ["%s: J3 %.0f%%  J2 %.0f%%" % (n, 100 * t_e / s, 100 * t2 / s) for n, s in SERVO_STALL.items()]
        log("carga %2.0f g: par J3 (antebrazo horizontal) %.2f kg*cm, J2 (con antebrazo en el codo) %.2f kg*cm -> %s" % (pay, t_e, t2, "   ".join(parts)))
        f_rod = t_e * 9.80665 * 10.0 / (e.RC * f_min)
        i_min = e.ROD_R * 2 * g.T ** 3 / 12.0
        pcr = math.pi ** 2 * 3000.0 * i_min / g.L1 ** 2
        log("   fuerza en la biela %.1f N; pandeo de Euler (E=3 GPa supuesto) %.0f N -> FS %.1f;  flexion manivela %.1f MPa"
            % (f_rod, pcr, pcr / f_rod, f_rod * e.RC / (g.T * (2 * e.ROD_R) ** 2 / 6.0)))
    log("(J2 ya no carga el peso del antebrazo a su distancia real: el paralelogramo lo traslada al servo J3)")
    log("")
    log("RESULTADO: %s" % ("OK" if ok else "FALLA"))
    with open(os.path.join(HERE, "elbow_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)



