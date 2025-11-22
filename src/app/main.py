# src/app/main.py

import time
from dotenv import load_dotenv

load_dotenv()

from ..agents.sensor_manager import SensorManager
from ..agents.weather_agent import WeatherAgent
from ..agents.decision_agent import DecisionAgent
from ..agents.image_agent import ImageAgent  # <--- nuovo import


def main():
    print("[SYSTEM] Avvio GreenField Advisor...")

    sensor_manager = SensorManager()
    weather = WeatherAgent()
    decision = DecisionAgent()
    image_agent = ImageAgent()  # <--- nuovo agente

    sensor_manager.start()
    weather.start()
    decision.start()
    image_agent.start()

    print("[SYSTEM] Agents in esecuzione. Premi Ctrl+C per uscire.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SYSTEM] Arresto richiesto. Sto chiudendo gli agenti...")
        sensor_manager.stop()
        weather.stop()
        decision.stop()
        image_agent.stop()
        time.sleep(1.0)
        print("[SYSTEM] Shutdown completo.")


if __name__ == "__main__":
    main()
