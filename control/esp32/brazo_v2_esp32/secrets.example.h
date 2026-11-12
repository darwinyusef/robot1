// Copiar a secrets.h (esta en .gitignore) y rellenar. NO subir secrets.h.
#pragma once
const char* STA_SSID = "";                 // tu WiFi (2.4 GHz). Vacio = sin MQTT, solo AP + WebSocket
const char* STA_PASS = "";
const char* MQTT_HOST = "178.156.191.90";  // TCP (el ESP32 no usa el wss://mqtt.aquicreamos.com)
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER = "";                // idealmente un usuario propio del brazo, no "admin"
const char* MQTT_PASS = "";
const char* MQTT_BASE = "brazo_v2";        // prefijo de topics
// Hub WebSocket (Docker, ver ../../hub): el ESP32 se conecta a el como cliente. HUB_HOST vacio = desactivado.
const char* HUB_HOST = "";                 // IP o dominio del servidor donde corre el hub (p. ej. "192.168.1.50" o "brazo.ejemplo.com")
const uint16_t HUB_PORT = 8080;            // 8080 sin TLS, 443 con el perfil "tls" (Caddy)
const bool HUB_TLS = false;                // true = wss:// (sin verificar el certificado; ver hub/README.md)
const char* HUB_TOKEN = "";                // el mismo HUB_TOKEN del .env del hub
