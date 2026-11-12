"""
Entry point del detector gestual.
Delega toda la lógica de CV al módulo cv.pipeline (CVPipeline).
Conecta el pipeline al hub del brazo (control/hub) por WebSocket.

  python detector.py                 modo zonas: 6 zonas A-F, 4 s de permanencia -> el hub reproduce la animacion de la zona
  python detector.py --modo pose     la mano mueve el brazo en vivo (palma = guinada/hombro, tamano = codo, pellizco = pinza)
Variables: HUB_URL (por defecto ws://localhost:8080/ws/client), HUB_TOKEN, CAM_INDEX.
"""
import argparse
import asyncio
import json
import os
import websockets
from cv.pipeline import CVPipeline

HUB_URL     = os.environ.get("HUB_URL", "ws://localhost:8080/ws/client")
HUB_TOKEN   = os.environ.get("HUB_TOKEN", "")
WS_SERVER   = f"{HUB_URL}?role=vision&token={HUB_TOKEN}"
CAM_INDEX   = int(os.environ.get("CAM_INDEX", "0"))
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
            self._keep = asyncio.create_task(self._keepalive(self._ws))
            print(f"[detector] Conectado a {self._url.split('token=')[0]}")
        except Exception as e:
            print(f"[detector] Sin conexión WS: {e}")
            self._ws = None

    async def _keepalive(self, ws):
        """lee (y descarta) lo que manda el hub para que su cola no se llene, y manda PING cada 20 s para que no nos corte por inactividad."""
        async def pinger():
            while True:
                await asyncio.sleep(20)
                await ws.send("PING")
        task = asyncio.create_task(pinger())
        try:
            async for _ in ws:
                pass
        except Exception:
            pass
        finally:
            task.cancel()
            if self._ws is ws:
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


async def main(pose_mode: bool = False):
    bridge = _WSBridge(WS_SERVER)
    await bridge.connect()

    pipeline = CVPipeline(
        camera_index  = CAM_INDEX,
        dwell_seconds = DWELL_SECS,
        monitor_index = MONITOR_IDX,
        debug_window  = True,
        mirror        = True,
        on_event      = bridge.send,
        pose_mode     = pose_mode,
    )

    print("[detector] Iniciando pipeline. Presiona 'q' en la ventana para salir.")
    try:
        await pipeline.run()
    finally:
        await bridge.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=("zonas", "pose"), default="zonas")
    asyncio.run(main(ap.parse_args().modo == "pose"))
