"""
Lector de fragmentos de pantalla.
Captura la región de pantalla correspondiente a cada zona A-F
y la convierte en thumbnail para mostrarla en la ventana de debug.
Mapea zonas del ZONE_GRID a píxeles reales de la pantalla.
"""
import numpy as np
import cv2
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

from .zone_mapper import ZONE_GRID


class ScreenReader:
    """
    Lee fragmentos de la pantalla usando mss (multi-screen-shot).
    En modo fallback (sin mss) retorna thumbnails de color sólido.
    """

    def __init__(self, monitor_index: int = 1):
        """
        monitor_index: 1 = pantalla principal, 2 = segunda pantalla (la del kiosco).
        """
        self._mon_idx  = monitor_index
        self._sct      = mss.mss() if MSS_AVAILABLE else None
        self._monitor  = None
        self._cache:   dict[str, np.ndarray] = {}
        self._frame_n  = 0
        self._refresh  = 15   # capturar cada N frames (no cada frame — costoso)

        if self._sct:
            monitors = self._sct.monitors
            idx      = min(monitor_index, len(monitors) - 1)
            self._monitor = monitors[idx]

    def capture_zone(self, zone: str, thumb_size: tuple[int, int] = (120, 80)) -> np.ndarray:
        """
        Captura y retorna un thumbnail BGR del fragmento de pantalla
        correspondiente a la zona indicada.
        """
        if zone in self._cache and self._frame_n % self._refresh != 0:
            return self._cache[zone]

        img = self._capture_zone_raw(zone)
        if img is None:
            img = self._color_fallback(zone, thumb_size)
        else:
            img = cv2.resize(img, thumb_size)

        self._cache[zone] = img
        return img

    def tick(self):
        """Llamar una vez por frame para mantener el contador de refresco."""
        self._frame_n += 1

    def capture_all(self, thumb_size: tuple[int, int] = (120, 80)) -> dict[str, np.ndarray]:
        """Captura thumbnails de todas las zonas."""
        self.tick()
        return {z: self.capture_zone(z, thumb_size) for z in ZONE_GRID}

    # ── Internos ──────────────────────────────────────────────────

    def _capture_zone_raw(self, zone: str) -> np.ndarray | None:
        if not self._sct or not self._monitor:
            return None

        xmin_n, xmax_n, ymin_n, ymax_n = ZONE_GRID[zone]
        mon = self._monitor
        w, h = mon["width"], mon["height"]

        region = {
            "left":   mon["left"] + int(xmin_n * w),
            "top":    mon["top"]  + int(ymin_n * h),
            "width":  int((xmax_n - xmin_n) * w),
            "height": int((ymax_n - ymin_n) * h),
        }

        try:
            shot = self._sct.grab(region)
            img  = np.frombuffer(shot.bgra, dtype=np.uint8)
            img  = img.reshape((shot.height, shot.width, 4))
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    def _color_fallback(self, zone: str, size: tuple[int, int]) -> np.ndarray:
        """Thumbnail de color sólido cuando mss no está disponible."""
        from .zone_mapper import ZONE_BGR
        color = ZONE_BGR.get(zone, (80, 80, 80))
        img   = np.full((size[1], size[0], 3), color, dtype=np.uint8)
        cv2.putText(img, zone, (size[0]//2 - 10, size[1]//2 + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        return img
