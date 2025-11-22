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
#  DecisionAgent – usa cache per TIPO di sensore (temp/hum/light)
#  Compatibile con sensori dinamici: prende sempre l'ultima lettura
#  per ogni tipo, indipendentemente dall'ID del sensore.
# ============================================================

class DecisionAgent(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

        # MQTT client
        self.client: MqttClient = make_client("decision")

        # Cache per tipo di grandezza (non per ID sensore)
        self.cache: Dict[str, Any] = {
            "temperature": None,
            "humidity": None,
            "light": None,
            "wind_kmh": None,
            "radiation": None,
        }

        # Timestamp ultimo aggiornamento per tipo
        self.last_update: Dict[str, float] = {k: 0.0 for k in self.cache}

        # Stato di funzionamento
        self._running = True

        # Topic
        sensors_topic = f"greenfield/{FIELD_ID}/sensors/+/+"
        weather_topic = f"greenfield/{FIELD_ID}/weather/current"
        control_strategy_topic = f"greenfield/{FIELD_ID}/control/strategy"

        # Callback MQTT
        self.client.on_message = self._on_message

        # Sottoscrizioni
        self.client.subscribe(sensors_topic, qos=0)
        self.client.subscribe(weather_topic, qos=0)
        self.client.subscribe(control_strategy_topic, qos=0)

        # Strategia iniziale (AI opzionale)
        self.current_strategy_name = (AI_STRATEGY or "simple_rules").lower().strip()
        self.strategy = make_strategy(self.current_strategy_name)

        # Pipeline AI (Chain of Responsibility)
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
            # LETTURE SENSORI (temperature / humidity / light)
            # ----------------------------------
            # Esempio payload sensore:
            # { "sensor": "temp-1", "type": "temperature", "value": 23.5, "ts": ... }
            if "type" in payload and "value" in payload:
                kind = payload["type"]
                if kind in self.cache:
                    self.cache[kind] = payload["value"]
                    self.last_update[kind] = now
                return

            # ----------------------------------
            # METEO – dati aggiuntivi (vento, radiazione, ecc.)
            # ----------------------------------
            # Esempio payload meteo:
            # { "temperature": 22.1, "humidity": 55.0, "wind_kmh": 5.2, "radiation": 300.0, ... }
            if "temperature" in payload and "humidity" in payload:
                for k in self.cache:
                    if k in payload:
                        self.cache[k] = payload[k]
                        self.last_update[k] = now
                return

        except Exception as e:
            print("[DecisionAgent] Errore parsing MQTT:", e)

    # ============================================================
    #  MAIN LOOP – genera decisioni periodiche
    # ============================================================
    def run(self):
        self.client.loop_start()
        print("[DecisionAgent] Avviato. In ascolto...")

        while self._running:
            try:
                time.sleep(1.0)

                now = time.time()

                # Richiediamo almeno temperatura & umidità per decidere qualcosa
                if not all(self.cache[k] is not None for k in ["temperature", "humidity"]):
                    continue

                # Invalida dati troppo vecchi (> 15s) per temp e umidità
                for k in ["temperature", "humidity"]:
                    if self.last_update[k] and now - self.last_update[k] > 15:
                        self.cache[k] = None

                # Se dopo l'invalidazione mancano ancora dati → aspettiamo
                if not all(self.cache[k] is not None for k in ["temperature", "humidity"]):
                    continue

                # Costruisce il record completo per la pipeline
                record = {
                    "temperature": self.cache["temperature"],
                    "humidity": self.cache["humidity"],
                    "light": self.cache["light"],
                    "wind_kmh": self.cache["wind_kmh"],
                    "radiation": self.cache["radiation"],
                    "ts": now,
                }

                # Passaggio attraverso la pipeline AI / regole
                processed = self.pipeline.handle(record)

                # Pubblica decisione
                out_topic = f"greenfield/{FIELD_ID}/decisions"
                self.client.publish(out_topic, json.dumps(processed), qos=0)
                # DEBUG opzionale:
                # print("[DecisionAgent] Decisione pubblicata:", processed)

                # Webhook n8n (se configurato)
                if N8N_WEBHOOK_URL:
                    try:
                        requests.post(N8N_WEBHOOK_URL, json=processed, timeout=2)
                    except Exception as e:
                        print("[DecisionAgent] n8n webhook error:", e)

            except Exception as e:
                print("[DecisionAgent] Errore loop:", e)

        self.client.loop_stop()

    # ============================================================
    #  Arresto sicuro
    # ============================================================
    def stop(self):
        self._running = False
