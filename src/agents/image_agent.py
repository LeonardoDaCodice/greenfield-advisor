# src/agents/image_agent.py

import time
import json
import random
import threading
from typing import Dict, Any

from ..common.mqtt_bus import make_client
from ..common.config import FIELD_ID, SENSOR_PUBLISH_INTERVAL_SECS


class ImageAgent(threading.Thread):
    """
    Simula un analizzatore di immagini del campo.
    In un sistema reale, questo agente riceverebbe immagini (es. da drone o camera fissa),
    le processerebbe con un modello di Computer Vision e pubblicherebbe feature aggregate
    come un indice di salute della vegetazione.

    Qui simuliamo un valore vegetation_health ∈ [0, 1].
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.client = make_client("image")
        # Topic dedicato alle feature estratte dalle immagini
        self.topic = f"greenfield/{FIELD_ID}/images/health"
        self._running = True

    def generate_features(self) -> Dict[str, Any]:
        """
        Genera un valore fittizio di salute vegetazione.
        Possiamo simulare una leggera variabilità nel tempo.
        """
        vegetation_health = random.uniform(0.4, 0.95)  # 0 = pessima, 1 = ottima salute
        return {
            "image_id": f"img-{int(time.time())}",
            "vegetation_health": round(vegetation_health, 3),
            "ts": time.time(),
        }

    def run(self):
        print("[ImageAgent] Avviato. Pubblico feature immagini simulate...")
        while self._running:
            data = self.generate_features()
            self.client.publish(self.topic, json.dumps(data), qos=0, retain=False)
            # Frequenza più lenta rispetto ai sensori classici
            time.sleep(SENSOR_PUBLISH_INTERVAL_SECS * 3)

    def stop(self):
        self._running = False
        print("[ImageAgent] Arresto richiesto.")
