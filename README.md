# GreenField Advisor — (Agent-based, AI-optional)

Sistema didattico modulare basato su agenti che simulano sensori ambientali, condizioni meteo e un modulo decisionale.
I dati vengono elaborati tramite una **pipeline** (Chain of Responsibility: cleaning → feature engineering → estimation)
con **strategie intercambiabili** (Strategy Pattern) e comunicazione basata su **Observer** tramite MQTT.
È disponibile una dashboard in **Streamlit** e integrazione opzionale con **n8n** per orchestrazione.

## Requisiti

* Python 3.10+
* Broker MQTT (es. Mosquitto) su `localhost:1883`
* Streamlit (dashboard)
* (Facoltativo) n8n per orchestrazione e webhook

## Installazione

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # poi modificare i valori se necessario
```

## Avvio rapido (simulazione locale)

Avvia Mosquitto in un terminale:

```bash
mosquitto -v
```

In un secondo terminale avvia gli agenti (sensori, meteo, decisioni):

```bash
venv\Scripts\activate
python src/app/main.py
```

In un terzo terminale avvia la dashboard:

```bash
venv\Scripts\activate
streamlit run src/streamlit_app/app.py
```

## Orchestrazione con n8n (opzionale)

1. Importare il workflow: `n8n/greenfield_webhook_demo.json`
2. Impostare `N8N_WEBHOOK_URL` nel `.env`
3. Il DecisionAgent invierà ogni decisione al webhook n8n configurato

## Pattern applicati

* **Observer**: comunicazione agenti → DecisionAgent tramite MQTT
* **Chain of Responsibility**: cleaning → feature engineering → estimation
* **Strategy**: strategie decisionali intercambiabili (`simple_rules`, `ml_placeholder`)
* **(Opz.) Mediator**: n8n come orchestratore esterno

## Estensione a sensori reali

I sensori simulati possono essere sostituiti da hardware reale (es. ESP32/Arduino → MQTT)
senza modifiche architetturali, mantenendo stessi topic e payload.

---

© 2025 — Starter didattico per GreenField Advisor.

---