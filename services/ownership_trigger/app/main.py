from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import csv
import time
import json
import random
from typing import Optional, List
from ccs_tools import ccs_get_meter_reads
from agentis_demo import run_demo as agentis_run_demo
from agentis_demo import run_referral_demo as agentis_run_referral
from libs.agentis.tools.policy import check_consent
from libs.agentis.llm_client import LLMClient
from libs.common.mcp_client import make_epic_client, make_hca_client, make_coo_client, make_maps_client

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


class SlotRequest(BaseModel):
    patient_id: str
    appointment_type: str
    date: str  # ISO local date, e.g. "2025-11-30"
    timezone: Optional[str] = "Australia/Sydney"


@app.post("/demo/followups/slots")
def followup_slots(req: SlotRequest):
    """Return a grid of 15-minute working-day slots with some randomly marked
    busy for demo purposes.

    This endpoint does not consult real provider calendars; it simply
    synthesises availability so the UI can render realistic-looking calendars
    with a mix of free and busy times.
    """

    from datetime import datetime, time as dtime, timedelta

    # Working day 09:00–17:00 local; 15-minute slots.
    try:
        day = datetime.fromisoformat(req.date)
    except Exception:
        # Fallback to today if the date is invalid
        day = datetime.now()

    start_dt = datetime.combine(day.date(), dtime(hour=9, minute=0))
    end_dt = datetime.combine(day.date(), dtime(hour=17, minute=0))
    slot_len = timedelta(minutes=15)

    slots = []
    cur = start_dt
    # Simple pseudo-random seed based on patient + type + provider + date so
    # the pattern is stable per patient/provider/day but different across
    # combinations.
    prov = getattr(req, "provider_id", None) or ""
    seed_str = f"{req.patient_id}-{req.appointment_type}-{prov}-{req.date}"
    rnd = random.Random(seed_str)

    while cur < end_dt:
        nxt = cur + slot_len
        # Roughly 30–40% of slots marked busy.
        busy = rnd.random() < 0.35
        slots.append({
            "start": cur.isoformat(),
            "end": nxt.isoformat(),
            "busy": busy,
        })
        cur = nxt

    return {"slots": slots}


class BookingItem(BaseModel):
    type: str
    datetime: str
    provider_id: Optional[str] = None
    reason: Optional[str] = None


class BookingRequest(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    bookings: list[BookingItem]


@app.post("/demo/followups/book")
def followup_book(req: BookingRequest):
    """Create EMR-level follow-up appointments for the supplied bookings.

    This endpoint is designed to be called by a generic appointment execution
    agent or the UI after a human has selected concrete date/times for the
    required follow-ups.
    """

    pid = req.patient_id
    enc_id = req.encounter_id or f"ENC{str(pid)[1:]}"

    appt_csv_path = os.path.join(BASE_DIR, "data", "csv", "FOLLOW_UP_APPOINTMENTS.csv")

    # Ensure CSV exists with header
    if not os.path.exists(appt_csv_path):
        with open(appt_csv_path, "w", newline="") as fcsv:
            w = csv.writer(fcsv)
            w.writerow([
                "APPOINTMENT_ID",
                "PATIENT_ID",
                "ENCOUNTER_ID",
                "TYPE",
                "PROVIDER_ID",
                "DATE_TIME",
                "STATUS",
            ])

    # Load existing rows to avoid naive duplicates for same patient/type/datetime
    existing = set()
    try:
        with open(appt_csv_path, newline="") as fcsv:
            rdr = csv.DictReader(fcsv)
            for row in rdr:
                if row.get("PATIENT_ID") == pid:
                    key = (row.get("TYPE") or "", row.get("DATE_TIME") or "")
                    existing.add(key)
    except Exception:
        pass

    epic = make_epic_client()

    created: list[dict] = []

    with open(appt_csv_path, "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        for item in req.bookings:
            t = item.type or "appointment"
            dt_str = item.datetime
            prov_id = item.provider_id or ""
            key = (t, dt_str)

            status = "SCHEDULED"
            already = key in existing

            if not already:
                appt_id = f"FU-{pid}-{int(time.time())}-{len(created)}"
                w.writerow([
                    appt_id,
                    pid,
                    enc_id,
                    t,
                    prov_id,
                    dt_str,
                    status,
                ])
                existing.add(key)
            else:
                appt_id = None

            # Optionally create a Task in Epic to mirror the booking
            task_id = None
            try:
                desc = item.reason or f"Follow-up: {t}"
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
                if isinstance(task_res, dict) and task_res.get("id"):
                    task_id = task_res["id"]
            except Exception:
                pass

            created.append(
                {
                    "type": t,
                    "datetime": dt_str,
                    "provider_id": prov_id,
                    "status": "CREATED" if not already else "ALREADY_SCHEDULED",
                    "appointment_id": appt_id,
                    "task_id": task_id,
                    "reason": item.reason,
                }
            )

    # Simple narrative summary for UI consumption
    created_count = sum(1 for a in created if a["status"] == "CREATED")
    already_count = sum(1 for a in created if a["status"] == "ALREADY_SCHEDULED")
    summary = (
        f"Created {created_count} new follow-up appointment(s) and "
        f"found {already_count} existing appointment(s) for patient {pid}."
    )

    return {"appointments": created, "summary_text": summary}


class PromptPack(BaseModel):
    name: str
    domain: Optional[str] = None
    instructions: Optional[str] = None
    policies_markdown: Optional[str] = None


class PromptPackRegisterRequest(BaseModel):
    packs: List[PromptPack]


@app.post("/prompt-packs/register")
def register_prompt_packs(req: PromptPackRegisterRequest):
    """Register/push prompt packs from the UI to the backend.

    For now this endpoint simply acknowledges receipt so that the
    front-end can explicitly "push" all prompt packs to the live LLM
    configuration layer without changing runtime behaviour.
    """
    ts = int(time.time())
    return {
        "received": len(req.packs),
        "timestamp": ts,
        "pack_names": [p.name for p in req.packs],
    }


class HdStepRequest(BaseModel):
    step_id: str
    patient_id: Optional[str] = None
    encounter_id: Optional[str] = None
    patient: dict = {}
    risk: dict = {}
    prompt_pack: dict = {}
    agent: Optional[str] = None
    # Optional addresses for transport / mapping steps (e.g. step7)
    hospital_address: Optional[str] = None
    hotel_address: Optional[str] = None


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

    # Also surface core EMR CSV slices so every step can see the same
    # underlying mock EMR snapshot for the selected patient. In addition to a
    # fixed set of core files, we attach any other CSVs that contain a
    # PATIENT_ID column so the LLM can see as much EMR context as possible.
    try:
        csv_ctx: dict = {}
        csv_dir = os.path.join(BASE_DIR, "data", "csv")

        def _load_csv(name: str, patient_key: str = "PATIENT_ID") -> list[dict]:
            rows: list[dict] = []
            path = os.path.join(csv_dir, name)
            if not os.path.exists(path):
                return rows
            fieldnames = None
            with open(path, newline="") as f:
                rdr = csv.DictReader(f)
                fieldnames = rdr.fieldnames or []
                if patient_key not in (fieldnames or []):
                    # This CSV does not contain per-patient rows keyed by the
                    # requested patient_key; skip it for patient-scoped views.
                    return []
                for r in rdr:
                    if r.get(patient_key) == pid:
                        rows.append(r)
            # If there is no real row for this patient, synthesise a stub so
            # that all patients have at least one entry per core CSV.
            if not rows and fieldnames:
                stub = {k: "" for k in fieldnames}
                stub[patient_key] = pid
                rows.append(stub)
            return rows

        csv_ctx["gp_information"] = _load_csv("EHR_GP_INFORMATION.csv")
        csv_ctx["discharge_meds"] = _load_csv("EMR_DISCHARGE_MEDICATIONS.csv")
        csv_ctx["inpatient_meds"] = _load_csv("EMR_MEDICATIONS.csv")
        csv_ctx["home_meds"] = _load_csv("EMR_HOME_MEDICATIONS.csv")
        csv_ctx["diagnosis"] = _load_csv("EMR_DIAGNOSIS.csv")
        csv_ctx["admission_encounter"] = _load_csv("PAS_ADMISSION_ENCOUNTER.csv")
        csv_ctx["risk_hospital"] = _load_csv("RISK_SCORE_HOSPITAL.csv")
        csv_ctx["risk_lace_plus"] = _load_csv("RISK_SCORE_LACE_PLUS.csv")
        csv_ctx["demographics"] = _load_csv("EMR_PATIENT_DEMOGRAPHICS.csv")

        # Attach any other CSVs that expose PATIENT_ID but are not already
        # mapped above, so the LLM can use them if relevant. Keys are the
        # lowercase filename without extension.
        try:
            existing_keys = set(csv_ctx.keys())
            for fname in os.listdir(csv_dir):
                if not fname.lower().endswith(".csv"):
                    continue
                base = os.path.splitext(fname)[0]
                key = base.lower()
                if key in existing_keys:
                    continue
                extra_rows = _load_csv(fname, patient_key="PATIENT_ID")
                if extra_rows:
                    csv_ctx[key] = extra_rows
        except Exception:
            # Best-effort only for additional CSVs
            pass

        mcp_context["csv"] = csv_ctx
    except Exception:
        # Best-effort only; if any CSVs are missing the step still runs on MCP mocks
        pass

    try:
        # Step-specific mock MCP data
        if step == "step2":  # medication reconciliation
            mcp_context["home_meds"] = epic.call("epic.search", {"resource_type": "MedicationRequest", "patient_id": pid})
            # Also surface CSV-backed meds so the LLM always sees medications
            # for demo patients like P0001/2/5 even if the Epic fixtures differ.
            try:
                meds_path = os.path.join(BASE_DIR, "data", "csv", "EMR_Medications.csv")
                rows: list[dict] = []
                with open(meds_path, newline="") as f:
                    rdr = csv.DictReader(f)
                    for r in rdr:
                        if r.get("PATIENT_ID") == pid:
                            rows.append(r)
                mcp_context["home_meds_csv"] = rows
            except Exception:
                # Best-effort: if CSV missing or unreadable, continue with mock data only
                pass
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

    # Step 1 (discharge readiness & risk) uses a structured JSON schema so we
    # get a predictable risk band, discharge bundle, and reasoning.
    if step == "step1":
        readiness_schema = {
            "type": "object",
            "properties": {
                "patient_id": {"type": ["string", "null"]},
                "agent": {"type": ["string", "null"]},
                "overall_risk_band": {"type": "string"},
                "recommended_bundle": {"type": "string"},
                "risk_factors": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "flags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "llm_reasoning": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["overall_risk_band"],
            "additionalProperties": True,
        }

        out = client.complete(system=system, user=user, tools=None, schema=readiness_schema)
        body = out.get("json") or {}
        if not body:
            body = {"raw_text": out.get("text", ""), "model": out.get("model")}

        # Derive summary fields from nested risk_assessment if the model did not
        # populate overall_risk_band / recommended_bundle at the top level. This
        # lets us reuse existing prompt packs while still surfacing concise
        # risk outputs to the UI.
        overall_band = body.get("overall_risk_band") or ctx["risk"].get("overall_risk_band") or ctx["risk"].get("lace_plus_risk_level")
        if not overall_band:
            try:
                ra = body.get("risk_assessment") or {}
                lace = (ra.get("lace_plus_score") or {}).get("risk_level")
                hosp = (ra.get("hospital_score") or {}).get("risk_level")
                overall_band = lace or hosp or None
            except Exception:
                overall_band = None

        recommended_bundle = body.get("recommended_bundle")
        if recommended_bundle is None:
            # Fall back to a simple bundle label based on the derived risk band.
            band_upper = (overall_band or "").upper()
            if band_upper == "HIGH":
                recommended_bundle = "High-intensity discharge bundle"
            elif band_upper in {"INTERMEDIATE", "MEDIUM"}:
                recommended_bundle = "Standard discharge bundle"
            elif band_upper == "LOW":
                recommended_bundle = "Light-touch discharge bundle"

        data: dict = {
            "patient_id": req.patient_id or pid,
            "agent": req.agent or "discharge_readiness_risk",
            "overall_risk_band": overall_band,
            "recommended_bundle": recommended_bundle,
            "risk_factors": body.get("risk_factors") or [],
            "flags": body.get("flags") or [],
            "llm_reasoning": body.get("llm_reasoning")
            or [
                f"LLM classified discharge readiness risk as {overall_band or 'UNKNOWN'} based on LACE+, HOSPITAL, and policy context.",
            ],
            "plan_raw": body,
        }
        return data

    # Step 2 (medication reconciliation) uses a structured JSON schema focused
    # on continued/started/stopped medicines and key counselling points.
    if step == "step2":
        med_schema = {
            "type": "object",
            "properties": {
                "patient_id": {"type": ["string", "null"]},
                "agent": {"type": ["string", "null"]},
                "reconciliation": {
                    "type": "object",
                    "properties": {
                        "continued": {"type": "array", "items": {"type": "object"}},
                        "started": {"type": "array", "items": {"type": "object"}},
                        "stopped": {"type": "array", "items": {"type": "object"}},
                        "education_points": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["continued", "started", "stopped"],
                    "additionalProperties": True,
                },
                "llm_reasoning": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["reconciliation"],
            "additionalProperties": True,
        }

        out = client.complete(system=system, user=user, tools=None, schema=med_schema)
        body = out.get("json") or {}
        if not body:
            body = {"raw_text": out.get("text", ""), "model": out.get("model")}

        recon = body.get("reconciliation") or {}

        # Education points may be suggested by the LLM; we always derive the
        # structural reconciliation (continued/started/stopped) from EMR CSVs
        # so the EMR is the single source of truth for medication changes.
        edu = recon.get("education_points") or []

        # Capture any simple natural-language descriptions the LLM may have
        # attached to its own reconciliation lists so we can merge them back
        # onto the EMR-derived meds by name. This lets policies like
        # "Provide a simple description of the medication they are taking in
        # the natural language output" take effect without ceding structural
        # control of the list to the LLM.
        desc_by_name: dict[str, str] = {}
        try:
            def _extract_desc_map(items: list[dict] | None) -> None:
                if not items:
                    return
                for m in items:
                    if not isinstance(m, dict):
                        continue
                    n = (
                        m.get("medication_name")
                        or m.get("name")
                        or m.get("MEDICATION_NAME")
                        or m.get("MED_NAME")
                        or ""
                    ).strip().lower()
                    if not n:
                        continue
                    desc = (
                        m.get("simple_description")
                        or m.get("description")
                        or m.get("nl_description")
                    )
                    if desc and n not in desc_by_name:
                        desc_by_name[n] = str(desc)

            _extract_desc_map(recon.get("continued"))
            _extract_desc_map(recon.get("started"))
            _extract_desc_map(recon.get("stopped"))
        except Exception:
            desc_by_name = {}

        try:
            csv_ctx = mcp_context.get("csv", {}) if isinstance(mcp_context, dict) else {}
            home_rows = csv_ctx.get("home_meds") or []
            inpatient_rows = csv_ctx.get("inpatient_meds") or []
            discharge_rows = csv_ctx.get("discharge_meds") or []

            def _med_from_row(r: dict, source: str) -> dict:
                name_val = r.get("MEDICATION_NAME") or r.get("MED_NAME") or "Medication"
                med: dict = {
                    "source": source,
                    "medication_name": name_val,
                    "dose": r.get("DOSE") or r.get("STRENGTH") or "",
                    "route": r.get("ROUTE") or "",
                    "frequency": r.get("FREQUENCY") or "",
                    "status": r.get("STATUS") or "ACTIVE",
                }
                # If the LLM provided a simple description for this med name,
                # attach it so the frontend can surface it in the narrative.
                try:
                    key = (name_val or "").strip().lower()
                    if key and desc_by_name.get(key):
                        med["simple_description"] = desc_by_name[key]
                except Exception:
                    pass
                return med

            def _key(r: dict) -> str:
                # Use a simple case-insensitive name key for grouping
                return (r.get("MEDICATION_NAME") or r.get("MED_NAME") or "").strip().lower()

            home_by_name = {_key(r): r for r in home_rows if _key(r)}
            discharge_by_name = {_key(r): r for r in discharge_rows if _key(r)}

            # Continued: appears in both home and discharge
            cont = []
            for name, row in home_by_name.items():
                if name in discharge_by_name:
                    cont.append(_med_from_row(discharge_by_name[name], "discharge"))

            # Started: in discharge but not in home
            started = []
            for name, row in discharge_by_name.items():
                if name not in home_by_name:
                    started.append(_med_from_row(row, "discharge"))

            # Stopped: in home but not on discharge
            stopped = []
            for name, row in home_by_name.items():
                if name not in discharge_by_name:
                    stopped.append(_med_from_row(row, "home"))

            # If there are no discharge rows at all, treat home meds as
            # continued so the demo still shows something sensible.
            if not discharge_rows and home_rows and not cont and not started and not stopped:
                cont = [_med_from_row(r, "home") for r in home_rows]

            # Add a generic education point for any high-risk-looking meds if the
            # LLM did not already specify any.
            base_rows = discharge_rows or home_rows or inpatient_rows
            if base_rows and not edu:
                names = " ".join([r.get("MEDICATION_NAME", "") for r in base_rows]).lower()
                if any(k in names for k in ["insulin", "prednisolone", "warfarin", "opioid", "morphine"]):
                    edu = [
                        "Reinforce sick-day rules and hypoglycaemia/side-effect monitoring for high-risk medicines.",
                    ]
        except Exception:
            # If CSV context is unavailable, fall back to whatever the LLM
            # provided for the structural reconciliation lists.
            cont = recon.get("continued") or []
            started = recon.get("started") or []
            stopped = recon.get("stopped") or []

        data = {
            "patient_id": req.patient_id or pid,
            "agent": req.agent or "medication_reconciliation",
            "reconciliation": {
                "continued": cont,
                "started": started,
                "stopped": stopped,
                "education_points": edu,
            },
            "llm_reasoning": body.get("llm_reasoning")
            or [
                "Medication reconciliation decisions were derived from home meds, in-hospital orders, discharge plan, and risk context.",
            ],
            "plan_raw": body,
        }
        return data

    # Step 3 (follow-up orchestration) uses a structured JSON schema so we
    # can both display the plan and execute it via Epic MCP tools.
    if step == "step3":
        # Strengthen instructions for safety-planned mental health follow-up.
        system = (
            system
            + "\n\nFor this follow-up orchestration step, you MUST:\n"
            "- Inspect risk, diagnosis, observation, and CSV context for suicidal ideation or mental health risk.\n"
            "- Ensure that at least one mental-health follow-up appointment exists (e.g., community mental health).\n"
            "- If no such appointment is already scheduled, schedule a follow-up (for example 'Community mental health follow-up') and represent it as an ALREADY_SCHEDULED appointment with appropriate details (type, timeframe, channel, reason).\n"
            "- Reflect whether the patient's safety plan is completed via 'safety_plan_status'.\n"
        )

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
                "safety_plan_status": {
                    "type": ["string", "null"],
                },
                "mental_health_followup_required": {
                    "type": ["boolean", "null"],
                },
                "mental_health_followup_scheduled": {
                    "type": ["boolean", "null"],
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

        # Helper to synthesise a concrete appointment date/time from a
        # free-text timeframe (e.g. "within 3-5 days", "within 1 week"). This
        # is only used for demo purposes when no real slot exists in the CSV.
        def _approx_appointment_datetime(timeframe: str | None) -> str | None:
            try:
                import re
                from datetime import datetime, timedelta, timezone

                if not timeframe:
                    days = 7
                else:
                    tf = str(timeframe).lower()
                    # First numeric token (handles ranges like "3-5" by
                    # taking the lower bound).
                    m = re.search(r"(\d+)", tf)
                    if m:
                        days = int(m.group(1))
                    elif "fortnight" in tf:
                        days = 14
                    elif "week" in tf:
                        days = 7
                    elif "month" in tf:
                        days = 30
                    else:
                        days = 7

                now = datetime.now(timezone.utc)
                dt = now + timedelta(days=days)
                # Return ISO8601 with UTC offset so the UI can format it for
                # the local display timezone.
                return dt.isoformat()
            except Exception:
                return None

        # Enrich follow-ups using existing scheduled appointments from CSV so
        # that ONLY truly scheduled appointments are marked as ALREADY_SCHEDULED
        # and carry a real appointment date/time.
        try:
            csv_dir = os.path.join(BASE_DIR, "data", "csv")
            appt_path = os.path.join(csv_dir, "FOLLOW_UP_APPOINTMENTS.csv")
            existing_by_type: dict[str, dict] = {}
            if os.path.exists(appt_path):
                with open(appt_path, newline="") as f:
                    rdr = csv.DictReader(f)
                    for row in rdr:
                        if not row.get("PATIENT_ID") or row.get("PATIENT_ID") != pid:
                            continue
                        if (row.get("STATUS") or "").upper() != "SCHEDULED":
                            continue
                        tkey = (row.get("TYPE") or "").strip().lower()
                        if not tkey:
                            continue
                        # If multiple rows share a type, keep the first for now.
                        existing_by_type.setdefault(tkey, row)

            # Attach concrete appointment info to matching follow-ups.
            for fup in required_followups:
                tkey = (str(fup.get("type")) or "").strip().lower()
                if not tkey or tkey not in existing_by_type:
                    continue
                row = existing_by_type[tkey]
                try:
                    fup["status"] = "ALREADY_SCHEDULED"
                    if row.get("DATE_TIME"):
                        fup["appointment_date_time"] = row["DATE_TIME"]
                    if row.get("APPOINTMENT_ID"):
                        fup["appointment_id"] = row["APPOINTMENT_ID"]
                    if row.get("PROVIDER_ID"):
                        fup["provider_id"] = row["PROVIDER_ID"]
                except Exception:
                    # Enrichment is best-effort; do not fail the whole step.
                    pass
        except Exception:
            # If CSV context is unavailable, fall back to LLM-only planning.
            pass

        # Normalise statuses: if anything is still labelled ALREADY_SCHEDULED
        # but has neither a concrete appointment_date_time (from CSV) nor a
        # Task backing it, treat it as MISSING so that only real bookings or
        # explicit Task creations appear as scheduled in the plan.
        for fup in required_followups:
            try:
                st = str(fup.get("status", "")).upper()
                has_dt = bool(fup.get("appointment_date_time"))
                has_task = bool(fup.get("task_id"))
                if st == "ALREADY_SCHEDULED" and not has_dt and not has_task:
                    fup["status"] = "MISSING"
            except Exception:
                continue

        # For any follow-ups that remain MISSING after normalisation (i.e. they
        # are required by the LLM but not present in FOLLOW_UP_APPOINTMENTS),
        # create a Task via Epic MCP so every required booking is acted on.
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

            # Reflect execution back into the follow-up object so the JSON and
            # UI can treat it as created/requested via Task for this run. CSV-
            # backed appointments remain ALREADY_SCHEDULED; Task-created ones
            # are marked as CREATED so downstream views can distinguish new
            # bookings from existing ones. We intentionally do NOT fabricate a
            # concrete appointment date/time or EMR row here; concrete
            # bookings are created later via the interactive booking flow
            # (/demo/followups/book).
            try:
                fup["status"] = "CREATED"
                if isinstance(task_res, dict) and task_res.get("id"):
                    fup["task_id"] = task_res["id"]
            except Exception:
                pass

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

    # Step 4 (GP & community handoff) uses a schema so we reliably capture
    # a GP summary and structured action items for downstream display.
    if step == "step4":
        handoff_schema = {
            "type": "object",
            "properties": {
                "patient_id": {"type": ["string", "null"]},
                "agent": {"type": ["string", "null"]},
                "gp_handoff": {
                    "type": "object",
                    "properties": {
                        "summary_bullets": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "gp_action_items": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "community_referrals": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                    "required": ["summary_bullets", "gp_action_items"],
                    "additionalProperties": True,
                },
                "gp_followup_required": {
                    "type": ["boolean", "null"],
                },
                "gp_followup_scheduled": {
                    "type": ["boolean", "null"],
                },
                "llm_reasoning": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["gp_handoff"],
            "additionalProperties": True,
        }

        out = client.complete(system=system, user=user, tools=None, schema=handoff_schema)
        body = out.get("json") or {}
        if not body:
            body = {"raw_text": out.get("text", ""), "model": out.get("model")}

        gp = body.get("gp_handoff") or {}
        gp_actions = gp.get("gp_action_items") or []

        data = {
            "patient_id": req.patient_id or pid,
            "agent": req.agent or "gp_community_handoff",
            "gp_handoff": {
                "summary_bullets": gp.get("summary_bullets") or [],
                "gp_action_items": gp_actions,
                "community_referrals": gp.get("community_referrals") or [],
            },
            "llm_reasoning": body.get("llm_reasoning")
            or [
                "GP and community handoff summary was derived from discharge, risk, and MCP provider context.",
            ],
            "plan_raw": body,
        }
        return data

    # Step 5 (post-discharge monitoring) uses a schema to describe the next
    # check-in channel, timing, and tailored questions.
    if step == "step5":
        monitoring_schema = {
            "type": "object",
            "properties": {
                "patient_id": {"type": ["string", "null"]},
                "agent": {"type": ["string", "null"]},
                "next_check_in": {
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "scheduled_time": {"type": "string"},
                        "questions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "alert_rules": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["channel", "questions"],
                    "additionalProperties": True,
                },
                "llm_reasoning": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["next_check_in"],
            "additionalProperties": True,
        }

        out = client.complete(system=system, user=user, tools=None, schema=monitoring_schema)
        body = out.get("json") or {}
        if not body:
            body = {"raw_text": out.get("text", ""), "model": out.get("model")}

        nci = body.get("next_check_in") or {}
        # If the model failed to propose monitoring questions, derive a simple
        # set of 5 questions informed by diagnosis/medication context so that
        # the UI and narrative are always populated.
        try:
            qs = nci.get("questions") or []
            if not qs:
                csv_ctx = mcp_context.get("csv", {}) if isinstance(mcp_context, dict) else {}
                diag = csv_ctx.get("diagnosis") or []
                meds = csv_ctx.get("inpatient_meds") or []
                diag_desc = diag[0].get("DESCRIPTION") if diag else "your main condition"
                med_name = meds[0].get("MEDICATION_NAME") if meds else "your medicines"
                qs = [
                    f"Since going home, how have you been feeling in yourself compared to before discharge?",
                    f"Have you noticed any new or worsening symptoms related to {diag_desc}?",
                    f"Are you taking {med_name} and your other medicines as prescribed, and have you missed any doses?",
                    "Have you had any side effects or concerns about your medicines that worry you?",
                    "Do you feel you would know when to seek urgent help or contact the hospital/GP if things worsen?",
                ]
                nci["questions"] = qs
                if not nci.get("alert_rules"):
                    nci["alert_rules"] = [
                        "Escalate to clinical review if the patient reports worsening symptoms, thoughts of self-harm, or stopping key medicines.",
                        "Escalate if the patient is unsure how or when to seek urgent help.",
                    ]
        except Exception:
            pass

        data = {
            "patient_id": req.patient_id or pid,
            "agent": req.agent or "post_discharge_monitoring",
            "next_check_in": {
                "channel": nci.get("channel"),
                "scheduled_time": nci.get("scheduled_time"),
                "questions": nci.get("questions") or [],
                "alert_rules": nci.get("alert_rules") or [],
            },
            "llm_reasoning": body.get("llm_reasoning")
            or [
                "Post-discharge monitoring plan was tailored to the patient's risk level and recent discharge context.",
            ],
            "plan_raw": body,
        }
        return data

    # Step 6 (outcomes & governance) uses a schema for cohort KPIs and period.
    if step == "step6":
        outcomes_schema = {
            "type": "object",
            "properties": {
                "patient_id": {"type": ["string", "null"]},
                "agent": {"type": ["string", "null"]},
                "dashboard_period": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                    },
                    "required": ["start_date"],
                    "additionalProperties": True,
                },
                "kpis": {
                    "type": "object",
                    "additionalProperties": True,
                },
                "llm_reasoning": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["dashboard_period", "kpis"],
            "additionalProperties": True,
        }

        out = client.complete(system=system, user=user, tools=None, schema=outcomes_schema)
        body = out.get("json") or {}
        if not body:
            body = {"raw_text": out.get("text", ""), "model": out.get("model")}

        period = body.get("dashboard_period") or {}
        if not period.get("start_date") and not period.get("end_date"):
            period = {"start_date": "the current period", "end_date": ""}
        data = {
            "patient_id": req.patient_id or pid,
            "agent": req.agent or "outcomes_analytics",
            "dashboard_period": {
                "start_date": period.get("start_date"),
                "end_date": period.get("end_date"),
            },
            "kpis": body.get("kpis") or {},
            "llm_reasoning": body.get("llm_reasoning")
            or [
                "Outcomes and governance KPIs were summarised for this discharge program and cohort.",
            ],
            "plan_raw": body,
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


@app.post("/demo/hd-step7")
def demo_hd_step7(req: HdStepRequest):
    """Hospital-to-hotel transport & map routing step.

    Reuses the generic _run_hd_step helper so the LLM prompt + schema
    come from the same discharge pipeline as steps 1–6.
    """
    base = _run_hd_step(req, "step7")

    # Best-effort integration with a Google Maps MCP server. This expects
    # an MCP server command configured via MCP_MAPS_CMD and a tool
    # (for example "maps.route_with_static_map") that returns a JSON
    # structure including a static map image URL.
    origin = req.hospital_address or ""
    destination = req.hotel_address or ""
    if origin and destination:
        try:
            maps = make_maps_client()
            route = maps.call(
                "maps.route_with_static_map",
                {
                    "origin": origin,
                    "destination": destination,
                },
            )
            # Attach map metadata under a dedicated key so the UI can
            # show a capture without disturbing existing step fields.
            base["transport_map"] = route
        except Exception:
            # If Maps MCP is unavailable or misconfigured, still return
            # the LLM step output so the demo UI continues to work.
            pass

    # Fallback: if no transport_map was attached (e.g. Maps MCP is not
    # configured), attempt to parse the LLM raw_text JSON and project
    # primary/fallback routes into a normalised transport_map structure
    # that the UI can render as multiple routes.
    if "transport_map" not in base:
        try:
            raw = base.get("raw_text") or ""
            doc = json.loads(raw) if raw else {}
        except Exception:
            doc = {}

        if isinstance(doc, dict):
            routes = []
            primary = doc.get("primary_route") or {}
            fallback = doc.get("fallback_route") or {}

            def _route_from(src: dict, label: str) -> dict | None:
                if not isinstance(src, dict) or not src:
                    return None
                murl = src.get("map_url") or ""
                if not murl:
                    return None
                summary_bits = []
                if src.get("mode"):
                    summary_bits.append(str(src["mode"]))
                if src.get("distance_km") is not None:
                    summary_bits.append(f"{src['distance_km']} km")
                if src.get("eta_minutes") is not None:
                    summary_bits.append(f"{src['eta_minutes']} min")
                summary = "  b7 ".join(summary_bits)
                if src.get("notes"):
                    if summary:
                        summary += "  b7 " + str(src["notes"])
                    else:
                        summary = str(src["notes"])
                return {
                    "label": label,
                    "map_url": murl,
                    "summary": summary,
                }

            r_primary = _route_from(primary, "Primary route")
            if r_primary:
                routes.append(r_primary)
            r_fallback = _route_from(fallback, "Fallback route")
            if r_fallback:
                routes.append(r_fallback)

            if routes:
                base["transport_map"] = {
                    "hospital_location": doc.get("hospital_location"),
                    "hotel_location": doc.get("hotel_location"),
                    "routes": routes,
                }

    return base


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
