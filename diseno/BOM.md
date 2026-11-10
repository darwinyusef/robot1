# Brazo robotico v2 - lista de materiales (BOM)

Las longitudes de tornillos y pernos salen del modelo 3D y son **estimadas**: verificar con el ensamble real antes de comprar por mayor.

## Electronica
| Cant | Pieza | Uso | Nota |
|---|---|---|---|
| 3 | Servo MG90S (engranes metalicos) | J1 base, J2 hombro, J3 codo | J2 y J3 cargan el brazo (J3 59 % del par con 50 g). Recomendado MG90S |
| 1 | Servo SG90 (o MG90S) | Pinza | Carga ligera; con SG90 el diente de MDF tiene FS 6 |
| 1 | Arduino UNO/Nano (o ESP32, o PCA9685) | Control | ver `WIRING.md` |
| 1 | Fuente 5 V >= 3 A (o 6 V si los servos la admiten) | Servos | **No alimentar los servos desde el Arduino** |
| 1 | Condensador electrolitico 1000 uF >= 10 V | Filtro de la fuente | cerca de los servos |
| ~1 m | Cable Dupont / 3 hilos | Servos | los J2/J3/pinza suben por la torreta |
| 1 | Jumper/conector para la fuente | | |

Cada servo trae su cuerno y tornillos. Usar el cuerno de **1 brazo largo/estrella** que coincida con el patron de agujeros del modelo (`HORN_HOLE_R`, `HORN_HOLE_D`; medir).

## MDF 3 mm (corte laser)
- **2 planchas de 350 x 350 mm** (aprovechamiento 37 %; sobra espacio para repuestos): `corte_final_mdf_3mm_1.svg` y `corte_final_mdf_3mm_2.svg`.
- Capas: AZUL = primer corte (agujeros y ranuras), NEGRO = corte final (contornos), ROJO = grabado (rotulos).
- 24 piezas: placa brazo der./izq., capa sector, 2 pinones, mejilla der./izq., manivela, biela, antebrazo izq./der., placa superior, placa inferior, torreta, travesano, pared frontal/trasera, 2 paredes laterales, placa de la pinza con cuello, 2 mandibulas A y 2 mandibulas B.
- Hacer **una prueba de kerf** antes (ranuras 3.1 mm, agujeros 3.2 y 2.2 mm, dientes con `BACKLASH`).

## Ferreteria (estimada)
| Cant | Pieza | Uso |
|---|---|---|
| 1 | Perno M3 x ~35 + tuerca | eje del hombro (S) |
| 1 | Pasador / perno M3 x ~30 + tuerca | eje del codo |
| 1 | Perno M3 x 30 + tuerca + tubo/separador O6 x 21.5 | separador entre las placas del antebrazo |
| 2 | Pasador M3 x 10 + tuerca | manivela y palanca (extremos de la biela) |
| 1 | Tornillo M3 x ~22 + separador O6 x 8 | pivote B de la pinza |
| 4 | Tornillo M3 x 16 + espaciador de nylon 8 mm + tuerca | patines de la torreta |
| 1 | Tornillo M3 pasante (largo para cuerno + torreta) + arandela grande | centro del cuerno J1 (**obligatorio**: la torreta tiende a levantarse 3.3 N con 50 g) |
| 4 | Tornillos M3 cortos | cuerno J1 a la torreta (4 agujeros) |
| 8-12 | Tornillos M2 x 8-10 (o los del servo) + tuercas | fijar los 4 servos |
| 4 | Tornillos M3 x 16-20 + tuercas | fijar la base a la mesa (agujeros O9 en las esquinas, accesibles desde arriba) |
| - | Cianoacrilato / cola para madera | lenguetas, cuello de la pinza, paredes |
| - | Pads de goma o cinta antideslizante | almohadillas de las mandibulas |

## Herramientas
Calibre (medir servos antes de cortar), llave de 5.5 mm, destornilladores, lija fina para ajustar lenguetas.

## Masa y alcance (referencia, ver `global_report.txt`)
- Alcance horizontal maximo de las puntas 261 mm; altura maxima ~289 mm; recoger de la mesa entre r = 122 y 238 mm del eje J1.
- Carga de diseno **<= 40 g** (MG90S en J2/J3). Maximo al 60 % del par: 50 g (MG90S) / 30 g (SG90).
