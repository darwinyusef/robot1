"""
Mapeo de coordenadas normalizadas (0-1) → zona A-F
y cálculo del dwell timer por zona.
"""
import time
from dataclasses import dataclass, field

# Layout: 2 filas × 3 columnas
ZONE_GRID: dict[str, tuple[float, float, float, float]] = {
    "A": (0.00, 0.33, 0.00, 0.50),
    "B": (0.33, 0.66, 0.00, 0.50),
    "C": (0.66, 1.00, 0.00, 0.50),
    "D": (0.00, 0.33, 0.50, 1.00),
    "E": (0.33, 0.66, 0.50, 1.00),
    "F": (0.66, 1.00, 0.50, 1.00),
}

# Colores BGR para OpenCV
ZONE_BGR: dict[str, tuple[int, int, int]] = {
    "A": (60,  60,  220),
    "B": (50,  180, 50),
    "C": (200, 80,  30),
    "D": (180, 60,  180),
    "E": (30,  180, 200),
    "F": (160, 140, 30),
}


@dataclass
class DwellState:
    zone:        str | None = None
    entry_time:  float      = 0.0
    progress:    float      = 0.0   # 0.0 → 1.0
    confirmed:   bool       = False


class ZoneMapper:
    def __init__(self, dwell_seconds: float = 4.0):
        self.dwell_seconds = dwell_seconds
        self._state        = DwellState()

    def update(self, x: float, y: float) -> DwellState:
        """
        Recibe coordenadas normalizadas del dedo (0.0-1.0).
        Retorna el estado actual del dwell.
        """
        zone = self._point_to_zone(x, y)
        now  = time.time()

        # Cambio de zona → resetear timer
        if zone != self._state.zone:
            self._state = DwellState(zone=zone, entry_time=now if zone else 0.0)
            return self._state

        if zone is None:
            return self._state

        elapsed              = now - self._state.entry_time
        self._state.progress = min(elapsed / self.dwell_seconds, 1.0)
        self._state.confirmed = elapsed >= self.dwell_seconds

        return self._state

    def reset(self):
        self._state = DwellState()

    def _point_to_zone(self, x: float, y: float) -> str | None:
        for name, (xmin, xmax, ymin, ymax) in ZONE_GRID.items():
            if xmin <= x < xmax and ymin <= y < ymax:
                return name
        return None
