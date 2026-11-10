"""Constructor de escenas SolidCraft (comandos JSON) para el hombro y el codo v2.

Plano de las placas: XZ (x adelante, z arriba); una placa con cara superior en y=y_top ocupa [y_top-T, y_top].
"""
import json
import math
import os
import subprocess

import shoulder_geom as g

CLI = r"I:\SolidCraft\solidcraft-cli.exe"


class Scene:
    def __init__(self):
        self.steps = []
        self.colors = {}

    def cmd(self, c, **p):
        self.steps.append({"command": c, "params": p})

    def plate(self, name, y_top, poly, holes=(), rects=(), color="#c8a165", thick=g.T, opacity=1.0):
        r4 = lambda p: [round(p[0], 4), round(p[1], 4)]
        self.cmd("sketch.create", plane={"origin": [0, y_top, 0], "x_dir": [1, 0, 0], "y_dir": [0, 0, 1]})
        self.cmd("sketch.line", points=[r4(p) for p in poly], closed=True)
        for (x0, z0, x1, z1) in rects:
            self.cmd("sketch.rectangle.two_point", p0=[round(x0, 4), round(z0, 4)], p1=[round(x1, 4), round(z1, 4)])
        for (x, z, d) in holes:
            self.cmd("sketch.circle.center", center=[round(x, 4), round(z, 4)], diameter=d)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=thick, body_name=name, operation="new")
        self.colors[name] = (color, opacity)

    def pplate(self, name, origin, xd, yd, poly, holes=(), rects=(), color="#c8a165", thick=g.T, opacity=1.0):
        """placa en un plano arbitrario: coordenadas 2D (u,v) sobre los ejes xd,yd; se extruye hacia xd x yd."""
        r4 = lambda p: [round(p[0], 4), round(p[1], 4)]
        self.cmd("sketch.create", plane={"origin": [round(c, 4) for c in origin], "x_dir": [round(c, 6) for c in xd], "y_dir": [round(c, 6) for c in yd]})
        self.cmd("sketch.line", points=[r4(p) for p in poly], closed=True)
        for (x0, z0, x1, z1) in rects:
            self.cmd("sketch.rectangle.two_point", p0=[round(x0, 4), round(z0, 4)], p1=[round(x1, 4), round(z1, 4)])
        for (x, z, d) in holes:
            self.cmd("sketch.circle.center", center=[round(x, 4), round(z, 4)], diameter=d)
        self.cmd("sketch.finish")
        self.cmd("solid.extrude", distance=thick, body_name=name, operation="new")
        self.colors[name] = (color, opacity)

    def zcyl(self, name, d, z0, z1, x, y, color, opacity=1.0):
        self.cmd("solid.cylinder", diameter=d, height=z1 - z0, base=[round(x, 4), round(y, 4), z0], axis="Z", body_name=name)
        self.colors[name] = (color, opacity)

    def cyl(self, name, d, y0, y1, x, z, color):
        self.cmd("solid.cylinder", diameter=d, height=y1 - y0, base=[round(x, 4), y0, round(z, 4)], axis="Y", body_name=name)
        self.colors[name] = (color, 1.0)

    def box(self, name, x0, y0, z0, dx, dy, dz, color):
        self.cmd("solid.box", length=dx, width=dy, height=dz, corner=[round(x0, 4), y0, round(z0, 4)], body_name=name)
        self.colors[name] = (color, 1.0)

    def finish(self):
        for n, (col, op) in self.colors.items():
            self.cmd("appearance.assign", bodies=[n], color=col, opacity=op)
        return self.steps

    def build(self, tag, here, views=("iso", "right"), size=(1400, 1000)):
        script = os.path.join(here, "%s_script.json" % tag)
        with open(script, "w", encoding="utf-8") as f:
            json.dump({"commands": self.finish()}, f)
        sc = os.path.join(here, "%s.sc" % tag)
        r = subprocess.run([CLI, "run", script, "--save", sc, "--quiet"], capture_output=True, text=True)
        print(tag, r.returncode, r.stderr[-600:])
        if r.returncode:
            return False
        for v in views:
            subprocess.run([CLI, "snapshot", "--in", sc, "--out", os.path.join(here, "%s_%s.png" % (tag, v)),
                            "--view", v, "--width", str(size[0]), "--height", str(size[1])], capture_output=True, text=True)
        os.remove(script)
        return True


def shoulder(sc, theta, rho_ref, turret=True):
    """torreta provisional (opcional), mejillas, servo J2 con piñon, brazo (3 capas) y perno S."""
    qx, qz = g.Q
    if turret:
        sc.cmd("solid.cylinder", radius=60, height=3, base=[0, 0, -3], axis="Z", body_name="torreta_prov")
        sc.colors["torreta_prov"] = ("#9a9a9a", 0.6)
    sc.plate("mejilla_der", g.Y_C + g.T, g.cheek_outline(), g.cheek_right_holes(), g.cheek_rects_right())
    sc.plate("mejilla_izq", -g.Y_C, g.cheek_outline(), g.cheek_left_holes(), g.cheek_rects_left())

    # servo J2: orejas sobre la cara interior de la mejilla der., cuerpo hacia afuera
    sc.box("servo_J2", qx + g.BODY_X0, g.Y_C - g.SV_ABOVE, qz - g.SV_W / 2, g.SV_L, g.SV_H, g.SV_W, "#202428")
    sc.box("servo_J2_orejas", qx + g.TAB_X0, g.Y_C - g.SV_TAB_T, qz - g.SV_W / 2, g.SV_TAB_L, g.SV_TAB_T, g.SV_W, "#202428")
    yg1 = g.Y_C - g.GEAR_GAP
    sc.cyl("servo_J2_eje", 4.8, g.Y_C - g.SV_ABOVE - 3.5, g.Y_C - g.SV_ABOVE, qx, qz, "#b8bec6")
    sc.cyl("cuerno_J2", 19.0, yg1, yg1 + 1.0, qx, qz, "#f2f2f2")
    rho = g.rho_at(theta, rho_ref)
    pin = g.pinion_pose(g.pinion(), rho)
    ph = [(qx + u * math.cos(rho) - v * math.sin(rho), qz + u * math.sin(rho) + v * math.cos(rho), d) for (u, v, d) in g.pinion_holes()]
    sc.plate("pinon_1", yg1, pin, ph, color="#ff8a1f")
    sc.plate("pinon_2", yg1 - g.T, pin, ph, color="#ff8a1f")

    c, s = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    hole_abs = lambda hs: [(u * c - v * s, g.H + u * s + v * c, d) for (u, v, d) in hs]
    sc.plate("brazo_der", g.Y_ARM_R[1], g.arm_pose(g.arm_link_ply(), theta), hole_abs(g.ARM_HOLES), color="#3aa0ff")
    sc.plate("brazo_sector", g.Y_SECT[1], g.arm_pose(g.arm_sector_ply(), theta), hole_abs(g.ARM_HOLES[:1]), color="#7cc0ff")
    sc.plate("brazo_izq", g.Y_ARM_L[1], g.arm_pose(g.arm_left_plate(), theta), hole_abs(g.ARM_HOLES), color="#3aa0ff")
    sc.cyl("perno_S", 3.0, -7.0, 26.0, 0.0, g.H, "#b8bec6")
