"""Puente MQTT opcional del hub (activo si MQTT_HOST esta definido).

Usa topics propios <MQTT_BASE>/hub/{cmd,evt,state,status} para no duplicar los del firmware (que tambien habla MQTT directo en <MQTT_BASE>/...).
MQTT_TRANSPORT=websockets (+ MQTT_PORT 443/9001, MQTT_TLS=1, MQTT_WS_PATH=/) para brokers detras de wss://, como mqtt.aquicreamos.com.
"""
import asyncio
import logging
import os

log = logging.getLogger("hub.mqtt")


def start_bridge(hub, loop):
    host = os.environ.get("MQTT_HOST", "")
    if not host:
        return lambda: None
    import paho.mqtt.client as mqtt
    from server import normalize

    base = os.environ.get("MQTT_BASE", "brazo_v2") + "/hub"
    ws = os.environ.get("MQTT_TRANSPORT", "tcp") == "websockets"
    tls = os.environ.get("MQTT_TLS", "1" if ws else "0") == "1"
    port = int(os.environ.get("MQTT_PORT", "443" if ws and tls else "9001" if ws else "8883" if tls else "1883"))
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="brazo_v2_hub", transport="websockets" if ws else "tcp")
    if os.environ.get("MQTT_USER"):
        c.username_pw_set(os.environ["MQTT_USER"], os.environ.get("MQTT_PASS", ""))
    if tls:
        c.tls_set()
    if ws:
        c.ws_set_options(path=os.environ.get("MQTT_WS_PATH", "/"))
    c.will_set(base + "/status", "offline", qos=1, retain=True)

    def on_connect(cl, ud, flags, rc, props=None):
        log.info("MQTT conectado a %s:%d (%s) rc=%s", host, port, "websockets" if ws else "tcp", rc)
        cl.subscribe(base + "/cmd")
        cl.publish(base + "/status", "online", retain=True)

    def on_message(cl, ud, msg):
        cmd = normalize(msg.payload.decode("utf-8", "ignore"))
        if cmd is None:
            return
        asyncio.run_coroutine_threadsafe(hub.to_esp(cmd), loop)

    def tap(kind, text):
        if c.is_connected():
            c.publish(base + "/" + kind, text, retain=(kind in ("state", "status")))

    c.on_connect, c.on_message = on_connect, on_message
    hub.taps.append(tap)
    c.reconnect_delay_set(2, 30)
    c.connect_async(host, port, keepalive=30)
    c.loop_start()

    def stop():
        c.publish(base + "/status", "offline", retain=True)
        c.loop_stop()
        c.disconnect()
    return stop
