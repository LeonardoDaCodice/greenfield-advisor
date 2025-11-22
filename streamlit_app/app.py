import streamlit as st
import time, threading, json, queue, os
from paho.mqtt import client as mqtt
import pandas as pd

# ---------------------------------------------------------
# Config da variabili d'ambiente
# ---------------------------------------------------------
MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
FIELD_ID = os.getenv("FIELD_ID", "field-01")

# ---------------------------------------------------------
# Configurazione pagina + CSS
# ---------------------------------------------------------
st.set_page_config(page_title="GreenField Advisor — Dashboard", layout="wide")

st.markdown("""
<style>
.metric-card {
    padding: 20px;
    border-radius: 15px;
    color: white;
    text-align: center;
    font-size: 24px;
    font-weight: bold;
}
.ok   { background: linear-gradient(135deg, #2ecc71, #27ae60); }
.warn { background: linear-gradient(135deg, #f1c40f, #f39c12); }
.bad  { background: linear-gradient(135deg, #e74c3c, #c0392b); }

.status-banner {
    padding: 18px;
    border-radius: 12px;
    color: white;
    font-size: 20px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 20px;
}
.status-ok   { background: linear-gradient(135deg, #2ecc71, #27ae60); }
.status-warn { background: linear-gradient(135deg, #2980b9, #3498db); }
.status-bad  { background: linear-gradient(135deg, #e74c3c, #c0392b); }

.section-title {
    margin-top: 20px;
    font-size: 22px;
    font-weight: bold;
}

/* Nasconde eventuali colonne indice auto-generate */
tbody th {
    display: none !important;
}
thead th:first-child {
    display: none !important;
}
table {
    border-collapse: collapse;
}
</style>
""", unsafe_allow_html=True)

st.title("GreenField Advisor — Dashboard in Tempo Reale")

# ---------------------------------------------------------
# Code dati
# ---------------------------------------------------------
readings_q = queue.Queue()
decisions_q = queue.Queue()

df = pd.DataFrame(columns=[
    "temperatura", "umidità", "luce", "vento_kmh",
    "radiazione", "stress_idrico", "salute_vegetazione",
    "decisione", "timestamp"
])


# ---------------------------------------------------------
# Stato Streamlit (strategia, sensori, tipi)
# ---------------------------------------------------------
if "current_strategy" not in st.session_state:
    st.session_state["current_strategy"] = None

if "known_sensors" not in st.session_state:
    st.session_state["known_sensors"] = ["temp-1", "hum-1", "light-1"]

if "sensor_types" not in st.session_state:
    st.session_state["sensor_types"] = {
        "temp-1": "temperature",
        "hum-1": "humidity",
        "light-1": "light",
    }

if "active_sensor_types" not in st.session_state:
    st.session_state["active_sensor_types"] = set(st.session_state["sensor_types"].values())

# ---------------------------------------------------------
# Modalità AI / Non-AI
# ---------------------------------------------------------
STRATEGY_LABELS = {
    "senza AI": "simple_rules",
    "AI (ML placeholder)": "ml_placeholder",
}

modalita_label = st.sidebar.radio("Modalità di decisione", list(STRATEGY_LABELS.keys()), index=0)
selected_strategy = STRATEGY_LABELS[modalita_label]

# ---------------------------------------------------------
# MQTT
# ---------------------------------------------------------
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except:
        return

    topic = msg.topic

    if topic.endswith("/decisions"):
        decisions_q.put(data)
        return

    if topic.endswith("/control/sensors/active"):
        sensors = data.get("sensors", [])
        st.session_state["known_sensors"] = [s["id"] for s in sensors]
        st.session_state["sensor_types"] = {s["id"]: s["type"] for s in sensors}
        st.session_state["active_sensor_types"] = set(st.session_state["sensor_types"].values())
        return

    if "/sensors/" in topic:
        readings_q.put(data)
        return


def mqtt_loop_sub():
    c = mqtt.Client()
    c.on_message = on_message
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    c.subscribe(f"greenfield/{FIELD_ID}/sensors/+/+", qos=0)
    c.subscribe(f"greenfield/{FIELD_ID}/decisions", qos=0)
    c.subscribe(f"greenfield/{FIELD_ID}/control/sensors/active", qos=0)

    c.loop_forever()


threading.Thread(target=mqtt_loop_sub, daemon=True).start()

mqtt_pub = mqtt.Client()
mqtt_pub.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
mqtt_pub.loop_start()

# cambio strategia runtime
if st.session_state["current_strategy"] != selected_strategy:
    payload = {"strategy": selected_strategy}
    mqtt_pub.publish(f"greenfield/{FIELD_ID}/control/strategy", json.dumps(payload))
    st.session_state["current_strategy"] = selected_strategy

# ---------------------------------------------------------
# Gestione sensori
# ---------------------------------------------------------
st.sidebar.subheader("Gestione Sensori")
st.sidebar.write(st.session_state["known_sensors"])

with st.sidebar.expander("Aggiungi sensore"):
    nuovo_tipo = st.selectbox("Tipo sensore", ["temperature", "humidity", "light"])
    if st.button("Crea nuovo sensore"):
        new_id = f"{nuovo_tipo[:4]}-{len(st.session_state['known_sensors']) + 1}"

        mqtt_pub.publish(f"greenfield/{FIELD_ID}/control/sensors",
                         json.dumps({"action": "add", "id": new_id, "type": nuovo_tipo}))

        st.session_state["known_sensors"].append(new_id)
        st.session_state["sensor_types"][new_id] = nuovo_tipo
        st.session_state["active_sensor_types"] = set(st.session_state["sensor_types"].values())

        st.success(f"Creato sensore {new_id}")

with st.sidebar.expander("Rimuovi sensore"):
    if st.session_state["known_sensors"]:
        sens = st.selectbox("Sensore", st.session_state["known_sensors"])
        if st.button("Rimuovi"):
            mqtt_pub.publish(f"greenfield/{FIELD_ID}/control/sensors",
                             json.dumps({"action": "remove", "id": sens}))

            st.session_state["known_sensors"].remove(sens)
            st.session_state["sensor_types"].pop(sens, None)
            st.session_state["active_sensor_types"] = set(st.session_state["sensor_types"].values())

            st.warning(f"Rimosso {sens}")

# ---------------------------------------------------------
# Placeholder layout
# ---------------------------------------------------------
placeholder_wait = st.empty()
placeholder_status = st.empty()
placeholder_metrics = st.empty()
placeholder_charts = st.empty()
placeholder_table = st.empty()

# ---------------------------------------------------------
# LOOP PRINCIPALE
# ---------------------------------------------------------
while True:

    while not decisions_q.empty():
        row = decisions_q.get()
        df.loc[len(df)] = {
            "temperatura": row.get("temperature"),
            "umidità": row.get("humidity"),
            "luce": row.get("light"),
            "vento_kmh": row.get("wind_kmh"),
            "radiazione": row.get("radiation"),
            "stress_idrico": row.get("water_stress_index"),
            "salute_vegetazione": row.get("vegetation_health"),
            "decisione": json.dumps(row.get("suggestion")),
            "timestamp": row.get("ts")
        }
        df.reset_index(drop=True, inplace=True)

    if df.empty:
        placeholder_wait.info("In attesa della prima decisione...")
        time.sleep(0.3)
        continue
    else:
        placeholder_wait.empty()

    last = df.iloc[-1]
    suggestion = json.loads(last["decisione"])
    action = suggestion.get("action", "")

    # tipi attivi
    active_types = st.session_state["active_sensor_types"]
    temp_active = "temperature" in active_types
    hum_active = "humidity" in active_types
    light_active = "light" in active_types

    # -----------------------------------------------------
    # Status Banner
    # -----------------------------------------------------
    with placeholder_status.container():
        st.markdown(f"**Modalità attuale:** `{modalita_label}`")

        if action == "hold":
            st.markdown("<div class='status-banner status-ok'>Condizioni Normali</div>", unsafe_allow_html=True)
        elif action == "irrigate":
            st.markdown("<div class='status-banner status-warn'>Irrigazione Raccomandata</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='status-banner status-bad'>Condizioni Critiche</div>", unsafe_allow_html=True)

    # -----------------------------------------------------
    # METRIC CARDS — dinamico
    # -----------------------------------------------------
    with placeholder_metrics.container():

        cards = []

        if temp_active and pd.notna(last["temperatura"]):
            cards.append(
                f"<div class='metric-card ok'>🌡️ {last['temperatura']}°C<br><small>Temperatura</small></div>"
            )

        if hum_active and pd.notna(last["umidità"]):
            hum = last["umidità"]
            hum_class = "ok" if hum > 60 else ("warn" if hum > 30 else "bad")
            cards.append(
                f"<div class='metric-card {hum_class}'>💧 {hum}%<br><small>Umidità</small></div>"
            )

        if light_active and pd.notna(last["luce"]):
            cards.append(
                f"<div class='metric-card warn'>🔆 {last['luce']} lx<br><small>Luce</small></div>"
            )

        if cards:
            cols = st.columns(len(cards))
            for i, html in enumerate(cards):
                cols[i].markdown(html, unsafe_allow_html=True)

        # stress idrico sempre visibile
        stress = last["stress_idrico"]
        stress_class = "ok" if stress < 0.4 else ("warn" if stress < 0.7 else "bad")
        st.markdown(
            f"<div class='metric-card {stress_class}' style='margin-top:20px;'>🔥 {round(stress,3)}<br><small>Stress Idrico</small></div>",
            unsafe_allow_html=True
        )

        # salute vegetazione (da immagini), se disponibile
        vh = last.get("salute_vegetazione")
        if pd.notna(vh):
            vh_class = "ok" if vh >= 0.8 else ("warn" if vh >= 0.5 else "bad")
            st.markdown(
                f"<div class='metric-card {vh_class}' style='margin-top:20px;'>🌿 {round(vh,3)}<br><small>Salute Vegetazione (da immagini)</small></div>",
                unsafe_allow_html=True
            )



    # -----------------------------------------------------
    # Grafici dinamici in 2 colonne
    # -----------------------------------------------------
    with placeholder_charts.container():
        st.markdown("<div class='section-title'>📈 Andamento dei Valori</div>", unsafe_allow_html=True)

        grafici = []

        if temp_active and not df["temperatura"].isna().all():
            grafici.append(("Temperatura", df["temperatura"]))

        if hum_active and not df["umidità"].isna().all():
            grafici.append(("Umidità", df["umidità"]))

        if light_active and not df["luce"].isna().all():
            grafici.append(("Luce", df["luce"]))

        grafici.append(("Stress Idrico", df["stress_idrico"]))

        cols = st.columns(2)

        for idx, (label, serie) in enumerate(grafici):
            with cols[idx % 2]:
                st.write(f"**{label}**")
                st.line_chart(serie, height=250)

    # -----------------------------------------------------
    # Decision Card
    # -----------------------------------------------------
    with placeholder_table.container():
        title = "Ultima Decisione AI" if selected_strategy == "ml_placeholder" else "Ultima Decisione del Sistema"
        st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)

        action_map = {
            "hold": "Nessuna irrigazione",
            "irrigate": "Irrigazione necessaria",
            "alert": "Condizioni critiche",
        }

        reason_map = {
            "conditions-normal": "Condizioni normali",
            "low-humidity-or-high-stress": "Umidità bassa o stress elevato",
            "extreme-conditions": "Condizioni estreme",
        }

        pretty_action = action_map.get(suggestion.get("action"), "N/A")
        pretty_reason = reason_map.get(suggestion.get("reason"), "N/A")
        volume = suggestion.get("volume_l_m2", 0)

        st.markdown(f"""
        <div style="
            padding: 20px;
            background: linear-gradient(135deg, #2c3e50, #34495e);
            border-radius: 12px;
            color: white;
            font-size: 20px;
            line-height: 1.6;
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        ">
            <b>Azione:</b> {pretty_action}<br>
            <b>Motivo:</b> {pretty_reason}<br>
            <b>Volume consigliato:</b> {volume} L/m²
        </div>
        """, unsafe_allow_html=True)

    time.sleep(0.3)
