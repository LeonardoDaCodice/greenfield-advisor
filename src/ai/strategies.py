from typing import Dict, Any
import random


# ============================================================
# Base delle strategie decisionali
# ============================================================
class BaseStrategy:
    """
    Classe base astratta che definisce l'interfaccia delle strategie decisionali.
    Ogni strategia deve implementare il metodo estimate().
    """
    name = "base"

    def estimate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError



# ============================================================
# Strategia 1 — Regole semplici (baseline senza AI)
# ============================================================
class SimpleRuleStrategy(BaseStrategy):
    """
    Strategia deterministica basata su regole:
    - Se l'umidità è bassa o lo stress idrico è alto → irrigare
    - Se la temperatura è troppo bassa → non irrigare
    """
    name = "simple_rules"

    def estimate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        hum = float(features.get("humidity", 50.0))
        temp = float(features.get("temperature", 25.0))
        wsi = float(features.get("water_stress_index", 0.2))

        action = "hold"
        reason = "conditions-normal"

        if hum < 45.0 or wsi > 0.6:
            action = "irrigate"
            reason = "low-humidity-or-high-stress"

        if temp < 5.0:
            action = "hold"
            reason = "too-cold-to-irrigate"

        volume_l_m2 = 2.0 if action == "irrigate" else 0.0

        return {
            "action": action,
            "reason": reason,
            "volume_l_m2": volume_l_m2
        }



# ============================================================
# Strategia 2 — Placeholder AI simulata (senza addestramento)
# ============================================================
class MLPlaceholderStrategy(BaseStrategy):
    """
    Strategia che simula un modello di Machine Learning.
    Non usa un modello addestrato ma introduce:
    - comportamento probabilistico
    - decisioni non deterministiche
    Lo scopo è dimostrare l'integrazione AI-ready senza training reale.
    """
    name = "ml_placeholder"

    def estimate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        p = random.random()

        # Simuliamo un modello probabilistico:
        # con p > 0.7 → irrigazione necessaria
        action = "irrigate" if p > 0.7 else "hold"

        return {
            "action": action,
            "reason": "simulated-ml-result",
            "volume_l_m2": 1.2 if action == "irrigate" else 0.0
        }



# ============================================================
# Factory delle strategie
# ============================================================
def make_strategy(name: str) -> BaseStrategy:
    """
    Ritorna l'istanza della strategia richiesta.
    Permette all'utente o al sistema di sostituire facilmente il motore decisionale.
    """
    name = (name or "simple_rules").lower().strip()

    if name == "ml_placeholder":
        return MLPlaceholderStrategy()

    return SimpleRuleStrategy()
