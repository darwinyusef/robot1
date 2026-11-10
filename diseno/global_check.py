"""Fase 5 - verificacion global del brazo v2: colisiones (capas + 3D + travesano), alcance, par por articulacion,
vuelco de la torreta, inercia de J1 y fuerza de la pinza.

Uso:  python -I global_check.py   (escribe global_report.txt y workspace.svg)
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
import elbow_check as ec    # noqa: E402
import base_check as bc     # noqa: E402
from shoulder_check import poly_props   # noqa: E402

DENS = 0.75e-3                      # g/mm3
G = 9.80665
KGCM = G * 10.0                     # N*mm por kg*cm
SERVO_G = {"SG90": 9.0, "MG90S": 13.4}
STALL = {"SG90": 1.8, "MG90S": 2.2}
EFF_GEAR, EFF_LINK = 0.9, 0.9
THETAS = list(range(int(g.THETA_MIN), int(g.THETA_MAX) + 1, 5))
RELS = list(range(int(e.REL_MIN), int(e.REL_MAX) + 1, 5))
PAYX = e.L2 + 80.0                  # carga en las almohadillas (mm desde el codo)
HW_G = 3.0                          # tornilleria de la pinza (g)
ELBOW_HW_G = 2.0                    # perno del codo y tuercas (g)


# ------------------------------------------------------------------ colisiones
def brace_part():
    br = g.BRACE
    return ("travesano", (-(g.Y_C + g.T), g.Y_C + g.T), ec.rect(br["x0"], br["z0"], br["x1"], br["z1"]), set())


def layer_collisions(theta, psi):
    P = ec.scene(theta, psi) + [brace_part()]
    bad = []
    ign = set(ec.IGNORE) | {frozenset(("pern_S", "travesano"))}
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            n1, y1, p1, ok1 = P[i]; n2, y2, p2, ok2 = P[j]
            if frozenset((n1, n2)) in ign or n2 in ok1 or n1 in ok2:
                continue
            if min(y1[1], y2[1]) - max(y1[0], y2[0]) <= 0.05:
                continue
            if not ec.bbox_hit(p1, p2):
                continue
            # servos J2/J3 se evaluan contra el travesano solo en el plano (estan en y fuera de el)
            if g.overlap_area(p1, p2, 0.25) > 0.1 or g.min_dist(p1, p2) < 0.6:
                bad.append("%s-%s" % (n1, n2))
    return bad


_P = bc.body_points()


def feasible(theta, rel):
    psi = theta + rel
    for yw in bc.YAWS:
        if bc.hits(theta, psi, yw, _P):
            return False
    return not layer_collisions(theta, psi)


# ------------------------------------------------------------------ masas
def m_of(poly, holes=()):
    return (g.area(poly) - sum(math.pi * d * d / 4 for (_, _, d) in holes)) * g.T * DENS


def centroid(poly):
    a, cx, cy = poly_props(poly)
    return cx, cy


def jaw_masses():
    A, B = gr.pose(gr.PHI_MID)
    out = []
    for poly, holes in ((A, gr.holes_A()), (B, gr.holes_B())):
        out.append((2 * m_of(poly, holes), centroid(poly)[0]))        # 2 capas
    return out


def masses(theta, psi, payload, servo_gr="SG90"):
    """devuelve listas (m[g], x, z) absolutas: arm (brazo), fa (antebrazo+pinza+carga, cuelga del codo), crank (manivela, la lleva el J3)."""
    ex, ez = e.elbow_pt(theta)
    arm, fa, crank = [], [], []

    def at_arm(poly, holes):
        pp = g.arm_pose(poly, theta)
        cx, cz = centroid(pp)
        arm.append((m_of(poly, holes), cx, cz))
    at_arm(g.arm_link_ply(), g.ARM_HOLES)
    at_arm(g.arm_sector_ply(), g.ARM_HOLES[:1])
    at_arm(g.arm_left_plate(), g.ARM_HOLES)

    def at_fa(poly, holes):
        pp = e.forearm_pose(poly, theta, psi)
        cx, cz = centroid(pp)
        fa.append((m_of(poly, holes), cx, cz))
    at_fa(e.forearm_left_ply(), e.FA_HOLES_L)
    at_fa(e.forearm_right_ply(), e.FA_HOLES_R)
    sp = e.pt_forearm(theta, psi, e.SPACER_X)
    fa.append((3.0, sp[0], sp[1]))                                       # separador y tornillos
    fa.append((ELBOW_HW_G, ex, ez))
    # biela: mitad en el pasador de la manivela, mitad en el de la palanca
    u = math.radians(psi + 180.0)
    cxp, czp = e.RC * math.cos(u), g.H + e.RC * math.sin(u)
    lxp, lzp = ex + e.RC * math.cos(u), ez + e.RC * math.sin(u)
    mrod = m_of(e.rod_ply(), e.ROD_HOLES)
    crank.append((mrod / 2, cxp, czp))
    fa.append((mrod / 2, lxp, lzp))
    cp = e.crank_pose(e.crank_ply(), psi)
    ccx, ccz = centroid(cp)
    crank.append((m_of(e.crank_ply(), e.CRANK_HOLES), ccx, ccz))
    # pinza
    gp = b.gripper_plate()
    gx, _ = centroid(gp)
    mplate = m_of(gp, b.gripper_plate_holes()) - (gr.WIN[1] - gr.WIN[0]) * (gr.WIN[3] - gr.WIN[2]) * g.T * DENS
    pt = lambda lx, lz=0.0: e.pt_forearm(theta, psi, lx, lz)
    p = pt(gx + b.GOFF)
    fa.append((mplate, p[0], p[1]))
    for m, jx in jaw_masses():
        p = pt(jx + b.GOFF, 3.0)
        fa.append((m, p[0], p[1]))
    p = pt(0.5 * (gr.BODY_X0 + gr.BODY_X1) + b.GOFF, -3.0)
    fa.append((SERVO_G[servo_gr], p[0], p[1]))
    p = pt(b.GOFF)
    fa.append((HW_G, p[0], p[1]))
    p = pt(PAYX)
    fa.append((payload, p[0], p[1]))
    return arm, fa, crank


def fixed_masses():
    """piezas fijas a la torreta: (m, x) en el plano del brazo."""
    ch = m_of(g.cheek_outline(), g.cheek_right_holes()) + m_of(g.cheek_outline(), g.cheek_left_holes())
    pin = 2 * m_of(g.pinion(), g.pinion_holes())
    tur = m_of(b.turret_disc(), b.turret_holes()) - len(b.turret_slots()) * 0.0
    return [(ch, -10.0), (SERVO_G["MG90S"], g.Q[0]), (SERVO_G["MG90S"], 0.0), (pin, g.Q[0]), (tur, 0.0),
            (m_of(b.brace_plate()), g.BRACE["x0"] + 1.5), (4 * 2.0, 0.0)]


def torques(theta, psi, payload):
    arm, fa, crank = masses(theta, psi, payload)
    ex, _ = e.elbow_pt(theta)
    t2 = sum(m * x for m, x, _ in arm) + sum(m * ex for m, _, _ in fa)          # g*mm * g -> N*mm tras multiplicar por G/1000
    t_f = sum(m * (x - ex) for m, x, _ in fa)
    t_c = sum(m * x for m, x, _ in crank)
    to = lambda gmm: gmm * G / 1000.0 / KGCM                                    # g*mm -> kg*cm (N*mm / (N*mm por kg*cm))
    return to(t2) / g.RATIO / EFF_GEAR, to(t_f + t_c) / EFF_LINK, arm, fa, crank


def tip_moment(theta, psi, payload, d):
    """momento de vuelco (N*mm) respecto de la linea de patines a distancia d adelante del eje."""
    arm, fa, crank = masses(theta, psi, payload)
    allm = arm + fa + crank
    mom = sum(m * (x - d) for m, x, _ in allm) + sum(m * (x - d) for m, x in fixed_masses())
    return mom * G / 1000.0, sum(m for m, _, _ in allm) + sum(m for m, _ in fixed_masses())


def inertia_z(theta, psi, payload):
    arm, fa, crank = masses(theta, psi, payload)
    allm = arm + fa + crank
    i = sum(m * x * x for m, x, _ in allm) + sum(m * x * x for m, x in fixed_masses())
    return i * 1e-3 * 1e-6                                                     # g*mm2 -> kg*m2


# ------------------------------------------------------------------ informe
def main():
    out, ok = [], True

    def log(s=""):
        out.append(s)
        print(s)

    log("VERIFICACION GLOBAL v2 (fase 5)  -  4 servos, MDF 3 mm")

    # --- 1. barrido global de colisiones
    log("")
    log("1. COLISIONES: rejilla theta (paso 5) x rel (paso 5) x guinada 0..90 (7 pasos); capas en Y + nube 3D + travesano")
    free, pts = {}, []
    log("theta  psi factible (rel dentro de [%.0f,%.0f])" % (e.REL_MIN, e.REL_MAX))
    bad_layer = set()
    for th in THETAS:
        row = []
        for r in RELS:
            lc = layer_collisions(th, th + r)
            bad_layer |= set(lc)
            ok_pose = not lc and not any(bc.hits(th, th + r, yw, _P) for yw in bc.YAWS)
            if ok_pose:
                row.append(th + r)
                pts.append((th, th + r))
        free[th] = row
        gaps = [p for p in range(min(row), max(row) + 1, 5) if p not in row] if row else []
        log("%5d  %s%s" % (th, ("%d..%d (%d poses)" % (min(row), max(row), len(row))) if row else "SIN POSES", "  HUECOS" if gaps else ""))
        if not row or gaps:
            ok = False
    only_floor = bad_layer
    log("choques de piezas de capas dentro de las poses de la rejilla (incluye travesano): %s" % (", ".join(sorted(only_floor)) or "ninguno"))
    log("poses factibles: %d de %d" % (len(pts), len(THETAS) * len(RELS)))
    lo = min(p for _, p in pts); hi = max(p for _, p in pts)
    log("psi total usado %d..%d = %d deg (servo J3: 180)   theta %d..%d = %d deg de brazo = %d deg de servo J2 (180)"
        % (lo, hi, hi - lo, g.THETA_MIN, g.THETA_MAX, g.THETA_MAX - g.THETA_MIN, g.RATIO * (g.THETA_MAX - g.THETA_MIN)))
    ok &= hi - lo <= 180

    # --- 2. alcance
    log("")
    log("2. ALCANCE (posicion de las puntas de la pinza, plano del brazo; r = distancia al eje J1, z desde la tapa de la torreta)")
    tips = []
    for th, psi in pts:
        t = e.pt_forearm(th, psi, e.L2 + b.GRIP_REACH)
        tips.append((t[0], t[1], th, psi))
    rmax = max(tips, key=lambda t: t[0]); zmax = max(tips, key=lambda t: t[1]); zmin = min(tips, key=lambda t: t[1])
    log("alcance horizontal maximo: r=%.0f mm (z=%.0f, theta=%d, psi=%d)" % (rmax[0], rmax[1], rmax[2], rmax[3]))
    log("altura maxima de las puntas: z=%.0f mm (r=%.0f)   minima: z=%.0f mm (r=%.0f)" % (zmax[1], zmax[0], zmin[1], zmin[0]))
    near = [t for t in tips if t[1] <= b.TABLE_Z + 8.0]
    if near:
        log("puntas a <= 8 mm de la mesa (recoger del suelo): r = %.0f .. %.0f mm" % (min(t[0] for t in near), max(t[0] for t in near)))
    else:
        log("las puntas NO llegan a 8 mm de la mesa en la rejilla")
        ok = False
    low = [t for t in tips if t[1] <= b.TABLE_Z + 40.0]
    log("puntas a <= 40 mm de la mesa: r = %.0f .. %.0f mm" % (min(t[0] for t in low), max(t[0] for t in low)))
    log("mapa (cada celda 20 mm; # = alguna punta; fila superior = z alto). r de 0 a 260:")
    for z in range(260, -60, -20):
        row = "".join("#" if any(r <= t[0] < r + 20 and z <= t[1] < z + 20 for t in tips) else ("-" if z == -40 else ".") for r in range(0, 280, 20))
        log("  z=%4d  %s" % (z, row))
    _svg(pts, tips)

    # --- 3. par por articulacion
    log("")
    log("3. PAR POR ARTICULACION (estatica con masas reales de las piezas; maximo sobre todas las poses factibles)")
    log("   rendimiento: engranes %.1f, biela %.1f; pinza SG90; J2/J3 comparados con SG90 y MG90S (limite recomendado 60 %% del par de bloqueo)" % (EFF_GEAR, EFF_LINK))
    worst = {}
    for pay in (0.0, 20.0, 50.0):
        w2 = max(((torques(th, psi, pay)[0]), th, psi) for th, psi in pts)
        w3 = max(((abs(torques(th, psi, pay)[1])), th, psi) for th, psi in pts)
        worst[pay] = (w2, w3)
        s2 = "  ".join("%s %.0f%%" % (n, 100 * w2[0] / s) for n, s in STALL.items())
        s3 = "  ".join("%s %.0f%%" % (n, 100 * w3[0] / s) for n, s in STALL.items())
        log("carga %2.0f g: J2 %.2f kg*cm (theta=%d, psi=%d) -> %s" % (pay, w2[0], w2[1], w2[2], s2))
        log("            J3 %.2f kg*cm (theta=%d, psi=%d) -> %s" % (w3[0], w3[1], w3[2], s3))
    a2, a3 = worst[50.0][0][0], worst[50.0][1][0]
    log("masa en el antebrazo + pinza + carga 50 g: %.0f g;  brazo (3 capas) %.1f g;  manivela+media biela %.1f g"
        % (sum(m for m, _, _ in masses(45, 0, 50.0)[1]), sum(m for m, _, _ in masses(45, 0, 50.0)[0]), sum(m for m, _, _ in masses(45, 0, 50.0)[2])))
    if a2 / STALL["MG90S"] > 0.6 or a3 / STALL["MG90S"] > 0.6:
        ok = False
        log("ERROR: con MG90S se pasa del 60 %% con 50 g")
    log("-> con 50 g: MG90S J2 %.0f%% / J3 %.0f%% (ok <60%%); con SG90 J3 seria %.0f%% (%s)"
        % (100 * a2 / STALL["MG90S"], 100 * a3 / STALL["MG90S"], 100 * a3 / STALL["SG90"], "pasa" if a3 / STALL["SG90"] <= 0.6 else "NO pasa"))
    cap = [pay for pay in (20.0, 35.0, 50.0, 65.0, 80.0) if max(abs(torques(th, psi, pay)[1]) for th, psi in pts) <= 0.6 * STALL["MG90S"]]
    pay_max = max(cap) if cap else 0.0
    log("carga maxima con MG90S bajo el 60 %%: %.0f g (barrido 20/35/50/65/80 g)" % pay_max)
    # carga util con SG90 en J3
    capsg = [pay for pay in (0.0, 10.0, 20.0, 30.0, 40.0, 50.0) if max(abs(torques(th, psi, pay)[1]) for th, psi in pts) <= 0.6 * STALL["SG90"]]
    log("carga maxima con SG90 en J3 bajo el 60 %%: %.0f g" % (max(capsg) if capsg else 0.0))

    # --- 4. biela
    f_min = min(abs(math.sin(math.radians(r))) for r in (e.REL_MIN, e.REL_MAX))
    frod = a3 * KGCM / (e.RC * f_min)
    pcr = math.pi ** 2 * 3000.0 * (e.ROD_R * 2 * g.T ** 3 / 12.0) / g.L1 ** 2
    log("")
    log("4. BIELA: fuerza maxima %.1f N (|sin rel| >= %.2f), pandeo de Euler %.0f N -> FS %.1f" % (frod, f_min, pcr, pcr / frod))
    ok &= pcr / frod > 3

    # --- 5. J1 y vuelco
    log("")
    log("5. J1 (guinada) y VUELCO DE LA TORRETA (patines a +-35 mm; la torreta esta sujeta al cuerno del J1 en el centro)")
    worst_hold = (0.0, None)
    for pay in (0.0, 50.0):
        for th, psi in pts:
            for nm, d in (("de frente", 35.0), ("en diagonal", 35.0 * math.sqrt(2))):
                mom, mt = tip_moment(th, psi, pay, d)
                hold = max(0.0, mom) / d
                if hold > worst_hold[0]:
                    worst_hold = (hold, (pay, th, psi, nm, mt))
    h, info = worst_hold
    log("fuerza de arranque en el centro (peor caso): %.1f N = %.0f gf   (carga %.0f g, theta=%d, psi=%d, %s; masa total %.0f g)"
        % (h, h / G * 1000, info[0], info[1], info[2], info[3], info[4]))
    log("  -> el tornillo central del cuerno del J1 debe sujetar la torreta; la salida del servo (SG90/MG90S) soporta cargas axiales de ese orden, pero no es un cojinete")
    sig = 6.0 * (h * 35.0) / (40.0 * g.T ** 2)
    log("  flexion del disco de la torreta junto al cuerno: ~%.1f MPa (MDF ~20 MPa)" % sig)
    ok &= sig < 6.0
    i_ext = max(inertia_z(th, psi, 50.0) for th, psi in pts)
    i_min = min(inertia_z(th, psi, 0.0) for th, psi in pts)
    # friccion de los patines: mu=0.3 (nylon sobre MDF), N = peso total, radio 49.5 mm -> N*mm -> kg*cm
    wtot = sum(m for m, _, _ in sum(masses(45, 0, 50.0)[:3], [])) + sum(m for m, _ in fixed_masses())
    tf = 0.3 * wtot * 1e-3 * G * 49.5 / KGCM
    log("inercia de J1 respecto del eje: %.2e (replegado, sin carga) .. %.2e kg*m2 (extendido, 50 g);  friccion de patines ~%.2f kg*cm (mu=0.3, %.0f g)" % (i_min, i_ext, tf, wtot))
    for nm, s in STALL.items():
        a_cap = (0.6 * s - tf) * KGCM * 1e-3 / i_ext          # N*m / kg*m2 = rad/s2
        t_sweep = math.sqrt(4 * math.pi / a_cap)             # barrido de 180 deg con perfil triangular: alpha = 4*dtheta/t^2
        log("  %s: aceleracion angular admisible al 60 %% = %.0f rad/s2 -> barrido de 180 deg en >= %.2f s (extendido, 50 g)" % (nm, a_cap, t_sweep))
        if nm == "SG90":
            ok &= t_sweep <= 1.0

    # --- 6. pinza
    log("")
    log("6. PINZA")
    A, _ = gr.pose(gr.PHI_MID)
    piv = (0.0, gr.PIV)
    rmx = max(math.hypot(p[0] - piv[0], p[1] - piv[1]) for p in A)
    rpad = 0.8 * rmx
    for nm, s in STALL.items():
        force = s * KGCM / rpad * EFF_GEAR
        log("  %s: fuerza en las almohadillas ~%.1f N por mandibula (radio %.0f mm); sujetar 50 g con mu=0.4 necesita %.1f N -> FS %.0f"
            % (nm, force, rpad, 50e-3 * G / (2 * 0.4), force * 2 * 0.4 / (50e-3 * G)))
    ft = STALL["SG90"] * KGCM / gr.RP
    sig = ft / (2 * g.T * gr.M * 0.28)
    log("  diente de la pinza (SG90): Ft=%.1f N, sigma=%.1f MPa (MDF 20 MPa -> FS %.1f)" % (ft, sig, 20.0 / sig))
    ok &= 20.0 / sig > 3

    log("")
    log("7. RECORRIDOS DE SERVO: J1 180 deg (guinada +-90), J2 %.0f deg, J3 %d deg, pinza %.0f deg (1:1)" % (g.RATIO * (g.THETA_MAX - g.THETA_MIN), hi - lo, gr.PHI_MAX))
    log("")
    log("RESULTADO: %s" % ("OK" if ok else "FALLA"))
    with open(os.path.join(HERE, "global_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return ok


def _svg(pts, tips):
    X0, X1, Z0, Z1 = -90, 290, -50, 270
    sx = 2.0
    W, H = (X1 - X0) * sx, (Z1 - Z0) * sx
    px = lambda x: (x - X0) * sx
    pz = lambda z: (Z1 - z) * sx
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" font-family="sans-serif" font-size="11">' % (W, H, W, H),
         '<rect width="100%" height="100%" fill="#fafafa"/>',
         '<line x1="0" y1="%.1f" x2="%d" y2="%.1f" stroke="#a66" stroke-width="2"/>' % (pz(b.TABLE_Z), W, pz(b.TABLE_Z)),
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#d9b27a" stroke="#765"/>' % (px(-b.HB), pz(b.Z_TOP[1] + 0), 2 * b.HB * sx, (b.Z_TOP[1] - b.Z_BOT[0]) * sx),
         '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#999"/>' % (px(-b.TURRET_R), pz(0), 2 * b.TURRET_R * sx, 3 * sx),
         '<polygon points="%s" fill="#c8a165" fill-opacity="0.6" stroke="#765"/>' % " ".join("%.1f,%.1f" % (px(x), pz(z)) for x, z in g.cheek_outline())]
    for (th, psi, col) in ((15, -40, "#2a7"), (45, -30, "#27a"), (75, 20, "#a52"), (30, -55, "#a2a")):
        ex, ez = e.elbow_pt(th)
        tip = e.pt_forearm(th, psi, e.L2 + b.GRIP_REACH)
        s.append('<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round"/>' % (px(0), pz(g.H), px(ex), pz(ez), px(tip[0]), pz(tip[1]), col))
    for x, z, _, _ in tips:
        s.append('<circle cx="%.1f" cy="%.1f" r="2.2" fill="#e33" fill-opacity="0.55"/>' % (px(x), pz(z)))
    s.append('<text x="10" y="18">Alcance de las puntas de la pinza (plano del brazo). Rojo: poses factibles en cualquier guinada. Linea: mesa z=%d. Escala 2 px/mm.</text>' % b.TABLE_Z)
    s.append("</svg>")
    with open(os.path.join(HERE, "workspace.svg"), "w", encoding="utf-8") as f:
        f.write("\n".join(s))


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
