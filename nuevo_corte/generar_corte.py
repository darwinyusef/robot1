"""Plancha SVG de corte laser (MDF 3 mm) con las piezas planas que NO cambian en la version impresa.

  python3 generar_corte.py   ->  corte_mdf_3mm_nuevo.svg  (400 x 400 mm)

Estas piezas se cortan en MDF; el resto del brazo se imprime (ver ../impresion_3d). Usa la geometria de ../diseno en solo lectura.
Capas del SVG: 2_AZUL_Primer_corte (agujeros), 3_NEGRO_Corte_final (contornos), 1_ROJO_Grabado (nombres).
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "diseno"))
import output_build as ob   # noqa: E402

CORTAR = ("PLACA BRAZO IZQ", "MEJILLA DER (J2)", "MEJILLA IZQ (J3)", "TRAVESANO", "MANIVELA", "BIELA",
          "ANTEBRAZO IZQ", "ANTEBRAZO DER", "PLACA PINZA+CUELLO")


def main():
    sel = [p for p in ob.parts() if p[0] in CORTAR]
    faltan = set(CORTAR) - {p[0] for p in sel}
    assert not faltan, faltan
    items = [(n,) + ob.orient(poly, holes, voids) for (n, qty, poly, holes, voids) in sel for _ in range(qty)]
    sheets = ob.pack(items)
    assert len(sheets) == 1, "no caben en una plancha: %d" % len(sheets)
    out = os.path.join(HERE, "corte_mdf_3mm_nuevo.svg")
    ob.write_sheet(out, "Brazo v2 - piezas MDF 3 mm que no cambian en la version impresa", sheets[0])
    print("OK", out, "-", len(items), "piezas")
    for (n, *_), ox, oy in sheets[0]:
        print("  ", n)


if __name__ == "__main__":
    main()
