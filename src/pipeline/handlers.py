from typing import Any, Dict, Optional

# ============================================================
#  BASE HANDLER (Chain of Responsibility)
# ============================================================
class Handler:
    def __init__(self, nxt: Optional['Handler'] = None):
        self._next = nxt

    def set_next(self, nxt: 'Handler') -> 'Handler':
        """Collega il prossimo handler nella pipeline."""
        self._next = nxt
        return nxt

    def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue il proprio step e passa al successivo."""
        processed = self._process(data)
        if self._next:
            return self._next.handle(processed)
        return processed

    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


# ============================================================
#  CLEANING HANDLER
# Normalizzazione valori sensori
# ============================================================
class CleaningHandler(Handler):
    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:

        # Temperature: clamp tra -20 e +60
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

        # Luce: clamp 0–2000 lx
        if "light" in data:
            try:
                v = float(data["light"])
                data["light"] = max(0.0, min(2000.0, v))
            except:
                data["light"] = None

        # Vegetation health: 0–1
        if "vegetation_health" in data and data["vegetation_health"] is not None:
            try:
                v = float(data["vegetation_health"])
                data["vegetation_health"] = max(0.0, min(1.0, v))
            except:
                data["vegetation_health"] = None

        return data


# ============================================================
#  FEATURE ENGINEERING HANDLER
# Calcolo Water Stress Index (WSI)
# ============================================================
class FeatureEngineeringHandler(Handler):
    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:

        # ---- Lettura sicura: default SOLO se None ----
        temp = data.get("temperature")
        hum = data.get("humidity")
        light = data.get("light")
        vh = data.get("vegetation_health")

        if temp is None: temp = 25.0
        if hum is None: hum = 50.0
        if light is None: light = 500.0
        if vh is None: vh = 0.7

        temp = float(temp)
        hum = float(hum)
        light = float(light)
        vh = float(vh)

        # ---- Calcolo WSI base ----
        wsi = (temp / 35.0) * ((100.0 - hum) / 100.0) * (light / 1000.0)

        # ---- Modulazione in base alla salute vegetazione ----
        vh_clamped = max(0.0, min(vh, 1.0))
        modulation_factor = 1.1 - vh_clamped * 0.2  # range 1.1 → 0.9
        wsi *= modulation_factor

        data["water_stress_index"] = round(max(0.0, min(wsi, 2.0)), 3)
        return data


# ============================================================
#  ESTIMATION HANDLER
# Strategy: regole o AI placeholder
# ============================================================
class EstimationHandler(Handler):
    def __init__(self, estimator, nxt: Optional['Handler'] = None):
        super().__init__(nxt)
        self.estimator = estimator

    def _process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        suggestion = self.estimator.estimate(data)
        data["suggestion"] = suggestion
        return data
