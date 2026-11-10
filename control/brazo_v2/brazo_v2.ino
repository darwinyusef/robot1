// Brazo robotico v2 - 4 servos (base, hombro 2:1, codo por paralelogramo, pinza)  -- SIN PROBAR en hardware.
// Arduino UNO/Nano + libreria Servo. Alimentar los servos con una fuente de 5 V >= 3 A aparte, GND comun (ver WIRING.md).
//
// Coordenadas de entrada (grados, las mismas del modelo):
//   yaw   -90..+90   giro de la base (J1)
//   theta   5..85    angulo del brazo sobre la horizontal (J2)
//   psi   angulo ABSOLUTO del antebrazo sobre la horizontal (J3); se limita segun theta con limites.h
//   grip    0..40    apertura de la pinza (0 = cerrada), servo 1:1
// Comandos por serie (115200, fin de linea):  "M yaw theta psi grip"   mover   |   "H" posicion de reposo   |   "?" estado
//
// ANTES DE CONECTAR EL BRAZO: calibrar con el brazo desarmado de las bielas (ver CALIBRACION abajo).
#include <Servo.h>
#include "limites.h"        // N_LIM, TH_LIM[], PSI_LO[], PSI_HI[] generados por output_build.py

// ---------- pines
const uint8_t PIN_J1 = 3, PIN_J2 = 5, PIN_J3 = 6, PIN_GRIP = 9;

// ---------- CALIBRACION (ajustar con el brazo real)
// angulo_servo = OFFSET + DIR * (valor_modelo - REF)
// J1: servo 90 = brazo mirando al frente (yaw 0).
// J2: servo 0 = theta 5 (brazo casi horizontal hacia abajo), servo 160 = theta 85; relacion 2:1 => servo = 2*(theta-5).
// J3: servo 0 = psi -65, servo 115 = psi 50 (el codo va coaxial con el hombro; sentido espejo del J2 -> probar DIR).
// Pinza: servo 0 = cerrada.
const int   DIR_J1 = +1, DIR_J2 = +1, DIR_J3 = +1, DIR_GRIP = +1;       // cambiar a -1 si gira al reves
const float OFF_J1 = 90.0, OFF_J2 = 0.0, OFF_J3 = 0.0, OFF_GRIP = 0.0;  // ajuste fino del cero (grados de servo)
const float GEAR_J2 = 2.0;                                              // reduccion del hombro
const int   US_MIN = 500, US_MAX = 2400;                                // ancho de pulso para 0..180 (MG90S/SG90)

// ---------- limites de seguridad
const float SAFE = 2.0;                                  // margen sobre la tabla (grados)
const float THETA_MIN = 5, THETA_MAX = 85;
const float YAW_MIN = -90, YAW_MAX = 90;
const float GRIP_MIN = 0, GRIP_MAX = 40;
const float REL_MIN = -135, REL_MAX = -35;               // rel = psi - theta (paralelogramo)
const unsigned STEP_MS = 15;                             // 1 grado por paso => ~65 grados/s

Servo sJ1, sJ2, sJ3, sGrip;
float yaw = 0, theta = 45, psi = -30, grip = 20;         // posicion actual (modelo)
float tYaw = 0, tTheta = 45, tPsi = -30, tGrip = 20;     // destino

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

// Limites de psi para un theta dado: se toma el caso mas estrecho de las dos filas vecinas (conservador) y el margen SAFE.
void psiLimits(float th, float &lo, float &hi) {
  th = clampf(th, TH_LIM[0], TH_LIM[N_LIM - 1]);
  int i = 0;
  while (i < N_LIM - 2 && th > TH_LIM[i + 1]) i++;
  float l = max(PSI_LO[i], PSI_LO[i + 1]);
  float h = min(PSI_HI[i], PSI_HI[i + 1]);
  lo = l + SAFE;
  hi = h - SAFE;
  if (lo > hi) lo = hi = 0.5f * (l + h);                  // zona muy estrecha (theta ~ 5): un solo valor
  lo = max(lo, th + REL_MIN);
  hi = min(hi, th + REL_MAX);
  if (lo > hi) lo = hi = 0.5f * (lo + hi);
}

// Aplica los limites al conjunto (theta, psi) y devuelve el psi permitido.
float safePsi(float th, float p) {
  float lo, hi;
  psiLimits(th, lo, hi);
  return clampf(p, lo, hi);
}

int usFor(float deg) {
  deg = clampf(deg, 0, 180);
  return US_MIN + (int)((US_MAX - US_MIN) * deg / 180.0f);
}

void writeServos() {
  sJ1.writeMicroseconds(usFor(OFF_J1 + DIR_J1 * yaw));
  sJ2.writeMicroseconds(usFor(OFF_J2 + DIR_J2 * GEAR_J2 * (theta - THETA_MIN)));
  sJ3.writeMicroseconds(usFor(OFF_J3 + DIR_J3 * (psi + 65.0f)));
  sGrip.writeMicroseconds(usFor(OFF_GRIP + DIR_GRIP * grip));
}

float stepToward(float cur, float tgt) {
  float d = tgt - cur;
  if (d > 1) return cur + 1;
  if (d < -1) return cur - 1;
  return tgt;
}

void setTarget(float ny, float nt, float np, float ng) {
  tYaw = clampf(ny, YAW_MIN, YAW_MAX);
  tTheta = clampf(nt, THETA_MIN, THETA_MAX);
  tPsi = safePsi(tTheta, np);
  tGrip = clampf(ng, GRIP_MIN, GRIP_MAX);
}

// Un paso: cada eje avanza <= 1 grado y psi se vuelve a limitar con el theta del momento (nunca fuera de la zona verificada).
void stepOnce() {
  yaw = stepToward(yaw, tYaw);
  theta = stepToward(theta, tTheta);
  psi = safePsi(theta, stepToward(psi, tPsi));
  grip = stepToward(grip, tGrip);
  writeServos();
}

bool atTarget() {
  return yaw == tYaw && theta == tTheta && psi == tPsi && grip == tGrip;
}

void moveTo(float ny, float nt, float np, float ng) {
  setTarget(ny, nt, np, ng);
  unsigned long guard = millis() + 20000UL;
  while (!atTarget() && millis() < guard) {
    stepOnce();
    delay(STEP_MS);
  }
}

void setup() {
  Serial.begin(115200);
  // posicion inicial: se escribe antes de adjuntar para que el servo no pegue un salto
  psi = safePsi(theta, psi);
  sJ1.attach(PIN_J1, US_MIN, US_MAX);
  sJ2.attach(PIN_J2, US_MIN, US_MAX);
  sJ3.attach(PIN_J3, US_MIN, US_MAX);
  sGrip.attach(PIN_GRIP, US_MIN, US_MAX);
  writeServos();
  tYaw = yaw; tTheta = theta; tPsi = psi; tGrip = grip;
  Serial.println(F("Brazo v2 listo. Comandos: M yaw theta psi grip | H | ?"));
}

void printState() {
  float lo, hi;
  psiLimits(theta, lo, hi);
  Serial.print(F("yaw=")); Serial.print(yaw);
  Serial.print(F(" theta=")); Serial.print(theta);
  Serial.print(F(" psi=")); Serial.print(psi);
  Serial.print(F(" (limites ")); Serial.print(lo); Serial.print(F("..")); Serial.print(hi);
  Serial.print(F(") grip=")); Serial.println(grip);
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'M' || c == 'm') {
      float a = Serial.parseFloat(), b = Serial.parseFloat(), p = Serial.parseFloat(), g = Serial.parseFloat();
      moveTo(a, b, p, g);
      printState();
    } else if (c == 'H' || c == 'h') {
      moveTo(0, 45, -30, 20);
      printState();
    } else if (c == '?') {
      printState();
    }
  }
}
