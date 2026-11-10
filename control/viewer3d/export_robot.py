"""Exporta el modelo 3D del brazo v2 para el visor three.js.

NO modifica ningun archivo original: importa los modulos de la carpeta padre solo para LEER la geometria,
construye la escena en una pose de referencia (en una carpeta temporal) y escribe aqui:
  robot_data.js   mallas (una por cuerpo, cuantizadas) + metadatos de cinematica

Uso:  python -I export_robot.py
"""
import base64
import json
import math
import os
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True          # no crear __pycache__ en la carpeta de los originales
HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "diseno")
sys.path.insert(0, PARENT)

import shoulder_geom as g       # noqa: E402
import elbow_geom as e          # noqa: E402
import gripper as gr            # noqa: E402
import base_geom as b           # noqa: E402
import scene as S               # noqa: E402
import elbow_build as eb        # noqa: E402
import base_build as bb         # noqa: E402

CLI = S.CLI
TH0, PSI0, PHI0 = 45.0, -30.0, 20.0     # pose de referencia en la que se construyen las mallas
RHO_REF, _ = g.find_phase()


def parse_limits():
    txt = open(os.path.join(os.path.dirname(HERE), "brazo_v2", "limites.h"), encoding="utf-8").read()
    out = {}
    for key in ("TH_LIM", "PSI_LO", "PSI_HI"):
        i = txt.index(key)
        body = txt[txt.index("{", i) + 1: txt.index("}", i)]
        out[key] = [int(x) for x in body.split(",")]
    return out


def build_scene():
    sc = S.Scene()
    bb.base(sc)
    S.shoulder(sc, TH0, RHO_REF, turret=False)
    eb.elbow(sc, TH0, PSI0)
    bb.gripper_on_forearm(sc, TH0, PSI0, PHI0)
    return sc


def export_obj(sc, path_obj):
    tmp = tempfile.mkdtemp(prefix="v2viewer_")
    script = os.path.join(tmp, "s.json")
    with open(script, "w", encoding="utf-8") as f:
        json.dump({"commands": sc.finish()}, f)
    r = subprocess.run([CLI, "run", script, "--out", path_obj, "--quiet"], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("solidcraft fallo: " + r.stderr[-800:])


def parse_obj(path):
    verts, bodies, cur = [], {}, None
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if ln.startswith("v "):
                verts.append(tuple(float(x) for x in ln.split()[1:4]))
            elif ln.startswith("o "):
                cur = ln[2:].strip()
                bodies[cur] = []
            elif ln.startswith("f ") and cur is not None:
                idx = [int(t.split("/")[0]) - 1 for t in ln.split()[1:]]
                for k in range(1, len(idx) - 1):          # abanico de triangulos
                    bodies[cur].append((idx[0], idx[k], idx[k + 1]))
    return verts, bodies


def pack(verts, tris, step=0.02):
    """suelda vertices, cuantiza a int16 (paso 'step' mm) respecto del centro del cuerpo."""
    used = sorted({i for t in tris for i in t})
    xs = [verts[i] for i in used]
    lo = [min(v[k] for v in xs) for k in range(3)]
    hi = [max(v[k] for v in xs) for k in range(3)]
    c = [0.5 * (lo[k] + hi[k]) for k in range(3)]
    q = lambda v: tuple(int(round((v[k] - c[k]) / step)) for k in range(3))
    remap, pos = {}, []
    ind = []
    for t in tris:
        row = []
        for i in t:
            qq = q(verts[i])
            if qq not in remap:
                remap[qq] = len(pos)
                pos.append(qq)
            row.append(remap[qq])
        if len(set(row)) == 3:
            ind += row
    pb = struct.pack("<%dh" % (3 * len(pos)), *[a for p in pos for a in p])
    if len(pos) < 65536:
        ib, itype = struct.pack("<%dH" % len(ind), *ind), 16
    else:
        ib, itype = struct.pack("<%dI" % len(ind), *ind), 32
    return dict(c=[round(a, 4) for a in c], s=step, n=len(pos), t=len(ind) // 3, itype=itype,
                p=base64.b64encode(pb).decode(), i=base64.b64encode(ib).decode(),
                bbox=[[round(a, 2) for a in lo], [round(a, 2) for a in hi]])


def main():
    sc = build_scene()
    tmp = tempfile.mkdtemp(prefix="v2viewer_")
    obj = os.path.join(tmp, "robot.obj")
    export_obj(sc, obj)
    verts, bodies = parse_obj(obj)
    print("cuerpos:", len(bodies), "vertices crudos:", len(verts))

    meshes = {}
    for name, tris in bodies.items():
        col, op = sc.colors.get(name, ("#c8a165", 1.0))
        m = pack(verts, tris)
        m["color"], m["opacity"] = col, op
        meshes[name] = m
    tot_t = sum(m["t"] for m in meshes.values())
    print("triangulos:", tot_t)

    ex, ez = e.elbow_pt(TH0)
    meta = dict(
        ref=dict(theta=TH0, psi=PSI0, phi=PHI0),
        H=g.H, L1=g.L1, L2=g.L2, RC=e.RC, Q=list(g.Q), RATIO=g.RATIO,
        GOFF=b.GOFF, GRIP_REACH=b.GRIP_REACH, PIV=gr.PIV, YC=e.FA_YC,
        PHI_MAX=gr.PHI_MAX, THETA_MIN=g.THETA_MIN, THETA_MAX=g.THETA_MAX,
        REL_MIN=e.REL_MIN, REL_MAX=e.REL_MAX, TABLE_Z=b.TABLE_Z,
        limits=parse_limits(),
    )
    data = "window.ROBOT_DATA = " + json.dumps(dict(meta=meta, meshes=meshes), separators=(",", ":")) + ";\n"
    out = os.path.join(HERE, "robot_data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write(data)
    print("escrito", out, "%.2f MB" % (len(data) / 1e6))


if __name__ == "__main__":
    main()
