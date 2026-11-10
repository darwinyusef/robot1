# Canal MQTT del brazo (dos canales: entrada y salida)

Broker: TCP `178.156.191.90:1883` (ESP32) | `wss://mqtt.aquicreamos.com` (navegador). Prefijo de topics: `brazo_v2` (`MQTT_BASE`).

| Canal | Topic | Sentido | Contenido |
|---|---|---|---|
| ENTRADA | `brazo_v2/cmd` | tu app -> brazo | una linea de comando por mensaje |
| SALIDA | `brazo_v2/evt` | brazo -> tu app | respuestas y eventos (`HELLO`, `ANIMS ..`, `PLAY id`, `DONE id`, `ERR ..`, `STOP`, `HOME`, `STATE ..`) |
| SALIDA | `brazo_v2/state` | brazo -> tu app | `STATE ...` cada 1 s (retenido) |
| SALIDA | `brazo_v2/status` | brazo -> tu app | `online` / `offline` (LWT, retenido) |

Comandos (`brazo_v2/cmd`): `P yaw theta psi phi` | `PLAY id [loop]` | `TOUR` | `STOP` | `HOME` | `LIST` | `?`.
Los eventos propios del brazo (`DONE`, cambio de animacion en `TOUR`) salen a todos los canales (MQTT y WebSocket).

## Probar sin el visor (mosquitto)
    # salida: escuchar todo
    mosquitto_sub -h 178.156.191.90 -u USUARIO -P CLAVE -t 'brazo_v2/#' -v
    # entrada: mandar comandos
    mosquitto_pub -h 178.156.191.90 -u USUARIO -P CLAVE -t brazo_v2/cmd -m 'PLAY wave'
    mosquitto_pub -h 178.156.191.90 -u USUARIO -P CLAVE -t brazo_v2/cmd -m 'STOP'

Credenciales: solo en `esp32/brazo_v2_esp32/secrets.h` (gitignored) y en el panel del visor (no se guardan). Crear un usuario del brazo con permiso solo sobre `brazo_v2/#`.
