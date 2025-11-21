import time, json, random, threading
from ..common.mqtt_bus import make_client
from ..common.config import FIELD_ID, SENSOR_PUBLISH_INTERVAL_SECS

class WeatherAgent(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.client = make_client("weather")
        self.topic = f"greenfield/{FIELD_ID}/weather/current"
        self._running = True

    def run(self):
        while self._running:
            data = {
                "temperature": round(random.uniform(10.0, 35.0), 2),
                "humidity": round(random.uniform(30.0, 80.0), 2),
                "wind_kmh": round(random.uniform(0.0, 25.0), 1),
                "radiation": round(random.uniform(100.0, 900.0), 1),
                "ts": time.time()
            }
            self.client.publish(self.topic, json.dumps(data), qos=0, retain=False)
            time.sleep(SENSOR_PUBLISH_INTERVAL_SECS * 2)

    def stop(self):
        self._running = False
