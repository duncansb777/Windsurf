from typing import Any, Dict

SCHEMA_FACTS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "problems": {"type": "array"},
        "meds": {"type": "array"},
        "followups": {"type": "array"},
        "risks": {"type": "array"},
    },
    "required": ["problems", "meds", "followups", "risks"],
}

SCHEMA_PLAN: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "tasks": {"type": "array"},
        "next_tool_calls": {"type": "array"},
    },
    "required": ["tasks", "next_tool_calls"],
}

SCHEMA_MESSAGES: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "patient_messages": {"type": "array"},
        "clinician_letters": {"type": "array"},
    },
    "required": ["patient_messages", "clinician_letters"],
}

SCHEMA_NORMALISE: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "coded_terms": {"type": "array"},
        "fhir_resources": {"type": "object"},
    },
    "required": ["coded_terms", "fhir_resources"],
}

SCHEMA_PREDICT: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendation": {"type": "object"},
        "inputs_used": {"type": "array"},
    },
    "required": ["recommendation", "inputs_used"],
}
