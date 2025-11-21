# src/agents/sensor_manager.py

import threading
import json
import time
from typing import Dict

from paho.mqtt.client import Client as MqttClient

from ..common.mqtt_bus import make_client
from ..common.config import FIELD_ID
from .sensor_agent import SensorAgent


class SensorManager(threading.Thread):
    """
    Responsabile di:
    - creare / gestire i sensori dinamici (add/remove)
    - esporre via MQTT la lista dei sensori attivi
    Topic di controllo:
      - IN  : greenfield/{FIELD_ID}/control/sensors
      - OUT : greenfield/{FIELD_ID}/control/sensors/active
    """

    def __init__(self):
        super().__init__(daemon=True)
        self._running = True

        # Mappa: id_sensore -> SensorAgent
        self.sensors: Dict[str, SensorAgent] = {}

        # Client MQTT per ricevere comandi e pubblicare stato
        self.client: MqttClient = make_client("sensor-manager")
        self.client.on_message = self._on_message

        self.control_topic = f"greenfield/{FIELD_ID}/control/sensors"
        self.active_topic = f"greenfield/{FIELD_ID}/control/sensors/active"

    # ---------------------------------------------------------
    # Gestione MQTT
    # ---------------------------------------------------------
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            print("[SensorManager] Errore parsing comando:", e)
            return

        action = payload.get("action")
        sensor_id = payload.get("id")
        sensor_type = payload.get("type")

        if action == "add":
            self._add_sensor(sensor_id, sensor_type)
        elif action == "remove":
            self._remove_sensor(sensor_id)
        else:
            print(f"[SensorManager] Azione sconosciuta: {action}")

    def _publish_active_sensors(self):
        """
        Pubblica la lista dei sensori attivi sulla topic:
        greenfield/{FIELD_ID}/control/sensors/active
        """
        sensors_list = [
            {"id": sid, "type": s.kind}
            for sid, s in self.sensors.items()
        ]
        msg = {"sensors": sensors_list, "ts": time.time()}
        self.client.publish(self.active_topic, json.dumps(msg), qos=0, retain=False)

    # ---------------------------------------------------------
    # Operazioni sui sensori
    # ---------------------------------------------------------
    def _add_sensor(self, sensor_id: str, sensor_type: str):
        if not sensor_id or not sensor_type:
            print("[SensorManager] Comando add incompleto.")
            return

        if sensor_id in self.sensors:
            print(f"[SensorManager] Sensore {sensor_id} già esistente.")
            return

        sensor = SensorAgent(sensor_id, sensor_type)
        sensor.start()
        self.sensors[sensor_id] = sensor

        print(f"[SensorManager] Aggiunto sensore: {sensor_id} ({sensor_type})")
        self._publish_active_sensors()

    def _remove_sensor(self, sensor_id: str):
        if not sensor_id:
            return

        if sensor_id not in self.sensors:
            print(f"[SensorManager] Sensore {sensor_id} non trovato.")
            return

        sensor = self.sensors.pop(sensor_id)
        sensor.stop()
        print(f"[SensorManager] Rimosso sensore: {sensor_id}")

        self._publish_active_sensors()

    # ---------------------------------------------------------
    # Thread lifecycle
    # ---------------------------------------------------------
    def run(self):
        # Sottoscrivo ai comandi
        self.client.subscribe(self.control_topic, qos=0)

        # Creo i sensori iniziali
        initial_sensors = [
            ("temp-1", "temperature"),
            ("hum-1", "humidity"),
            ("light-1", "light"),
        ]
        for sid, stype in initial_sensors:
            self._add_sensor(sid, stype)

        # Pubblico subito lo stato iniziale
        self._publish_active_sensors()

        self.client.loop_start()
        print("[SensorManager] Avviato. In ascolto dei comandi sensori...")

        try:
            while self._running:
                time.sleep(1.0)
        finally:
            self.client.loop_stop()
            # Stoppa tutti i sensori attivi
            for s in self.sensors.values():
                s.stop()
            print("[SensorManager] Arrestato.")

    def stop(self):
        self._running = False
