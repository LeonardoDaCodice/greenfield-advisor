import time, json, random, threading
from typing import Dict
from ..common.mqtt_bus import make_client
from ..common.config import SENSOR_PUBLISH_INTERVAL_SECS, FIELD_ID

class SensorAgent(threading.Thread):
    def __init__(self, name: str, kind: str):
        super().__init__(daemon=True)
        self.name = name
        self.kind = kind  # temperature | humidity | light
        self.client = make_client(f"sensor-{name}")
        self.topic = f"greenfield/{FIELD_ID}/sensors/{self.kind}/{self.name}"
        self._running = True

    def generate_reading(self) -> Dict:
        if self.kind == "temperature":
            value = random.uniform(12.0, 35.0)
        elif self.kind == "humidity":
            value = random.uniform(30.0, 90.0)
        elif self.kind == "light":
            value = random.uniform(100.0, 1800.0)
        else:
            value = random.uniform(0.0, 1.0)
        return {"sensor": self.name, "type": self.kind, "value": round(value, 2), "ts": time.time()}

    def run(self):
        while self._running:
            reading = self.generate_reading()
            self.client.publish(self.topic, json.dumps(reading), qos=0, retain=False)
            time.sleep(SENSOR_PUBLISH_INTERVAL_SECS)

    def stop(self):
        self._running = False
