# Visor 3D del brazo robotico v2 (4 servos)

Carpeta **nueva**; no modifica ningun archivo original del proyecto (solo los lee).

## Ver
Doble clic en `index.html` (funciona desde `file://`, sin servidor ni internet).
- Animaciones: recorrido completo, articulaciones, recoger y colocar, saludo, circulos, barrido, mecanismos (MDF translucido), despiece.
- Control manual de J1..J3 y pinza, con los limites de `limites.h` (J3 depende de J2).
- Vista frontal / lateral / planta / 3/4, MDF translucido, despiece.

## Video
`brazo_v2_tour.mp4` (recorrido completo, 1280x720, 30 fps). Regenerar:

    cd tools
    npm install            # puppeteer-core (usa Microsoft Edge instalado) ; ffmpeg en el PATH
    node render_video.js ../brazo_v2_tour.mp4 tour 30 1280 720

Otra animacion: cambiar `tour` por `joints|pick|wave|circles|scan|mech|explode`.

## Regenerar la geometria
    python -I export_robot.py     # importa los modulos del padre (solo lectura), exporta con solidcraft-cli y escribe robot_data.js

## Notas
- La malla se exporta una vez en la pose de referencia (th=45, psi=-30, phi=20) y se articula en JS (`kin.js`, `app.js`).
- Con la geometria real de las mordazas, las almohadillas solo llegan a z ~ 0..5 mm; la mesa esta en z = -33. Por eso "recoger y colocar" usa pedestales (cara superior z = 0). El `global_check.py` original asumia una punta nominal a 182 mm que si alcanzaria la mesa.
- Todas las animaciones se verifican contra los limites con `node tools/test_anims.js`.
- `node tools/shot.js out.png "{anim:'pick',t:10}"` hace capturas de prueba.
