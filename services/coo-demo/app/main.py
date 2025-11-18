from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List
import os
import csv

# Shared data directory (Option B): default to sibling agent-orchestration-service/app
# relative to the Health project root, override via COO_DATA_DIR if needed.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
COO_DATA_DIR = os.environ.get(
    "COO_DATA_DIR",
    os.path.abspath(os.path.join(PROJECT_ROOT, "..", "agent-orchestration-service", "app")),
)


def _csv_path(name: str) -> str:
    return os.path.join(COO_DATA_DIR, name)


def _read_csv(name: str) -> List[Dict[str, Any]]:
    path = _csv_path(name)
    rows: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(dict(r))
    return rows


class Artifact(BaseModel):
    type: str
    name: str
    path: str


class FlowResult(BaseModel):
    tool: str
    arguments: Dict[str, Any]
    output: Dict[str, Any]


class FlowResponse(BaseModel):
    result: FlowResult
    artifacts: List[Artifact]


app = FastAPI(title="Embedded CoO Billing Demo Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/coo/health")
def coo_health() -> Dict[str, Any]:
    return {"status": "ok", "data_dir": COO_DATA_DIR}


@app.post("/coo/address-standardize", response_model=FlowResponse)
def coo_address_standardize() -> FlowResponse:
    props = _read_csv("Property.csv")
    count = len(props)
    sample = props[:3]
    return FlowResponse(
        result=FlowResult(
            tool="coo.address-standardize",
            arguments={},
            output={
                "summary": f"Standardized addresses for {count} properties (demo only)",
                "total_properties": count,
                "sample_properties": sample,
            },
        ),
        artifacts=[Artifact(type="csv", name="Property.csv", path=_csv_path("Property.csv"))],
    )


@app.post("/coo/ownership", response_model=FlowResponse)
def coo_ownership() -> FlowResponse:
    history = _read_csv("coohistory.csv")
    props = _read_csv("Property.csv")
    return FlowResponse(
        result=FlowResult(
            tool="coo.ownership",
            arguments={},
            output={
                "summary": "Ownership change demo executed (mock)",
                "history_rows": len(history),
                "property_rows": len(props),
            },
        ),
        artifacts=[
            Artifact(type="csv", name="coohistory.csv", path=_csv_path("coohistory.csv")),
            Artifact(type="csv", name="Property.csv", path=_csv_path("Property.csv")),
        ],
    )


@app.post("/coo/ownership-deterministic", response_model=FlowResponse)
def coo_ownership_deterministic() -> FlowResponse:
    history = _read_csv("coohistory.csv")
    return FlowResponse(
        result=FlowResult(
            tool="coo.ownership-deterministic",
            arguments={},
            output={
                "summary": "Deterministic ownership apply demo executed (mock)",
                "history_rows": len(history),
            },
        ),
        artifacts=[Artifact(type="csv", name="coohistory.csv", path=_csv_path("coohistory.csv"))],
    )


@app.post("/coo/special-read", response_model=FlowResponse)
def coo_special_read() -> FlowResponse:
    triggers = _read_csv("specialreadtrigger.csv")
    schedule = _read_csv("meterreadschedule.csv")
    return FlowResponse(
        result=FlowResult(
            tool="coo.special-read",
            arguments={},
            output={
                "summary": "Special read schedule demo executed (mock)",
                "triggers": len(triggers),
                "scheduled_reads": len(schedule),
            },
        ),
        artifacts=[
            Artifact(type="csv", name="specialreadtrigger.csv", path=_csv_path("specialreadtrigger.csv")),
            Artifact(type="csv", name="meterreadschedule.csv", path=_csv_path("meterreadschedule.csv")),
        ],
    )


@app.post("/coo/bill-transfer", response_model=FlowResponse)
def coo_bill_transfer() -> FlowResponse:
    bills = _read_csv("billing_C000001.csv")
    transfers = _read_csv("BalanceTransfers.csv") if os.path.exists(_csv_path("BalanceTransfers.csv")) else []
    return FlowResponse(
        result=FlowResult(
            tool="coo.bill-transfer",
            arguments={},
            output={
                "summary": "Bill transfer demo executed (mock)",
                "billing_rows": len(bills),
                "transfer_rows": len(transfers),
            },
        ),
        artifacts=[
            Artifact(type="csv", name="billing_C000001.csv", path=_csv_path("billing_C000001.csv")),
            Artifact(type="csv", name="BalanceTransfers.csv", path=_csv_path("BalanceTransfers.csv")),
        ],
    )


@app.post("/coo/reset", response_model=FlowResponse)
def coo_reset() -> FlowResponse:
    # For Option B we assume reset is handled by the original orchestration service or manually.
    # Here we just surface current file presence as a no-op reset.
    files = [
        "Property.csv",
        "WaterUtility_CRM_Example.csv",
        "coohistory.csv",
        "billing_C000001.csv",
        "meterreadschedule.csv",
        "rates.csv",
        "specialreadtrigger.csv",
    ]
    existing = [f for f in files if os.path.exists(_csv_path(f))]
    return FlowResponse(
        result=FlowResult(
            tool="coo.reset",
            arguments={},
            output={
                "summary": "CoO demo reset is a no-op (shared data directory)",
                "existing_files": existing,
            },
        ),
        artifacts=[Artifact(type="csv", name=f, path=_csv_path(f)) for f in existing],
    )
