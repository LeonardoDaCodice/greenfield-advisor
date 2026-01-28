from typing import Dict, Any
import random


# ============================================================
# Base Strategy
# ============================================================
class BaseStrategy:
    name = "base"

    def estimate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


# ============================================================
# STRATEGIA REALISTICA BASATA SUI RANGE USATI NELLE CARD
# ============================================================
class SimpleRuleStrategy(BaseStrategy):
    name = "simple_rules"

    def estimate(self, f: Dict[str, Any]) -> Dict[str, Any]:

        temp = float(f.get("temperature", 25.0))
        hum = float(f.get("humidity", 50.0))
        light = float(f.get("light", 500.0))
        vh = float(f.get("vegetation_health", 0.7))
        wsi = float(f.get("water_stress_index", 0.25))

        # ---------------------------------------------------------
        # 1) CONDIZIONI DAVVERO ESTREME → ALERT
        # ---------------------------------------------------------
        if temp > 40 or hum < 20 or light < 80 or vh < 0.2 or wsi > 1.2:
            return {
                "action": "alert",
                "reason": "extreme-conditions",
                "volume_l_m2": 0.0
            }

        # ---------------------------------------------------------
        # 2) WSI → BASE PER L'IRRIGAZIONE
        # ---------------------------------------------------------
        if wsi < 0.4:
            irrig_action = "hold"
            volume = 0.0
            reason = "conditions-normal"

        elif 0.4 <= wsi < 0.7:
            irrig_action = "irrigate_light"
            volume = 2.0
            reason = "moderate-water-stress"

        elif 0.7 <= wsi < 1.0:
            irrig_action = "irrigate"
            volume = 4.0
            reason = "high-water-stress"

        else:  # wsi >= 1.0
            irrig_action = "irrigate_heavy"
            volume = 6.0
            reason = "very-high-water-stress"

        # ---------------------------------------------------------
        # 3) UMIDITÀ — override della decisione
        # ---------------------------------------------------------

        # Umidità troppo bassa → irrigazione forte garantita
        if hum < 30:
            irrig_action = "irrigate_heavy"
            volume = max(volume, 5.0)
            reason = "low-humidity"

        # Umidità troppo alta → MAI irrigare
        elif hum > 85:
            irrig_action = "hold"
            volume = 0.0
            reason = "humidity-too-high"

        # ---------------------------------------------------------
        # 4) Temperatura bassa → vietata irrigazione
        # ---------------------------------------------------------
        if temp < 5:
            return {
                "action": "hold",
                "reason": "too-cold-to-irrigate",
                "volume_l_m2": 0.0
            }

        # ---------------------------------------------------------
        # 5) Vegetation health molto bassa → ALERT
        # ---------------------------------------------------------
        if vh < 0.3 and irrig_action != "alert":
            return {
                "action": "alert",
                "reason": "vegetation-health-critical",
                "volume_l_m2": 0.0
            }

        # ---------------------------------------------------------
        # 6) RISPOSTA FINALE
        # ---------------------------------------------------------
        return {
            "action": irrig_action,
            "reason": reason,
            "volume_l_m2": volume
        }


# ============================================================
# AI PLACEHOLDER — Comportamento probabilistico
# ============================================================
class MLPlaceholderStrategy(BaseStrategy):
    name = "ml_placeholder"

    def estimate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        p = random.random()
        action = "irrigate" if p > 0.7 else "hold"

        return {
            "action": action,
            "reason": "simulated-ml-result",
            "volume_l_m2": 1.5 if action == "irrigate" else 0.0
        }


# ============================================================
# FACTORY — Selezione strategia
# ============================================================
def make_strategy(name: str) -> BaseStrategy:
    name = (name or "simple_rules").lower().strip()

    if name == "ml_placeholder":
        return MLPlaceholderStrategy()

    return SimpleRuleStrategy()
