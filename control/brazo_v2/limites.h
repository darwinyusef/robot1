// Generado por output_build.py (fase 6). Limites de psi (angulo absoluto del antebrazo) segun theta (angulo del brazo), en grados.
// Zona libre verificada para cualquier guinada (barrido de la fase 5); el programa agrega SAFE grados de margen.
const int N_LIM = 17;
const int TH_LIM[N_LIM]  = {5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85};
const int PSI_LO[N_LIM]  = {-30, -35, -35, -40, -40, -45, -50, -50, -55, -60, -65, -65, -65, -60, -60, -55, -50};
const int PSI_HI[N_LIM]  = {-30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50};
