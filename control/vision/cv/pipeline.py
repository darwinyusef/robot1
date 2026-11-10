"""
Orquestador principal del pipeline de computer vision.
Conecta HandTracker + PresenceDetector + ZoneMapper + ScreenReader + Overlay
en un único loop de captura.
"""
import cv2
import time
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from .hand_tracker   import HandTracker, HandResult
from .presence       import PresenceDetector
from .zone_mapper    import ZoneMapper, DwellState
from .screen_reader  import ScreenReader
from .overlay        import draw_zone_grid, draw_finger, draw_status_panel


@dataclass
class FrameResult:
    hand:       HandResult  = field(default_factory=HandResult)
    dwell:      DwellState  = field(default_factory=DwellState)
    present:    bool        = False
    fps:        float       = 0.0


# Tipo para el callback de eventos (zone_change, dwell_progress, zone_selected)
EventCallback = Callable[[dict], Awaitable[None]]


class CVPipeline:
    """
    Pipeline completo de visión para el kiosco gestual dwell.

    Uso típico:
        async def on_event(evt): await ws.send_json(evt)
        pipe = CVPipeline(camera_index=0, on_event=on_event)
        await pipe.run()
    """

    def __init__(
        self,
        camera_index:   int   = 0,
        dwell_seconds:  float = 4.0,
        monitor_index:  int   = 1,
        debug_window:   bool  = True,
        mirror:         bool  = True,
        on_event:       EventCallback | None = None,
    ):
        self._cam_idx      = camera_index
        self._debug        = debug_window
        self._mirror       = mirror
        self._on_event     = on_event

        self._tracker      = HandTracker()
        self._presence     = PresenceDetector()
        self._zone_mapper  = ZoneMapper(dwell_seconds=dwell_seconds)
        self._screen       = ScreenReader(monitor_index=monitor_index)

        self._cap          = None
        self._running      = False
        self._fps_t        = time.time()
        self._fps          = 0.0
        self._frame_count  = 0

    # ── Ciclo principal ───────────────────────────────────────────

    async def run(self):
        """Abre la cámara y corre el pipeline hasta que se llame stop()."""
        self._cap = cv2.VideoCapture(self._cam_idx)
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara {self._cam_idx}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self._running = True

        prev_zone     = None
        prev_selected = False

        try:
            while self._running:
                ok, frame = self._cap.read()
                if not ok:
                    await asyncio.sleep(0.01)
                    continue

                if self._mirror:
                    frame = cv2.flip(frame, 1)

                result = await self._process_frame(frame)

                # ── Emitir eventos ──────────────────────────────
                if self._on_event:
                    dwell = result.dwell

                    if dwell.zone != prev_zone:
                        prev_zone     = dwell.zone
                        prev_selected = False
                        await self._emit({
                            "type": "zone_change",
                            "zone": dwell.zone,
                        })

                    if dwell.zone and dwell.progress > 0:
                        await self._emit({
                            "type":     "dwell_progress",
                            "zone":     dwell.zone,
                            "progress": round(dwell.progress, 3),
                        })

                    if dwell.confirmed and not prev_selected:
                        prev_selected = True
                        self._zone_mapper.reset()
                        await self._emit({
                            "type": "zone_selected",
                            "zone": dwell.zone,
                        })

                # ── Ventana de debug ────────────────────────────
                if self._debug:
                    self._draw_debug(frame, result)
                    cv2.imshow("dwellv1 — debug", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                await asyncio.sleep(0)  # cede control al event loop

        finally:
            self.stop()

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None
        if self._debug:
            cv2.destroyAllWindows()
        self._tracker.close()

    # ── Procesamiento interno ─────────────────────────────────────

    async def _process_frame(self, frame) -> FrameResult:
        self._frame_count += 1
        now = time.time()
        dt  = now - self._fps_t
        if dt >= 0.5:
            self._fps   = self._frame_count / dt
            self._fps_t = now
            self._frame_count = 0

        present = self._presence.update(frame)

        hand  = HandResult()
        dwell = DwellState()

        hand  = self._tracker.process(frame)
        if hand.detected:
            dwell = self._zone_mapper.update(hand.index_x, hand.index_y)
        else:
            dwell = self._zone_mapper.update(-1, -1)

        return FrameResult(hand=hand, dwell=dwell, present=present, fps=self._fps)

    def _draw_debug(self, frame, result: FrameResult):
        thumbnails = self._screen.capture_all()

        draw_zone_grid(frame, result.dwell, thumbnails)

        if result.hand.detected:
            from .zone_mapper import ZONE_BGR
            color = ZONE_BGR.get(result.dwell.zone, (255, 255, 255)) if result.dwell.zone else (255, 255, 255)
            self._tracker.draw_landmarks(frame, result.hand)
            draw_finger(frame, result.hand.index_x, result.hand.index_y, color, result.hand.pinching)

        draw_status_panel(frame, result.dwell, result.present, result.fps, result.hand.confidence)

    async def _emit(self, event: dict):
        if self._on_event:
            try:
                await self._on_event(event)
            except Exception:
                pass
