from typing import Any, Dict


def run(handover_facts: Dict[str, Any]) -> Dict[str, Any]:
    return {"coded_terms": [], "fhir_resources": {}, "citations": [], "confidence": 0.0, "caveats": ["mock"]}
