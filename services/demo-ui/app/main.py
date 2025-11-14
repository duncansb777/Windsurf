from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import os

OWNERSHIP_URL = os.environ.get("OWNERSHIP_URL", "http://127.0.0.1:8001")

app = FastAPI(title="Health Agentic Demo UI")
app.mount("/static", StaticFiles(directory="services/demo-ui/app/static"), name="static")
templates = Jinja2Templates(directory="services/demo-ui/app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/discharge")
async def api_discharge(request: Request):
    steps = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        steps.append({"agent": "Ownership Trigger", "action": "POST /demo/discharge", "status": "running"})
        body = await request.json()
        r = await client.post(f"{OWNERSHIP_URL}/demo/discharge", json=body)
        steps[-1]["status"] = "done"
        data = r.json()
        # infer sub-steps
        steps.append({"agent": "Epic MCP", "action": "epic.discharge_event.get + epic.patient_bundle.get", "status": "done"})
        steps.append({"agent": "HCA MCP", "action": "hca.directory.search_providers", "status": "done"})
        return JSONResponse({"result": data, "trace": steps})


@app.post("/api/audit-check")
async def api_audit_check():
    steps = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        steps.append({"agent": "Ownership Trigger", "action": "POST /demo/audit-check", "status": "running"})
        r = await client.post(f"{OWNERSHIP_URL}/demo/audit-check")
        steps[-1]["status"] = "done"
        steps.append({"agent": "Epic MCP", "action": "epic.fhir_write_back.create + epic.inbasket.alert + epic.audit.search", "status": "done"})
        return JSONResponse({"result": r.json(), "trace": steps})


@app.post("/api/consent-check")
async def api_consent_check(request: Request):
    steps = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        steps.append({"agent": "Ownership Trigger", "action": "POST /demo/consent-check", "status": "running"})
        body = await request.json()
        r = await client.post(f"{OWNERSHIP_URL}/demo/consent-check", json=body)
        steps[-1]["status"] = "done"
        steps.append({"agent": "Policy Agent", "action": "check_consent decision", "status": "done"})
        return JSONResponse({"result": r.json(), "trace": steps})


@app.post("/api/referral")
async def api_referral(request: Request):
    steps = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        steps.append({"agent": "Ownership Trigger", "action": "POST /demo/referral", "status": "running"})
        body = await request.json()
        r = await client.post(f"{OWNERSHIP_URL}/demo/referral", json=body)
        steps[-1]["status"] = "done"
        steps.append({"agent": "Epic MCP", "action": "epic.search(ServiceRequest) + epic.fhir_write_back.create(Task)", "status": "done"})
        return JSONResponse({"result": r.json(), "trace": steps})


@app.post("/api/agentis")
async def api_agentis(request: Request):
    steps = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        steps.append({"agent": "Ownership Trigger", "action": "POST /demo/agentis", "status": "running"})
        body = await request.json()
        r = await client.post(f"{OWNERSHIP_URL}/demo/agentis", json=body)
        steps[-1]["status"] = "done"
        steps.append({"agent": "Agentis LLM", "action": "prompt → completion", "status": "done"})
        return JSONResponse({"result": r.json(), "trace": steps})


@app.post("/api/agentis-referral")
async def api_agentis_referral(request: Request):
    steps = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        steps.append({"agent": "Agent Referral", "action": "POST /demo/agentis-referral", "status": "running"})
        body = await request.json()
        r = await client.post(f"{OWNERSHIP_URL}/demo/agentis-referral", json=body)
        steps[-1]["status"] = "done"
        data = r.json()
        steps.append({"agent": "Agentis LLM", "action": "plan → consent-checked execution", "status": "done"})
        # Expand flow with per-message interactions (Email/SMS/etc.) and task writes
        executed = (data or {}).get("executed") or {}
        # Tasks: indicate creation/denial intents
        for t in executed.get("tasks", []):
            res = t.get("result") or {}
            status = res.get("status") or "denied"
            owner = (t.get("input") or {}).get("owner_ref", "")
            steps.append({
                "agent": "Task Adapter",
                "action": f"create Task for {owner}",
                "status": "done" if status == "created" else "denied",
            })
        # Messages: route by channel to show communication MCPs
        for m in executed.get("messages", []):
            inp = m.get("input") or {}
            res = m.get("result") or {}
            ch = (inp.get("channel") or "").lower()
            to_ref = inp.get("to_ref") or ""
            status = res.get("status") or "denied"
            agent_name = "Comm MCP"
            if ch == "email":
                agent_name = "Email MCP"
            elif ch == "sms":
                agent_name = "SMS MCP"
            elif ch == "inbasket":
                agent_name = "Epic InBasket MCP"
            steps.append({
                "agent": agent_name,
                "action": f"send {ch or 'message'} to {to_ref}",
                "status": "done" if status == "queued" else "denied",
            })
        return JSONResponse({"result": data, "trace": steps})


@app.get("/api/patients")
async def api_patients():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{OWNERSHIP_URL}/patients")
        return JSONResponse(r.json())


@app.post("/api/uber")
async def api_uber(request: Request):
    steps = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        steps.append({"agent": "Transport Orchestrator", "action": "POST /demo/uber", "status": "running"})
        body = await request.json()
        r = await client.post(f"{OWNERSHIP_URL}/demo/uber", json=body)
        steps[-1]["status"] = "done"
        data = r.json()
        # Reflect external booking via MCP
        steps.append({
            "agent": "Rideshare MCP",
            "action": f"book ride → {data.get('booking', {}).get('service', 'uber').capitalize()} #{data.get('booking', {}).get('id', '')}",
            "status": "done" if (data.get('booking', {}).get('status') == 'confirmed') else "denied",
        })
        return JSONResponse({"result": data, "trace": steps})
