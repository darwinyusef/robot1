# Brazo v2 en ESP32 (sin probar en hardware)

Firmware: `brazo_v2_esp32/` (Arduino IDE, placa "ESP32 Dev Module"; librerias `ESP32Servo`, `WebSockets` y `PubSubClient`).

## Conexion
| Servo | Pin ESP32 |
|---|---|
| J1 base | GPIO 18 |
| J2 hombro | GPIO 19 |
| J3 codo | GPIO 21 |
| Pinza | GPIO 22 |

Servos con fuente de 5 V >= 3 A aparte, **GND comun** con el ESP32 (ver `../WIRING.md`). Calibrar ceros y sentidos (`DIR_*`, `OFF_*` en el .ino) con el brazo sin bielas antes de moverlo.

## Usar
1. Cargar `brazo_v2_esp32.ino`. El ESP32 crea la red WiFi `BrazoV2` (clave `brazo1234`).
2. Conectar el PC a esa red y abrir `../viewer3d/index.html`.
3. Panel "Brazo real (ESP32)": `Conectar` (`ws://192.168.4.1:81`).
   - **Espejo en vivo**: el brazo sigue lo que muestra el visor (animacion o sliders).
   - **Ejecutar en el ESP32**: un boton por animacion (`joints, pick, wave, circles, scan, mech`) + Recorrido; el brazo la corre solo, sin el visor.
4. Tambien por Serial 115200: `PLAY wave`, `PLAY circles loop`, `TOUR`, `STOP`, `HOME`, `LIST`, `?`, `P yaw th psi phi`.

## MQTT
1. Copiar `brazo_v2_esp32/secrets.example.h` a `secrets.h` (esta en `.gitignore`) y poner tu WiFi 2.4 GHz y usuario/clave del broker. El ESP32 usa TCP `178.156.191.90:1883` (el `wss://mqtt.aquicreamos.com` es solo para el navegador).
2. Topics (prefijo `brazo_v2`): publicar comandos en `brazo_v2/cmd` (los mismos de Serial: `PLAY wave`, `TOUR`, `STOP`, `HOME`, `P y t p g`, `LIST`, `?`); leer `brazo_v2/evt` (respuestas), `brazo_v2/state` (1 Hz, retenido) y `brazo_v2/status` (`online`/`offline`, LWT).
3. En el visor: "Brazo real" -> `MQTT (internet)` -> usuario/clave -> Conectar. Espejo en vivo y botones de animacion funcionan igual que por WiFi directo.
4. Las tres vias (WebSocket, MQTT, Serial) conviven; el AP `BrazoV2` sigue activo aunque no haya internet.
5. Si el broker no responde, el firmware reintenta cada 5 s solo con el brazo quieto o en modo en vivo (nunca a mitad de una animacion).

Seguridad: el broker por TCP 1883 no va cifrado; crear un usuario propio del brazo con permiso solo sobre `brazo_v2/#` en vez de usar `admin`.

## Seguridad en el firmware
- J3 (psi) se limita siempre con la tabla de choques `limites.h` segun el J2 del momento (+2 grados de margen).
- Velocidad maxima por eje (`MAX_VEL`); antes de cada animacion el brazo viaja a la pose inicial y solo entonces corre el reloj.
- La animacion `explode` no se exporta: solo mueve la camara, el brazo no se mueve.

## Regenerar las animaciones
Si cambia `viewer3d/anims.js` o los limites:

    cd ../viewer3d && node tools/export_esp32.js

Escribe `brazo_v2_esp32/anims.h` (poses a 25 Hz) y `limites.h`, y lista cuanto recorta el firmware (J3 hasta 5 grados en `joints`) y las velocidades maximas.
