#!/usr/bin/env python3
import json
import sys
import time
from typing import Any, Dict, List

# Minimal JSON-RPC 2.0 over stdio for demo purposes.
# Methods exposed:
# - hca.directory.search_providers
# - mcp.list_tools

TOOLS = [
    {
        "name": "hca.directory.search_providers",
        "input": {
            "patient_id": "string",
            "location": "string",
            "roles": ["string"],
            "consent_context": "object"
        },
        "output": {"type": "providers_list"},
    }
]

PROVIDERS_FIXTURE: List[Dict[str, Any]] = [
    {
        "resourceType": "Practitioner",
        "id": "prac-001",
        "name": [{"text": "Dr Alex GP"}],
        "telecom": [{"system": "phone", "value": "+61 2 9000 0001"}],
        "qualification": [{"code": {"text": "General Practitioner"}}],
        "location": {"postcode": "2000"},
    },
    {
        "resourceType": "Practitioner",
        "id": "prac-002",
        "name": [{"text": "Case Manager Kim"}],
        "telecom": [{"system": "phone", "value": "+61 2 9000 0002"}],
        "qualification": [{"code": {"text": "Mental Health Case Manager"}}],
        "location": {"postcode": "2000"},
    },
    {
        "resourceType": "Practitioner",
        "id": "prac-003",
        "name": [{"text": "Pharmacist Pat"}],
        "telecom": [{"system": "phone", "value": "+61 2 9000 0003"}],
        "qualification": [{"code": {"text": "Pharmacist"}}],
        "location": {"postcode": "2000"},
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


def hca_directory_search_providers(params: Dict[str, Any]):
    roles = params.get("roles") or []
    location = params.get("location") or "2000"
    # Simple filter: match by role keyword in qualification text and postcode.
    out = []
    for p in PROVIDERS_FIXTURE:
        ok_loc = p.get("location", {}).get("postcode") == location
        if not roles:
            role_ok = True
        else:
            qual_texts = [q.get("code", {}).get("text", "").lower() for q in p.get("qualification", [])]
            role_ok = any(r.lower() in qt for r in roles for qt in qual_texts)
        if ok_loc and role_ok:
            out.append(p)
    return {"count": len(out), "providers": out, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


METHODS = {
    "mcp.list_tools": lambda p: list_tools(),
    "hca.directory.search_providers": hca_directory_search_providers,
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
