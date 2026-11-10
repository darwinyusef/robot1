"""Hombro v2 - verificacion numerica: engrane en todo el recorrido, holguras, resistencia del diente y torque del servo.

Uso:  python -I shoulder_check.py        (escribe shoulder_report.txt)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402

DENS = 0.75e-3          # g/mm3 (MDF ~0.75 g/cm3, supuesto)
GRAV_NOTE = "kg*cm"
SERVO_STALL = {"SG90 (1.8 kg*cm)": 1.8, "MG90S (2.2 kg*cm)": 2.2}
EFF = 0.9               # rendimiento del par de engranes (supuesto)

# masas provisionales hasta la fase 3 (g) y posicion a lo largo del brazo (mm desde S)
FOREARM_G = 20.0        # 2 placas + biela + herrajes (estimado)
GRIPPER_G = 25.0        # placa 6 + 4 capas de mandibula 7 + servo 9 + herrajes 3 (estimado)
ROD_G = 5.0


def poly_props(poly, holes=()):
    a = g.area(poly)
    cx = sum((poly[i][0] + poly[(i + 1) % len(poly)][0]) * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]) for i in range(len(poly))) / (6 * a)
    cy = sum((poly[i][1] + poly[(i + 1) % len(poly)][1]) * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]) for i in range(len(poly))) / (6 * a)
    ha = sum(math.pi * d * d / 4 for (_, _, d) in holes)
    return a - ha, cx, cy


def simple(poly):
    n = len(poly)

    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])

    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            a, b, c, d = poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]
            if ccw(a, b, c) * ccw(a, b, d) < 0 and ccw(c, d, a) * ccw(c, d, b) < 0:
                return False
    return True


def main():
    out, ok = [], True

    def log(s=""):
        out.append(s)
        print(s)

    link, sect, left, pin = g.arm_link_ply(), g.arm_sector_ply(), g.arm_left_plate(), g.pinion()
    log("HOMBRO v2  m=%.1f  pinon z=%d  sector z=%d  relacion %.1f:1  entre ejes %.1f mm" % (g.M, g.Z1, g.Z2, g.RATIO, g.CD))
    log("eje S=(0, %.0f)  servo J2 en Q=(%.1f, %.1f)  brazo L1=%.0f  recorrido %.0f..%.0f deg -> servo 0..%.0f deg"
        % (g.H, g.Q[0], g.Q[1], g.L1, g.THETA_MIN, g.THETA_MAX, g.RATIO * (g.THETA_MAX - g.THETA_MIN)))
    for nm, p in (("placa brazo", link), ("capa sector", sect), ("placa izq", left), ("pinon", pin)):
        s = simple(p)
        ok &= s and g.area(p) > 0
        log("  contorno %-12s puntos=%4d area=%7.1f mm2  simple=%s" % (nm, len(p), g.area(p), s))

    rho_ref, zero = g.find_phase()
    log("fase del pinon: %.2f deg (intervalo sin solape %.2f..%.2f deg)" % (math.degrees(rho_ref), zero[0], zero[-1]))

    log("")
    log("theta  servo   solape(mm2)  dist.min(mm)  z_min sector (mm)")
    zmin_all = 1e9
    worst = 0.0
    for th in range(int(g.THETA_MIN), int(g.THETA_MAX) + 1, 10):
        sec = g.arm_pose(link, th)
        pp = g.pinion_pose(pin, g.rho_at(th, rho_ref))
        ov = g.overlap_area(sec, pp, 0.1)
        dm = g.min_dist(sec, pp)
        zmin = min(p[1] for p in sec)
        zmin_all = min(zmin_all, zmin)
        worst = max(worst, ov)
        log("%5d  %5.0f  %10.2f  %12.2f  %16.1f" % (th, g.RATIO * (th - g.THETA_MIN), ov, dm, zmin))
    if worst > 0.3:
        ok = False
        log("ERROR: interferencia de engranes")
    log("holgura sector-torreta (z_min - 0) = %.1f mm" % zmin_all)
    if zmin_all < 5:
        ok = False
        log("ERROR: el sector roza la torreta")

    # resistencia del diente (Lewis, Y~0.28), MDF ~20 MPa de flexion (supuesto conservador)
    for nm, stall in SERVO_STALL.items():
        t_nmm = stall * 9.80665 * 10.0           # kg*cm -> N*mm
        ft = t_nmm / g.RP1
        sig = ft / (2 * 3.0 * g.M * 0.28)        # 2 capas de 3 mm
        log("diente con %s: Ft=%.1f N  sigma=%.1f MPa  (MDF ~20 MPa -> FS %.1f)" % (nm, ft, sig, 20.0 / sig))

    # masas y torque en el hombro
    a1, c1x, c1y = poly_props(link, g.ARM_HOLES)
    a2, c2x, c2y = poly_props(sect)
    aL, cLx, cLy = poly_props(left, g.ARM_HOLES)
    m_link = a1 * g.T * DENS
    m_sect = a2 * g.T * DENS
    m_left = aL * g.T * DENS
    parts = [("placa der. brazo", m_link, c1x, c1y), ("capa sector", m_sect, c2x, c2y), ("placa izq. brazo", m_left, cLx, cLy),
             ("biela (est.)", ROD_G, g.L1 / 2, 0.0), ("antebrazo (est.)", FOREARM_G, g.L1 + g.L2 / 2, 0.0),
             ("pinza+servo (est.)", GRIPPER_G, g.L1 + g.L2 + 20, 0.0)]
    log("")
    log("masas (g): " + "  ".join("%s %.1f" % (n, m) for n, m, _, _ in parts))
    for payload in (20.0, 50.0):
        pl = parts + [("carga", payload, g.L1 + g.L2 + 45, 0.0)]
        for th in (g.THETA_MIN, 45.0):
            c, s = math.cos(math.radians(th)), math.sin(math.radians(th))
            tq_kgcm = sum(m * (u * c - v * s) for _, m, u, v in pl) / 10.0 / 1000.0     # g*mm -> kg*cm
            tq_servo = tq_kgcm / g.RATIO / EFF
            marg = "  ".join("%s: %.0f%% del par max." % (n.split()[0], 100 * tq_servo / st) for n, st in SERVO_STALL.items())
            log("carga %2.0f g, theta=%2.0f: par en el brazo %.2f kg*cm -> servo %.2f kg*cm   %s" % (payload, th, tq_kgcm, tq_servo, marg))
    log("(regla practica: mantener el servo por debajo de ~60% de su par maximo en reposo)")
    log("")
    log("RESULTADO: %s" % ("OK" if ok else "FALLA"))
    with open(os.path.join(HERE, "shoulder_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
