// Brazo robotico v2 - ESP32 (4 servos) - SIN PROBAR en hardware.
// Reproduce las animaciones del visor 3D (anims.h) y/o sigue en vivo la pose que manda el visor por WebSocket.
//
// Librerias (Gestor de librerias): "ESP32Servo" (Kevin Harrington), "WebSockets" (Markus Sattler) y "PubSubClient" (Nick O'Leary).
// Placa: "ESP32 Dev Module". Antes de compilar: copiar secrets.example.h a secrets.h y rellenarlo (no se sube a git).
// Control por 4 vias a la vez: WebSocket local (AP "BrazoV2" -> ws://192.168.4.1:81), HUB (el ESP32 se conecta como cliente WebSocket
// al servidor Docker de ../hub, via tu WiFi), MQTT directo y Serial.
//
// HUB (secrets.h: HUB_HOST, HUB_PORT, HUB_TLS, HUB_TOKEN; HUB_HOST vacio = desactivado): ws[s]://HUB_HOST:HUB_PORT/ws/esp32?token=HUB_TOKEN
//   el hub reenvia los comandos del visor 3D / vision artificial; el ESP32 le manda HELLO, ANIMS, STATE (cada 1 s), DONE y ERR.
//
// MQTT (prefijo MQTT_BASE, por defecto "brazo_v2"):
//   <base>/cmd      (suscrito)  mismos comandos de abajo, una linea por mensaje
//   <base>/evt      (publica)   respuestas: HELLO, ANIMS ..., PLAY id, DONE id, ERR ..., STOP, HOME, STATE ...
//   <base>/state    (publica)   STATE cada 1 s (retenido)
//   <base>/status   (publica)   "online" / "offline" (LWT, retenido)
//
// Comandos (por WebSocket o por Serial 115200, una linea cada uno):
//   P yaw theta psi phi     pose en vivo (grados del modelo); cancela cualquier animacion
//   PLAY id [loop]          reproduce una animacion (ids: ver LIST); "loop" la repite
//   TOUR                    reproduce todas en orden, en bucle
//   STOP                    detiene y mantiene la pose
//   HOME                    va a la pose de reposo
//   LIST                    ids de las animaciones   |   ?   estado
#include <WiFi.h>
#include <WebSocketsServer.h>
#include <WebSocketsClient.h>
#include <ESP32Servo.h>
#include <PubSubClient.h>
#include "secrets.h"        // STA_SSID, STA_PASS, MQTT_*, HUB_HOST, HUB_PORT, HUB_TLS, HUB_TOKEN
#include "limites.h"        // N_LIM, TH_LIM[], PSI_LO[], PSI_HI[]  (tabla de choques, ver ../../WIRING.md)
#include "anims.h"          // ANIMS[], N_ANIMS, ANIM_HZ            (generado por viewer3d/tools/export_esp32.js)

// ---------- red
const char* AP_SSID = "BrazoV2";
const char* AP_PASS = "brazo1234";       // minimo 8 caracteres
const uint16_t WS_PORT = 81;

// ---------- pines de senal (alimentar los servos con fuente externa de 5 V, GND comun: ver WIRING.md)
const uint8_t PIN_J1 = 18, PIN_J2 = 19, PIN_J3 = 21, PIN_GRIP = 22;

// ---------- calibracion (igual que brazo_v2.ino): servo = OFF + DIR * f(valor_modelo)
const int   DIR_J1 = +1, DIR_J2 = +1, DIR_J3 = +1, DIR_GRIP = +1;
const float OFF_J1 = 90.0, OFF_J2 = 0.0, OFF_J3 = 0.0, OFF_GRIP = 0.0;
const float GEAR_J2 = 2.0;
const int   US_MIN = 500, US_MAX = 2400;
const unsigned REST_MS = 3000;                    // sin moverse este tiempo, los 4 pines se apagan (servos sin par). 0 = nunca
#define LED_TEST 1                                 // 1 = prueba con LEDs: brillo proporcional al angulo (0 = servos reales)

// ---------- limites de seguridad (modelo)
const float SAFE = 2.0;
const float YAW_MIN = -90, YAW_MAX = 90, TH_MIN = 5, TH_MAX = 85, GRIP_MIN = 0, GRIP_MAX = 40;
const float REL_MIN = -135, REL_MAX = -35;
const float MAX_VEL[4] = {240, 120, 240, 240};     // deg/s del modelo (yaw, theta, psi, phi); J2 va x2 en el servo
const unsigned TICK_MS = 20;                       // 50 Hz
const float HOME_POSE[4] = {0, 45, -20, 20};

Servo sJ1, sJ2, sJ3, sGrip;
WebSocketsServer ws(WS_PORT);
WebSocketsClient hub;
unsigned long lastHubState = 0;
WiFiClient netClient;
PubSubClient mqtt(netClient);
String tCmd, tEvt, tState, tStatus;
unsigned long lastMqttTry = 0, lastStatePub = 0;
const int REPLY_SERIAL = -1, REPLY_MQTT = -2, REPLY_ALL = -3, REPLY_HUB = -4;   // ALL: eventos propios del brazo (DONE, siguiente anim del TOUR) a todos los canales

float cur[4] = {0, 45, -20, 20};                   // pose actual (modelo)
float tgt[4] = {0, 45, -20, 20};                   // destino
enum Mode { IDLE, LIVE, APPROACH, RUN };
Mode mode = IDLE;
int animIdx = -1; bool loopAnim = false, tourMode = false;
unsigned long animT0 = 0, lastTick = 0, lastActive = 0;
bool resting = false;
bool jOn[4] = {false, false, false, false};         // LED_TEST: solo el pin que se mueve esta activo; los demas se sueltan
unsigned long lastMv[4] = {0, 0, 0, 0};
String serialBuf;
int replyTo = REPLY_SERIAL;                        // quien mando el comando: cliente WS (>=0), Serial o MQTT

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

// mismo calculo que brazo_v2.ino: caso mas estrecho de las dos filas vecinas + margen SAFE
void psiLimits(float th, float &lo, float &hi) {
  th = clampf(th, TH_LIM[0], TH_LIM[N_LIM - 1]);
  int i = 0;
  while (i < N_LIM - 2 && th > TH_LIM[i + 1]) i++;
  float l = max(PSI_LO[i], PSI_LO[i + 1]);
  float h = min(PSI_HI[i], PSI_HI[i + 1]);
  lo = l + SAFE; hi = h - SAFE;
  if (lo > hi) lo = hi = 0.5f * (lo + hi);
  lo = max(lo, th + REL_MIN);
  hi = min(hi, th + REL_MAX);
  if (lo > hi) lo = hi = 0.5f * (lo + hi);
}
float safePsi(float th, float p) { float lo, hi; psiLimits(th, lo, hi); return clampf(p, lo, hi); }

int usFor(float deg) { return US_MIN + (int)((US_MAX - US_MIN) * clampf(deg, 0, 180) / 180.0f); }

int usJoint(int i) {
  switch (i) {
    case 0: return usFor(OFF_J1 + DIR_J1 * cur[0]);
    case 1: return usFor(OFF_J2 + DIR_J2 * GEAR_J2 * (cur[1] - TH_MIN));
    case 2: return usFor(OFF_J3 + DIR_J3 * (cur[2] + 65.0f));
    default: return usFor(OFF_GRIP + DIR_GRIP * cur[3]);
  }
}

#if LED_TEST
void ledOut(uint8_t pin, int us) { ledcWrite(pin, (uint32_t)((us - US_MIN) * 255L / (US_MAX - US_MIN))); }
void writeServos() {
  ledOut(PIN_J1, usFor(OFF_J1 + DIR_J1 * cur[0]));
  ledOut(PIN_J2, usFor(OFF_J2 + DIR_J2 * GEAR_J2 * (cur[1] - TH_MIN)));
  ledOut(PIN_J3, usFor(OFF_J3 + DIR_J3 * (cur[2] + 65.0f)));
  ledOut(PIN_GRIP, usFor(OFF_GRIP + DIR_GRIP * cur[3]));
}
#else
void writeServos() {
  sJ1.writeMicroseconds(usFor(OFF_J1 + DIR_J1 * cur[0]));
  sJ2.writeMicroseconds(usFor(OFF_J2 + DIR_J2 * GEAR_J2 * (cur[1] - TH_MIN)));
  sJ3.writeMicroseconds(usFor(OFF_J3 + DIR_J3 * (cur[2] + 65.0f)));
  sGrip.writeMicroseconds(usFor(OFF_GRIP + DIR_GRIP * cur[3]));
}
#endif

void setTarget(float y, float t, float p, float g) {
  tgt[0] = clampf(y, YAW_MIN, YAW_MAX);
  tgt[1] = clampf(t, TH_MIN, TH_MAX);
  tgt[2] = safePsi(tgt[1], p);
  tgt[3] = clampf(g, GRIP_MIN, GRIP_MAX);
}

float slew(float c, float t, float maxStep) {
  float d = t - c;
  return d > maxStep ? c + maxStep : (d < -maxStep ? c - maxStep : t);
}

bool atTarget(float tol) {
  for (int i = 0; i < 4; i++) if (fabsf(cur[i] - tgt[i]) > tol) return false;
  return true;
}

void say(const String &s) {
  Serial.println(s);
  if (replyTo >= 0) { String m = s; ws.sendTXT((uint8_t)replyTo, m); }
  else if (replyTo == REPLY_ALL) { String m = s; ws.broadcastTXT(m); if (mqtt.connected()) mqtt.publish(tEvt.c_str(), s.c_str()); if (hub.isConnected()) hub.sendTXT(m); }
  else if (replyTo == REPLY_HUB && hub.isConnected()) { String m = s; hub.sendTXT(m); }
  else if (replyTo == REPLY_MQTT && mqtt.connected()) mqtt.publish(tEvt.c_str(), s.c_str());
}

String stateStr() {
  float lo, hi; psiLimits(cur[1], lo, hi);
  String s = "STATE yaw=" + String(cur[0], 1) + " th=" + String(cur[1], 1) + " psi=" + String(cur[2], 1) +
             " phi=" + String(cur[3], 1) + " psi_ok=" + String(lo, 0) + ".." + String(hi, 0) + " mode=";
  s += (mode == IDLE ? "idle" : mode == LIVE ? "live" : "anim");
  if (animIdx >= 0 && mode >= APPROACH) s += " anim=" + String(ANIMS[animIdx].id);
  return s;
}
void stateLine() { say(stateStr()); }

// ---------- prueba individual: apaga todo, barre un servo 0 -> 180 -> 0 (angulo del servo, sin limites del modelo) y lo apaga; luego el siguiente
void hubService();
const uint8_t TEST_PINS[4] = {PIN_J1, PIN_J2, PIN_J3, PIN_GRIP};
const char *TEST_NAMES[4] = {"J1", "J2", "J3", "GRIP"};

void testPump(unsigned ms) {
  unsigned long t0 = millis();
  while (millis() - t0 < ms) { ws.loop(); hubService(); delay(2); }
}

void testOut(int i, int us) {
#if LED_TEST
  // "apagado" = pin liberado (alta impedancia): el LED queda apagado con cualquier cableado (a GND o a 3V3)
  static bool on[4] = {true, true, true, true};
  if (us <= 0) { if (on[i]) { ledcDetach(TEST_PINS[i]); pinMode(TEST_PINS[i], INPUT); on[i] = false; } }
  else {
    if (!on[i]) { ledcAttach(TEST_PINS[i], 1000, 8); on[i] = true; }
    ledcWrite(TEST_PINS[i], (uint32_t)((us - US_MIN) * 255L / (US_MAX - US_MIN)));
  }
#else
  Servo *sv[4] = {&sJ1, &sJ2, &sJ3, &sGrip};
  if (us <= 0) sv[i]->detach();
  else { if (!sv[i]->attached()) { sv[i]->setPeriodHertz(50); sv[i]->attach(TEST_PINS[i], US_MIN, US_MAX); } sv[i]->writeMicroseconds(us); }
#endif
}

void testAllOff() { for (int i = 0; i < 4; i++) { testOut(i, 0); jOn[i] = false; } }

// manda al visor la pose del modelo que corresponde al angulo del servo (i<0: la pose actual) para que el 3D siga la prueba
void tpSend(int i, float a) {
  float p[4] = {cur[0], cur[1], cur[2], cur[3]};
  if (i == 0) p[0] = (a - OFF_J1) / DIR_J1;
  else if (i == 1) p[1] = TH_MIN + (a - OFF_J2) / (DIR_J2 * GEAR_J2);
  else if (i == 2) p[2] = (a - OFF_J3) / DIR_J3 - 65.0f;
  else if (i == 3) p[3] = (a - OFF_GRIP) / DIR_GRIP;
  String m = "TP " + String(p[0], 1) + " " + String(p[1], 1) + " " + String(p[2], 1) + " " + String(p[3], 1);
  ws.broadcastTXT(m);
  if (hub.isConnected()) hub.sendTXT(m);
}

void testServo(int i) {
  say(String("TEST ") + TEST_NAMES[i]);
  testAllOff();
  tpSend(i, 0);
  testPump(600);
  for (int dir = 0; dir < 2; dir++) {                      // sube 0 -> 180, luego baja 180 -> 0
    for (int k = 0; k <= 100; k++) {
      float a = (dir == 0 ? k : 100 - k) * 1.8f;
      testOut(i, usFor(a));
      tpSend(i, a);
      testPump(20);
    }
    testPump(300);
  }
  testPump(500);                                           // queda en 0
  testOut(i, 0);                                           // apagado
  testPump(800);
}

bool testing = false;                                      // durante la prueba se ignoran los demas comandos (el espejo del visor encenderia los otros pines)

void runTest(int only) {                                   // only: 0..3 un servo, -1 todos
  testing = true;
  mode = IDLE;
  for (int i = 0; i < 4; i++) tgt[i] = cur[i];
  for (int i = 0; i < 4; i++) if (only < 0 || only == i) testServo(i);
  testAllOff();
  resting = true; lastActive = millis(); lastTick = millis();   // termina apagado; el siguiente movimiento reengancha todo
  testing = false;
  tpSend(-1, 0);
  say("TEST fin");
}

void startAnim(int idx, bool loop, bool tour) {
  animIdx = idx; loopAnim = loop; tourMode = tour;
  const int16_t *r = ANIMS[idx].d[0];
  setTarget(r[0] / 10.0f, r[1] / 10.0f, r[2] / 10.0f, r[3] / 10.0f);
  mode = APPROACH;                                  // primero llegar a la pose inicial, luego correr el reloj
  say(String("PLAY ") + ANIMS[idx].id);
}

int findAnim(const char *id) {
  for (int i = 0; i < N_ANIMS; i++) if (strcmp(ANIMS[i].id, id) == 0) return i;
  return -1;
}

void handleCmd(String line) {
  line.trim();
  if (testing) return;
  if (!line.length()) return;
  const char *c = line.c_str();
  if (c[0] == 'P' && c[1] == ' ') {
    float y, t, p, g;
    if (sscanf(c + 2, "%f %f %f %f", &y, &t, &p, &g) == 4) { mode = LIVE; setTarget(y, t, p, g); }
    else say("ERR formato: P yaw theta psi phi");
  } else if (!strncmp(c, "PLAY ", 5)) {
    char id[24] = {0}, opt[8] = {0};
    sscanf(c + 5, "%23s %7s", id, opt);
    int i = findAnim(id);
    if (i < 0) say("ERR animacion desconocida (ver LIST)"); else startAnim(i, !strcmp(opt, "loop"), false);
  } else if (!strcmp(c, "TOUR")) {
    startAnim(0, false, true);
  } else if (!strcmp(c, "STOP")) {
    mode = IDLE; for (int i = 0; i < 4; i++) tgt[i] = cur[i];
    say("STOP");
  } else if (!strcmp(c, "HOME")) {
    mode = LIVE; setTarget(HOME_POSE[0], HOME_POSE[1], HOME_POSE[2], HOME_POSE[3]);
    say("HOME");
  } else if (!strncmp(c, "TEST", 4) && (c[4] == 0 || (c[4] == ' ' && c[5] >= '1' && c[5] <= '4' && c[6] == 0))) {
    runTest(c[4] ? c[5] - '1' : -1);
  } else if (!strcmp(c, "OFF")) {
    mode = IDLE; for (int i = 0; i < 4; i++) tgt[i] = cur[i];
    testAllOff(); resting = true;
    say("OFF");
  } else if (!strcmp(c, "LIST")) {
    String s = "ANIMS ";
    for (int i = 0; i < N_ANIMS; i++) { if (i) s += ","; s += ANIMS[i].id; }
    say(s);
  } else if (c[0] == '?') {
    stateLine();
  } else {
    say("ERR comando desconocido");
  }
}

void onMqtt(char *topic, uint8_t *payload, unsigned int length) {
  char buf[96]; size_t n = min((size_t)length, sizeof(buf) - 1);
  memcpy(buf, payload, n); buf[n] = 0;
  replyTo = REPLY_MQTT;
  handleCmd(String(buf));
}

// no bloquea las animaciones: solo reintenta con el brazo quieto o en modo en vivo, cada 5 s
void mqttService() {
  if (!strlen(STA_SSID) || WiFi.status() != WL_CONNECTED) return;
  if (mqtt.connected()) {
    mqtt.loop();
    if (millis() - lastStatePub >= 1000) { lastStatePub = millis(); mqtt.publish(tState.c_str(), stateStr().c_str(), true); }
    return;
  }
  if (mode == APPROACH || mode == RUN) return;
  if (millis() - lastMqttTry < 5000) return;
  lastMqttTry = millis();
  String cid = String("brazo_v2_") + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.printf("MQTT -> %s:%d ... ", MQTT_HOST, MQTT_PORT);
  if (mqtt.connect(cid.c_str(), MQTT_USER, MQTT_PASS, tStatus.c_str(), 1, true, "offline")) {
    Serial.println("ok");
    mqtt.publish(tStatus.c_str(), "online", true);
    mqtt.subscribe(tCmd.c_str());
    replyTo = REPLY_MQTT; say("HELLO brazo_v2_esp32"); handleCmd("LIST");
  } else {
    Serial.printf("fallo (rc=%d)\n", mqtt.state());
  }
}

void onWs(uint8_t num, WStype_t type, uint8_t *payload, size_t length) {
  if (type == WStype_CONNECTED) {
    replyTo = num; say("HELLO brazo_v2_esp32"); handleCmd("LIST");
  } else if (type == WStype_TEXT) {
    char buf[96]; size_t n = min(length, sizeof(buf) - 1);
    memcpy(buf, payload, n); buf[n] = 0;
    // las poses en vivo llegan a ~25 Hz: solo se responde si hay error
    replyTo = num;
    handleCmd(String(buf));
  }
}

void onHub(WStype_t type, uint8_t *payload, size_t length) {
  if (type == WStype_CONNECTED) {
    Serial.println("HUB conectado");
    replyTo = REPLY_HUB; say("HELLO brazo_v2_esp32"); handleCmd("LIST"); lastHubState = 0;
  } else if (type == WStype_DISCONNECTED) {
    Serial.println("HUB desconectado");
  } else if (type == WStype_TEXT) {
    char buf[96]; size_t n = min(length, sizeof(buf) - 1);
    memcpy(buf, payload, n); buf[n] = 0;
    replyTo = REPLY_HUB;
    handleCmd(String(buf));
  }
}

// reconectar bloquea el loop unos segundos si el hub no responde: solo con el brazo quieto o en modo en vivo sin hub
void hubService() {
  if (!strlen(HUB_HOST) || WiFi.status() != WL_CONNECTED) return;
  if (hub.isConnected()) {
    hub.loop();
    if (millis() - lastHubState >= 1000) { lastHubState = millis(); String m = stateStr(); hub.sendTXT(m); }
  } else if (mode == IDLE) {
    hub.loop();
  }
}

// avanza la animacion: interpola entre filas muestreadas a ANIM_HZ
void runAnim() {
  const Anim &a = ANIMS[animIdx];
  float f = (millis() - animT0) * 0.001f * ANIM_HZ;
  int i = (int)f;
  if (i >= a.n - 1) {
    if (tourMode) { int nx = animIdx + 1; if (nx >= N_ANIMS) nx = 0; startAnim(nx, false, true); return; }
    if (loopAnim) { startAnim(animIdx, true, false); return; }
    mode = IDLE; say("DONE " + String(a.id));
    return;
  }
  float u = f - i;
  const int16_t *r0 = a.d[i], *r1 = a.d[i + 1];
  float v[4];
  for (int k = 0; k < 4; k++) v[k] = (r0[k] + (r1[k] - r0[k]) * u) / 10.0f;
  setTarget(v[0], v[1], v[2], v[3]);
}

void tick() {
  if (mode == APPROACH && atTarget(0.5f)) { mode = RUN; animT0 = millis(); }
  else if (mode == RUN) { replyTo = REPLY_ALL; runAnim(); }
  bool moving = !atTarget(0.01f) || mode == APPROACH || mode == RUN;
  float prev[4] = {cur[0], cur[1], cur[2], cur[3]};
  float dt = TICK_MS * 0.001f;
  cur[0] = slew(cur[0], tgt[0], MAX_VEL[0] * dt);
  cur[1] = slew(cur[1], tgt[1], MAX_VEL[1] * dt);
  cur[2] = safePsi(cur[1], slew(cur[2], tgt[2], MAX_VEL[2] * dt));   // psi se vuelve a limitar con el theta del momento
  cur[3] = slew(cur[3], tgt[3], MAX_VEL[3] * dt);
#if LED_TEST
  for (int i = 0; i < 4; i++) {                       // cada pin vive solo mientras su articulacion se mueve; REST_MS despues se suelta
    bool mv = fabsf(cur[i] - prev[i]) > 0.001f || fabsf(cur[i] - tgt[i]) > 0.01f;
    if (mv) { lastMv[i] = millis(); jOn[i] = true; testOut(i, usJoint(i)); }
    else if (jOn[i]) {
      if (REST_MS && millis() - lastMv[i] > REST_MS) { testOut(i, 0); jOn[i] = false; }
      else testOut(i, usJoint(i));
    }
  }
  (void)moving;
#else
  if (moving) {
    if (resting) for (int i = 0; i < 4; i++) testOut(i, usFor(0));   // reengancha los pines antes de escribir la pose
    resting = false; lastActive = millis();
    writeServos();
  } else if (!resting) {
    if (REST_MS && millis() - lastActive > REST_MS) { testAllOff(); resting = true; }
    else writeServos();
  }
#endif
}

void setup() {
  Serial.begin(115200);
  ESP32PWM::allocateTimer(0); ESP32PWM::allocateTimer(1); ESP32PWM::allocateTimer(2); ESP32PWM::allocateTimer(3);
  cur[2] = safePsi(cur[1], cur[2]);
  for (int i = 0; i < 4; i++) tgt[i] = cur[i];
  Servo *s[4] = {&sJ1, &sJ2, &sJ3, &sGrip};
  const uint8_t pins[4] = {PIN_J1, PIN_J2, PIN_J3, PIN_GRIP};
#if LED_TEST
  for (int i = 0; i < 4; i++) ledcAttach(pins[i], 1000, 8);
#else
  for (int i = 0; i < 4; i++) { s[i]->setPeriodHertz(50); s[i]->attach(pins[i], US_MIN, US_MAX); }
#endif
  testAllOff(); resting = true; lastActive = millis();   // arranca apagado (0); se enciende al primer movimiento
  WiFi.mode(WIFI_AP_STA);                           // AP propio (visor) + cliente de tu WiFi (MQTT)
  WiFi.softAP(AP_SSID, AP_PASS);
  if (strlen(STA_SSID)) { WiFi.setAutoReconnect(true); WiFi.begin(STA_SSID, STA_PASS); }
  tCmd = String(MQTT_BASE) + "/cmd"; tEvt = String(MQTT_BASE) + "/evt";
  tState = String(MQTT_BASE) + "/state"; tStatus = String(MQTT_BASE) + "/status";
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqtt);
  mqtt.setBufferSize(512);
  mqtt.setSocketTimeout(2);
  ws.begin();
  ws.onEvent(onWs);
  if (strlen(HUB_HOST) && strlen(STA_SSID)) {
    String path = String("/ws/esp32?token=") + HUB_TOKEN;
    if (HUB_TLS) hub.beginSSL(HUB_HOST, HUB_PORT, path.c_str()); else hub.begin(HUB_HOST, HUB_PORT, path.c_str());
    hub.onEvent(onHub);
    hub.setReconnectInterval(3000);
    hub.enableHeartbeat(15000, 5000, 2);
  }
  Serial.printf("Brazo v2 listo. WiFi \"%s\" (clave %s) -> ws://%s:%u\n", AP_SSID, AP_PASS, WiFi.softAPIP().toString().c_str(), WS_PORT);
  Serial.println("Comandos: P y t p g | PLAY id [loop] | TOUR | STOP | HOME | OFF | TEST [1-4] | LIST | ?");
  lastTick = millis();
}

void loop() {
  ws.loop();
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') { replyTo = REPLY_SERIAL; handleCmd(serialBuf); serialBuf = ""; }
    else if (serialBuf.length() < 90) serialBuf += ch;
  }
  mqttService();
  hubService();
  if (millis() - lastTick >= TICK_MS) {
    lastTick += TICK_MS;
    if (millis() - lastTick > 100) lastTick = millis();   // tras un bloqueo (WiFi/MQTT) no recuperar ticks en rafaga: saltaria el limite de velocidad
    tick();
  }
}
