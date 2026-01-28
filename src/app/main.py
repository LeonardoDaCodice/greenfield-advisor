# src/app/main.py

import time
import os
from dotenv import load_dotenv

load_dotenv()

from ..agents.sensor_manager import SensorManager
from ..agents.weather_agent import WeatherAgent
from ..agents.decision_agent import DecisionAgent
from ..agents.image_agent import ImageAgent  # supporto immagini


def main():
    print("[SYSTEM] Avvio GreenField Advisor...")

    # Modalità DEMO controllata dalla dashboard
    demo_mode = os.getenv("GF_DEMO_MODE", "false").lower() == "true"

    # Decision Agent sempre attivo
    decision = DecisionAgent()

    if demo_mode:
        print("[SYSTEM] Modalità DEMO attiva: avvio solo DecisionAgent.")
        decision.start()

    else:
        print("[SYSTEM] Modalità LIVE attiva: avvio tutti gli agenti.")

        sensor_manager = SensorManager()
        weather = WeatherAgent()
        image_agent = ImageAgent()

        sensor_manager.start()
        weather.start()
        image_agent.start()
        decision.start()

    print("[SYSTEM] Agents in esecuzione. Premi Ctrl+C per uscire.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SYSTEM] Arresto richiesto. Sto chiudendo gli agenti...")

        decision.stop()

        if not demo_mode:
            sensor_manager.stop()
            weather.stop()
            image_agent.stop()

        time.sleep(1.0)
        print("[SYSTEM] Shutdown completo.")


if __name__ == "__main__":
    main()
