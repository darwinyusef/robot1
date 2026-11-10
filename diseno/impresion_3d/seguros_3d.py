"""Genera los STL de los seguros del eje de las ruedas (impresion 3D) con solidcraft-cli.

  python3 seguros_3d.py            -> seguro.stl, calzo_rodamiento.stl (en esta carpeta)

Cada pieza se genera con el eje en Z y la cara de apoyo en z=0 (impresion sin soportes: el bolsillo mira hacia arriba).
"""
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import shoulder_geom as g  # noqa: E402
import base_geom as b  # noqa: E402

CLI = os.environ.get("SOLIDCRAFT_CLI") or shutil.which("solidcraft-cli") or "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli"
XY = {"origin": [0, 0, 0], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}


def plane(z):
    return {"origin": [0, 0, z], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]}


def disc(name, d, h):
    return [{"command": "sketch.create", "params": {"plane": XY}},
            {"command": "sketch.circle.center", "params": {"center": [0, 0], "diameter": d}},
            {"command": "sketch.finish", "params": {}},
            {"command": "solid.extrude", "params": {"distance": h, "body_name": name, "operation": "new"}}]


def hole(d, z0, depth):
    return [{"command": "sketch.create", "params": {"plane": plane(z0)}},
            {"command": "sketch.circle.center", "params": {"center": [0, 0], "diameter": d}},
            {"command": "sketch.finish", "params": {}},
            {"command": "solid.extrude", "params": {"distance": depth, "operation": "cut"}}]


def hexpocket(af, z0, depth):
    r = af / math.sqrt(3)
    pts = [[round(r * math.cos(math.radians(60 * k)), 4), round(r * math.sin(math.radians(60 * k)), 4)] for k in range(6)]
    return [{"command": "sketch.create", "params": {"plane": plane(z0)}},
            {"command": "sketch.line", "params": {"points": pts, "closed": True}},
            {"command": "sketch.finish", "params": {}},
            {"command": "solid.extrude", "params": {"distance": depth, "operation": "cut"}}]


def export(name, steps):
    import json
    tmp = os.path.join(HERE, name + "_script.json")
    with open(tmp, "w") as f:
        json.dump({"commands": steps}, f)
    r = subprocess.run([CLI, "run", tmp, "--out", os.path.join(HERE, name + ".stl"), "--quiet"], capture_output=True, text=True)
    os.remove(tmp)
    print(name, r.returncode, r.stderr[-300:])
    return r.returncode == 0


def main():
    ok = True
    # un solo seguro para cabeza y tuerca: disco O7.6 x 2.0, paso O3.4, bolsillo hexagonal (llave 5.8, aloja la cabeza O5.7 o la tuerca M3) de 1.6 abierto hacia arriba, piso de 0.4
    h = b.CAP_T
    ok &= export("seguro", disc("seguro", b.CAP_OD, h) + hole(g.CAP_HOLE, -1, h + 2) + hexpocket(g.CAP_AF, g.CAP_FLOOR, 3))
    ok &= export("calzo_rodamiento", disc("calzo_rodamiento", b.SHIM_OD, b.SHIM_T) + hole(b.SHIM_ID, -1, b.SHIM_T + 2))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
