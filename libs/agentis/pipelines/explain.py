from typing import Any, Dict


def run(summary: str, risk_flag: str, discharge_date: str) -> Dict[str, Any]:
    return {"patient_messages": [], "clinician_letters": [], "citations": [], "confidence": 0.0, "caveats": ["mock"]}
