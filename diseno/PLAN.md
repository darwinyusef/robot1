# Brazo robotico v2 - plan

## Decisiones (confirmadas por el usuario)
- Reducir la cantidad de servos (la v1 tenia 6). Se usan engranajes / bielas en lugar de un servo por articulacion.
- Se elimina el giro de muneca (J5).
- Carga: objetos pequenos y ligeros.
- Material: MDF 3 mm, corte laser.

## Arquitectura objetivo: 4 servos SG90/MG90S
| Servo | Funcion | Transmision |
|---|---|---|
| 1 | Base (giro J1) | directo, vertical, en la base |
| 2 | Hombro (J2) | reduccion de engranes 2:1 (mas torque; la articulacion recorre ~90 deg) |
| 3 | Codo (J3) | servo junto al hombro + manivela y biela en paralelogramo (el antebrazo toma el angulo absoluto de la manivela) |
| 4 | Pinza | 1 servo, 2 engranes involutos 1:1 (HECHO) |

Sin servo de muneca: la pinza va fija al extremo del antebrazo. Opcional mas adelante: segundo paralelogramo para que la pinza se mantenga horizontal.

## Fases
- [x] **Fase 1 - Pinza** (`gripper.py`): modelo 3D, SVG de corte, verificacion numerica (engrane sin solape de 0 a 40 deg, puntas cerradas a 0.6 mm, almohadillas paralelas a 20 deg, apertura maxima ~70 mm).
- [x] **Fase 2 - Hombro** (`shoulder_geom.py`, `shoulder_check.py`, `shoulder_build.py`): pinon z=14 + sector z=28 (m=2, 2:1, entre ejes 42 mm). Engrane sin solape en todo el recorrido (brazo 5..85 deg = servo 0..160 deg, distancia min ~0.1 mm). Diente MDF FS ~4-5. Par en el servo con 50 g de carga en el peor caso: SG90 60 %, MG90S 49 % -> **recomendado MG90S**. Salidas: `shoulder_{min,med,max}.sc/.png`, `corte_mdf_3mm_hombro_{1,2}.svg`, `shoulder_report.txt`.
  - Pila de capas en Y (mm): mejilla izq [-23,-20] | manivela/servo J3 (fase 3) [-12,-9] | placa izq. brazo [-8,-5] | capa sector [6,9] | placa der. brazo [9,12] | mejilla der. [20,23]; servo J2 por fuera de la mejilla der. (pinon en [6,12], cuerno [12,13]). Eje del hombro: perno de 3 mm, y in [-26,26].
  - Provisional: la torreta (disco) y las lenguetas de las mejillas se rehacen en la fase 4; la ventana del servo J3 en la mejilla izq. va en la fase 3; masas de antebrazo/pinza son estimadas.
- [x] **Fase 3 - Codo** (`elbow_geom.py`, `elbow_check.py`, `elbow_build.py`, `scene.py`): servo J3 coaxial con el eje S en la mejilla izquierda (espejo del J2); manivela RC=16 + biela de 90 mm (paralela al brazo) + palanca en la placa izq. del antebrazo. El antebrazo toma el angulo absoluto psi de la manivela (1:1, sin reduccion).
  - Capas en Y: cuerno J3 [-13,-12] | manivela y placa izq. antebrazo [-12,-9] | biela [-8.5,-5.5] | placa izq. brazo [-5,-2] (se corrio 3 mm) | placa der. antebrazo [12.5,15.5]; separador de 21.5 mm entre las placas del antebrazo (x=40 del antebrazo). Pernos: S de y=-7 a 26 (el brazo gira sobre ese perno, apoyado solo en la mejilla der.), codo y in [-13,16.5].
  - Limite acoplado por software: rel = psi - theta en [-135, -35] (fuera de eso el paralelogramo se aplana y pierde control, o la biela toca el perno S) y la pinza sobre la mesa (supuesta a 40 mm bajo la torreta). Recorrido de psi: -90..50 = 140 deg de servo (de 180).
  - Sin choques de piezas en todo el rango permitido (barrido theta x psi por capas). Par con 50 g: J3 SG90 55 % / MG90S 45 %; J2 baja a 26 % / 21 % porque el paralelogramo traslada el peso del antebrazo al J3 (la tabla de `shoulder_report.txt` es la estimacion vieja, pesimista). Biela: 11 N, pandeo FS 7.
  - Salidas: `arm_{a,b,c}.sc/.png`, `corte_mdf_3mm_codo.svg`, `elbow_report.txt`.
  - Riesgos abiertos: el perno S en voladizo (30 mm, solo apoyado en la mejilla der.); holgura de la biela con su perno; antebrazo con pinza de 25 g estimados.
- [x] **Fase 4 - Base y ensamblaje** (`base_geom.py`, `base_check.py`, `base_build.py`): servo J1 **vertical** dentro de una caja de MDF; torreta circular con el cuerno J1 y las mejillas.
  - Pila en z (tapa de la torreta = 0): torreta [-3,0] | cuerno J1 [-4,-3] | placa sup. [-14,-11] (orejas del servo encima, [-11,-8.5]; cuerpo por la ventana hasta -26.9) | paredes [-30,-14] con lenguetas de 3 mm que cruzan las dos placas | placa inf. [-33,-30]. Mesa en z=-33. Caja 140x140, paredes 3 mm hacia adentro, orificio de cables O10 en la pared trasera, 4 agujeros de esquina (acceso a tornillos de mesa).
  - La torreta rueda sobre 4 rodamientos 693 (eje M3 radial, a R=51 sobre los ejes x/y, 2 orejas de MDF por rueda con lengueta en la torreta, eje sujeto con 2 seguros impresos en 3D, el mismo O7.6 x 2 mm de todos los pasadores, y 2 calzos de 0.2 mm por rodamiento) sobre la placa sup. Las mejillas entran con lenguetas de 3 mm en ranuras de la torreta (x -44..-28 y 2..18) y se atan con un travesano (x 20..23, z 12..32) que cruza ranuras de ambas mejillas.
  - Interfaz de la pinza: la placa de la pinza tiene un **cuello** (x -52..-24, y +-13.75) que se pega en las ranuras abiertas al frente (3.1 mm) de las dos placas del antebrazo; se quitaron los 2 agujeros provisionales (-26,+-20). Alcance codo-puntas 182 mm (L2 + 92).
  - Verificado (`base_report.txt`, RESULTADO OK): antebrazo + pinza (nube 3D) contra mesa/torreta/base en guinada 0..90 deg, y contra mejillas/travesano/servos: psi permitido por theta de -30 (theta 5) a -65..50 (theta 65); total psi -65..50 = 115 deg de servo J3. Con theta < 15 el rango util de psi es muy corto porque la mesa esta a solo 93 mm bajo el eje S: se resuelve con el limite acoplado por software (tabla del reporte).
  - Par con 50 g en las puntas (pinza centrada a 36 mm): J3 SG90 67 % (sobre la regla de 60 %) / MG90S 55 % -> **MG90S en J3 y J2**; J2 21-26 %. Con 20 g: SG90 38 %.
  - Salidas: `robot_{a,b,c}.sc/.png` (3 poses: iso/right/top), `corte_mdf_3mm_base_{1,2}.svg`, `base_report.txt`. Los SVG del hombro y del codo se regeneraron con las lenguetas, las ranuras del travesano y la muesca frontal del antebrazo.
  - Riesgos abiertos: calibre real del servo J1 (ventana 23.4 x 12.8); la rueda toca la torreta en linea (hueco de 4.4 mm en la torreta evita roce) y la placa a la vez: si patina o roza, lijar 0.2 mm el borde inferior de las orejas o poner una arandela bajo la tuerca del eje; cable del J1 y de los J2/J3/pinza que suben por la torreta (dejar bucle para +-90 deg de guinada); el cuello de la pinza trabaja a flexion bajo carga (probar; si cede, doblar la capa o agregar un refuerzo).
- [x] **Fase 5 - Verificacion global** (`global_check.py` -> `global_report.txt`, `workspace.svg`; RESULTADO OK): rejilla theta x rel (paso 5) x guinada 0..90 con capas en Y + nube 3D + travesano.
  - Colisiones: 223 de 357 poses de la rejilla son factibles (las demas violan mesa/base/torreta o rel); sin choques de piezas, travesano incluido. psi usado -65..50 (115 deg de J3), theta 5..85 (160 deg de J2). Con theta <= 15 quedan 1-4 poses por fila (el eje S esta a 93 mm de la mesa).
  - Alcance de las puntas: horizontal maximo 261 mm; altura maxima ~289 mm; recoger de la mesa (puntas a <= 8 mm) solo entre r = 122 y 238 mm del eje J1 (nada dentro de la base).
  - Par con masas reales de las piezas, 50 g en las almohadillas: J2 21 % (MG90S), **J3 59 % MG90S / 72 % SG90** (peor pose: antebrazo horizontal, theta ~65). Carga maxima al 60 %: MG90S 50 g, SG90 30 g. Con 20 g: J3 34 % / 41 %. Recomendado: **MG90S en J2 y J3, carga de diseno <= 40 g** para dejar margen.
  - Biela 13.9 N, pandeo FS 5.3. Pinza: ~4-5 N por mandibula, FS 6-8 para 50 g; diente FS 6.
  - Torreta: con carga 50 g la torreta intenta levantarse atras con 3.3 N (335 gf) en el centro -> el tornillo del cuerno J1 debe ser pasante con arandela (no confiar solo en el estriado). J1 con 4.3e-3 kg*m2 extendido: barrido de 180 deg en >= 0.83 s (SG90) / 0.73 s (MG90S).
  - Riesgos abiertos: J3 al 59 % con 50 g es el eslabon justo (contrapeso o limitar a 40 g); medir masas reales; todo estatico, sin dinamica ni holguras reales.
- [x] **Fase 6 - Salida** (`output_build.py` -> `output_report.txt`, RESULTADO OK): 
  - Planchas finales de **2 x 350x350 mm** (24 piezas, 37 % de aprovechamiento): `corte_final_mdf_3mm_{1,2}.svg`, con la convencion de taller del usuario: **AZUL = primer corte (interiores), NEGRO = corte final (contornos), ROJO = grabado (rotulos)** (las fases 1-5 usaban rojo=corte / azul=grabado; los SVG por fase quedan solo como referencia).
  - Control de puentes minimos (>= 1.5 mm entre contornos y huecos): corregido el radio del cubo de la manivela y de la mandibula A (`HUB_R` y `RH` 10 -> 11.5 mm; pinza y codo re-verificados) y un error de orden de `gr.WIN` (x0,x1,y0,y1) en la ventana de la placa de la pinza (`base_geom.gripper_plate_window()`). **Excepcion documentada**: 1.05 mm de MDF entre la ventana del servo y el tornillo de la oreja del lado del eje (mejillas, placa superior, placa de la pinza); no es estructural (la oreja se apoya en la placa).
  - Paso de cables: agujero O10 en (-28, 0) en la placa superior y en la torreta (`CABLE_PASS`), mas el O10 de la pared trasera.
  - `BOM.md` (3 MG90S + 1 SG90, ferreteria estimada, 2 planchas), `../control/WIRING.md` (D3/D5/D6/D9, fuente 5 V >= 3 A, tierra comun, ruta de cables, calibracion), `../control/brazo_v2/brazo_v2.ino` (**sin probar**) y `../control/brazo_v2/limites.h` (psi_min/psi_max por theta; generado).
  - **Planos con cadcraft-cli** (`planos_cadcraft.py`, `python -I`): `plano_01_conjunto` (vista lateral + planta, pose theta 45 / psi 0 / apertura 20, datos tecnicos), `plano_02_brazo_piezas` (piezas 1-10 y 18-20) y `plano_03_base_piezas` (piezas 11-17), cada uno en `.dxf`, `.png` y `.pdf`, mm, 1:1, con cotas, ejes y cajetin. La numeracion de piezas es la de `output_report.txt`. Se generan desde la misma geometria, asi que se regeneran al cambiar los parametros.
  - Riesgos abiertos: ver "Pendiente de confirmar con el hardware real".

## Pendiente de confirmar con el hardware real
- Cotas del servo en `gripper.py` (SV_*): cuerpo 22.8x12.2x22.7, orejas 32.5, agujeros a 2.4 mm del borde, eje a 6 mm del extremo, cuerpo 15.9 mm bajo las orejas. Medir con calibre antes de cortar.
- Patron de agujeros del cuerno (`HORN_HOLE_R`, `HORN_HOLE_D`) segun el cuerno que se use.
- Puente de 1.05 mm junto a los tornillos de las orejas de los servos (si se rompe en la prueba, usar 1 tornillo + cola o ensanchar el margen).
- Rigidez del perno S en voladizo, J3 al 59 % con 50 g (limitar a 40 g), cuello de la pinza a flexion, calibracion de ceros/sentidos en `brazo_v2.ino`.
- Holgura de los dientes (`BACKLASH`): ajustar tras una prueba de corte, segun el kerf del laser.
