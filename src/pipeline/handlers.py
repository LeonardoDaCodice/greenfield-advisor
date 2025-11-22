from typing import Any, Dict, Optional

# ============================================================
# 🎯 BASE HANDLER (Chain of Responsibility)
# ============================================================
class Handler:
    def __init__(self, nxt: Optional['Handler'] = None):
        self._next = nxt

    def set_next(self, nxt: 'Handler') -> 'Handler':
        """Collega il prossimo handler nella pipeline."""
        self._next = nxt
        return nxt

    def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue il proprio step e poi passa al prossimo."""
        processed = self._process(data)
        if self._next:
            return self._next.handle(processed)
        return processed

    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


# ============================================================
# 🧹 CLEANING HANDLER
# Normalizza valori e rimuove anomalie grezze
# ============================================================
class CleaningHandler(Handler):
    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:

        # Temperature: accettabile da -20 a 60°C
        if "temperature" in data:
            try:
                v = float(data["temperature"])
                data["temperature"] = max(-20.0, min(60.0, v))
            except:
                data["temperature"] = None

        # Umidità: clamp 0–100%
        if "humidity" in data:
            try:
                v = float(data["humidity"])
                data["humidity"] = max(0.0, min(100.0, v))
            except:
                data["humidity"] = None

        # Luce: max 2000 lx (per simulazioni)
        if "light" in data:
            try:
                v = float(data["light"])
                data["light"] = max(0.0, min(2000.0, v))
            except:
                data["light"] = None

        return data


# ============================================================
# 🧠 FEATURE ENGINEERING HANDLER
# Calcolo Water Stress Index (WSI)
# ============================================================
class FeatureEngineeringHandler(Handler):
    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:

        # Lettura sicura valori
        temp = float(data.get("temperature") or 25.0)
        hum = float(data.get("humidity") or 50.0)
        light = float(data.get("light") or 500.0)

        # Nuova feature da immagini: salute vegetazione (0–1)
        # In un sistema reale deriverebbe da un modello CV (es. NDVI).
        vh = float(data.get("vegetation_health") or 0.7)

        # Formula WSI (semplificata, prima parte come prima)
        wsi = (temp / 35.0) * ((100.0 - hum) / 100.0) * (light / 1000.0)

        # Modulazione in base a vegetazione_health:
        # - se la vegetazione è molto sana (vh → 1), riduciamo leggermente lo stress percepito
        # - se è scarsa (vh → 0), lo lasciamo invariato o leggermente amplificato
        vh_clamped = max(0.0, min(vh, 1.0))
        # Fattore tra ~0.9 e 1.1
        modulation_factor = 1.1 - vh_clamped * 0.2
        wsi = wsi * modulation_factor

        data["water_stress_index"] = round(max(0.0, min(wsi, 2.0)), 3)
        return data




# ============================================================
# 🤖 ESTIMATION HANDLER
# Applica la strategia (regole o AI)
# ============================================================
class EstimationHandler(Handler):
    def __init__(self, estimator, nxt: Optional['Handler'] = None):
        super().__init__(nxt)
        self.estimator = estimator  # Strategy selezionata

    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Applica lo strategy estimator per ottenere una decisione."""
        suggestion = self.estimator.estimate(data)
        data["suggestion"] = suggestion
        return data
