"""ESP32 simulado: habla con el hub igual que el firmware (sin servos). Sirve para probar el visor y la vision sin hardware.

  pip install websockets
  HUB_TOKEN=... python sim_esp32.py [ws://localhost:8080]
"""
import asyncio
import os
import sys

import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8080"
URL = "%s/ws/esp32?token=%s" % (BASE, os.environ.get("HUB_TOKEN", ""))
ANIMS = "joints,pick,wave,circles,scan,mech"
HOME = (0.0, 45.0, -20.0, 20.0)
LIM = ((-90, 90), (5, 85), (-65, 50), (0, 40))


async def main():
    pose, mode = list(HOME), "idle"
    async with websockets.connect(URL) as ws:
        print("simulador conectado al hub")
        await ws.send("HELLO brazo_v2_esp32 (simulado)")
        await ws.send("ANIMS " + ANIMS)

        async def state():
            while True:
                await ws.send("STATE yaw=%.1f th=%.1f psi=%.1f phi=%.1f mode=%s" % (*pose, mode))
                await asyncio.sleep(1)

        async def done(i):
            await asyncio.sleep(3)
            await ws.send("DONE " + i)

        t = asyncio.create_task(state())
        async for line in ws:
            c = line.strip()
            if c.startswith("P "):
                pose = [max(lo, min(hi, float(v))) for v, (lo, hi) in zip(c.split()[1:], LIM)]
                mode = "live"
                print("pose", pose)
            elif c.startswith("PLAY "):
                mode = "anim"; print(c)
                await ws.send(c)
                asyncio.create_task(done(c.split()[1]))
            elif c in ("HOME", "STOP"):
                pose, mode = (list(HOME), "live") if c == "HOME" else (pose, "idle")
                print(c); await ws.send(c)
            elif c == "LIST":
                await ws.send("ANIMS " + ANIMS)
            elif c == "?":
                await ws.send("STATE yaw=%.1f th=%.1f psi=%.1f phi=%.1f mode=%s" % (*pose, mode))
        t.cancel()


asyncio.run(main())
