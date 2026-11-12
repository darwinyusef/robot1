# Hub WebSocket del brazo v2

```
visor 3D / vision (JS o Python) --\
                                   >-- hub (Docker, :8080) --ws--> ESP32 (WiFi)
MQTT (opcional) ------------------/
```

El ESP32 se conecta al hub como cliente (`/ws/esp32`). Visor, vision y MQTT mandan las mismas lineas de texto que entiende el firmware
(`P yaw th psi phi`, `PLAY id`, `TOUR`, `HOME`, `STOP`, `LIST`, `?`). El hub valida cada linea, recorta `P` a los limites y la limita a 25 Hz.

## Arrancar (5 min)

1. `cd control/hub && cp .env.example .env` y pon un `HUB_TOKEN` largo (`openssl rand -hex 24`).
2. `docker compose up -d --build`
3. Abre `http://localhost:8080/` (el visor 3D lo sirve el hub), panel "Brazo real", via "Hub", pega el token, Conectar.
4. Sin brazo: `HUB_TOKEN=... python sim_esp32.py` simula el ESP32.

## ESP32

En `control/esp32/brazo_v2_esp32/secrets.h` (ver `secrets.example.h`): `STA_SSID/STA_PASS` (tu WiFi), `HUB_HOST` (IP de la maquina con Docker, o el dominio),
`HUB_PORT` 8080, `HUB_TLS` false (true con dominio + Caddy), `HUB_TOKEN` igual que el `.env`. Se mantienen WiFi directo (AP, puerto 81), MQTT y Serial.

## Vision (camara)

- Navegador: panel "Control por mano" del visor. Mueve el modelo 3D; marca "enviar al brazo real" para mandarlo al ESP32.
- Python/OpenCV: `cd control/vision && HUB_TOKEN=... python detector.py --modo pose` (o `--modo zonas`). Variables `HUB_URL`, `CAM_INDEX`.
- Mapa mano -> pose en `viewer3d/handpose.js` y `vision/cv/pose_map.py` (un test compara ambos).

## MQTT (opcional)

Define `MQTT_HOST` (+ `MQTT_PORT`, `MQTT_USER`, `MQTT_PASS`, `MQTT_BASE`, `MQTT_TRANSPORT=websockets` para `wss://`) en `.env`.
Topics: `<base>/hub/cmd` (entra), `<base>/hub/evt`, `<base>/hub/state`, `<base>/hub/status` (salen).

## Desplegado en el servidor (aquicreamos)

Hub en `/opt/stacks/brazo-hub` (compose con `.env` propio, sin publicar puertos; red `caddy-net`), enrutado por Caddy (`sites/brazo-hub.caddy`).
URL: `wss://ws-mq.aquicreamos.com` (usa el guion `-`: con `_` los clientes estrictos rechazan el certificado). ESP32: `HUB_HOST=ws-mq.aquicreamos.com`, `HUB_PORT=443`, `HUB_TLS=true`.
Actualizar: rsync de `hub/` y `viewer3d/` a `/opt/stacks/brazo-hub/control/` y `docker compose up -d --build`.

## TLS / internet

`DOMAIN=tu.dominio docker compose --profile tls up -d` levanta Caddy con HTTPS; usa `wss://` y `HUB_TLS=true`.
El firmware usa `beginSSL` sin verificar el certificado: protege contra espias pasivos, no contra uno activo. El token va en la URL: no lo expongas sin TLS.

## Pruebas

`cd control/hub && python -m pytest test_hub.py` (9) y `cd control/vision && python -m pytest test_pose_map.py` (4).
