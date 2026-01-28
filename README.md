# **GreenField Advisor — (Agent-based, AI-optional)**

Sistema didattico modulare basato su agenti che simulano sensori ambientali, condizioni meteo,
feature derivate da immagini (salute della vegetazione) e un modulo decisionale.
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

## **Clonazione del progetto**

Repository: https://github.com/LeonardoDaCodice/greenfield-advisor

```bash
git clone https://github.com/LeonardoDaCodice/greenfield-advisor.git
cd greenfield-advisor
````


---

## **Installazione Mosquitto (Windows) — Download + PATH**

Per eseguire `mosquitto` da terminale (es. `mosquitto -v`) è necessario:

1. **Scaricare e installare Mosquitto** dal sito ufficiale:
   [https://mosquitto.org/download/](https://mosquitto.org/download/)

2. Verificare che la cartella di installazione sia nel **PATH** delle Variabili di sistema.

### **Percorso tipico di installazione**

Esempio:
`C:\Program Files\mosquitto`

### **Aggiungere Mosquitto al PATH (Variabili di sistema)**

1. Apri: **Pannello di Controllo → Sistema → Impostazioni di sistema avanzate**
2. Clicca: **Variabili d’ambiente**
3. In **Variabili di sistema**, seleziona **Path** → **Modifica**
4. Clicca **Nuovo** e aggiungi:
   `C:\Program Files\mosquitto`
5. Conferma con **OK** su tutte le finestre
6. **Chiudi e riapri** il terminale (per ricaricare le variabili)

### **Verifica**

Da un nuovo terminale:

```bash
mosquitto -h
```

Se il comando viene riconosciuto, il PATH è configurato correttamente.

---

## **Installazione progetto**

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

### **Terminale 2 — Avviare gli agenti (sensori + meteo + immagini + decisioni)**

```bash
venv\Scripts\activate
python -m src.app.main
```

---

### **Terminale 3 — Avviare la dashboard Streamlit**

```bash
venv\Scripts\activate
streamlit run streamlit_app\app.py
```

---

## **Orchestrazione con n8n (opzionale)**

1. Importare il workflow: `n8n/greenfield_webhook_demo.json`
2. Impostare `N8N_WEBHOOK_URL` nel `.env`
3. Il DecisionAgent invierà ogni decisione al webhook configurato

---

## **Pattern applicati**

* **Observer** – Agenti sensori / meteo / immagini → DecisionAgent tramite MQTT
* **Chain of Responsibility** – cleaning → feature engineering → estimation
* **Strategy** – strategie decisionali intercambiabili (`simple_rules`, `ml_placeholder`)
* **(Opz.) Mediator** – n8n come orchestratore esterno
* **Integrazione indice di salute vegetazione da immagini (ImageAgent)** – un agente dedicato simula l’analisi delle immagini del campo e pubblica un indice di `vegetation_health` usato nel calcolo del water stress index.

---

## **Estensione a sensori reali**

I sensori simulati possono essere sostituiti da ESP32/Arduino con pubblicazione MQTT,
senza modifiche all’architettura: si mantengono stessi topic e payload.
In modo analogo, l’`ImageAgent` può essere sostituito da un servizio reale di Computer Vision
che elabora immagini del campo (da drone o camera fissa) e pubblica feature aggregate
(es. indici di salute della vegetazione).

---

© 2025 — Starter didattico per GreenField Advisor.

```
```
