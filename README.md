# **GreenField Advisor — (Agent-based, AI-optional)**

Sistema didattico modulare basato su agenti che simulano sensori ambientali, condizioni meteo e un modulo decisionale.
I dati vengono elaborati tramite una **pipeline** (Chain of Responsibility: cleaning → feature engineering → estimation)
con **strategie intercambiabili** (Strategy Pattern) e comunicazione asincrona basata su **Observer** tramite MQTT.
È disponibile una dashboard in **Streamlit** e integrazione opzionale con **n8n** per orchestrazione.

---

## **Requisiti**

* Python 3.10+
* Broker MQTT (es. Mosquitto) su `localhost:1883`
* Streamlit (dashboard)
* (Opzionale) n8n per orchestrazione e webhook

---

## **Installazione**

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # poi modificare i valori se necessario
```

---

## **Avvio rapido (simulazione locale)**

### **Terminale 1 — Avviare Mosquitto**

```bash
mosquitto -v
```

---

### **Terminale 2 — Avviare gli agenti (sensori + meteo + decisioni)**

```bash
venv\Scripts\activate
python -m src.app.main
```

---

### **Terminale 3 — Avviare la dashboard Streamlit**

```bash
venv\Scripts\activate
streamlit run streamlit_app/app.py
```

---

## **Orchestrazione con n8n (opzionale)**

1. Importare il workflow: `n8n/greenfield_webhook_demo.json`
2. Impostare `N8N_WEBHOOK_URL` nel `.env`
3. Il DecisionAgent invierà ogni decisione al webhook configurato

---

## **Pattern applicati**

* **Observer** – Agenti sensori → DecisionAgent tramite MQTT
* **Chain of Responsibility** – cleaning → feature engineering → estimation
* **Strategy** – strategie decisionali intercambiabili (`simple_rules`, `ml_placeholder`)
* **(Opz.) Mediator** – n8n come orchestratore esterno

---

## **Estensione a sensori reali**

I sensori simulati possono essere sostituiti da ESP32/Arduino con pubblicazione MQTT,
senza modifiche all’architettura: si mantengono stessi topic e payload.

---

© 2025 — Starter didattico per GreenField Advisor.
