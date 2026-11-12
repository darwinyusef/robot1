# Brazo v2 - version para impresion 3D (FDM)

Mismo brazo que la version MDF (`../diseno`): misma cinematica, engranes, alcance, limites y firmware (`../control`). Esta carpeta **no modifica** nada de la version MDF; solo lee su geometria.

## Generar los STL

```
python3 generar_stl.py            # todo -> stl/*.stl  (~12 s)
python3 generar_stl.py torreta    # solo piezas cuyo nombre contiene "torreta"
```

Requiere `solidcraft-cli` (se busca en el PATH, en `/Applications/SolidCraft.app/Contents/MacOS/` o en `$SOLIDCRAFT_CLI`).
Cada STL sale ya en su orientacion de impresion (cara de apoyo en z=0). Cama minima: 200 x 200 mm (la mayor pieza es 140 x 140).

## Ajustes de impresion

FDM, boquilla 0.4, PLA o PETG, capa 0.2 mm. Piezas planas: 4 perimetros, 25-40 % de relleno. `seguro` y `calzo`: 100 %. Sin soportes en ninguna pieza.

Holguras FDM aplicadas (la version MDF usa otras): agujeros +0.2 mm, ranuras +0.25 mm, juego de dientes 0.30 mm.
Si tu impresora queda justa o floja, cambia `HOLE_ADD`, `SLOT_FDM` o `BACKLASH_FDM` al inicio de `generar_stl.py` y regenera.

## Piezas

| Archivo | Cant | Notas |
|---|---|---|
| 01_brazo_der_sector | 1 | placa + capa de sector fundidas, 6 mm |
| 02_brazo_izq | 1 | |
| 03_pinon_J2 | 1 | 6 mm, va en el cuerno del servo J2 |
| 04_mejilla_der_J2 | 1 | |
| 05_mejilla_izq_J3 | 1 | |
| 06_travesano | 1 | |
| 07_manivela | 1 | |
| 08_biela | 1 | |
| 09_antebrazo_izq | 1 | |
| 10_antebrazo_der | 1 | |
| 11_torreta | 1 | **boca abajo** como sale en el STL; las 8 orejas de rueda van fundidas al disco |
| 12_caja_base | 1 | placa inferior + 4 paredes + 4 postes con piloto M3 en una sola pieza |
| 13_placa_superior | 1 | tapa de la caja, 4 tornillos M3 x 8 a los postes |
| 14_placa_pinza | 1 | servo de la pinza arriba, orejas apoyadas sobre la placa |
| 15_mandibula_A | 1 | 6 mm, va en el cuerno del servo de la pinza |
| 16_mandibula_B | 1 | 6 mm |
| 17_separador_pinza | 1 | 3 mm, pivote B |
| 18_seguro | 20 | bolsillo hexagonal hacia arriba |
| 19_calzo_rodamiento | 8 | 0.2 mm |

## Que cambia respecto a MDF

- Capas de MDF pegadas (sector, piñon, mandibulas) -> una sola pieza de 6 mm.
- Caja de la base sin ranuras ni lengüetas; la tapa se atornilla a 4 postes (M3 x 8 en piloto de 2.6 mm; tambien sirven insertos roscados de laton).
- Pinza con el servo arriba: orejas sobre la placa, cuerpo arriba, mandibulas por debajo (cara superior de la mandibula a z = -6 mm, separador de 3 mm en el pivote B).
- Torreta con orejas integradas, se imprime sin soportes.

## Estado

Hecho: las 19 piezas generan STL validos (estancos, un solo cuerpo, apoyados en z=0).

Pendiente:
1. Servo J1 de la base **arriba** (hoy la base replica la pila de capas de MDF: servo dentro de la caja).
2. Bolsillos y postes de tornillo para los servos J2/J3 en las mejillas y para el de la pinza.
3. Revalidar los limites de colision con la geometria impresa (la pinza arriba dio entre igual y ~5 deg peor en simulacion). El firmware sigue usando `../control/brazo_v2/limites.h` de la version MDF hasta entonces.
4. Medir los servos con calibre antes de imprimir: la geometria asume 25 x 14 x 24.5 mm, orejas 33 mm.

## Ferreteria

Igual que `../diseno/BOM.md`, cambiando: sin pegamento para lengüetas; +4 tornillos M3 x 8 (tapa de la caja); separadores de pivote impresos (`17_separador_pinza`).
