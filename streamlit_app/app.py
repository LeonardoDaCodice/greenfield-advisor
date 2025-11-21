import streamlit as st
import time, threading, json, queue, os
from paho.mqtt import client as mqtt
import pandas as pd

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
FIELD_ID = os.getenv("FIELD_ID", "field-01")

# ---------------------------------------------------------------------
# Configurazione pagina + CSS moderno
# ---------------------------------------------------------------------
st.set_page_config(page_title="GreenField Advisor", layout="wide")

st.markdown("""
<style>
.metric-card {
    padding: 20px;
    border-radius: 15px;
    color: white;
    text-align: center;
    font-size: 28px;
    font-weight: bold;
}
.ok { background: linear-gradient(135deg, #2ecc71, #27ae60); }
.warn { background: linear-gradient(135deg, #f1c40f, #f39c12); }
.bad { background: linear-gradient(135deg, #e74c3c, #c0392b); }

.status-banner {
    padding: 18px;
    border-radius: 12px;
    color: white;
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 20px;
}
.status-ok { background: linear-gradient(135deg, #2ecc71, #27ae60); }
.status-warn { background: linear-gradient(135deg, #2980b9, #3498db); }
.status-bad { background: linear-gradient(135deg, #e74c3c, #c0392b); }

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

st.title("🌾 GreenField Advisor — Dashboard in Tempo Reale")

# ---------------------------------------------------------------------
# Code dati
# ---------------------------------------------------------------------
readings_q = queue.Queue()
decisions_q = queue.Queue()

df = pd.DataFrame(columns=[
    "temperatura", "umidità", "luce", "vento_kmh",
    "radiazione", "stress_idrico", "decisione", "timestamp"
])

# ---------------------------------------------------------------------
# Stato Streamlit (per modalità AI / Regole)
# ---------------------------------------------------------------------
if "current_strategy" not in st.session_state:
    st.session_state["current_strategy"] = None

# Mappa etichette UI -> nome strategia interna
STRATEGY_LABELS = {
    "senza AI": "simple_rules",
    "AI (ML placeholder)": "ml_placeholder",
}

# Sidebar: selettore modalità
modalita_label = st.sidebar.radio(
    "Modalità di decisione",
    list(STRATEGY_LABELS.keys()),
    index=0
)
selected_strategy = STRATEGY_LABELS[modalita_label]

# ---------------------------------------------------------------------
# MQTT Callback
# ---------------------------------------------------------------------
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except:
        return

    if "/sensors/" in msg.topic:
        readings_q.put(data)
    elif "/decisions" in msg.topic:
        decisions_q.put(data)

def mqtt_loop_sub():
    c = mqtt.Client()
    c.on_message = on_message
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    c.subscribe(f"greenfield/{FIELD_ID}/sensors/+/+", qos=0)
    c.subscribe(f"greenfield/{FIELD_ID}/decisions", qos=0)
    c.loop_forever()

threading.Thread(target=mqtt_loop_sub, daemon=True).start()

# Client separato per pubblicare comandi (es. cambio strategia)
mqtt_pub = mqtt.Client()
mqtt_pub.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
mqtt_pub.loop_start()

# Se l'utente ha cambiato modalità, inviamo comando al DecisionAgent
if st.session_state["current_strategy"] != selected_strategy:
    payload = {"strategy": selected_strategy}
    control_topic = f"greenfield/{FIELD_ID}/control/strategy"
    mqtt_pub.publish(control_topic, json.dumps(payload), qos=0, retain=False)
    st.session_state["current_strategy"] = selected_strategy

# ---------------------------------------------------------------------
# Layout placeholder
# ---------------------------------------------------------------------
placeholder_wait = st.empty()
placeholder_status = st.empty()
placeholder_metrics = st.empty()
placeholder_charts = st.empty()
placeholder_table = st.empty()

# ---------------------------------------------------------------------
# CICLO PRINCIPALE
# ---------------------------------------------------------------------
while True:

    # Recupero nuove decisioni
    while not decisions_q.empty():
        row = decisions_q.get()
        df.loc[len(df)] = {
            "temperatura": row.get("temperature"),
            "umidità": row.get("humidity"),
            "luce": row.get("light"),
            "vento_kmh": row.get("wind_kmh"),
            "radiazione": row.get("radiation"),
            "stress_idrico": row.get("water_stress_index"),
            "decisione": json.dumps(row.get("suggestion")),
            "timestamp": row.get("ts")
        }
        # reset index per sicurezza
        df.reset_index(drop=True, inplace=True)

    # Messaggio iniziale
    if df.empty:
        placeholder_wait.info("⏳ In attesa di ricevere la prima decisione...")
        time.sleep(0.3)
        continue
    else:
        placeholder_wait.empty()

    last = df.iloc[-1]
    suggestion = json.loads(last["decisione"])
    action = suggestion.get("action", "")

    # -----------------------------------------------------------------
    # BANNER DI STATO
    # -----------------------------------------------------------------
    with placeholder_status.container():
        # Mostro anche la modalità attuale in alto
        st.markdown(f"**Modalità attuale:** `{modalita_label}`")

        if action == "hold":
            st.markdown("<div class='status-banner status-ok'>🟢 Condizioni Normali</div>", unsafe_allow_html=True)
        elif action == "irrigate":
            st.markdown("<div class='status-banner status-warn'>🔵 Irrigazione Raccomandata</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='status-banner status-bad'>🔴 Condizioni Critiche</div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # METRIC CARDS
    # -----------------------------------------------------------------
    with placeholder_metrics.container():
        col1, col2, col3, col4 = st.columns(4)

        col1.markdown(
            f"<div class='metric-card ok'>🌡️ {last['temperatura']}°C<br><small>Temperatura</small></div>",
            unsafe_allow_html=True
        )

        if last['umidità'] > 60:
            hum_class = "ok"
        elif last['umidità'] > 30:
            hum_class = "warn"
        else:
            hum_class = "bad"

        col2.markdown(
            f"<div class='metric-card {hum_class}'>💧 {last['umidità']}%<br><small>Umidità</small></div>",
            unsafe_allow_html=True
        )

        col3.markdown(
            f"<div class='metric-card warn'>🔆 {last['luce']} lx<br><small>Luce</small></div>",
            unsafe_allow_html=True
        )

        stress = last['stress_idrico']
        stress_class = "ok" if stress < 0.4 else ("warn" if stress < 0.7 else "bad")

        col4.markdown(
            f"<div class='metric-card {stress_class}'>🔥 {round(stress,3)}<br><small>Stress Idrico</small></div>",
            unsafe_allow_html=True
        )

    # -----------------------------------------------------------------
    # GRAFICI LIVE
    # -----------------------------------------------------------------
    with placeholder_charts.container():
        st.markdown("<div class='section-title'>📈 Andamento dei Valori</div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        c1.line_chart(df['temperatura'], height=250)
        c2.line_chart(df['umidità'], height=250)

        c3, c4 = st.columns(2)
        c3.line_chart(df['luce'], height=250)
        c4.line_chart(df['stress_idrico'], height=250)

    # -----------------------------------------------------------------
    # CARD DECISIONALE (ELEGANTE)
    # -----------------------------------------------------------------
    with placeholder_table.container():

        # Titolo dinamico in base alla modalità scelta
        titolo_sezione = (
            "🧠 Ultima Decisione AI"
            if selected_strategy == "ml_placeholder"
            else "🧭 Ultima Decisione del Sistema"
        )

        st.markdown(f"<div class='section-title'>{titolo_sezione}</div>", unsafe_allow_html=True)

        action_map = {
            "hold": "Nessuna irrigazione",
            "irrigate": "Irrigazione necessaria",
            "alert": "Condizioni critiche"
        }

        reason_map = {
            "conditions-normal": "Condizioni normali",
            "low-humidity-or-high-stress": "Umidità bassa o stress elevato",
            "extreme-conditions": "Condizioni estreme rilevate"
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
