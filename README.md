# Brazo robotico v2 (4 servos, MDF 3 mm)

    diseno/    SOLO el diseno: geometria (*_geom.py), verificacion (*_check.py), cortes SVG, planos DXF/PDF,
               modelos .sc, renders, reportes, BOM.md y PLAN.md
    control/   Lo que mueve el brazo
      esp32/     firmware ESP32 (WiFi directo + MQTT + Serial) y sus animaciones
      mqtt/      contrato de topics (entrada brazo_v2/cmd, salida brazo_v2/evt|state|status)
      viewer3d/  visor 3D, espejo en vivo y botones de animacion
      brazo_v2/  sketch Arduino UNO/Nano (solo servos) y limites.h
      WIRING.md  cableado y calibracion

Dependencias entre carpetas (una sola direccion: diseno -> control):
- `diseno/output_build.py` escribe `control/brazo_v2/limites.h`.
- `control/viewer3d/export_robot.py` lee `diseno/*.py` y genera `robot_data.js` (necesita solidcraft-cli).
- `cd control/viewer3d && node tools/export_esp32.js` genera `control/esp32/brazo_v2_esp32/{anims.h,limites.h}`.

Primeros pasos con MQTT: ver `control/mqtt/README.md` y `control/esp32/README.md`.
