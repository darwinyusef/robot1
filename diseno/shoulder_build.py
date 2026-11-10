"""Hombro v2 - modelo 3D (SolidCraft) en 3 poses y planchas SVG de corte (MDF 3 mm).

Uso:  python -I shoulder_build.py [--no3d]
Salida: shoulder_*.sc/.png, corte_mdf_3mm_hombro_1.svg (brazo y engranes), corte_mdf_3mm_hombro_2.svg (mejillas)
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402

RHO_REF, _ = g.find_phase()


def run_3d():
    import scene as S
    ok = True
    for th, tag in ((g.THETA_MIN, "min"), (45.0, "med"), (g.THETA_MAX, "max")):
        sc = S.Scene()
        S.shoulder(sc, th, RHO_REF)
        ok &= sc.build("shoulder_" + tag, HERE)
    return ok


class Sheet:
    def __init__(self, title, w=350, h=200):
        self.w, self.h, self.title, self.cut, self.eng = w, h, title, [], []

    def poly(self, pts, ox, oy):
        self.cut.append('<path d="M%sZ"/>' % "L".join("%.3f %.3f" % (ox + x, oy - y) for x, y in pts))

    def circle(self, x, y, d, ox, oy):
        self.cut.append('<circle cx="%.3f" cy="%.3f" r="%.3f"/>' % (ox + x, oy - y, d / 2))

    def rect(self, x0, y0, x1, y1, ox, oy):
        self.cut.append('<path d="M%.3f %.3fH%.3fV%.3fH%.3fZ"/>' % (ox + x0, oy - y0, ox + x1, oy - y1, ox + x0))

    def label(self, x, y, s, size=3.5):
        self.eng.append('<text x="%.2f" y="%.2f" font-size="%.1f" font-family="monospace">%s</text>' % (x, y, size, s))

    def save(self, fname):
        svg = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<svg xmlns="http://www.w3.org/2000/svg" width="%dmm" height="%dmm" viewBox="0 0 %d %d">' % (self.w, self.h, self.w, self.h),
               "<title>%s</title>" % self.title,
               '<rect id="PLANCHA" x="0" y="0" width="%d" height="%d" fill="none" stroke="#888" stroke-width="0.2" stroke-dasharray="2 2"/>' % (self.w, self.h),
               '<g id="CORTE" fill="none" stroke="#ff0000" stroke-width="0.1">'] + self.cut + ["</g>",
               '<g id="GRABADO" fill="#0000ff" stroke="none">'] + self.eng + ["</g>", "</svg>"]
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(svg))


def part(sh, poly, holes, x, y, label, rects=()):
    sh.poly(poly, x, y)
    for (a, b, c, d) in rects:
        sh.rect(a, b, c, d, x, y)
    for (u, v, d) in holes:
        sh.circle(u, v, d, x, y)
    sh.label(x - 10, y - max(p[1] for p in poly) - 3, label)


def svgs():
    s1 = Sheet("Hombro v2 - brazo y engranes - MDF 3 mm")
    part(s1, g.arm_link_ply(), g.ARM_HOLES, 45, 60, "PLACA BRAZO DER x1")
    part(s1, g.arm_left_plate(), g.ARM_HOLES, 45, 120, "PLACA BRAZO IZQ x1")
    part(s1, g.arm_sector_ply(), g.ARM_HOLES[:1], 215, 60, "CAPA SECTOR x1 (pegar sobre placa der.)")
    for k in range(2):
        part(s1, g.pinion(), g.pinion_holes(), 205 + 40 * k, 140, "PINON %d/2" % (k + 1))
    s1.label(5, 8, "Rojo = corte, azul = grabado. 1:1 mm. Engranes m=2: pinon z=14, sector z=28 (2:1). Pegar capas con dientes alineados.", 3.0)
    s1.save(os.path.join(HERE, "corte_mdf_3mm_hombro_1.svg"))
    s2 = Sheet("Hombro v2 - mejillas - MDF 3 mm")
    part(s2, g.cheek_outline(), g.cheek_right_holes(), 80, 120, "MEJILLA DER x1 (servo J2)", rects=g.cheek_rects_right())
    part(s2, g.cheek_outline(), g.cheek_left_holes(), 215, 120, "MEJILLA IZQ x1 (servo J3)", rects=g.cheek_rects_left())
    s2.label(5, 8, "Lenguetas inferiores (3 mm) a la torreta; ranura de 3.1 mm para el travesano (x 20..23). Ventana del servo en cada mejilla.", 3.0)
    s2.save(os.path.join(HERE, "corte_mdf_3mm_hombro_2.svg"))


if __name__ == "__main__":
    svgs()
    print("svg ok")
    sys.exit(0 if ("--no3d" in sys.argv or run_3d()) else 1)
