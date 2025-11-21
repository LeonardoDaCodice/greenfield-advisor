import os

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_CLIENT_PREFIX = os.getenv("MQTT_CLIENT_PREFIX", "greenfield")

SENSOR_PUBLISH_INTERVAL_SECS = int(os.getenv("SENSOR_PUBLISH_INTERVAL_SECS", "5"))
FIELD_ID = os.getenv("FIELD_ID", "field-01")

AI_STRATEGY = os.getenv("AI_STRATEGY", "simple_rules")  # simple_rules | ml_placeholder

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
