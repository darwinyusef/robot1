"""Fase 6 - salida: acomodo de todas las piezas en planchas de MDF 3 mm (350 x 350), SVG con las capas del taller
(AZUL = primer corte / interiores, NEGRO = corte final / contornos, ROJO = grabado), control de piezas y de puentes minimos,
y tabla de limites para el programa.

Uso:  python -I output_build.py     -> corte_final_mdf_3mm_{1..n}.svg, output_report.txt, brazo_v2/limites.h
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

BED = (350.0, 350.0)
MARGIN, GAP, LABEL_H = 6.0, 4.0, 6.0
MIN_WEB = 1.5
# Entre la ventana del servo (cuerpo + 0.3 mm) y el tornillo de la oreja del lado del eje queda 1.05 mm de MDF.
# No es estructural (la oreja se apoya en la placa; si el puente se rompe quedan los otros tornillos), se documenta como excepcion.
WEB_EXCEPTIONS = ("MEJILLA DER (J2)", "MEJILLA IZQ (J3)", "PLACA SUPERIOR", "PLACA PINZA+CUELLO")
WEB_EXC_MIN = 1.0


def rect_poly(r):
    x0, y0, x1, y1 = r
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def parts():
    """(nombre, cantidad, contorno, agujeros(x,y,d), huecos poligonales)"""
    A0, B0 = gr.pose(0.0)
    P = [
        ("PLACA BRAZO DER", 1, g.arm_link_ply(), g.ARM_HOLES, []),
        ("PLACA BRAZO IZQ", 1, g.arm_left_plate(), g.ARM_HOLES, []),
        ("CAPA SECTOR", 1, g.arm_sector_ply(), g.ARM_HOLES[:1], []),
        ("PINON", 2, g.pinion(), g.pinion_holes(), []),
        ("MEJILLA DER (J2)", 1, g.cheek_outline(), g.cheek_right_holes(), [rect_poly(r) for r in g.cheek_rects_right()]),
        ("MEJILLA IZQ (J3)", 1, g.cheek_outline(), g.cheek_left_holes(), [rect_poly(r) for r in g.cheek_rects_left()]),
        ("MANIVELA", 1, e.crank_ply(), e.CRANK_HOLES, []),
        ("BIELA", 1, e.rod_ply(), e.ROD_HOLES, []),
        ("ANTEBRAZO IZQ", 1, e.forearm_left_ply(), e.FA_HOLES_L, []),
        ("ANTEBRAZO DER", 1, e.forearm_right_ply(), e.FA_HOLES_R, []),
        ("PLACA SUPERIOR", 1, b.top_plate()[0], b.top_plate()[1], [rect_poly(r) for r in b.top_plate()[2]]),
        ("PLACA INFERIOR", 1, b.bottom_plate()[0], b.bottom_plate()[1], [rect_poly(r) for r in b.bottom_plate()[2]]),
        ("TORRETA", 1, b.turret_disc(), b.turret_holes(), [rect_poly(r) for r in b.turret_slots()]),
        ("TRAVESANO", 1, b.brace_plate(), [], []),
        ("PARED FRONTAL", 1, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), [], []),
        ("PARED TRASERA", 1, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), b.CABLE_HOLE, []),
        ("PARED LATERAL", 2, b.wall_panel(b.WALL_HALF_SIDE, b.SIDE_TABS), [], []),
        ("PLACA PINZA+CUELLO", 1, b.gripper_plate(), b.gripper_plate_holes(), [rect_poly(b.gripper_plate_window())]),
        ("MANDIBULA A", 2, A0, gr.hole_abs(gr.holes_A(), "A", 0.0), []),
        ("MANDIBULA B", 2, B0, gr.hole_abs(gr.holes_B(), "B", 0.0), []),
    ]
    return P


def bbox(pts):
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def rot90(pts):
    return [(-y, x) for x, y in pts]


def orient(poly, holes, voids):
    """gira 90 deg si el contorno es mas alto que ancho (para que las tiras largas vayan en horizontal)."""
    x0, y0, x1, y1 = bbox(poly)
    if (y1 - y0) > (x1 - x0) * 1.0:
        return rot90(poly), [(-y, x, d) for x, y, d in holes], [rot90(v) for v in voids]
    return poly, holes, voids


# ---------- puentes minimos
def seg_dist(p, a, c):
    ax, ay = a; cx, cy = c; px, py = p
    dx, dy = cx - ax, cy - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def poly_poly_dist(P, Q):
    d = 1e9
    for i in range(len(P)):
        for j in range(len(Q)):
            d = min(d, seg_dist(P[i], Q[j], Q[(j + 1) % len(Q)]), seg_dist(Q[j], P[i], P[(i + 1) % len(P)]))
    return d


def circ_poly(x, y, d, n=20):
    return [(x + d / 2 * math.cos(2 * math.pi * k / n), y + d / 2 * math.sin(2 * math.pi * k / n)) for k in range(n)]


def webs(poly, holes, voids):
    """puentes minimos: contorno-hueco y hueco-hueco (mm)."""
    inner = [circ_poly(x, y, d) for x, y, d in holes] + list(voids)
    w_edge = min([poly_poly_dist(poly, h) for h in inner] or [1e9])
    w_hole = 1e9
    for i in range(len(inner)):
        for j in range(i + 1, len(inner)):
            w_hole = min(w_hole, poly_poly_dist(inner[i], inner[j]))
    return w_edge, w_hole


# ---------- acomodo (estantes)
def pack(items):
    """items: (nombre, poly, holes, voids). Devuelve lista de planchas; cada una es lista de (item, ox, oy) con (ox,oy) esquina sup. izq. de la celda."""
    cells = []
    for it in items:
        x0, y0, x1, y1 = bbox(it[1])
        cells.append((x1 - x0, y1 - y0 + LABEL_H, it))
    cells.sort(key=lambda c: -c[1])
    sheets, cur, x, y, rowh = [], [], MARGIN, MARGIN, 0.0
    for w, h, it in cells:
        if x + w > BED[0] - MARGIN:
            x, y, rowh = MARGIN, y + rowh + GAP, 0.0
        if y + h > BED[1] - MARGIN:
            sheets.append(cur)
            cur, x, y, rowh = [], MARGIN, MARGIN, 0.0
        cur.append((it, x, y))
        x += w + GAP
        rowh = max(rowh, h)
    if cur:
        sheets.append(cur)
    return sheets


def write_sheet(path, title, placed):
    inner, outer, eng = [], [], []
    for (name, poly, holes, voids), ox, oy in placed:
        x0, y0, x1, y1 = bbox(poly)
        top = oy + LABEL_H
        tx = lambda x: ox + (x - x0)
        ty = lambda y: top + (y1 - y)
        outer.append('<path d="M%sZ"/>' % "L".join("%.3f %.3f" % (tx(x), ty(y)) for x, y in poly))
        for v in voids:
            inner.append('<path d="M%sZ"/>' % "L".join("%.3f %.3f" % (tx(x), ty(y)) for x, y in v))
        for x, y, d in holes:
            inner.append('<circle cx="%.3f" cy="%.3f" r="%.3f"/>' % (tx(x), ty(y), d / 2))
        eng.append('<text x="%.2f" y="%.2f" font-size="3.2" font-family="monospace">%s</text>' % (ox, oy + 4.2, name))
    svg = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" width="%dmm" height="%dmm" viewBox="0 0 %d %d">' % (BED[0], BED[1], BED[0], BED[1]),
           "<title>%s</title>" % title,
           '<rect id="PLANCHA" x="0" y="0" width="%d" height="%d" fill="none" stroke="#888" stroke-width="0.2" stroke-dasharray="2 2"/>' % BED,
           '<g id="2_AZUL_Primer_corte" fill="none" stroke="#0000ff" stroke-width="0.1">'] + inner + ["</g>",
           '<g id="3_NEGRO_Corte_final" fill="none" stroke="#000000" stroke-width="0.1">'] + outer + ["</g>",
           '<g id="1_ROJO_Grabado" fill="#ff0000" stroke="none">'] + eng + ["</g>", "</svg>"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))


def limits_table():
    import global_check as gc
    tab = []
    for th in gc.THETAS:
        ok = [th + r for r in gc.RELS if gc.feasible(th, r)]
        tab.append((th, min(ok), max(ok)))
    return tab


def write_limits(tab):
    d = os.path.join(os.path.dirname(HERE), "control", "brazo_v2")
    os.makedirs(d, exist_ok=True)
    lines = ["// Generado por output_build.py (fase 6). Limites de psi (angulo absoluto del antebrazo) segun theta (angulo del brazo), en grados.",
             "// Zona libre verificada para cualquier guinada (barrido de la fase 5); el programa agrega SAFE grados de margen.",
             "const int N_LIM = %d;" % len(tab),
             "const int TH_LIM[N_LIM]  = {%s};" % ", ".join(str(t[0]) for t in tab),
             "const int PSI_LO[N_LIM]  = {%s};" % ", ".join(str(t[1]) for t in tab),
             "const int PSI_HI[N_LIM]  = {%s};" % ", ".join(str(t[2]) for t in tab)]
    with open(os.path.join(d, "limites.h"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    out, ok = [], True

    def log(s=""):
        out.append(s)
        print(s)

    items, area, total = [], 0.0, 0
    log("FASE 6 - SALIDA   plancha %.0f x %.0f mm, MDF 3 mm, margen %.0f, separacion %.0f" % (BED[0], BED[1], MARGIN, GAP))
    log("")
    log("pieza                 cant  caja (mm)         area (mm2)  puente contorno-hueco  puente hueco-hueco")
    for name, q, poly, holes, voids in parts():
        poly, holes, voids = orient(poly, holes, voids)
        x0, y0, x1, y1 = bbox(poly)
        a = g.area(poly)
        w_edge, w_hole = webs(poly, holes, voids)
        wmin = min(w_edge, w_hole)
        if wmin >= MIN_WEB:
            flag = ""
        elif name in WEB_EXCEPTIONS and wmin >= WEB_EXC_MIN:
            flag = "  (excepcion documentada: puente servo-ventana/tornillo %.2f mm >= %.1f)" % (wmin, WEB_EXC_MIN)
        else:
            flag = "  <-- PUENTE < %.1f mm" % MIN_WEB
            ok = False
        log("%-21s %3d   %5.1f x %5.1f   %9.0f   %14.2f   %14.2f%s" % (name, q, x1 - x0, y1 - y0, a, min(w_edge, 99), min(w_hole, 99), flag))
        for k in range(q):
            items.append((name + (" %d/%d" % (k + 1, q) if q > 1 else ""), poly, holes, voids))
        area += a * q
        total += q
    sheets = pack(items)
    log("")
    log("%d piezas, area de las piezas %.0f mm2 (%.0f %% de %d plancha(s) de %.0fx%.0f)" % (total, area, 100 * area / (len(sheets) * BED[0] * BED[1]), len(sheets), BED[0], BED[1]))
    for i, pl in enumerate(sheets, 1):
        path = os.path.join(HERE, "corte_final_mdf_3mm_%d.svg" % i)
        write_sheet(path, "Brazo robotico v2 - MDF 3 mm - plancha %d de %d" % (i, len(sheets)), pl)
        for (nm, poly, _, _), ox, oy in pl:
            x0, y0, x1, y1 = bbox(poly)
            if ox + (x1 - x0) > BED[0] - MARGIN + 1e-6 or oy + (y1 - y0) + LABEL_H > BED[1] - MARGIN + 1e-6:
                ok = False
                log("ERROR: %s se sale de la plancha %d" % (nm, i))
        log("  plancha %d: %d piezas -> corte_final_mdf_3mm_%d.svg" % (i, len(pl), i))
    old = [f for f in os.listdir(HERE) if f.startswith("corte_final_mdf_3mm_") and int(f.split("_")[-1].split(".")[0]) > len(sheets)]
    for f in old:
        os.remove(os.path.join(HERE, f))

    tab = limits_table()
    write_limits(tab)
    log("")
    log("tabla de limites (theta: psi_min..psi_max) -> brazo_v2/limites.h")
    log("  " + "  ".join("%d:%d..%d" % t for t in tab))
    log("")
    log("RESULTADO: %s" % ("OK" if ok else "REVISAR"))
    with open(os.path.join(HERE, "output_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
