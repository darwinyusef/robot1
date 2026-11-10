"""
Detector de presencia por sustracción de fondo.
Activa el pipeline de manos solo cuando hay alguien frente al kiosco.
Ahorra CPU cuando el kiosco está en idle.
"""
import cv2
import numpy as np


class PresenceDetector:
    """
    Usa MOG2 (Mixture of Gaussians) para detectar movimiento/presencia.
    Si el área de movimiento supera el umbral → hay alguien presente.
    """

    def __init__(
        self,
        motion_threshold: float = 0.012,  # fracción del frame con movimiento
        warmup_frames:    int   = 30,      # frames para calibrar el fondo
    ):
        self._bg      = cv2.createBackgroundSubtractorMOG2(
                            history=120, varThreshold=40, detectShadows=False)
        self._thresh  = motion_threshold
        self._warmup  = warmup_frames
        self._counter = 0
        self._present = False
        self._mask    = None

    @property
    def ready(self) -> bool:
        """True cuando el fondo de referencia ya fue calibrado."""
        return self._counter >= self._warmup

    @property
    def present(self) -> bool:
        return self._present

    @property
    def mask(self) -> np.ndarray | None:
        """Máscara binaria del último frame procesado."""
        return self._mask

    def update(self, frame: np.ndarray) -> bool:
        """
        Procesa el frame y retorna True si hay presencia detectada.
        """
        small  = cv2.resize(frame, (160, 120))
        fg     = self._bg.apply(small)

        # Limpiar ruido
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg     = cv2.morphologyEx(fg, cv2.MORPH_OPEN,  kernel)
        fg     = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel)

        self._mask    = fg
        self._counter += 1

        if not self.ready:
            return False

        motion_ratio  = np.count_nonzero(fg) / fg.size
        self._present = motion_ratio > self._thresh
        return self._present
