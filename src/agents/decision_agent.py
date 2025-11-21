import json
import threading
import time
import queue
import requests
from typing import Dict, Any
from paho.mqtt.client import Client as MqttClient

from ..common.mqtt_bus import make_client
from ..common.config import FIELD_ID, AI_STRATEGY, N8N_WEBHOOK_URL
from ..pipeline.handlers import CleaningHandler, FeatureEngineeringHandler, EstimationHandler
from ..ai.strategies import make_strategy



# ============================================================
# DECISION AGENT
# Coordina sensori → pipeline → decisioni AI/regole → MQTT
# ============================================================
class DecisionAgent(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

        # Client MQTT principale
        self.client: MqttClient = make_client("decision")

        # Cache dati sensori/meteo
        self.cache = {
            "temperature": None,
            "humidity": None,
            "light": None,
            "wind_kmh": None,
            "radiation": None,
        }

        # Timestamp ultimo aggiornamento sensori
        self.last_update = {k: 0 for k in self.cache}

        self._running = True

        # Topic MQTT
        sensors_topic = f"greenfield/{FIELD_ID}/sensors/+/+"
        weather_topic = f"greenfield/{FIELD_ID}/weather/current"
        control_strategy_topic = f"greenfield/{FIELD_ID}/control/strategy"

        self.client.on_message = self._on_message

        # Sottoscrizioni
        self.client.subscribe(sensors_topic, qos=0)
        self.client.subscribe(weather_topic, qos=0)
        self.client.subscribe(control_strategy_topic, qos=0)

        # Strategia iniziale
        self.current_strategy_name = (AI_STRATEGY or "simple_rules").lower().strip()
        self.strategy = make_strategy(self.current_strategy_name)

        # Pipeline AI (Cleaning → Features → Estimation)
        self.cleaning = CleaningHandler()
        self.feature_engineering = FeatureEngineeringHandler()
        self.estimation = EstimationHandler(self.strategy)

        self.cleaning.set_next(self.feature_engineering).set_next(self.estimation)
        self.pipeline = self.cleaning

        print(f"[DecisionAgent] Strategia iniziale: {self.current_strategy_name}")



    # ============================================================
    # MQTT Callback — sensori, meteo, comandi
    # ============================================================
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            now = time.time()
            topic = msg.topic

            # -------------------------------
            # Cambio strategia da Streamlit
            # -------------------------------
            if topic.endswith("/control/strategy"):
                new_name = payload.get("strategy", "").lower().strip()
                if new_name:
                    print(f"[DecisionAgent] Cambio strategia → {new_name}")
                    self.current_strategy_name = new_name
                    self.strategy = make_strategy(new_name)
                    self.estimation.estimator = self.strategy
                return

            # -------------------------------
            # Sensori fisici
            # -------------------------------
            if "type" in payload and "value" in payload:
                kind = payload["type"]
                if kind in self.cache:
                    self.cache[kind] = payload["value"]
                    self.last_update[kind] = now
                return

            # -------------------------------
            # Meteo (API esterna)
            # -------------------------------
            if "temperature" in payload and "humidity" in payload:
                for k in self.cache:
                    if k in payload:
                        self.cache[k] = payload[k]
                        self.last_update[k] = now

        except Exception as e:
            print("DecisionAgent parse error:", e)



    # ============================================================
    # LOOP PRINCIPALE — genera decisioni periodiche
    # ============================================================
    def run(self):
        self.client.loop_start()
        print("[DecisionAgent] Avviato. In attesa di dati...")

        while self._running:
            try:
                time.sleep(1.0)

                # Richiediamo almeno temperatura & umidità
                if not all(self.cache[k] is not None for k in ["temperature", "humidity"]):
                    continue

                now = time.time()

                # Invalida dati troppo vecchi (> 15s)
                for k in ["temperature", "humidity"]:
                    if self.last_update[k] and now - self.last_update[k] > 15:
                        self.cache[k] = None

                # Se invalidato, aspettiamo nuovi dati
                if not all(self.cache[k] is not None for k in ["temperature", "humidity"]):
                    continue

                # Record completo da passare alla pipeline
                record = {
                    "temperature": self.cache["temperature"],
                    "humidity": self.cache["humidity"],
                    "light": self.cache["light"],
                    "wind_kmh": self.cache["wind_kmh"],
                    "radiation": self.cache["radiation"],
                    "ts": now
                }

                # AI / Regole → output
                processed = self.pipeline.handle(record)

                # Pubblica risultato
                out_topic = f"greenfield/{FIELD_ID}/decisions"
                self.client.publish(out_topic, json.dumps(processed), qos=0)

                # Eventuale integrazione con n8n
                if N8N_WEBHOOK_URL:
                    try:
                        requests.post(N8N_WEBHOOK_URL, json=processed, timeout=2)
                    except Exception as e:
                        print("n8n webhook error:", e)

            except Exception as e:
                print("DecisionAgent main loop error:", e)

        self.client.loop_stop()



    # ============================================================
    # Arresto sicuro
    # ============================================================
    def stop(self):
        self._running = False
