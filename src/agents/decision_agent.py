import json
import threading
import time
import requests
from typing import Dict, Any
from paho.mqtt.client import Client as MqttClient
import os

from ..common.mqtt_bus import make_client
from ..common.config import FIELD_ID, AI_STRATEGY, N8N_WEBHOOK_URL
from ..pipeline.handlers import CleaningHandler, FeatureEngineeringHandler, EstimationHandler
from ..ai.strategies import make_strategy


# ============================================================
#  DecisionAgent – LIVE MODE + DEMO MODE con test cases
# ============================================================

class DecisionAgent(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

        # MQTT client
        self.client: MqttClient = make_client("decision")

        # Cache dei valori LIVE
        self.cache: Dict[str, Any] = {
            "temperature": None,
            "humidity": None,
            "light": None,
            "wind_kmh": None,
            "radiation": None,
            "vegetation_health": None,
        }

        # Timestamp ultimo update
        self.last_update: Dict[str, float] = {k: 0.0 for k in self.cache}

        # Demo mode
        self.demo_mode = False
        self.demo_case_data = None

        self._running = True

        # Topic di sottoscrizione
        sensors_topic = f"greenfield/{FIELD_ID}/sensors/+/+"
        weather_topic = f"greenfield/{FIELD_ID}/weather/current"
        image_topic = f"greenfield/{FIELD_ID}/images/health"
        control_strategy_topic = f"greenfield/{FIELD_ID}/control/strategy"
        control_test_case_topic = f"greenfield/{FIELD_ID}/control/test_case"

        self.client.on_message = self._on_message

        self.client.subscribe(sensors_topic, qos=0)
        self.client.subscribe(weather_topic, qos=0)
        self.client.subscribe(image_topic, qos=0)
        self.client.subscribe(control_strategy_topic, qos=0)
        self.client.subscribe(control_test_case_topic, qos=0)

        # Strategy iniziale
        self.current_strategy_name = (AI_STRATEGY or "simple_rules").lower().strip()
        self.strategy = make_strategy(self.current_strategy_name)

        # Pipeline AI (Cleaning → FeatureEngineering → Estimation)
        self.cleaning = CleaningHandler()
        self.feature_engineering = FeatureEngineeringHandler()
        self.estimation = EstimationHandler(self.strategy)
        self.cleaning.set_next(self.feature_engineering).set_next(self.estimation)
        self.pipeline = self.cleaning

        print(f"[DecisionAgent] Strategia iniziale: {self.current_strategy_name}")

    # ============================================================
    #  Carica test case JSON
    # ============================================================
    def load_test_case(self, case_name: str) -> Dict[str, Any]:
        try:
            path = os.path.join("test_cases", f"{case_name}.json")
            with open(path, "r") as f:
                data = json.load(f)
            print(f"[DecisionAgent] Test case caricato: {case_name}")
            return data
        except Exception as e:
            print(f"[DecisionAgent] Errore caricando test case '{case_name}': {e}")
            return None

    # ============================================================
    #  MESSAGE HANDLER
    # ============================================================
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            topic = msg.topic
            now = time.time()

            # ------------------------------------------------------
            # CAMBIO STRATEGIA
            # ------------------------------------------------------
            if topic.endswith("/control/strategy"):
                new_name = payload.get("strategy", "").lower().strip()
                if new_name:
                    print(f"[DecisionAgent] Cambio strategia → {new_name}")
                    self.current_strategy_name = new_name
                    self.strategy = make_strategy(new_name)
                    self.estimation.estimator = self.strategy
                return

            # ------------------------------------------------------
            # DEMO MODE: attiva/disattiva
            # ------------------------------------------------------
            if topic.endswith("/control/test_case"):
                mode = payload.get("mode", "live")

                if mode == "live":
                    self.demo_mode = False
                    self.demo_case_data = None
                    print("[DecisionAgent] DEMO disattivata → modalità LIVE")
                    return

                if mode == "demo":
                    case_name = payload.get("case")
                    case_data = self.load_test_case(case_name)
                    if case_data:
                        self.demo_mode = True
                        self.demo_case_data = case_data
                        print(f"[DecisionAgent] DEMO ATTIVA → caso '{case_name}'")
                    return

            # Se siamo in DEMO: ignora TUTTI i sensori reali
            if self.demo_mode:
                return

            # ------------------------------------------------------
            # FEATURE DA IMMAGINI
            # ------------------------------------------------------
            if topic.endswith("/images/health"):
                vh = payload.get("vegetation_health")
                if vh is not None:
                    self.cache["vegetation_health"] = float(vh)
                    self.last_update["vegetation_health"] = now
                return

            # ------------------------------------------------------
            # SENSORI (temperature / humidity / light)
            # ------------------------------------------------------
            if "type" in payload and "value" in payload:
                kind = payload["type"]
                if kind in self.cache:
                    self.cache[kind] = float(payload["value"])
                    self.last_update[kind] = now
                return

            # ------------------------------------------------------
            # METEO
            # ------------------------------------------------------
            if "temperature" in payload and "humidity" in payload:
                for k in self.cache:
                    if k in payload:
                        self.cache[k] = payload[k]
                        self.last_update[k] = now
                return

        except Exception as e:
            print("[DecisionAgent] Errore parsing MQTT:", e)

    # ============================================================
    #  MAIN LOOP
    # ============================================================
    def run(self):
        self.client.loop_start()
        print("[DecisionAgent] Agente decisionale avviato...")

        while self._running:
            try:
                time.sleep(1.0)
                now = time.time()

                # ====================================================
                # DEMO MODE
                # ====================================================
                if self.demo_mode and self.demo_case_data:
                    record = self.demo_case_data.copy()
                    record["ts"] = now

                else:
                    # ====================================================
                    # LIVE MODE
                    # ====================================================
                    if not all(self.cache[k] is not None for k in ["temperature", "humidity"]):
                        continue

                    # Invalida dati vecchi (>15 sec)
                    for k in ["temperature", "humidity"]:
                        if self.last_update[k] and (now - self.last_update[k] > 15):
                            self.cache[k] = None

                    if not all(self.cache[k] is not None for k in ["temperature", "humidity"]):
                        continue

                    record = {
                        "temperature": self.cache["temperature"],
                        "humidity": self.cache["humidity"],
                        "light": self.cache["light"],
                        "wind_kmh": self.cache["wind_kmh"],
                        "radiation": self.cache["radiation"],
                        "vegetation_health": self.cache["vegetation_health"],
                        "ts": now,
                    }

                # ====================================================
                # Pipeline AI
                # ====================================================
                processed = self.pipeline.handle(record)

                # ====================================================
                # Pubblica decisione
                # ====================================================
                out_topic = f"greenfield/{FIELD_ID}/decisions"
                self.client.publish(out_topic, json.dumps(processed), qos=0)

                # Webhook n8n
                if N8N_WEBHOOK_URL:
                    try:
                        requests.post(N8N_WEBHOOK_URL, json=processed, timeout=2)
                    except Exception:
                        pass

            except Exception as e:
                print("[DecisionAgent] Errore loop:", e)

        self.client.loop_stop()

    # ============================================================
    #  Arresto sicuro
    # ============================================================
    def stop(self):
        self._running = False
