from typing import Any, Dict


def run(signals: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    return {"recommendation": {"action": "none", "priority": "low", "rationale": "mock"}, "inputs_used": [], "citations": [], "confidence": 0.0, "caveats": ["mock"]}
