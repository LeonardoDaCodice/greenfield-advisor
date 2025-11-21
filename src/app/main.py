import time
from dotenv import load_dotenv
load_dotenv()

from ..agents.sensor_agent import SensorAgent
from ..agents.weather_agent import WeatherAgent
from ..agents.decision_agent import DecisionAgent

def main():
    sensors = [
        SensorAgent("temp-1", "temperature"),
        SensorAgent("hum-1", "humidity"),
        SensorAgent("light-1", "light"),
    ]
    weather = WeatherAgent()
    decision = DecisionAgent()

    for s in sensors: s.start()
    weather.start()
    decision.start()

    print("Agents running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping agents...")
        for s in sensors: s.stop()
        weather.stop()
        decision.stop()

if __name__ == "__main__":
    main()
