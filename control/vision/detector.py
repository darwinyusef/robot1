"""
Entry point del detector gestual.
Delega toda la lógica de CV al módulo cv.pipeline (CVPipeline).
Conecta el pipeline al servidor FastAPI via WebSocket.
"""
import asyncio
import json
import websockets
from cv.pipeline import CVPipeline

WS_SERVER   = "ws://localhost:8000/ws/detector"
CAM_INDEX   = 0
DWELL_SECS  = 4.0
MONITOR_IDX = 1   # 1 = pantalla principal, 2 = segunda pantalla


class _WSBridge:
    """Mantiene la conexión WebSocket y reintenta si cae."""

    def __init__(self, url: str):
        self._url = url
        self._ws  = None

    async def connect(self):
        try:
            self._ws = await websockets.connect(self._url)
            print(f"[detector] Conectado a {self._url}")
        except Exception as e:
            print(f"[detector] Sin conexión WS: {e}")
            self._ws = None

    async def send(self, event: dict):
        if self._ws is None:
            await self.connect()
        if self._ws:
            try:
                await self._ws.send(json.dumps(event))
            except Exception:
                self._ws = None

    async def close(self):
        if self._ws:
            await self._ws.close()


async def main():
    bridge = _WSBridge(WS_SERVER)
    await bridge.connect()

    pipeline = CVPipeline(
        camera_index  = CAM_INDEX,
        dwell_seconds = DWELL_SECS,
        monitor_index = MONITOR_IDX,
        debug_window  = True,
        mirror        = True,
        on_event      = bridge.send,
    )

    print("[detector] Iniciando pipeline. Presiona 'q' en la ventana para salir.")
    try:
        await pipeline.run()
    finally:
        await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
