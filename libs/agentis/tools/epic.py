from typing import Any, Dict

from libs.common.mcp_client import make_epic_client


def discharge_event_get(params: Dict[str, Any]) -> Dict[str, Any]:
    return make_epic_client().call("epic.discharge_event.get", params)


def patient_bundle_get(patient_id: str) -> Dict[str, Any]:
    return make_epic_client().call("epic.patient_bundle.get", {"patient_id": patient_id})


def fhir_create(resource_type: str, resource_json: Dict[str, Any]) -> Dict[str, Any]:
    return make_epic_client().call("epic.fhir_write_back.create", {"resource_type": resource_type, "resource_json": resource_json})


def inbasket_alert(patient_id: str, subject: str, body: str, priority: str) -> Dict[str, Any]:
    return make_epic_client().call("epic.inbasket.alert", {"patient_id": patient_id, "subject": subject, "body": body, "priority": priority})
