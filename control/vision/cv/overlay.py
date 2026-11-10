"""
Dibuja el overlay de debug sobre el frame de la cámara:
  - Cuadrícula de zonas A-F con colores
  - Barra de progreso de dwell
  - Fragmento de pantalla en miniatura dentro de cada zona
  - Indicador del dedo (círculo + crosshair)
  - Panel de estado en esquina superior izquierda
"""
import math
import cv2
import numpy as np
from .zone_mapper import ZONE_GRID, ZONE_BGR, DwellState


CIRCUMFERENCE = 2 * math.pi * 22   # radio=22px para el arco de progreso


def draw_zone_grid(
    frame:       np.ndarray,
    dwell:       DwellState,
    thumbnails:  dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    h, w = frame.shape[:2]

    for zone, (xmin, xmax, ymin, ymax) in ZONE_GRID.items():
        x1, y1 = int(xmin * w), int(ymin * h)
        x2, y2 = int(xmax * w), int(ymax * h)
        color   = ZONE_BGR[zone]
        active  = zone == dwell.zone

        # Fondo semitransparente en zona activa
        if active:
            overlay      = frame.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

        # Miniatura del fragmento de pantalla
        if thumbnails and zone in thumbnails:
            thumb  = thumbnails[zone]
            tw, th = thumb.shape[1], thumb.shape[0]
            tx     = x1 + (x2 - x1 - tw) // 2
            ty     = y1 + (y2 - y1 - th) // 2
            if tx >= 0 and ty >= 0 and tx + tw <= w and ty + th <= h:
                roi = frame[ty:ty+th, tx:tx+tw]
                alpha_frame = 0.35 if not active else 0.50
                cv2.addWeighted(thumb, alpha_frame, roi, 1 - alpha_frame, 0, roi)
                frame[ty:ty+th, tx:tx+tw] = roi

        # Borde de zona
        thick = 3 if active else 1
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thick)

        # Etiqueta de zona
        cv2.putText(frame, zone,
                    (x1 + 10, y1 + 34),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, color, 2, cv2.LINE_AA)

        # Barra de progreso horizontal en la parte inferior de la zona
        if active and dwell.progress > 0:
            bar_w = int((x2 - x1) * dwell.progress)
            cv2.rectangle(frame, (x1, y2 - 6), (x1 + bar_w, y2), color, -1)

        # Arco de progreso (esquina superior derecha de la zona)
        if active and dwell.progress > 0:
            _draw_arc_progress(frame, x2 - 30, y1 + 30, 22, dwell.progress, color)

    return frame


def draw_finger(
    frame:  np.ndarray,
    x_norm: float,
    y_norm: float,
    color:  tuple[int, int, int] = (255, 255, 255),
    pinching: bool = False,
) -> np.ndarray:
    if x_norm < 0:
        return frame
    h, w  = frame.shape[:2]
    px    = int(x_norm * w)
    py    = int(y_norm * h)
    r     = 10 if not pinching else 6

    # Círculo exterior
    cv2.circle(frame, (px, py), r + 5, (0, 0, 0), 2)
    cv2.circle(frame, (px, py), r + 5, color, 1)
    # Relleno
    cv2.circle(frame, (px, py), r, color, -1)
    # Crosshair
    cv2.line(frame, (px - 18, py), (px - r - 2, py), color, 1)
    cv2.line(frame, (px + r + 2, py), (px + 18, py), color, 1)
    cv2.line(frame, (px, py - 18), (px, py - r - 2), color, 1)
    cv2.line(frame, (px, py + r + 2), (px, py + 18), color, 1)

    if pinching:
        cv2.putText(frame, "PINCH", (px + 14, py - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    return frame


def draw_status_panel(
    frame:       np.ndarray,
    dwell:       DwellState,
    present:     bool,
    fps:         float,
    confidence:  float,
) -> np.ndarray:
    lines = [
        f"FPS:        {fps:.0f}",
        f"Presencia:  {'SI' if present else 'NO'}",
        f"Confianza:  {confidence:.0%}",
        f"Zona:       {dwell.zone or '-'}",
        f"Progreso:   {dwell.progress:.0%}",
    ]
    bg_h = len(lines) * 20 + 16
    cv2.rectangle(frame, (8, 8), (185, 8 + bg_h), (0, 0, 0), -1)
    cv2.rectangle(frame, (8, 8), (185, 8 + bg_h), (60, 60, 60), 1)

    for i, line in enumerate(lines):
        color = (200, 200, 200)
        if 'Zona' in line and dwell.zone:
            color = ZONE_BGR.get(dwell.zone, color)
        if 'Presencia' in line:
            color = (80, 220, 80) if present else (80, 80, 220)
        cv2.putText(frame, line, (14, 26 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
    return frame


# ── Helpers internos ──────────────────────────────────────────────

def _draw_arc_progress(
    frame: np.ndarray,
    cx: int, cy: int,
    radius: int,
    progress: float,
    color: tuple[int, int, int],
):
    """Dibuja un arco de progreso (círculo parcial) con polylines."""
    angle_start = -90                       # empieza arriba
    angle_end   = angle_start + int(360 * progress)
    pts = []
    for deg in range(angle_start, angle_end + 1, 3):
        rad = math.radians(deg)
        pts.append((
            int(cx + radius * math.cos(rad)),
            int(cy + radius * math.sin(rad)),
        ))
    if len(pts) > 1:
        cv2.polylines(frame, [np.array(pts)], False, color, 3, cv2.LINE_AA)
    # Círculo de fondo
    cv2.circle(frame, (cx, cy), radius, (50, 50, 50), 2)
