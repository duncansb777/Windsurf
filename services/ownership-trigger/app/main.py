from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import csv
import time
import json
from typing import Optional, List
from .ccs_tools import ccs_get_meter_reads
from .agentis_demo import run_demo as agentis_run_demo
from .agentis_demo import run_referral_demo as agentis_run_referral
from libs.agentis.tools.policy import check_consent
from libs.agentis.llm_client import LLMClient
from libs.common.mcp_client import make_epic_client, make_hca_client, make_coo_client

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


@app.get("/llm-info")
def llm_info():
    client = LLMClient()
    return {
        "provider": client.provider,
        "model": client.model,
        "is_mock": client.provider == "mock",
    }


# Resolve project root (one level above 'services') so CSV/context paths are correct
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


@app.get("/patients")
def list_patients():
    path = os.path.join(BASE_DIR, "data", "csv", "patient.csv")
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
    except Exception:
        # any other error: still provide a fallback to avoid UI failure
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


class HdStepRequest(BaseModel):
    step_id: str
    patient_id: Optional[str] = None
    encounter_id: Optional[str] = None
    patient: dict = {}
    risk: dict = {}
    prompt_pack: dict = {}
    agent: Optional[str] = None


def _run_hd_step(req: HdStepRequest, step: str) -> dict:
    """Execute a Hospital Discharge step via the configured LLM provider.

    The frontend passes patient + risk context and the active Prompt Studio
    instructions/policies. We turn that into a step-specific system/user
    prompt and ask the LLM to return structured JSON.
    """

    client = LLMClient()
    pp = req.prompt_pack or {}
    instructions = pp.get("instructions", "")
    policies = pp.get("policies_markdown", "")

    # Pull additional clinical context from MCP mocks so each step sees
    # realistic EMR-style data in addition to the UI payload.
    epic = make_epic_client()
    hca = make_hca_client()
    pid = req.patient_id or "123"

    mcp_context: dict = {"patient_id": pid, "step_id": step}

    try:
        # Shared baseline: discharge event + patient bundle
        mcp_context["discharge_event"] = epic.call("epic.discharge_event.get", {"patient_id": pid})
        mcp_context["patient_bundle"] = epic.call("epic.patient_bundle.get", {"patient_id": pid})
    except Exception:
        # Keep context best-effort; UI should still work if MCP mock is offline
        pass

    try:
        # Step-specific mock MCP data
        if step == "step2":  # medication reconciliation
            mcp_context["home_meds"] = epic.call("epic.search", {"resource_type": "MedicationRequest", "patient_id": pid})
        elif step == "step3":  # follow-up orchestration
            mcp_context["followup_observations"] = epic.call("epic.search", {"resource_type": "Observation", "patient_id": pid})
        elif step == "step4":  # GP & community handoff
            mcp_context["service_requests"] = epic.call("epic.search", {"resource_type": "ServiceRequest", "patient_id": pid})
        elif step == "step5":  # post-discharge monitoring
            mcp_context["care_plans"] = epic.call("epic.search", {"resource_type": "CarePlan", "patient_id": pid})
        elif step == "step6":  # outcomes / governance
            # For demo purposes, reuse audit search as a governance signal
            mcp_context["audit"] = epic.call(
                "epic.audit.search",
                {"actor_ref": "Agent/demo-client", "entity_ref": None, "action": None},
            )
    except Exception:
        pass

    try:
        # For some steps (handoff/referral), also show directory context from HCA MCP
        if step in {"step3", "step4"}:
            mcp_context["providers"] = hca.call(
                "hca.directory.search_providers",
                {"patient_id": pid, "location": "2000", "roles": ["GP", "Case Manager", "Pharmacist"], "consent_context": {}},
            )
    except Exception:
        pass

    # Build a compact context block for the user message
    ctx = {
        "step_id": step,
        "agent": req.agent,
        "patient_id": req.patient_id,
        "encounter_id": req.encounter_id,
        "patient": req.patient,
        "risk": req.risk,
        "mcp_context": mcp_context,
    }

    system = (
        "You are a Hospital Discharge agent executing step "
        f"{step}. Use the provided Prompt Studio instructions and "
        "policies as guardrails. Return STRICT JSON only, matching the "
        "schema for this step. Include an array field 'llm_reasoning' "
        "with short bullet-point explanations of the decision.\n\n"
        "INSTRUCTIONS:\n" + instructions + "\n\nPOLICIES:\n" + policies
    )

    user = (
        "Here is the context for this discharge step as JSON. "
        "Decide and populate the JSON result for this step. "
        "Do not include any text outside the JSON object.\n\n" +
        json.dumps(ctx, indent=2)
    )

    # Step 3 (follow-up orchestration) uses a structured JSON schema so we
    # can both display the plan and execute it via Epic MCP tools.
    if step == "step3":
        followup_schema = {
            "type": "object",
            "properties": {
                "required_followups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "reason": {"type": "string"},
                            "recommended_timeframe": {"type": "string"},
                            "status": {"type": "string"},  # e.g. ALREADY_SCHEDULED or MISSING
                            "channel": {"type": "string"},
                            "priority": {"type": "string"},
                        },
                        "required": ["type", "recommended_timeframe", "status"],
                        "additionalProperties": True,
                    },
                },
                "llm_reasoning": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["required_followups"],
            "additionalProperties": True,
        }

        out = client.complete(system=system, user=user, tools=None, schema=followup_schema)
        plan = out.get("json") or {}
        if not plan:
            # Fallback if schema-based parsing failed
            plan = {"raw_text": out.get("text", ""), "model": out.get("model")}

        required_followups = plan.get("required_followups") or []
        executed: dict = {"tasks": []}

        # For any follow-ups the LLM marks as MISSING, create a Task via Epic MCP
        for fup in required_followups:
            if str(fup.get("status", "")).upper() != "MISSING":
                continue
            desc = fup.get("reason") or f"Follow-up: {fup.get('type','appointment')}"
            task_res = epic.call(
                "epic.fhir_write_back.create",
                {
                    "resource_type": "Task",
                    "resource_json": {
                        "resourceType": "Task",
                        "status": "requested",
                        "intent": "order",
                        "for": {"reference": f"Patient/{pid}"},
                        "description": desc,
                    },
                },
            )
            executed["tasks"].append({"input": fup, "result": task_res})

        data: dict = {
            "patient_id": req.patient_id or pid,
            "agent": req.agent or "followup_orchestration",
            "required_followups": required_followups,
            "executed": executed,
            "llm_reasoning": plan.get("llm_reasoning")
            or [
                "Follow-up requirements were derived from discharge, risk, and MCP context.",
                "Missing follow-ups were converted into Task create operations via Epic MCP.",
            ],
            "plan_raw": plan,
        }
        return data

    # Default behaviour for other steps: free-form JSON response
    out = client.complete(system=system, user=user, tools=None, schema=None)
    data = out.get("json") or {}
    if not data:
        data = {"raw_text": out.get("text", ""), "model": out.get("model")}

    if "llm_reasoning" not in data:
        data["llm_reasoning"] = [
            f"LLM decision for {step} based on provided discharge, risk, and policy context."
        ]
    data.setdefault("patient_id", req.patient_id)
    data.setdefault("agent", req.agent or f"hd_{step}")
    return data


@app.post("/demo/hd-step1")
def demo_hd_step1(req: HdStepRequest):
    return _run_hd_step(req, "step1")


@app.post("/demo/hd-step2")
def demo_hd_step2(req: HdStepRequest):
    return _run_hd_step(req, "step2")


@app.post("/demo/hd-step3")
def demo_hd_step3(req: HdStepRequest):
    return _run_hd_step(req, "step3")


@app.post("/demo/hd-step4")
def demo_hd_step4(req: HdStepRequest):
    return _run_hd_step(req, "step4")


@app.post("/demo/hd-step5")
def demo_hd_step5(req: HdStepRequest):
    return _run_hd_step(req, "step5")


@app.post("/demo/hd-step6")
def demo_hd_step6(req: HdStepRequest):
    return _run_hd_step(req, "step6")


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


# ======================
# CCS MCP Tools (CCS API)
# ======================
class MeterReadsRequest(BaseModel):
    nmi: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    user: Optional[str] = None
    purpose_of_use: Optional[str] = None


class MeterRead(BaseModel):
    read_type: str
    date: str
    value: float


class MeterReadsResponse(BaseModel):
    reads: List[MeterRead]


@app.post("/ccs/get-meter-reads", response_model=MeterReadsResponse)
def api_ccs_get_meter_reads(req: MeterReadsRequest):
    """MCP tool endpoint: Retrieve meter reads for a given NMI/date range.
    SACSF controls enforced by ccs_tools module (AC-1, AC-3, LG-1).
    """
    out = ccs_get_meter_reads(
        nmi=req.nmi,
        from_date=req.from_date,
        to_date=req.to_date,
        user=req.user,
        purpose_of_use=req.purpose_of_use,
    )
    return out


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


# ======================
# Context management (for Prompt Studio UI)
# ======================
from fastapi import HTTPException, UploadFile, File

# Resolve context folder relative to project root, not cwd, so it works
# when the service is started from different environments (desktop app, uvicorn, etc.).
CONTEXT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "context"))
ALLOWED_SUBDIRS = {"specs", "architecture", "integrations", "constraints"}


def _safe_context_path(subpath: str) -> str:
    # Normalise and restrict to CONTEXT_ROOT and allowed subdirs
    full = os.path.abspath(os.path.join(CONTEXT_ROOT, subpath))
    if not full.startswith(CONTEXT_ROOT + os.sep):
        raise HTTPException(status_code=400, detail="Invalid path")
    # Ensure first segment is allowed
    parts = os.path.relpath(full, CONTEXT_ROOT).split(os.sep)
    if not parts or parts[0] not in ALLOWED_SUBDIRS:
        raise HTTPException(status_code=400, detail="Path not allowed")
    return full


class ContextAddRequest(BaseModel):
    path: str  # e.g., specs/new_spec.md
    content: str


@app.get("/context/list")
def context_list():
    items = []
    if not os.path.isdir(CONTEXT_ROOT):
        return {"items": items}
    for root, _, files in os.walk(CONTEXT_ROOT):
        rel_root = os.path.relpath(root, CONTEXT_ROOT)
        # skip root files; show only allowed subdirs
        if rel_root == ".":
            continue
        top = rel_root.split(os.sep)[0]
        if top not in ALLOWED_SUBDIRS:
            continue
        for f in files:
            p_rel = os.path.join(rel_root, f)
            p_abs = os.path.join(root, f)
            try:
                with open(p_abs, "r", encoding="utf-8", errors="ignore") as fh:
                    sample = fh.read(4000)
            except Exception:
                sample = ""
            items.append({"path": p_rel.replace("\\", "/"), "sample": sample})
    return {"items": items}


@app.get("/context/file")
def context_file(path: str):
    full = _safe_context_path(path)
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        with open(full, "r", encoding="utf-8", errors="ignore") as fh:
            return {"path": path, "content": fh.read()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ======================
# CoO / Billing MCP wrappers (for Billing screen in app)
# ======================


class CoOFlowResponse(BaseModel):
    tool: str
    arguments: dict
    output: dict


def _coo_call(method: str, params: dict | None = None) -> CoOFlowResponse:
    client = make_coo_client()
    res = client.call(method, params or {})
    # Normalise into a simple pydantic model
    return CoOFlowResponse(
        tool=res.get("tool", method),
        arguments=res.get("arguments", {}),
        output=res.get("output", {}),
    )


@app.post("/coo/address-standardize", response_model=CoOFlowResponse)
def coo_address_standardize_http():
    return _coo_call("coo.address-standardize")


@app.post("/coo/ownership", response_model=CoOFlowResponse)
def coo_ownership_http():
    return _coo_call("coo.ownership")


@app.post("/coo/ownership-deterministic", response_model=CoOFlowResponse)
def coo_ownership_deterministic_http():
    return _coo_call("coo.ownership-deterministic")


@app.post("/coo/special-read", response_model=CoOFlowResponse)
def coo_special_read_http():
    return _coo_call("coo.special-read")


@app.post("/coo/bill-transfer", response_model=CoOFlowResponse)
def coo_bill_transfer_http():
    return _coo_call("coo.bill-transfer")


@app.post("/coo/reset", response_model=CoOFlowResponse)
def coo_reset_http():
    return _coo_call("coo.reset")


@app.post("/context/add")
def context_add(req: ContextAddRequest):
    full = _safe_context_path(req.path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(req.content or "")
        return {"ok": True, "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ======================
# Meter Read CSV ingest (demo)
# ======================
@app.get("/ccs/meter-reads/sample")
def ccs_meter_reads_sample():
    sample = (
        "nmi,date,read_type,value\n"
        "70011233,2025-10-01,ACTUAL,1234\n"
        "70011233,2025-11-01,ESTIMATE,1270\n"
        "70011999,2025-10-15,ACTUAL,4312\n"
    )
    return {"filename": "meter_reads_sample.csv", "content": sample}


@app.post("/ccs/meter-reads/upload")
def ccs_meter_reads_upload(file: UploadFile = File(...)):
    try:
        content = file.file.read().decode("utf-8", errors="ignore")
        rdr = csv.DictReader(content.splitlines())
        required = {"nmi", "date", "read_type", "value"}
        if not required.issubset(set([c.strip() for c in rdr.fieldnames or []])):
            raise HTTPException(status_code=400, detail="Invalid columns; expected nmi,date,read_type,value")
        rows = list(rdr)
        per_nmi = {}
        for r in rows:
            nmi = r.get("nmi", "").strip()
            per_nmi.setdefault(nmi, 0)
            per_nmi[nmi] += 1
        return {"ok": True, "total": len(rows), "by_nmi": per_nmi}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
