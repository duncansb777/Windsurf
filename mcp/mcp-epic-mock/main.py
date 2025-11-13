#!/usr/bin/env python3
import json
import sys
import time
from typing import Any, Dict
from fixtures import (
    patients,
    encounters,
    care_teams,
    care_plans,
    medication_requests,
    observations,
    service_requests,
    consents,
    document_references,
    providers,
    organizations,
    locations,
    audit_events,
    fhir_bundle_for_patient,
)

# Minimal JSON-RPC 2.0 over stdio for demo purposes.
# Methods exposed:
# - epic.discharge_event.get
# - epic.patient_bundle.get
# - epic.fhir_write_back.create
# - epic.inbasket.alert
# - auth.smart.token

TOOLS = [
    {
        "name": "epic.discharge_event.get",
        "input": {},
        "output": {"type": "cloudevent"},
    },
    {
        "name": "epic.patient_bundle.get",
        "input": {"patient_id": "string"},
        "output": {"type": "fhir_bundle"},
    },
    {
        "name": "epic.resource.get",
        "input": {"resource_type": "string", "id": "string"},
        "output": {"resource": "object"},
    },
    {
        "name": "epic.search",
        "input": {"resource_type": "string", "patient_id": "string"},
        "output": {"total": "number", "entry": "array"},
    },
    {
        "name": "epic.fhir_write_back.create",
        "input": {"resource_type": "string", "resource_json": "object"},
        "output": {"id": "string", "status": "string"},
    },
    {
        "name": "epic.inbasket.alert",
        "input": {"patient_id": "string", "subject": "string", "body": "string", "priority": "string"},
        "output": {"status": "string", "alert_id": "string"},
    },
    {
        "name": "auth.smart.token",
        "input": {"scope": "string"},
        "output": {"access_token": "string", "expires_in": "number", "scope": "string"},
    },
    {
        "name": "epic.audit.search",
        "input": {"actor_ref": "string", "entity_ref": "string", "action": "string"},
        "output": {"count": "number", "entries": "array"},
    },
]

FIXTURE_PATIENT_ID = "123"


def _write(obj: Dict[str, Any]):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _ok(id_, result):
    _write({"jsonrpc": "2.0", "id": id_, "result": result})


def _err(id_, code, message, data=None):
    _write({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message, "data": data}})


def list_tools():
    return {"tools": TOOLS}


def epic_discharge_event_get(params: Dict[str, Any]):
    patient_id = params.get("patient_id", FIXTURE_PATIENT_ID)
    return {
        "specversion": "1.0",
        "type": "epic.discharge.summary",
        "source": "mcp:epic.discharge_event",
        "id": "evt-" + str(int(time.time() * 1000)),
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "datacontenttype": "application/fhir+json",
        "subject": f"Patient/{patient_id}",
        "data": {
            "dischargeSummaryId": "DS-789",
            "patientId": patient_id,
            "encounterId": "ENC-456",
            "diagnoses": ["F33.1"],
            "followUpRecommended": True,
        },
    }


def epic_patient_bundle_get(params: Dict[str, Any]):
    patient_id = params.get("patient_id") or FIXTURE_PATIENT_ID
    # Even-numbered patient IDs return a denial object
    try:
        n = int(patient_id)
        if n % 2 == 0:
            return {
                "denied": True,
                "reason": "access_denied_by_policy",
                "patient_id": patient_id,
                "message": "Patient bundle access is denied for this patient in the mock."
            }
    except Exception:
        pass
    return fhir_bundle_for_patient(patient_id)


def epic_resource_get(params: Dict[str, Any]):
    rtype = params.get("resource_type")
    rid = params.get("id")
    store = {
        "Patient": patients,
        "Encounter": encounters,
        "CareTeam": care_teams,
        "CarePlan": care_plans,
        "MedicationRequest": medication_requests,
        "Observation": observations,
        "ServiceRequest": service_requests,
        "Consent": consents,
        "DocumentReference": document_references,
        "Practitioner": providers,
        "Organization": organizations,
        "Location": locations,
        "Task": {},
    }.get(rtype)
    if store is None:
        raise ValueError(f"Unsupported resource_type: {rtype}")
    res = store.get(rid)
    if not res:
        raise ValueError(f"Resource not found: {rtype}/{rid}")
    return {"resource": res}


def epic_search(params: Dict[str, Any]):
    rtype = params.get("resource_type")
    pid = params.get("patient_id") or FIXTURE_PATIENT_ID
    entries = []
    if rtype == "MedicationRequest":
        src = medication_requests.values()
    elif rtype == "Observation":
        src = observations.values()
    elif rtype == "ServiceRequest":
        src = service_requests.values()
    elif rtype == "CareTeam":
        src = care_teams.values()
    elif rtype == "CarePlan":
        src = care_plans.values()
    elif rtype == "Encounter":
        src = encounters.values()
    else:
        raise ValueError(f"Unsupported search resource_type: {rtype}")
    for res in src:
        subj = res.get("subject", {}).get("reference") or res.get("for", {}).get("reference")
        if subj == f"Patient/{pid}":
            entries.append({"resource": res})
    # If searching ServiceRequest and none found, synthesize a minimal referral
    if rtype == "ServiceRequest" and len(entries) == 0:
        try:
            n = int(pid)
            # Only synthesize for odd-numbered (share-allowed) demo patients
            if n % 2 == 1:
                sr_auto = {
                    "resourceType": "ServiceRequest",
                    "id": f"sr-auto-{pid}",
                    "status": "active",
                    "intent": "order",
                    "code": {"text": "Community mental health follow-up"},
                    "subject": {"reference": f"Patient/{pid}"},
                    "authoredOn": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "requester": {"reference": "Practitioner/prov-001"},
                    "performer": [{"reference": "Organization/org-001"}],
                }
                entries.append({"resource": sr_auto})
        except Exception:
            pass
    return {"total": len(entries), "entry": entries}


def epic_fhir_write_back_create(params: Dict[str, Any]):
    rid = "res-" + str(int(time.time() * 1000))
    # append audit entry with specified schema
    audit_events.append({
        "audit_id": f"aud-{rid}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor_ref": "Agent/demo-client",
        "action": "create",
        "entity_ref": f"{params.get('resource_type')}/{rid}",
        "outcome": "success",
        "source": "mcp-epic-mock",
    })
    return {"id": rid, "status": "created", "echo": params}


def epic_inbasket_alert(params: Dict[str, Any]):
    aid = "alert-" + str(int(time.time() * 1000))
    audit_events.append({
        "audit_id": f"aud-{aid}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor_ref": "Agent/demo-client",
        "action": "alert",
        "entity_ref": f"Patient/{params.get('patient_id','')}",
        "outcome": "sent",
        "source": "mcp-epic-mock",
    })
    return {"status": "sent", "alert_id": aid}


def auth_smart_token(params: Dict[str, Any]):
    scope = params.get("scope", "user/*.*")
    return {"access_token": "mock-token", "expires_in": 3600, "scope": scope}


def epic_audit_search(params: Dict[str, Any]):
    actor_ref = params.get("actor_ref")
    entity_ref = params.get("entity_ref")
    action = params.get("action")
    out = []
    for a in audit_events:
        if actor_ref and a.get("actor_ref") != actor_ref:
            continue
        if entity_ref and a.get("entity_ref") != entity_ref:
            continue
        if action and a.get("action") != action:
            continue
        out.append(a)
    return {"count": len(out), "entries": out}


METHODS = {
    "mcp.list_tools": lambda p: list_tools(),
    "epic.discharge_event.get": epic_discharge_event_get,
    "epic.patient_bundle.get": epic_patient_bundle_get,
    "epic.resource.get": epic_resource_get,
    "epic.search": epic_search,
    "epic.fhir_write_back.create": epic_fhir_write_back_create,
    "epic.inbasket.alert": epic_inbasket_alert,
    "auth.smart.token": auth_smart_token,
    "epic.audit.search": epic_audit_search,
}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            _write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error", "data": str(e)}})
            continue
        id_ = req.get("id")
        method = req.get("method")
        params = req.get("params", {})
        if method not in METHODS:
            _err(id_, -32601, f"Method not found: {method}")
            continue
        try:
            result = METHODS[method](params)
            _ok(id_, result)
        except Exception as e:
            _err(id_, -32000, "Server error", {"message": str(e)})


if __name__ == "__main__":
    main()
