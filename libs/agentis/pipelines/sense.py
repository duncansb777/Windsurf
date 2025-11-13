from typing import Any, Dict


def run(discharge_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "handover_facts": {"problems": [], "meds": [], "followups": [], "risks": []},
        "risk_signals": {},
        "citations": [],
        "confidence": 0.0,
        "caveats": ["mock"],
    }
