"""Planos del brazo v2 generados con cadcraft-cli (DXF + PNG + PDF), unidades mm, escala 1:1.

  plano_01_conjunto.dxf     vista lateral + planta (pose theta=45, psi=0, apertura 20) y datos tecnicos
  plano_02_brazo_piezas.dxf piezas del hombro, codo y pinza (cotas y agujeros)
  plano_03_base_piezas.dxf  piezas de la base (placas, torreta, travesano, paredes)

Usa la misma geometria que los scripts de las fases 1-6 (shoulder_geom, elbow_geom, gripper, base_geom).
Uso:  python -I planos_cadcraft.py
"""
import datetime
import json
import math
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shoulder_geom as g   # noqa: E402
import elbow_geom as e      # noqa: E402
import gripper as gr        # noqa: E402
import base_geom as b       # noqa: E402

EXE = r"I:\CADCraft\cadcraft-cli.exe"
TODAY = datetime.date.today().isoformat()
MAXCHARS = 18000            # largo maximo de los argumentos de cada llamada a la CLI

POSE = (45.0, 0.0, 20.0)    # theta, psi, apertura de las mandibulas


# ============================================================== hoja
class Sheet:
    def __init__(self, code, title, W, H, num, total):
        self.code, self.title, self.W, self.H, self.num, self.total = code, title, W, H, num, total
        self.cmds = []
        self._setup()

    def c(self, cid, **p):
        self.cmds.append((cid, p))

    def layer(self, name):
        self.c("layer.current", name=name)

    def dimstyle(self, scale):
        self.c("dimstyle", name="ESC%s" % str(scale).replace(".", "_"), current=True, DIMSCALE=scale)

    def pline(self, pts, closed=True):
        self.c("pline", vertices=[[round(x, 3), round(y, 3)] for x, y in pts], closed=closed)

    def line(self, *pts):
        self.c("line", points=[[round(x, 3), round(y, 3)] for x, y in pts])

    def circle(self, x, y, d):
        self.c("circle", center=[round(x, 3), round(y, 3)], diameter=round(d, 3))

    def text(self, at, s, h=3.5, **kw):
        self.c("text", at=[round(at[0], 3), round(at[1], 3)], text=s, height=h, **kw)

    def _setup(self):
        self.c("linetype", load="*", text="*HIDDEN,Hidden\nA,4,-2\n*CENTER,Center\nA,16,-3,3,-3\n*DASHED,Dashed\nA,8,-4\n")
        for name, color, lt in [("CONTORNO", "white", None), ("EJES", "red", "CENTER"), ("OCULTO", "yellow", "HIDDEN"),
                                ("COTAS", "cyan", None), ("TEXTO", "green", None), ("MARCO", "white", None),
                                ("ENVOLVENTE", "magenta", "DASHED"), ("SERVO", "yellow", None), ("SUELO", "8", None),
                                ("PASO", "magenta", "DASHED")]:
            kw = {"name": name, "color": color}
            if lt:
                kw["linetype"] = lt
            self.c("layer.new", **kw)
        self.c("ltscale", scale=1.0)
        self.dimstyle(1.0)
        self.frame()

    def frame(self):
        W, H = self.W, self.H
        self.layer("MARCO")
        self.c("rectang", p1=[0, 0], p2=[W, H])
        self.c("rectang", p1=[8, 8], p2=[W - 8, H - 8])
        x0, y0, x1, y1 = W - 8 - 250, 8, W - 8, 8 + 44
        self.line((x0, y0 + 22), (x1, y0 + 22))
        self.line((x0, y0 + 44), (x0, y0), (x1, y0))
        self.line((x0 + 160, y0), (x0 + 160, y0 + 22))
        self.layer("TEXTO")
        self.text((x0 + 4, y0 + 33), "BRAZO ROBOTICO v2 - 4 SERVOS", 4.5)
        self.text((x0 + 4, y0 + 25.5), self.title, 3.2)
        self.text((x0 + 4, y0 + 12), "MDF 3 mm  |  corte laser  |  mm", 3.0)
        self.text((x0 + 4, y0 + 4), "Rev A  %s  Escala 1:1" % TODAY, 3.0)
        self.text((x0 + 165, y0 + 12), "HOJA %d/%d" % (self.num, self.total), 4.0)
        self.text((x0 + 165, y0 + 4), self.code, 4.0)
        self.layer("CONTORNO")

    # ---- cotas
    def hdim(self, p1, p2, y):
        self.c("dimlinear", p1=[round(p1[0], 3), round(p1[1], 3)], p2=[round(p2[0], 3), round(p2[1], 3)], at=[round((p1[0] + p2[0]) / 2, 3), round(y, 3)])

    def vdim(self, p1, p2, x):
        self.c("dimlinear", p1=[round(p1[0], 3), round(p1[1], 3)], p2=[round(p2[0], 3), round(p2[1], 3)], at=[round(x, 3), round((p1[1] + p2[1]) / 2, 3)], rotation=90)

    def adim(self, p1, p2, at):
        self.c("dimaligned", p1=[round(p1[0], 3), round(p1[1], 3)], p2=[round(p2[0], 3), round(p2[1], 3)], at=[round(at[0], 3), round(at[1], 3)])

    def ddim(self, cx, cy, d, ang_deg):
        a = math.radians(ang_deg)
        self.c("dimdiameter", center=[round(cx, 3), round(cy, 3)], point=[round(cx + d / 2 * math.cos(a), 3), round(cy + d / 2 * math.sin(a), 3)])

    def save(self):
        dxf = os.path.join(HERE, self.code + ".dxf")
        batches, cur, n = [], [], 0
        for cid, p in self.cmds:
            s = len(cid) + len(json.dumps(p, separators=(",", ":"))) + 12
            if cur and n + s > MAXCHARS:
                batches.append(cur)
                cur, n = [], 0
            cur.append((cid, p))
            n += s
        if cur:
            batches.append(cur)
        for i, batch in enumerate(batches):
            a = [EXE, "run"] + (["--metric"] if i == 0 else [dxf])
            for cid, p in batch:
                a += ["--cmd", cid + " " + json.dumps(p, separators=(",", ":"))]
            a += ["--save", dxf] + ([] if i == 0 else ["--in-place"])
            r = subprocess.run(a, capture_output=True, text=True)
            if r.returncode != 0 or "error" in r.stderr.lower() or "error" in r.stdout.lower():
                print("FALLO en %s lote %d/%d" % (self.code, i + 1, len(batches)))
                print(r.stdout[-1500:], r.stderr[-1500:])
                sys.exit(1)
        win = "--window=0,0,%d,%d" % (self.W, self.H)
        for ext in ("png", "pdf"):
            r = subprocess.run([EXE, "run", dxf, win, "--export", os.path.join(HERE, "%s.%s" % (self.code, ext))], capture_output=True, text=True)
            if r.returncode != 0:
                print("FALLO exportando", ext, r.stderr[-500:])
                sys.exit(1)
        print("%s: %d comandos en %d lote(s) -> .dxf .png .pdf" % (self.code, len(self.cmds), len(batches)))


# ============================================================== piezas
def bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def rect_poly(r):
    x0, y0, x1, y1 = r
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def part_size(poly):
    x0, y0, x1, y1 = bbox(poly)
    return x1 - x0, y1 - y0


CELL_L, CELL_R, CELL_B, CELL_T = 26.0, 30.0, 46.0, 22.0


def draw_part(sh, ox, oy, num, name, qty, poly, holes, voids, notes=(), pitch=None):
    """dibuja una pieza con su caja inferior-izquierda en (ox, oy), con cotas y rotulo."""
    x0, y0, x1, y1 = bbox(poly)
    dx, dy = ox - x0, oy - y0
    M = lambda x, y: (x + dx, y + dy)
    X0, Y0, X1, Y1 = ox, oy, ox + (x1 - x0), oy + (y1 - y0)
    sh.layer("CONTORNO")
    sh.pline([M(*p) for p in poly])
    for v in voids:
        sh.pline([M(*p) for p in v])
    for (hx, hy, d) in holes:
        sh.circle(*M(hx, hy), d)
    # ejes de los agujeros grandes y circulos primitivos
    sh.layer("EJES")
    for (hx, hy, d) in holes:
        if d >= 3.0:
            cx, cy = M(hx, hy)
            r = d / 2 + 2.5
            sh.line((cx - r, cy), (cx + r, cy))
            sh.line((cx, cy - r), (cx, cy + r))
    if pitch:
        sh.layer("PASO")
        for kind, cx, cy, r, a0, a1 in pitch:
            mx, my = M(cx, cy)
            if kind == "circle":
                sh.c("circle", center=[round(mx, 3), round(my, 3)], radius=round(r, 3))
            else:
                sh.c("arc", center=[round(mx, 3), round(my, 3)], radius=round(r, 3), start=round(a0, 3), end=round(a1, 3))
    # cotas
    sh.layer("COTAS")
    sh.hdim((X0, Y0), (X1, Y0), Y0 - 12)
    sh.vdim((X1, Y0), (X1, Y1), X1 + 14)
    key = [(hx, hy, d) for (hx, hy, d) in holes if d > 1.9]
    xs = sorted({round(M(hx, hy)[0], 2) for hx, hy, d in key})
    ys = sorted({round(M(hx, hy)[1], 2) for hx, hy, d in key})
    refs = {}
    for hx, hy, d in key:
        mx, my = M(hx, hy)
        refs.setdefault(round(mx, 2), (mx, my))
    if 2 <= len(xs) <= 7:
        pts = [(x, refs[x][1]) for x in xs]
        if xs[0] - X0 > 1.0:
            pts = [(X0, pts[0][1])] + pts
        if X1 - xs[-1] > 1.0:
            pts = pts + [(X1, pts[-1][1])]
        for p, q in zip(pts[:-1], pts[1:]):
            sh.hdim(p, q, Y1 + 10)
    refy = {}
    for hx, hy, d in key:
        mx, my = M(hx, hy)
        refy.setdefault(round(my, 2), (mx, my))
    if 2 <= len(ys) <= 6:
        pts = [(refy[y][0], y) for y in ys]
        if ys[0] - Y0 > 1.0:
            pts = [(pts[0][0], Y0)] + pts
        if Y1 - ys[-1] > 1.0:
            pts = pts + [(pts[-1][0], Y1)]
        for p, q in zip(pts[:-1], pts[1:]):
            sh.vdim(p, q, X0 - 12)
    seen, k = set(), 0
    for hx, hy, d in holes:
        if round(d, 2) in seen:
            continue
        seen.add(round(d, 2))
        mx, my = M(hx, hy)
        sh.ddim(mx, my, d, [45, 135, 225, 315][k % 4])
        k += 1
    if pitch:
        for kind, cx, cy, r, a0, a1 in pitch:
            if kind == "circle":
                mx, my = M(cx, cy)
                sh.ddim(mx, my, 2 * r, 225)
    for v in voids:
        vx0, vy0, vx1, vy1 = bbox(v)
        if len(v) == 4 and (vx1 - vx0) >= 8 and (vy1 - vy0) >= 8:
            sh.hdim(M(vx0, vy0), M(vx1, vy0), M(0, vy0)[1] + 7)
            sh.vdim(M(vx1, vy0), M(vx1, vy1), M(vx1, 0)[0] - 7)
    # rotulo
    sh.layer("TEXTO")
    sh.text((X0, Y0 - 25), "%d  %s%s" % (num, name, "   x%d" % qty if qty > 1 else "   x1"), 4.5)
    for i, s in enumerate(notes):
        sh.text((X0, Y0 - 31 - 4.2 * i), s, 3.0)
    sh.layer("CONTORNO")


def note_lines(poly, notes):
    """parte las notas en renglones que no pasen del ancho de la celda de la pieza."""
    w = part_size(poly)[0]
    n = max(28, int((w + CELL_L + CELL_R - 6) / 2.5))
    out = []
    for s in notes:
        out += textwrap.wrap(s, n)
    return out


def pack(items, width, y0):
    """acomodo por estantes. items: (w, h, extra) de la pieza; devuelve ([(x,y)], altura_total)."""
    x, y, rowh = 20.0, y0, 0.0
    cells = [(w + CELL_L + CELL_R, h + extra + CELL_B + CELL_T) for w, h, extra in items]
    order = sorted(range(len(items)), key=lambda i: -cells[i][1])
    res = {}
    for i in order:
        cw, ch = cells[i]
        if x + cw > width - 20.0 and x > 20.0:
            x, y, rowh = 20.0, y + rowh, 0.0
        res[i] = (x + CELL_L, y + CELL_B + items[i][2])
        x += cw
        rowh = max(rowh, ch)
    return [res[i] for i in range(len(items))], y + rowh


def sheet_parts(code, title, num, total, W, plist):
    lines = [note_lines(p[3], p[6]) for p in plist]
    sizes = [part_size(p[3]) + (4.2 * max(0, len(ln) - 3),) for p, ln in zip(plist, lines)]
    pos, top = pack(sizes, W, 58.0)
    sh = Sheet(code, title, W, int(math.ceil(top + 18)), num, total)
    for (x, y), (n, name, q, poly, holes, voids, notes, pitch), ln in zip(pos, plist, lines):
        draw_part(sh, x, y, n, name, q, poly, holes, voids, ln, pitch)
    sh.save()


def build_parts():
    A0, B0 = gr.pose(0.0)
    sector_arc = [("arc", 0.0, 0.0, g.RP2, (g.BETA - g.THETA_MAX - g.S_MARGIN) % 360.0, (g.BETA - g.THETA_MIN + g.S_MARGIN) % 360.0)]
    P = {
        1: ("PLACA BRAZO DER", 1, g.arm_link_ply(), g.ARM_HOLES, [], ["Eje S en (0,0), codo a 90. Sector z=28 m=2 (R prim. 28)", "Capa exterior del sector: va pegada a la capa 3"], sector_arc),
        2: ("PLACA BRAZO IZQ", 1, g.arm_left_plate(), g.ARM_HOLES, [], ["Sin dientes"], None),
        3: ("CAPA SECTOR", 1, g.arm_sector_ply(), g.ARM_HOLES[:1], [], ["Engrane del hombro (pegar entre placa der. y el cubo)"], sector_arc),
        4: ("PINON J2", 2, g.pinion(), g.pinion_holes(), [], ["z=14 m=2 (O prim. 28), 2 capas pegadas", "4 x O1.8 en circulo R8 (cuerno del servo), centro O7.6"], [("circle", 0.0, 0.0, g.RP1, 0, 0)]),
        5: ("MEJILLA DER (J2)", 1, g.cheek_outline(), g.cheek_right_holes(), [rect_poly(r) for r in g.cheek_rects_right()],
            ["Eje S O3.2 en (0,60). Ventana del servo J2 y ranura del travesano 3.1", "Lenguetas de 3 mm hacia la torreta"], None),
        6: ("MEJILLA IZQ (J3)", 1, g.cheek_outline(), g.cheek_left_holes(), [rect_poly(r) for r in g.cheek_rects_left()],
            ["Servo J3 coaxial con el eje S. Ventana + ranura del travesano 3.1"], None),
        7: ("MANIVELA J3", 1, e.crank_ply(), e.CRANK_HOLES, [], ["Radio de manivela 16; cuerno del servo J3 en el origen"], None),
        8: ("BIELA", 1, e.rod_ply(), e.ROD_HOLES, [], ["Entre ejes 90 (paralela al brazo)"], None),
        9: ("ANTEBRAZO IZQ", 1, e.forearm_left_ply(), e.FA_HOLES_L, [], ["Palanca de la biela en x=-16; ranura frontal 3.1 para el cuello de la pinza"], None),
        10: ("ANTEBRAZO DER", 1, e.forearm_right_ply(), e.FA_HOLES_R, [], ["Separador entre placas en x=40; ranura frontal 3.1"], None),
        11: ("PLACA SUPERIOR", 1, b.top_plate()[0], b.top_plate()[1], [rect_poly(r) for r in b.top_plate()[2]],
             ["Ventana del servo J1 y 12 ranuras 20.1 x 3.1 de las paredes", "Paso de cables O10 en (-28,0); esquinas O9 (tornillos de mesa)"], None),
        12: ("PLACA INFERIOR", 1, b.bottom_plate()[0], b.bottom_plate()[1], [rect_poly(r) for r in b.bottom_plate()[2]],
             ["12 ranuras de paredes 20.1 x 3.1; esquinas O4"], None),
        13: ("TORRETA", 1, b.turret_disc(), b.turret_holes(), [rect_poly(r) for r in b.turret_slots()],
             ["Disco R60. Centro O7.6 + 4 x O1.8 (R8, cuerno J1); 4 patines O3.2; paso de cables O10", "Ranuras 16.1 x 3.1 de las lenguetas de las mejillas"], None),
        14: ("TRAVESANO", 1, b.brace_plate(), [], [], ["Une las mejillas: pasa por sus ranuras de 3.1 (z 12..32)"], None),
        15: ("PARED FRONTAL", 1, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), [], [], ["Lenguetas de 20 x 3 que cruzan las placas"], None),
        16: ("PARED TRASERA", 1, b.wall_panel(b.WALL_HALF_FRONT, b.FRONT_TABS), b.CABLE_HOLE, [], ["Agujero de cables O10"], None),
        17: ("PARED LATERAL", 2, b.wall_panel(b.WALL_HALF_SIDE, b.SIDE_TABS), [], [], ["Izquierda y derecha iguales"], None),
        18: ("PLACA PINZA + CUELLO", 1, b.gripper_plate(), b.gripper_plate_holes(), [rect_poly(b.gripper_plate_window())],
             ["El cuello (x -52..-24) se pega en las ranuras del antebrazo", "Ventana del servo de la pinza"], None),
        19: ("MANDIBULA A", 2, A0, gr.hole_abs(gr.holes_A(), "A", 0.0), [], ["z=16 m=2; mandibula con cuerno del servo (pose cerrada)", "2 capas pegadas"], None),
        20: ("MANDIBULA B", 2, B0, gr.hole_abs(gr.holes_B(), "B", 0.0), [], ["Pivote libre O3.2 (pose cerrada)", "2 capas pegadas"], None),
    }
    return P


# ============================================================== conjunto
def conjunto():
    P = Sheet("plano_01_conjunto", "CONJUNTO - VISTA LATERAL Y PLANTA", 860, 610, 1, 3)
    th, psi, phi = POSE
    rho_ref, _ = g.find_phase()
    SX, SY = 130.0, 380.0            # origen del mundo (centro de la torreta, z=0) en la hoja, vista lateral
    TX, TY = 130.0, 150.0            # origen de la planta

    def side(poly, layer="CONTORNO", closed=True):
        P.layer(layer)
        P.pline([(x + SX, z + SY) for x, z in poly], closed)

    def siderect(x0, z0, x1, z1, layer="CONTORNO"):
        side(rect_poly((x0, z0, x1, z1)), layer)

    # ---------- mesa y base
    P.layer("SUELO")
    P.line((SX - 110, SY - 33), (SX + 300, SY - 33))
    for k in range(-110, 300, 14):
        P.line((SX + k, SY - 33), (SX + k - 8, SY - 41))
    siderect(-70, -33, 70, -30)                                # placa inferior
    siderect(-67, -30, 67, -14)                                # paredes (contorno)
    siderect(-70, -14, 70, -11)                                # placa superior
    siderect(-60, -3, 60, 0)                                   # torreta
    P.layer("SERVO")
    siderect(g.BODY_X0, -26.9, g.BODY_X1, -4.2, "SERVO")       # servo J1
    siderect(g.TAB_X0, -11.0, g.TAB_X1, -8.5, "SERVO")
    P.layer("EJES")
    P.line((SX, SY - 45), (SX, SY + 140))                      # eje J1
    # ---------- mejilla, brazo, hombro
    side(g.cheek_outline())
    for r in g.cheek_rects_right():
        side(rect_poly(r))
    P.layer("CONTORNO")
    side(g.arm_pose(g.arm_link_ply(), th))
    side(g.pinion_pose(g.pinion(), g.rho_at(th, rho_ref)))
    qx, qz = g.Q
    siderect(qx + g.TAB_X0, qz - g.SV_W / 2, qx + g.TAB_X1, qz + g.SV_W / 2, "SERVO")
    siderect(qx + g.BODY_X0, qz - g.SV_W / 2, qx + g.BODY_X1, qz + g.SV_W / 2, "SERVO")
    # ---------- codo (partes ocultas tras la placa del brazo)
    side(e.crank_pose(e.crank_ply(), psi), "OCULTO")
    side(e.rod_pose(e.rod_ply(), th, psi), "OCULTO")
    side(e.forearm_pose(e.forearm_left_ply(), th, psi), "OCULTO")
    side(e.forearm_pose(e.forearm_right_ply(), th, psi))
    # ---------- pinza (siluetas en el plano del antebrazo: u a lo largo, w normal)
    ex, ez = e.elbow_pt(th)
    p = math.radians(psi)
    xd, nn = (math.cos(p), math.sin(p)), (-math.sin(p), math.cos(p))
    A, B = gr.pose(phi)
    umax = max(max(q[0] for q in A), max(q[0] for q in B))

    def gw(u, w):
        uu = b.GOFF + u
        return (ex + uu * xd[0] + w * nn[0], ez + uu * xd[1] + w * nn[1])

    def grect(u0, w0, u1, w1, layer="CONTORNO"):
        side([gw(u0, w0), gw(u1, w0), gw(u1, w1), gw(u0, w1)], layer=layer)

    grect(b.NECK_X0, -1.5, gr.PLATE["x1"], 1.5)                                          # placa + cuello
    grect(gr.BODY_X0, -gr.SV_BELOW + 1.5, gr.BODY_X1, -gr.SV_BELOW + gr.SV_H + 1.5, "SERVO")   # servo
    grect(gr.TAB_X0, 1.5, gr.TAB_X1, 1.5 + gr.SV_TAB_T, "SERVO")
    grect(-9.5, gr.GEAR_Z0 + 0.5, 9.5, gr.GEAR_Z0 + 1.5)                                  # cuerno
    ulo = min(min(q[0] for q in A), min(q[0] for q in B))
    grect(ulo, gr.GEAR_Z0 + 1.5, umax, gr.GEAR_Z0 + 1.5 + 2 * g.T)                         # mandibulas (2 capas)
    tip = gw(umax, gr.GEAR_Z0 + 1.5 + g.T)
    # ---------- ejes y envolvente de J2
    P.layer("EJES")
    for (cx, cz) in ((0.0, g.H), (ex, ez)):
        P.line((SX + cx - 14, SY + cz), (SX + cx + 14, SY + cz))
        P.line((SX + cx, SY + cz - 14), (SX + cx, SY + cz + 14))
    P.layer("ENVOLVENTE")
    P.c("arc", center=[SX, SY + g.H], radius=g.L1, start=g.THETA_MIN, end=g.THETA_MAX)
    for t in (g.THETA_MIN, g.THETA_MAX):
        P.line((SX, SY + g.H), (SX + g.L1 * math.cos(math.radians(t)), SY + g.H + g.L1 * math.sin(math.radians(t))))
    # ---------- cotas lateral
    P.layer("COTAS")
    P.dimstyle(1.6)
    P.hdim((SX - 70, SY - 33), (SX + 70, SY - 33), SY - 62)
    P.vdim((SX - 70, SY - 33), (SX - 70, SY + g.H), SX - 100)
    P.vdim((SX - 60, SY), (SX - 60, SY + g.H), SX - 78)
    P.adim((SX, SY + g.H), (SX + ex, SY + ez), (SX - 30, SY + g.H + 60))
    P.hdim((SX + ex, SY + ez), (SX + tip[0], SY + tip[1]), SY + 150)
    P.hdim((SX, SY + g.H), (SX + tip[0], SY + g.H), SY + 178)
    P.c("dimangular", vertex=[SX, SY + g.H], p1=[SX + 55, SY + g.H], p2=[SX + 55 * math.cos(math.radians(th)), SY + g.H + 55 * math.sin(math.radians(th))],
        at=[SX + 48, SY + g.H + 16])
    P.layer("TEXTO")
    P.text((SX - 100, SY + 212), "VISTA LATERAL  (theta %.0f, psi %.0f, apertura %.0f deg)" % (th, psi, phi), 5.0)
    P.text((SX + 94, SY + g.H - 4), "J2: 5..85 deg", 3.0)
    P.text((SX + 4, SY - 50), "eje J1", 3.5)
    P.text((SX - 12, SY + g.H - 22), "S", 3.5)
    P.text((SX + ex + 4, SY + ez - 20), "E", 3.5)

    # ---------- planta (z -> y)
    def top(pts, layer="CONTORNO", closed=True):
        P.layer(layer)
        P.pline([(x + TX, y + TY) for x, y in pts], closed)

    def toprect(x0, y0, x1, y1, layer="CONTORNO"):
        top(rect_poly((x0, y0, x1, y1)), layer)

    toprect(-70, -70, 70, 70)
    P.layer("CONTORNO")
    P.c("circle", center=[TX, TY], radius=b.TURRET_R)
    toprect(g.BODY_X0, -g.SV_W / 2, g.BODY_X1, g.SV_W / 2, "OCULTO")                      # servo J1 (debajo)
    cx0, _, cx1, _ = bbox(g.cheek_outline())
    toprect(cx0, g.Y_C, cx1, g.Y_C + g.T)                                                  # mejillas
    toprect(cx0, -g.Y_C - g.T, cx1, -g.Y_C)
    toprect(g.BRACE["x0"], -g.Y_C - g.T, g.BRACE["x1"], g.Y_C + g.T)                      # travesano
    xr = lambda poly: (min(q[0] for q in poly), max(q[0] for q in poly))
    for poly, yr, lay in ((g.arm_pose(g.arm_link_ply(), th), g.Y_ARM_R, "CONTORNO"), (g.arm_pose(g.arm_left_plate(), th), g.Y_ARM_L, "CONTORNO"),
                          (g.arm_pose(g.arm_sector_ply(), th), g.Y_SECT, "OCULTO"),
                          (e.rod_pose(e.rod_ply(), th, psi), e.Y_ROD, "OCULTO"), (e.crank_pose(e.crank_ply(), psi), e.Y_CRANK, "OCULTO"),
                          (e.forearm_pose(e.forearm_left_ply(), th, psi), e.Y_FA_L, "CONTORNO"), (e.forearm_pose(e.forearm_right_ply(), th, psi), e.Y_FA_R, "CONTORNO")):
        a0, a1 = xr(poly)
        toprect(a0, yr[0], a1, yr[1], lay)
    # pinza en planta (psi = 0: el plano de las mandibulas es horizontal)
    yc = e.FA_YC

    def gtop(poly, layer="CONTORNO"):
        top([(ex + b.GOFF + u, v + yc) for u, v in poly], layer)

    gtop(b.gripper_plate())
    gtop(rect_poly((gr.BODY_X0, gr.PIV - gr.SV_W / 2, gr.BODY_X1, gr.PIV + gr.SV_W / 2)), "SERVO")
    for hx, hy, d in b.gripper_plate_holes():
        pass
    gtop(A)
    gtop(B)
    P.layer("EJES")
    P.line((TX - 80, TY), (TX + 300, TY))
    P.line((TX, TY - 80), (TX, TY + 80))
    # ---------- cotas planta
    P.layer("COTAS")
    P.hdim((TX - 70, TY - 70), (TX + 70, TY - 70), TY - 90)
    P.vdim((TX - 70, TY - 70), (TX - 70, TY + 70), TX - 90)
    P.vdim((TX + cx1 - 6, TY - g.Y_C - g.T), (TX + cx1 - 6, TY + g.Y_C + g.T), TX + cx1 + 14)
    P.hdim((TX, TY + 70), (TX + tip[0], TY + 70), TY + 92)
    P.ddim(TX, TY, 2 * b.TURRET_R, 135)
    P.layer("TEXTO")
    P.text((TX - 100, TY + 110), "PLANTA  (yaw 0; la torreta gira +-90 deg)", 5.0)
    P.dimstyle(1.0)

    # ---------- datos tecnicos
    px, py = 600.0, 580.0
    P.layer("TEXTO")
    P.text((px, py), "DATOS TECNICOS", 5.0)
    rows = [
        "Servos: 4  (J1, J2, J3 = MG90S; pinza = SG90 o MG90S)",
        "J1 base: servo vertical directo, guinada +-90 deg",
        "J2 hombro: theta 5..85 deg, engranes 2:1 (z14/z28, m2),",
        "   servo 0..160 deg",
        "J3 codo: servo coaxial con J2 + manivela 16 + biela 90",
        "   (paralelogramo). psi absoluto -65..50 deg;",
        "   rel = psi - theta en [-135, -35]",
        "Pinza: 1 servo, 2 engranes z16 m2 (1:1); cada mandibula",
        "   0..40 deg; apertura maxima ~70 mm",
        "Brazo L1 = 90, antebrazo L2 = 90, codo-puntas 182 (cerrada);",
        "   con apertura 20 deg las puntas quedan a 167 del codo",
        "Eje S a 60 sobre la torreta, mesa a 33 bajo la torreta",
        "Alcance horizontal max 261 mm; altura max ~289 mm",
        "Recoger de la mesa: r = 122..238 mm del eje J1",
        "Carga de diseno <= 40 g (J3 al 59 % del par con 50 g)",
        "Material MDF 3 mm; ranuras 3.1; kerf ~0.2 mm",
        "Piezas: planos 02 y 03; cortes: corte_final_mdf_3mm_*.svg",
        "Lineas: continua = a la vista, trazos = oculta,",
        "   magenta = envolvente de J2 (5..85 deg)",
    ]
    for i, s in enumerate(rows):
        P.text((px, py - 9 - 5.2 * i), s, 3.2)
    P.save()


def main():
    parts = build_parts()
    keys2 = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19, 20)
    keys3 = (11, 12, 13, 14, 15, 16, 17)
    conjunto()
    for code, title, num, keys, W in (("plano_02_brazo_piezas", "PIEZAS DEL BRAZO (HOMBRO, CODO Y PINZA)", 2, keys2, 800),
                                      ("plano_03_base_piezas", "PIEZAS DE LA BASE", 3, keys3, 720)):
        plist = [(k,) + parts[k][:2] + (parts[k][2], parts[k][3], parts[k][4], parts[k][5], parts[k][6]) for k in keys]
        sheet_parts(code, title, num, 3, W, plist)


if __name__ == "__main__":
    main()
