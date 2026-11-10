// Copiar a secrets.h (esta en .gitignore) y rellenar. NO subir secrets.h.
#pragma once
const char* STA_SSID = "";                 // tu WiFi (2.4 GHz). Vacio = sin MQTT, solo AP + WebSocket
const char* STA_PASS = "";
const char* MQTT_HOST = "178.156.191.90";  // TCP (el ESP32 no usa el wss://mqtt.aquicreamos.com)
const uint16_t MQTT_PORT = 1883;
const char* MQTT_USER = "";                // idealmente un usuario propio del brazo, no "admin"
const char* MQTT_PASS = "";
const char* MQTT_BASE = "brazo_v2";        // prefijo de topics
