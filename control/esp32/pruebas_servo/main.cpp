#include <Arduino.h>
#include <ESP32Servo.h>

Servo base;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);
  base.attach(18);
  base.write(90);
}

void loop() {
  if (Serial.available() > 0) {
    String texto = Serial.readStringUntil('\n');
    texto.trim();

    int angulo = texto.toInt();
    if (angulo >= 20 && angulo <= 180) {
      base.write(angulo);
    }
  }
}