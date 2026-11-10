# Cableado y control - brazo v2 (4 servos)

## Conexiones (Arduino UNO/Nano, sketch `brazo_v2/brazo_v2.ino`)
| Servo | Funcion | Pin de senal | Recorrido servo | Variable del modelo |
|---|---|---|---|---|
| J1 | Base (vertical) | D3 | 180 deg | yaw -90..+90 -> servo = 90 + yaw |
| J2 | Hombro (2:1) | D5 | 160 deg | theta 5..85 -> servo = 2 x (theta - 5) |
| J3 | Codo (paralelogramo) | D6 | 115 deg | psi -65..50 -> servo = psi + 65 |
| Pinza | Mandibulas (1:1) | D9 | 40 deg | apertura 0..40 -> servo = apertura |

Los pines D3/D5/D6/D9 son PWM, pero la libreria `Servo` no los necesita; se pueden usar otros.

```
Fuente 5 V (>=3 A) +  --->  rojo de los 4 servos  ----+--- condensador 1000 uF ---+
Fuente GND            --->  marron/negro de los 4  ---+-------------------------+--- GND del Arduino (COMUN)
Arduino D3,D5,D6,D9   --->  naranja/amarillo (senal) de J1, J2, J3, pinza
```
- **Tierra comun** entre fuente y Arduino; el Arduino va por USB o por Vin aparte, nunca alimentar los servos con su 5 V.
- Condensador de 1000 uF (>= 10 V) entre + y GND lo mas cerca posible de los servos.
- Un MG90S bloqueado consume ~0.7-0.8 A; 4 servos moviendose a la vez pueden pedir 2 A: de ahi la fuente de >= 3 A.

### Alternativas
- **PCA9685** (I2C, 16 canales): V+ de servos desde la fuente, canales 0..3; ancho de pulso 500-2400 us equivale a 0..180 deg. Util si se agregan servos.
- **ESP32**: usar `ESP32Servo`, pines 18/19/21/22 por ejemplo. Alimentacion separada igual.

## Pasar los cables
1. Los cables de J2, J3 y pinza salen del brazo hacia la torreta (las mejillas estan encima).
2. Bajan por el **paso O10 de la torreta en (-28, 0)**, que cae justo sobre el **paso O10 de la placa superior** (mismo punto).
3. Dentro de la caja hacen un **bucle holgado** (el giro de la torreta es +-90 deg) y salen por el **agujero O10 de la pared trasera**.
4. El cable del J1 sale por el mismo agujero (el servo J1 es fijo).
5. Dejar al menos ~120 mm de cable libre entre la torreta y la caja; sujetar con una brida en la placa inferior (no en la torreta).

## Limites de control (obligatorios por software)
- Tabla `brazo_v2/limites.h` (generada por `diseno/output_build.py`): para cada theta, psi minimo y maximo libres de choque con mesa/base/torreta en cualquier guinada 0..90. El sketch interpola con el caso mas estrecho de las dos filas vecinas y agrega 2 deg de margen.
- Acoplamiento adicional: `rel = psi - theta` en [-135, -35] (si no, el paralelogramo se aplana o la biela toca el perno S).
- Con theta < 15 el rango util de psi es de pocos grados (el eje del hombro queda a solo 93 mm de la mesa).
- La tabla vale para la mesa a 33 mm bajo la torreta (z = -33 respecto a la tapa de la torreta). Si el brazo se monta sobre otra altura, regenerar.

## Calibracion (hacer **antes** de cargar el brazo)
1. Con el brazo sin bielas/antebrazo, cargar el sketch y mandar `H`; montar cada cuerno en su posicion central del modelo:
   - J1: servo 90 deg = brazo al frente.
   - J2: servo 0 deg = theta 5 (brazo casi horizontal).
   - J3: servo 0 deg = psi -65.
   - Pinza: servo 0 deg = cerrada.
2. Si algun eje gira al reves, cambiar `DIR_Jx` a -1 y ajustar `OFF_Jx`.
3. Mover a poca velocidad (`M 0 45 -30 20`, luego `M 0 60 0 20`, etc.) y verificar a mano las esquinas de la tabla antes de acercar a la mesa.
4. Alimentar siempre con la mano lista para desconectar la fuente la primera vez.

## Advertencias
- El sketch **no esta probado en hardware**. Los angulos de servo ya incluyen el recorrido del modelo pero requieren calibracion real (cero de cada cuerno, sentido, holgura de los engranes).
- Medir los servos con calibre y compararlos con las cotas de `gripper.py` / `shoulder_geom.py` antes de cortar.
