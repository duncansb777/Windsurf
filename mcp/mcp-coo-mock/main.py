#!/usr/bin/env python3
import json
import sys
import os
import csv
from typing import Any, Dict, List

# Minimal JSON-RPC 2.0 over stdio for demo purposes.
# Tools exposed (CoO / Billing flows):
# - coo.address-standardize
# - coo.ownership
# - coo.ownership-deterministic
# - coo.special-read
# - coo.bill-transfer
# - coo.reset
# - mcp.list_tools

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "agent-orchestration-service", "app"))
COO_DATA_DIR = os.environ.get("COO_DATA_DIR", DEFAULT_DATA_DIR)


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


TOOLS = [
    {
        "name": "coo.address-standardize",
        "input": {},
        "output": {"type": "address_summary"},
    },
    {
        "name": "coo.ownership",
        "input": {},
        "output": {"type": "ownership_summary"},
    },
    {
        "name": "coo.ownership-deterministic",
        "input": {},
        "output": {"type": "ownership_summary"},
    },
    {
        "name": "coo.special-read",
        "input": {},
        "output": {"type": "special_read_summary"},
    },
    {
        "name": "coo.bill-transfer",
        "input": {},
        "output": {"type": "bill_transfer_summary"},
    },
    {
        "name": "coo.reset",
        "input": {},
        "output": {"type": "reset_summary"},
    },
]


def _write(obj: Dict[str, Any]):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _ok(id_, result):
    _write({"jsonrpc": "2.0", "id": id_, "result": result})


def _err(id_, code, message, data=None):
    _write({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message, "data": data}})


def list_tools():
    return {"tools": TOOLS}


def coo_address_standardize_method(params: Dict[str, Any]):
    props = _read_csv("Property.csv")
    count = len(props)
    sample = props[:3]
    return {
        "tool": "coo.address-standardize",
        "arguments": params or {},
        "output": {
            "summary": f"Standardized addresses for {count} properties (demo only)",
            "total_properties": count,
            "sample_properties": sample,
        },
    }


def coo_ownership_method(params: Dict[str, Any]):
    history = _read_csv("coohistory.csv")
    props = _read_csv("Property.csv")
    return {
        "tool": "coo.ownership",
        "arguments": params or {},
        "output": {
            "summary": "Ownership change demo executed (mock)",
            "history_rows": len(history),
            "property_rows": len(props),
        },
    }


def coo_ownership_deterministic_method(params: Dict[str, Any]):
    history = _read_csv("coohistory.csv")
    return {
        "tool": "coo.ownership-deterministic",
        "arguments": params or {},
        "output": {
            "summary": "Deterministic ownership apply demo executed (mock)",
            "history_rows": len(history),
        },
    }


def coo_special_read_method(params: Dict[str, Any]):
    triggers = _read_csv("specialreadtrigger.csv")
    schedule = _read_csv("meterreadschedule.csv")
    return {
        "tool": "coo.special-read",
        "arguments": params or {},
        "output": {
            "summary": "Special read schedule demo executed (mock)",
            "triggers": len(triggers),
            "scheduled_reads": len(schedule),
        },
    }


def coo_bill_transfer_method(params: Dict[str, Any]):
    bills = _read_csv("billing_C000001.csv")
    transfers = _read_csv("BalanceTransfers.csv") if os.path.exists(_csv_path("BalanceTransfers.csv")) else []
    return {
        "tool": "coo.bill-transfer",
        "arguments": params or {},
        "output": {
            "summary": "Bill transfer demo executed (mock)",
            "billing_rows": len(bills),
            "transfer_rows": len(transfers),
        },
    }


def coo_reset_method(params: Dict[str, Any]):
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
    return {
        "tool": "coo.reset",
        "arguments": params or {},
        "output": {
            "summary": "CoO demo reset is a no-op (shared data directory)",
            "existing_files": existing,
        },
    }


METHODS = {
    "mcp.list_tools": lambda p: list_tools(),
    "coo.address-standardize": coo_address_standardize_method,
    "coo.ownership": coo_ownership_method,
    "coo.ownership-deterministic": coo_ownership_deterministic_method,
    "coo.special-read": coo_special_read_method,
    "coo.bill-transfer": coo_bill_transfer_method,
    "coo.reset": coo_reset_method,
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
