from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import csv
import time
from typing import Optional, List
from .agentis_demo import run_demo as agentis_run_demo
from .agentis_demo import run_referral_demo as agentis_run_referral
from libs.agentis.tools.policy import check_consent
from libs.common.mcp_client import make_epic_client, make_hca_client

app = FastAPI(title="Ownership Trigger Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DischargeDemoResponse(BaseModel):
    discharge_event: dict
    patient_bundle: dict
    providers: dict


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/patients")
def list_patients():
    path = os.path.join(os.getcwd(), "data", "csv", "patient.csv")
    rows: List[dict] = []
    try:
        with open(path, newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append({
                    "patient_id": row.get("patient_id"),
                    "mrn": row.get("mrn"),
                    "ihi": row.get("ihi"),
                    "name": f"{row.get('given_name')} {row.get('family_name')}",
                })
    except FileNotFoundError:
        # fallback to demo single patient
        rows = [{"patient_id": "123", "mrn": "MRN-123-LOCAL", "ihi": "8003608166690503", "name": "Jane Doe"}]
    return {"count": len(rows), "patients": rows}


class DischargeRequest(BaseModel):
    patient_id: Optional[str] = None


@app.post("/demo/discharge", response_model=DischargeDemoResponse)
def demo_discharge(req: DischargeRequest):
    epic = make_epic_client()
    hca = make_hca_client()
    selected_patient = req.patient_id or "123"

    # Get mock discharge event and patient bundle
    evt = epic.call("epic.discharge_event.get", {})
    # Overwrite event subject/data to reflect selected patient (mock supports a single default)
    if isinstance(evt, dict):
        evt.setdefault("data", {})
        evt["subject"] = f"Patient/{selected_patient}"
        evt["data"]["patientId"] = selected_patient
    bundle = epic.call("epic.patient_bundle.get", {"patient_id": selected_patient})

    # Lookup providers (GP, Case Manager, Pharmacist) in postcode 2000
    providers = hca.call(
        "hca.directory.search_providers",
        {"patient_id": selected_patient, "location": "2000", "roles": ["GP", "Case Manager", "Pharmacist"], "consent_context": {}},
    )

    return {
        "discharge_event": evt,
        "patient_bundle": bundle,
        "providers": providers,
    }


class AgentisDemoRequest(BaseModel):
    patient_id: Optional[str] = None
    context: Optional[dict] = None


@app.post("/demo/agentis")
def demo_agentis(req: AgentisDemoRequest):
    pid = req.patient_id or "123"
    return agentis_run_demo(pid)


@app.post("/demo/agentis-referral")
def demo_agentis_referral(req: AgentisDemoRequest):
    pid = req.patient_id or "123"
    return agentis_run_referral(pid, extra_context=(req.context or {}))


class ConsentCheckRequest(BaseModel):
    patient_id: Optional[str] = None
    recipient_ref: str
    action: str
    purpose_of_use: str


@app.post("/demo/consent-check")
def demo_consent_check(req: ConsentCheckRequest):
    pid = req.patient_id or "123"
    patient_ref = f"Patient/{pid}"
    decision = check_consent(
        subject_ref=patient_ref,
        recipient_ref=req.recipient_ref,
        action=req.action,
        purpose_of_use=req.purpose_of_use,
    )
    # Expand response for UI readability
    allowed = []
    denied = []
    # Normalise decision into boolean when possible
    allow_truthy = decision is True or (isinstance(decision, str) and decision.lower() in ("allow", "allowed", "permit", "permitted", "yes", "true"))
    if allow_truthy:
        allowed = [req.recipient_ref]
    else:
        denied = [req.recipient_ref]
    return {
        "patient_ref": patient_ref,
        "recipient_ref": req.recipient_ref,
        "action": req.action,
        "purpose_of_use": req.purpose_of_use,
        "decision": decision,
        "allowed": allowed,
        "denied": denied,
        "restrictions": {},
    }


class AuditCheckResponse(BaseModel):
    write_back_id: str
    alert_id: str
    audit: dict


@app.post("/demo/audit-check", response_model=AuditCheckResponse)
def demo_audit_check():
    epic = make_epic_client()
    # Use fixed patient for demo
    patient_ref = "Patient/123"
    # 1) Create a simple Observation via FHIR write-back
    obs = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"text": "Demo write-back"},
        "subject": {"reference": patient_ref},
        "valueString": "hello",
    }
    wb = epic.call("epic.fhir_write_back.create", {"resource_type": "Observation", "resource_json": obs})
    # 2) Send an inbasket alert
    alert = epic.call("epic.inbasket.alert", {"patient_id": "123", "subject": "Demo Alert", "body": "Elevated risk flagged", "priority": "high"})
    # 3) Query audit trail
    audit = epic.call("epic.audit.search", {"actor_ref": "Agent/demo-client", "entity_ref": None, "action": None})
    return {"write_back_id": wb.get("id"), "alert_id": alert.get("alert_id"), "audit": audit}


class ReferralDemoResponse(BaseModel):
    referrals: dict
    created_task: dict


class ReferralRequest(BaseModel):
    patient_id: Optional[str] = None


@app.post("/demo/referral", response_model=ReferralDemoResponse)
def demo_referral(req: ReferralRequest):
    epic = make_epic_client()
    pid = req.patient_id or "123"
    # Search for ServiceRequest referrals for selected patient
    referrals = epic.call("epic.search", {"resource_type": "ServiceRequest", "patient_id": pid})
    created_task = {}
    if referrals.get("total", 0) > 0:
        first = referrals["entry"][0]["resource"]
        # Create a Task focused on the referral
        task_res = {
            "resourceType": "Task",
            "status": "requested",
            "intent": "order",
            "for": {"reference": f"Patient/{pid}"},
            "focus": {"reference": f"ServiceRequest/{first.get('id')}"},
            "owner": {"reference": "Practitioner/prov-002"},
            "description": "Follow up referral",
        }
        created_task = epic.call("epic.fhir_write_back.create", {"resource_type": "Task", "resource_json": task_res})
    return {"referrals": referrals, "created_task": created_task}


class UberRequest(BaseModel):
    patient_id: Optional[str] = None
    purpose: Optional[str] = None


@app.post("/demo/uber")
def demo_uber(req: UberRequest):
    pid = req.patient_id or "123"
    purpose = req.purpose or "discharge_transport"
    # Mock booking details
    ts = int(time.time())
    booking = {
        "id": f"UB{ts % 100000}",
        "service": "uber",
        "status": "confirmed",
        "eta_min": 7,
        "pickup": {"address": "Hospital Main Entrance"},
        "dropoff": {"address": "Home on file"},
        "driver": {"name": "Sam K", "rating": 4.9},
        "vehicle": {"make": "Toyota", "model": "Camry", "plate": "UBR-123"},
    }
    return {"patient_id": pid, "purpose": purpose, "booking": booking}
