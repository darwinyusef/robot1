"""Junta las piezas a imprimir en UN solo archivo, ya acomodadas en placas (camas) de 256 x 256 mm.

  python3 organizar_impresion.py          -> placas/todo_impresion.3mf + .stl + vista.png (solo las piezas que se imprimen)
  python3 organizar_impresion.py --todo   -> igual, pero con las 19 piezas (tambien las que se cortan en MDF)
  python3 organizar_impresion.py --cama 220

Lee stl/*.stl (generar_stl.py). Cada placa queda separada 40 mm de la anterior en X; en el slicer se elige una placa a la vez.
Requiere trimesh + numpy + matplotlib.
"""
import glob
import os
import sys

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
STL, OUT = os.path.join(HERE, "stl"), os.path.join(HERE, "placas")
GAP, MARGIN, SEP = 4.0, 3.0, 40.0
# piezas que en la version nueva se cortan en MDF (ver ../nuevo_corte): el resto se imprime
MDF = ("01_", "02_", "03_", "04_", "05_", "06_", "07_", "08_", "09_", "10_", "14_")
CANT = {"18_seguro": 20, "19_calzo_rodamiento": 8}


def cargar(todo):
    items = []
    for f in sorted(glob.glob(os.path.join(STL, "*.stl"))):
        name = os.path.basename(f)[:-4]
        if not todo and name.startswith(MDF):
            continue
        m = trimesh.load(f)
        if m.extents[1] > m.extents[0]:
            m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))
        m.apply_translation(-m.bounds[0])
        for k in range(CANT.get(name, 1)):
            items.append(("%s_%d" % (name, k + 1) if name in CANT else name, m.copy()))
    return items


def empacar(items, cama):
    """cada pieza en la primera posicion libre (esquina inferior izquierda) de una malla de 1 mm; prueba tambien girada 90 grados."""
    n = int(cama - 2 * MARGIN)
    gap = int(np.ceil(GAP))
    items = sorted(items, key=lambda it: -(it[1].extents[0] * it[1].extents[1]))
    grids, plates = [], []
    for name, m in items:
        w, h = int(np.ceil(m.extents[0])) + gap, int(np.ceil(m.extents[1])) + gap
        for gi in range(len(grids) + 1):
            if gi == len(grids):
                grids.append(np.zeros((n, n), bool))
                plates.append([])
            G, hit = grids[gi], None
            for rot in (False, True):
                ww, hh = (h, w) if rot else (w, h)
                for y in range(0, n - hh + gap + 1):
                    for x in range(0, n - ww + gap + 1):
                        if not G[y:y + hh, x:x + ww].any():
                            hit = (x, y, ww, hh, rot)
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                x, y, ww, hh, rot = hit
                G[y:y + hh, x:x + ww] = True
                mm = m.copy()
                if rot:
                    mm.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))
                    mm.apply_translation(-mm.bounds[0])
                plates[gi].append((name, mm, x + MARGIN, y + MARGIN))
                break
    return plates


def main(argv):
    todo = "--todo" in argv
    cama = float(argv[argv.index("--cama") + 1]) if "--cama" in argv else 256.0
    items = cargar(todo)
    big = max(max(m.extents[:2]) for _, m in items)
    assert big <= cama - 2 * MARGIN, "la pieza mas grande (%.0f mm) no cabe en la cama de %.0f" % (big, cama)
    plates = empacar(items, cama)
    os.makedirs(OUT, exist_ok=True)
    scene = trimesh.Scene()
    fig, axs = plt.subplots(1, len(plates), figsize=(5.2 * len(plates), 5.4), squeeze=False)
    for i, plate in enumerate(plates):
        ox = i * (cama + SEP)
        print("placa %d: %d piezas" % (i + 1, len(plate)))
        ax = axs[0][i]
        ax.add_patch(plt.Rectangle((0, 0), cama, cama, fill=False, ec="#888", ls="--"))
        for name, m, x, y in plate:
            m = m.copy()
            m.apply_translation([ox + x, y, 0])
            scene.add_geometry(m, node_name="P%d_%s" % (i + 1, name), geom_name="P%d_%s" % (i + 1, name))
            ax.add_patch(plt.Rectangle((x, y), m.extents[0], m.extents[1], fc="#e8e4d8", ec="k", lw=0.5))
            if min(m.extents[:2]) > 12:
                ax.text(x + 1.5, y + m.extents[1] / 2, name[:14], fontsize=5)
        ax.set_xlim(-2, cama + 2)
        ax.set_ylim(-2, cama + 2)
        ax.set_aspect("equal")
        ax.set_title("Placa %d  (%d piezas)" % (i + 1, len(plate)), fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "vista.png"), dpi=130)
    scene.export(os.path.join(OUT, "todo_impresion.3mf"))
    trimesh.util.concatenate(list(scene.geometry.values())).export(os.path.join(OUT, "todo_impresion.stl"))
    print("OK", OUT, "-", len(items), "piezas en", len(plates), "placas de", cama, "mm")


if __name__ == "__main__":
    main(sys.argv[1:])
