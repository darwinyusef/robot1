"""
Wrapper de MediaPipe Hand Landmarker (Tasks API v0.10+).
Extrae el landmark #8 (punta del índice) y #4 (pulgar)
para posición del dedo y detección de pinch.
"""
import time
import pathlib
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision.hand_landmarker import HandLandmark, HandLandmarksConnections
from dataclasses import dataclass

_CONNECTIONS = HandLandmarksConnections.HAND_CONNECTIONS

# Modelo en la raíz del proyecto (dwellv1/hand_landmarker.task)
_MODEL_PATH = str(pathlib.Path(__file__).parent.parent / "hand_landmarker.task")

PINCH_THRESHOLD = 0.06


@dataclass
class HandResult:
    detected:    bool   = False
    index_x:     float  = -1.0
    index_y:     float  = -1.0
    thumb_x:     float  = -1.0
    thumb_y:     float  = -1.0
    pinching:    bool   = False
    confidence:  float  = 0.0
    landmarks:   object = None   # lista de NormalizedLandmark


class HandTracker:
    def __init__(
        self,
        max_hands:  int   = 1,
        det_conf:   float = 0.70,
        track_conf: float = 0.65,
    ):
        base = mp_tasks.BaseOptions(model_asset_path=_MODEL_PATH)
        opts = mp_vision.HandLandmarkerOptions(
            base_options                  = base,
            running_mode                  = mp_vision.RunningMode.VIDEO,
            num_hands                     = max_hands,
            min_hand_detection_confidence = det_conf,
            min_hand_presence_confidence  = track_conf,
            min_tracking_confidence       = track_conf,
        )
        self._detector = mp_vision.HandLandmarker.create_from_options(opts)
        self._t0 = time.time()

    def process(self, frame_bgr: np.ndarray) -> HandResult:
        rgb    = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms  = int((time.time() - self._t0) * 1000)
        result = self._detector.detect_for_video(image, ts_ms)

        if not result.hand_landmarks:
            return HandResult()

        lms       = result.hand_landmarks[0]
        index_tip = lms[HandLandmark.INDEX_FINGER_TIP]
        thumb_tip = lms[HandLandmark.THUMB_TIP]

        dx       = index_tip.x - thumb_tip.x
        dy       = index_tip.y - thumb_tip.y
        pinching = (dx**2 + dy**2) ** 0.5 < PINCH_THRESHOLD

        conf = 0.0
        if result.handedness:
            conf = result.handedness[0][0].score

        return HandResult(
            detected   = True,
            index_x    = index_tip.x,
            index_y    = index_tip.y,
            thumb_x    = thumb_tip.x,
            thumb_y    = thumb_tip.y,
            pinching   = pinching,
            confidence = conf,
            landmarks  = lms,
        )

    def draw_landmarks(self, frame: np.ndarray, hand_result: HandResult) -> np.ndarray:
        if not hand_result.landmarks:
            return frame
        h, w = frame.shape[:2]
        lms  = hand_result.landmarks

        for conn in _CONNECTIONS:
            a = lms[conn.start]
            b = lms[conn.end]
            cv2.line(frame,
                     (int(a.x * w), int(a.y * h)),
                     (int(b.x * w), int(b.y * h)),
                     (80, 80, 80), 1, cv2.LINE_AA)

        for lm in lms:
            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 3, (200, 200, 200), -1)

        return frame

    def close(self):
        self._detector.close()
