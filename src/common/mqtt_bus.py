from paho.mqtt import client as mqtt
import uuid
from .config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_CLIENT_PREFIX

def make_client(name: str) -> mqtt.Client:
    client_id = f"{MQTT_CLIENT_PREFIX}-{name}-{uuid.uuid4().hex[:6]}"
    c = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt.MQTTv311)
    c.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    return c
