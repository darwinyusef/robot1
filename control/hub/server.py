"""Hub WebSocket del brazo v2: une el ESP32 (cliente) con el visor 3D, la vision artificial y, opcional, MQTT.

  ws://HOST:8080/ws/esp32?token=T     el ESP32 (uno solo; si entra otro, reemplaza al anterior)
  ws://HOST:8080/ws/client?token=T    visor 3D / vision (JS o Python): mandan comandos, reciben lo que diga el brazo
  GET /health                         estado (sin token)
  GET /                               visor 3D (si existe VIEWER_DIR)

Los clientes pueden mandar PING (el hub responde PONG, no llega al brazo).
Protocolo = el del firmware (una linea de texto por mensaje): P yaw th psi phi | PLAY id [loop] | TOUR | STOP | HOME | OFF | TEST [1-4] | LIST | ?
El hub valida cada linea antes de pasarla al brazo y limita P a ~25 Hz (gana la ultima). Ademas acepta JSON de la vision en Python:
  {"type":"zone_selected","zone":"B"}                  -> PLAY de la animacion de esa zona (ZONE_ANIMS)
  {"type":"pose","yaw":..,"th":..,"psi":..,"phi":..}   -> P (recortado a los limites del brazo)
Mensajes propios del hub hacia los clientes: "HUB esp32=online|offline clients=N".
"""
import asyncio
import hmac
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("hub")
TOKEN = os.environ.get("HUB_TOKEN", "")
MAX_LEN = 256
P_PERIOD = 1.0 / float(os.environ.get("HUB_P_HZ", "25"))
IDLE_TIMEOUT = float(os.environ.get("HUB_IDLE_TIMEOUT", "300"))      # un cliente sin mandar nada en ese tiempo se desconecta (el visor manda PING cada 20 s)
ZONE_ANIMS = dict(kv.split("=") for kv in os.environ.get(
    "ZONE_ANIMS", "A=joints,B=pick,C=wave,D=circles,E=scan,F=mech").split(","))
LIMITS = {"yaw": (-90.0, 90.0), "th": (5.0, 85.0), "psi": (-65.0, 50.0), "phi": (0.0, 40.0)}   # el firmware vuelve a limitar psi segun theta

NUM = r"-?\d{1,4}(?:\.\d{1,3})?"
RE_P = re.compile(r"^P (%s) (%s) (%s) (%s)$" % (NUM, NUM, NUM, NUM))
RE_TEST = re.compile(r"^TEST(?: [1-4])?$")
RE_PLAY = re.compile(r"^PLAY ([a-z0-9_]{1,23})(?: (loop))?$")
SIMPLE = {"TOUR", "STOP", "HOME", "OFF", "LIST", "?"}


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def normalize(line):
    """linea de comando valida -> linea limpia, o None."""
    line = line.strip()
    if line in SIMPLE or RE_PLAY.match(line) or RE_TEST.match(line):
        return line
    m = RE_P.match(line)
    if m:
        y, t, p, g = (float(x) for x in m.groups())
        return "P %.1f %.1f %.1f %.1f" % (clamp(y, *LIMITS["yaw"]), clamp(t, *LIMITS["th"]), clamp(p, *LIMITS["psi"]), clamp(g, *LIMITS["phi"]))
    return None


def from_json(obj):
    """evento JSON de la vision en Python -> linea de comando, o None."""
    if not isinstance(obj, dict):
        return None
    kind = obj.get("type")
    if kind == "zone_selected":
        anim = ZONE_ANIMS.get(str(obj.get("zone", "")))
        return "PLAY " + anim if anim else None
    if kind == "pose":
        try:
            v = [float(obj[k]) for k in ("yaw", "th", "psi", "phi")]
        except (KeyError, TypeError, ValueError):
            return None
        if not all(abs(x) < 1e4 for x in v):
            return None
        return "P %.1f %.1f %.1f %.1f" % tuple(v)
    return None


class Hub:
    def __init__(self):
        self.esp = None                 # WebSocket del ESP32
        self.clients = set()
        self.cache = {}                 # HELLO / ANIMS / STATE: se reenvian a los clientes que entran
        self.pending_p = None           # ultima pose en vivo por enviar
        self.last_p = 0.0
        self.p_task = None
        self.taps = []                  # funciones (linea_evt) -> None: p. ej. el puente MQTT

    def status(self):
        return "HUB esp32=%s clients=%d" % ("online" if self.esp else "offline", len(self.clients))

    async def _send(self, c, text):
        try:
            await asyncio.wait_for(c.send_text(text), 2.0)      # un cliente atascado no debe frenar a los demas
        except Exception:
            self.clients.discard(c)
            asyncio.create_task(c.close())

    async def broadcast(self, text):
        await asyncio.gather(*(self._send(c, text) for c in list(self.clients)))

    async def announce(self):
        await self.broadcast(self.status())
        for t in self.taps:
            t("status", self.status())

    async def to_esp(self, line, origin=None):
        """manda una linea validada al ESP32; devuelve False si no hay brazo conectado."""
        if self.esp is None:
            return False
        if line.startswith("P "):                       # poses en vivo: como mucho P_PERIOD, la ultima gana
            self.pending_p = line
            if self.p_task is None or self.p_task.done():
                self.p_task = asyncio.create_task(self._flush_p())
            return True
        self.pending_p = None                           # un comando discreto cancela la pose pendiente (STOP no debe quedar tapado por un P)
        try:
            await self.esp.send_text(line)
        except Exception:
            return False
        return True

    async def _flush_p(self):
        while self.pending_p is not None and self.esp is not None:
            wait = self.last_p + P_PERIOD - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            line, self.pending_p = self.pending_p, None
            if line is None or self.esp is None:
                break
            self.last_p = time.monotonic()
            try:
                await self.esp.send_text(line)
            except Exception:
                break

    def from_esp(self, text):
        key = text.split(" ", 1)[0]
        if key in ("HELLO", "ANIMS", "STATE"):
            self.cache[key] = text
        for t in self.taps:
            t("state" if key == "STATE" else "evt", text)


hub = Hub()


def authorized(token):
    return not TOKEN or hmac.compare_digest(token.encode(), TOKEN.encode())


@asynccontextmanager
async def lifespan(app):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if not TOKEN:
        log.warning("HUB_TOKEN vacio: cualquiera que llegue al puerto puede mover el brazo")
    from mqtt_bridge import start_bridge
    stop = start_bridge(hub, asyncio.get_running_loop())
    yield
    stop()


app = FastAPI(title="Brazo v2 hub", lifespan=lifespan)


@app.get("/health")
async def health():
    return JSONResponse({"esp32": hub.esp is not None, "clients": len(hub.clients), "state": hub.cache.get("STATE")})


@app.websocket("/ws/esp32")
async def ws_esp32(ws: WebSocket, token: str = Query("")):
    if not authorized(token):
        await ws.close(code=4401)
        return
    await ws.accept()
    old, hub.esp = hub.esp, ws
    if old is not None:
        try:
            await old.close(code=4000)
        except Exception:
            pass
    log.info("ESP32 conectado desde %s", ws.client)
    await hub.announce()
    try:
        while True:
            text = await ws.receive_text()
            if len(text) > MAX_LEN * 4:
                continue
            text = text.strip()
            if not text:
                continue
            hub.from_esp(text)
            await hub.broadcast(text)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.info("ESP32: %s", e)
    finally:
        if hub.esp is ws:
            hub.esp = None
            hub.pending_p = None
            hub.cache.pop("STATE", None)
            log.info("ESP32 desconectado")
            await hub.announce()


@app.websocket("/ws/client")
async def ws_client(ws: WebSocket, token: str = Query(""), role: str = Query("viewer")):
    if not authorized(token):
        await ws.close(code=4401)
        return
    await ws.accept()
    hub.clients.add(ws)
    log.info("cliente %s (%s) conectado, total %d", role, ws.client, len(hub.clients))
    await hub.announce()
    for k in ("HELLO", "ANIMS", "STATE"):
        if k in hub.cache:
            await ws.send_text(hub.cache[k])
    try:
        while True:
            try:
                text = await asyncio.wait_for(ws.receive_text(), IDLE_TIMEOUT)
            except asyncio.TimeoutError:
                await ws.close(code=4408)
                break
            if len(text) > MAX_LEN:
                await ws.send_text("ERR hub: mensaje demasiado largo")
                continue
            if text == "PING":
                await ws.send_text("PONG")
                continue
            if text.startswith("{"):
                try:
                    line = from_json(json.loads(text))
                except ValueError:
                    line = None
                if line is None:
                    continue                            # eventos de la vision que no mueven el brazo (zone_change, dwell_progress)
            else:
                line = text
            cmd = normalize(line)
            if cmd is None:
                await ws.send_text("ERR hub: comando no permitido")
            elif not await hub.to_esp(cmd):
                await ws.send_text("ERR hub: brazo desconectado")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.info("cliente: %s", e)
    finally:
        hub.clients.discard(ws)
        await hub.announce()


VIEWER = Path(os.environ.get("VIEWER_DIR", Path(__file__).resolve().parent.parent / "viewer3d"))
if VIEWER.is_dir():
    app.mount("/", StaticFiles(directory=VIEWER, html=True), name="viewer")
