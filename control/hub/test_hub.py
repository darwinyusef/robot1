"""Pruebas del hub (sin red ni hardware):  python -m pytest -q test_hub.py"""
import os
import time

os.environ["HUB_TOKEN"] = "tok"
os.environ["VIEWER_DIR"] = "/nonexistent"
os.environ.pop("MQTT_HOST", None)

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import server

ESP, CLI = "/ws/esp32?token=tok", "/ws/client?token=tok"


@pytest.fixture
def client():
    server.hub.__init__()
    with TestClient(server.app) as c:
        yield c


def test_token_requerido(client):
    for path in ("/ws/esp32", "/ws/client?token=mal"):
        with pytest.raises(WebSocketDisconnect) as e:
            with client.websocket_connect(path):
                pass
        assert e.value.code == 4401


def test_comando_llega_al_esp32_y_respuesta_al_cliente(client):
    with client.websocket_connect(ESP) as esp, client.websocket_connect(CLI) as cli:
        assert cli.receive_text().startswith("HUB esp32=online")
        cli.send_text("HOME")
        assert esp.receive_text() == "HOME"
        esp.send_text("HOME")
        while True:
            m = cli.receive_text()
            if m == "HOME":
                break
        cli.send_text("PLAY wave loop")
        assert esp.receive_text() == "PLAY wave loop"


def test_comandos_invalidos_no_llegan(client):
    with client.websocket_connect(ESP) as esp, client.websocket_connect(CLI) as cli:
        cli.receive_text()
        for bad in ("rm -rf", "P 1 2 3", "P a b c d", "PLAY ../x", "play wave", "P 1 2 3 4 5", "x" * 300, "TEST 5", "TEST 0", "TEST x"):
            cli.send_text(bad)
            while True:
                m = cli.receive_text()
                if m.startswith("ERR hub"):
                    break
        cli.send_text("STOP")
        assert esp.receive_text() == "STOP"          # lo primero que llego al ESP32 es el STOP: nada invalido paso


def test_pose_se_recorta_y_limita_a_25hz(client):
    with client.websocket_connect(ESP) as esp, client.websocket_connect(CLI) as cli:
        cli.receive_text()
        cli.send_text("P 200 0 100 99")
        assert esp.receive_text() == "P 90.0 5.0 50.0 40.0"
        for i in range(20):
            cli.send_text("P %d 45 -20 20" % i)
        t0 = time.monotonic()
        got = []
        while not got or got[-1] != "P 19.0 45.0 -20.0 20.0":
            got.append(esp.receive_text())
        assert len(got) < 20                            # se agruparon
        assert time.monotonic() - t0 < 1.0


def test_stop_cancela_pose_pendiente(client):
    with client.websocket_connect(ESP) as esp, client.websocket_connect(CLI) as cli:
        cli.receive_text()
        cli.send_text("P 10 45 -20 20")
        assert esp.receive_text().startswith("P ")
        cli.send_text("P 20 45 -20 20")
        cli.send_text("STOP")
        seen = [esp.receive_text() for _ in range(1)]
        assert seen[0] in ("STOP", "P 20.0 45.0 -20.0 20.0")
        if seen[0] != "STOP":
            assert esp.receive_text() == "STOP"


def test_json_de_la_vision(client):
    with client.websocket_connect(ESP) as esp, client.websocket_connect(CLI) as cli:
        cli.receive_text()
        cli.send_text('{"type":"zone_selected","zone":"B"}')
        assert esp.receive_text() == "PLAY pick"
        cli.send_text('{"type":"zone_change","zone":"B"}')          # se ignora
        cli.send_text('{"type":"pose","yaw":10,"th":50,"psi":-30,"phi":5}')
        assert esp.receive_text() == "P 10.0 50.0 -30.0 5.0"
        cli.send_text('{"type":"zone_selected","zone":"Z"}')         # zona desconocida: nada
        cli.send_text("HOME")
        assert esp.receive_text() == "HOME"


def test_sin_brazo_avisa(client):
    with client.websocket_connect(CLI) as cli:
        assert cli.receive_text() == "HUB esp32=offline clients=1"
        cli.send_text("HOME")
        assert cli.receive_text() == "ERR hub: brazo desconectado"
        cli.send_text("PING")
        assert cli.receive_text() == "PONG"


def test_cliente_nuevo_recibe_cache(client):
    with client.websocket_connect(ESP) as esp:
        esp.send_text("HELLO brazo_v2_esp32")
        esp.send_text("ANIMS joints,pick")
        esp.send_text("STATE yaw=0.0 th=45.0")
        time.sleep(0.2)
        with client.websocket_connect(CLI) as cli:
            got = [cli.receive_text() for _ in range(4)]
            assert got[0].startswith("HUB esp32=online")
            assert got[1:4] == ["HELLO brazo_v2_esp32", "ANIMS joints,pick", "STATE yaw=0.0 th=45.0"]


def test_segundo_esp32_reemplaza_al_primero(client):
    with client.websocket_connect(ESP) as a:
        with client.websocket_connect(ESP) as b:
            with pytest.raises(WebSocketDisconnect):
                a.receive_text()
            assert client.get("/health").json()["esp32"] is True


def test_comando_test_pasa(client):
    with client.websocket_connect(ESP) as esp, client.websocket_connect(CLI) as cli:
        cli.receive_text()
        for ok in ("TEST", "TEST 3", "OFF"):
            cli.send_text(ok)
            assert esp.receive_text() == ok
