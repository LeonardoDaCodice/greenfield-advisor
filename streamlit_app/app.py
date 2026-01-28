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
    font-size: 22px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 20px;
}
.status-ok   { background: linear-gradient(135deg, #2ecc71, #27ae60); }
.status-warn { background: linear-gradient(135deg, #f1c40f, #f39c12); }
.status-bad  { background: linear-gradient(135deg, #e74c3c, #c0392b); }

.section-title {
    margin-top: 20px;
    font-size: 22px;
    font-weight: bold;
}

tbody th { display: none !important; }
thead th:first-child { display: none !important; }
table { border-collapse: collapse; }
</style>
""", unsafe_allow_html=True)

st.title("GreenField Advisor — Dashboard in Tempo Reale")

# ---------------------------------------------------------
# Code dati
# ---------------------------------------------------------
readings_q = queue.Queue()
decisions_q = queue.Queue()

df = pd.DataFrame(columns=[
    "temperatura", "umidità", "luce",
    "stress_idrico", "vegetation_health",
    "decisione", "timestamp"
])

# ---------------------------------------------------------
# Stato Streamlit
# ---------------------------------------------------------
if "mode" not in st.session_state:
    st.session_state["mode"] = "live"

if "current_strategy" not in st.session_state:
    st.session_state["current_strategy"] = None

# ---------------------------------------------------------
# Scelta modalità LIVE / DEMO
# ---------------------------------------------------------
st.sidebar.header("Modalità dati")
mode_selected = st.sidebar.radio(
    "Modalità di acquisizione dati",
    ["Live", "Demo (Test Cases)"],
    index=0
).lower().split()[0]

if st.session_state["mode"] != mode_selected:
    st.session_state["mode"] = mode_selected

    if mode_selected == "live":
        mqtt_pub = mqtt.Client()
        mqtt_pub.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_pub.publish(
            f"greenfield/{FIELD_ID}/control/test_case",
            json.dumps({"mode": "live"})
        )
        mqtt_pub.loop_start()

# ---------------------------------------------------------
# Modalità AI (solo LIVE)
# ---------------------------------------------------------
STRATEGY_LABELS = {
    "senza AI": "simple_rules",
    "AI (ML placeholder)": "ml_placeholder",
}

if st.session_state["mode"] == "live":
    st.sidebar.subheader("Modalità decisionale")
    modalita_label = st.sidebar.radio("Decision engine", list(STRATEGY_LABELS.keys()), index=0)
    selected_strategy = STRATEGY_LABELS[modalita_label]
else:
    selected_strategy = "simple_rules"

# ---------------------------------------------------------
# MQTT Setup
# ---------------------------------------------------------
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
    except:
        return

    if msg.topic.endswith("/decisions"):
        decisions_q.put(data)
        return


def mqtt_loop_sub():
    c = mqtt.Client()
    c.on_message = on_message
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    c.subscribe(f"greenfield/{FIELD_ID}/decisions", qos=0)
    c.loop_forever()


threading.Thread(target=mqtt_loop_sub, daemon=True).start()

mqtt_pub = mqtt.Client()
mqtt_pub.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
mqtt_pub.loop_start()

# ---------------------------------------------------------
# DEMO MODE — Selezione test case
# ---------------------------------------------------------
if st.session_state["mode"] == "demo":

    st.sidebar.subheader("Test Cases")

    files = [
        f.replace(".json", "")
        for f in os.listdir("test_cases")
        if f.endswith(".json")
    ]

    selected_case = st.sidebar.selectbox("Seleziona scenario", files)

    if st.sidebar.button("Applica Test Case"):
        mqtt_pub.publish(
            f"greenfield/{FIELD_ID}/control/test_case",
            json.dumps({"mode": "demo", "case": selected_case})
        )
        st.sidebar.success(f"Scenario '{selected_case}' applicato!")


# ---------------------------------------------------------
# Funzioni classificazione card
# ---------------------------------------------------------
def classify_temperature(t):
    if t is None: return "bad"
    if 18 <= t <= 30: return "ok"
    if 10 <= t < 18 or 30 < t <= 35: return "warn"
    return "bad"

def classify_humidity(h):
    if h is None: return "bad"
    if 40 <= h <= 70: return "ok"
    if 20 <= h < 40 or 70 < h <= 85: return "warn"
    return "bad"

def classify_light(lx):
    if lx is None: return "bad"
    if 300 <= lx <= 1200: return "ok"
    if 150 <= lx < 300 or 1200 < lx <= 1500: return "warn"
    return "bad"

def classify_veg_health(vh):
    if vh is None: return "bad"
    if vh >= 0.8: return "ok"
    if 0.5 <= vh < 0.8: return "warn"
    return "bad"

def classify_wsi(w):
    if w is None: return "bad"
    if w < 0.4: return "ok"
    if w < 0.7: return "warn"
    return "bad"


# ---------------------------------------------------------
# MAPPATURE TESTUALI (CONDIZIONI + SUGGERIMENTO)
# ---------------------------------------------------------
reason_map = {
    "conditions-normal": "Condizioni normali del campo.",
    "moderate-water-stress": "Stress idrico moderato.",
    "high-water-stress": "Stress idrico elevato.",
    "very-high-water-stress": "Stress idrico molto elevato.",
    "low-humidity": "Umidità troppo bassa.",
    "humidity-too-high": "Umidità eccessiva.",
    "too-cold-to-irrigate": "Temperatura troppo bassa per irrigare.",
    "vegetation-health-critical": "Salute vegetazione critica.",
    "extreme-conditions": "Condizioni ambientali estreme.",
    "simulated-ml-result": "Risultato generato dal modello AI simulato."
}

action_map = {
    "hold": "Nessuna irrigazione necessaria",
    "irrigate_light": "Irrigazione lieve consigliata",
    "irrigate": "Irrigazione consigliata",
    "irrigate_heavy": "Irrigazione intensa necessaria",
    "alert": "⚠️ Intervento immediato richiesto"
}


# ---------------------------------------------------------
# LOOP PRINCIPALE
# ---------------------------------------------------------
placeholder_wait = st.empty()
placeholder_status = st.empty()
placeholder_metrics = st.empty()
placeholder_charts = st.empty()
placeholder_table = st.empty()

while True:

    while not decisions_q.empty():
        row = decisions_q.get()
        df.loc[len(df)] = {
            "temperatura": row.get("temperature"),
            "umidità": row.get("humidity"),
            "luce": row.get("light"),
            "stress_idrico": row.get("water_stress_index"),
            "vegetation_health": row.get("vegetation_health"),
            "decisione": json.dumps(row.get("suggestion")),
            "timestamp": row.get("ts")
        }
        df.reset_index(drop=True, inplace=True)

    if df.empty:
        placeholder_wait.info("In attesa della prima decisione...")
        time.sleep(0.3)
        continue
    placeholder_wait.empty()

    last = df.iloc[-1]
    suggestion = json.loads(last["decisione"])

    action = suggestion.get("action", "")
    reason = suggestion.get("reason", "")

    # ---------------------------------------------------------
    # BANNER SUPERIORE — CONDIZIONI (based on reason)
    # ---------------------------------------------------------
    with placeholder_status.container():

        reason_text = reason_map.get(reason, "Stato non disponibile")

        if reason in ["conditions-normal"]:
            banner_class = "status-ok"
        elif reason in ["moderate-water-stress", "high-water-stress", "low-humidity"]:
            banner_class = "status-warn"
        else:
            banner_class = "status-bad"

        st.markdown(
            f"<div class='status-banner {banner_class}'>{reason_text}</div>",
            unsafe_allow_html=True
        )

    # ---------------------------------------------------------
    # CARDS SENSORI
    # ---------------------------------------------------------
    with placeholder_metrics.container():
        cards = []

        t = last["temperatura"]
        cards.append(f"<div class='metric-card {classify_temperature(t)}'>🌡️ {t}°C<br><small>Temperatura</small></div>")

        h = last["umidità"]
        cards.append(f"<div class='metric-card {classify_humidity(h)}'>💧 {h}%<br><small>Umidità</small></div>")

        l = last["luce"]
        cards.append(f"<div class='metric-card {classify_light(l)}'>🔆 {l} lx<br><small>Luce</small></div>")

        cols = st.columns(len(cards))
        for i, html in enumerate(cards):
            cols[i].markdown(html, unsafe_allow_html=True)

        stress = last["stress_idrico"]
        st.markdown(
            f"<div class='metric-card {classify_wsi(stress)}' style='margin-top:20px;'>🔥 {stress}<br><small>Stress Idrico</small></div>",
            unsafe_allow_html=True
        )

        vh = last["vegetation_health"]
        st.markdown(
            f"<div class='metric-card {classify_veg_health(vh)}' style='margin-top:20px;'>🌿 {vh}<br><small>Salute Vegetazione</small></div>",
            unsafe_allow_html=True
        )

    # ---------------------------------------------------------
    # GRAFICI
    # ---------------------------------------------------------
    with placeholder_charts.container():
        st.markdown("<div class='section-title'>📈 Andamento dei Valori</div>", unsafe_allow_html=True)

        grafici = [
            ("Temperatura", df["temperatura"]),
            ("Umidità", df["umidità"]),
            ("Luce", df["luce"]),
            ("Stress Idrico", df["stress_idrico"]),
        ]

        cols = st.columns(2)
        for idx, (label, serie) in enumerate(grafici):
            with cols[idx % 2]:
                st.write(f"**{label}**")
                st.line_chart(serie, height=250)

    # ---------------------------------------------------------
    # BANNER INFERIORE — SUGGERIMENTO (based on action)
    # ---------------------------------------------------------
    with placeholder_table.container():

        pretty_action = action_map.get(action, "Azione sconosciuta")
        pretty_reason = reason_map.get(reason, "Motivo non disponibile")

        volume = suggestion.get("volume_l_m2", 0)

        # colore banner suggeriemento
        if action == "hold":
            banner_class = "status-ok"
        elif action in ["irrigate_light", "irrigate"]:
            banner_class = "status-warn"
        else:
            banner_class = "status-bad"

        st.markdown(
            f"<div class='status-banner {banner_class}'><b>{pretty_action}</b></div>",
            unsafe_allow_html=True
        )

        st.markdown(f"""
        <div style="
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 12px;
            font-size: 18px;
            color: white;
            line-height: 1.6;
            margin-top: -10px;">
            <b>Motivo:</b> {pretty_reason}<br>
            <b>Volume consigliato:</b> {volume} L/m²
        </div>
        """, unsafe_allow_html=True)

    time.sleep(0.3)
