import json
import threading
import time
import requests
from typing import Dict, Any
from paho.mqtt.client import Client as MqttClient

from ..common.mqtt_bus import make_client
from ..common.config import FIELD_ID, AI_STRATEGY, N8N_WEBHOOK_URL
from ..pipeline.handlers import CleaningHandler, FeatureEngineeringHandler, EstimationHandler
from ..ai.strategies import make_strategy


# ============================================================
#  DecisionAgent – ora compatibile con sensori dinamici
# ============================================================

class DecisionAgent(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

        # MQTT client
        self.client: MqttClient = make_client("decision")

        # Cache dinamica: contiene solo i sensori attivi
        self.sensor_cache: Dict[str, Dict[str, Any]] = {}

        # Cache meteo
        self.weather_cache = {
            "temperature": None,
            "humidity": None,
            "wind_kmh": None,
            "radiation": None,
        }
        self.weather_last_update = 0

        # Stato di funzionamento
        self._running = True

        # Topic
        sensors_topic = f"greenfield/{FIELD_ID}/sensors/+/+"
        weather_topic = f"greenfield/{FIELD_ID}/weather/current"
        control_strategy_topic = f"greenfield/{FIELD_ID}/control/strategy"
        control_sensor_topic = "greenfield/control/sensors"  # add/remove

        # MQTT callbacks
        self.client.on_message = self._on_message

        # Sottoscrizioni
        self.client.subscribe(sensors_topic, qos=0)
        self.client.subscribe(weather_topic, qos=0)
        self.client.subscribe(control_strategy_topic, qos=0)
        self.client.subscribe(control_sensor_topic, qos=0)

        # Strategia iniziale
        self.current_strategy_name = (AI_STRATEGY or "simple_rules").lower().strip()
        self.strategy = make_strategy(self.current_strategy_name)

        # Pipeline AI (CoR)
        self.cleaning = CleaningHandler()
        self.feature_engineering = FeatureEngineeringHandler()
        self.estimation = EstimationHandler(self.strategy)
        self.cleaning.set_next(self.feature_engineering).set_next(self.estimation)
        self.pipeline = self.cleaning

        print(f"[DecisionAgent] Strategia iniziale: {self.current_strategy_name}")

    # ============================================================
    #  MQTT MESSAGE HANDLER
    # ============================================================
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            topic = msg.topic
            now = time.time()

            # ----------------------------------
            # COMANDO: Cambio Strategia
            # ----------------------------------
            if topic.endswith("/control/strategy"):
                new_name = payload.get("strategy", "").lower().strip()
                if new_name:
                    print(f"[DecisionAgent] Cambio strategia → {new_name}")
                    self.current_strategy_name = new_name
                    self.strategy = make_strategy(new_name)
                    self.estimation.estimator = self.strategy
                return

            # ----------------------------------
            # COMANDO: Aggiunta / Rimozione sensori
            # ----------------------------------
            if topic == "greenfield/control/sensors":
                action = payload.get("action")
                sensor_id = payload.get("id")

                if action == "add":
                    print(f"[DecisionAgent] Registrato sensore: {sensor_id}")
                    self.sensor_cache[sensor_id] = {"last_update": 0}

                elif action == "remove":
                    print(f"[DecisionAgent] Rimosso sensore: {sensor_id}")
                    if sensor_id in self.sensor_cache:
                        del self.sensor_cache[sensor_id]

                return

            # ----------------------------------
            # SENSORE – Inserito solo se attivo
            # ----------------------------------
            if "sensor" in payload and "value" in payload:

                sensor_id = payload.get("sensor")

                # Ignora sensori rimossi
                if sensor_id not in self.sensor_cache:
                    return

                self.sensor_cache[sensor_id]["data"] = payload
                self.sensor_cache[sensor_id]["last_update"] = now
                return

            # ----------------------------------
            # METEO – sempre utile
            # ----------------------------------
            if "temperature" in payload and "humidity" in payload:
                for k in self.weather_cache:
                    if k in payload:
                        self.weather_cache[k] = payload[k]

                self.weather_last_update = now

        except Exception as e:
            print("[DecisionAgent] Errore parsing MQTT:", e)

    # ============================================================
    #  MAIN LOOP – genera decisioni
    # ============================================================
    def run(self):
        self.client.loop_start()
        print("[DecisionAgent] Avviato. In ascolto...")

        while self._running:

            try:
                time.sleep(1)

                now = time.time()

                # Se non ci sono sensori attivi → nessuna decisione
                if len(self.sensor_cache) == 0:
                    continue

                # Tenta di trovare almeno temperatura e umidità
                temperature = None
                humidity = None
                light = None

                for s in self.sensor_cache.values():
                    if "data" not in s:
                        continue
                    d = s["data"]
                    if d["type"] == "temperature": temperature = d["value"]
                    if d["type"] == "humidity": humidity = d["value"]
                    if d["type"] == "light": light = d["value"]

                # Se mancano temp/umidità → skip
                if temperature is None or humidity is None:
                    continue

                record = {
                    "temperature": temperature,
                    "humidity": humidity,
                    "light": light,
                    "wind_kmh": self.weather_cache["wind_kmh"],
                    "radiation": self.weather_cache["radiation"],
                    "ts": now
                }

                # Pipeline AI
                processed = self.pipeline.handle(record)

                # Pubblica decisione
                out_topic = f"greenfield/{FIELD_ID}/decisions"
                self.client.publish(out_topic, json.dumps(processed), qos=0)

                # Webhook n8n (opzionale)
                if N8N_WEBHOOK_URL:
                    try:
                        requests.post(N8N_WEBHOOK_URL, json=processed, timeout=2)
                    except:
                        pass

            except Exception as e:
                print("[DecisionAgent] Errore loop:", e)

        self.client.loop_stop()

    # ============================================================
    #  Arresto sicuro
    # ============================================================
    def stop(self):
        self._running = False
