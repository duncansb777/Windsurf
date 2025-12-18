#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
from typing import Any, Dict

# Minimal JSON-RPC 2.0 over stdio for demo purposes.
# Tools exposed:
# - maps.route_with_static_map
# - mcp.list_tools
#
# This is a MOCK Google Maps MCP. It does not call real Google APIs.
# Instead, it constructs embeddable map URLs using the origin and
# destination strings. In a real deployment you would replace the URL
# builders with calls to the official Google Maps APIs using an API key
# stored in a secure configuration location (never hard-coded here).


TOOLS = [
    {
        "name": "maps.route_with_static_map",
        "input": {"origin": "string", "destination": "string"},
        "output": {
            "type": "transport_map",
            "fields": [
                "origin",
                "destination",
                "static_map_url",
                "map_url",
                "summary",
            ],
        },
    }
]


def _write(obj: Dict[str, Any]):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _ok(id_, result):
    _write({"jsonrpc": "2.0", "id": id_, "result": result})


def _err(id_, code, message, data=None):
    _write({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message, "data": data}})


def list_tools() -> Dict[str, Any]:
    return {"tools": TOOLS}


def _encode_addr(s: str) -> str:
    return urllib.parse.quote_plus(s or "")


def maps_route_with_static_map(params: Dict[str, Any]) -> Dict[str, Any]:
    origin = str(params.get("origin", "")).strip()
    destination = str(params.get("destination", "")).strip()
    if not origin or not destination:
        raise ValueError("origin and destination are required")

    o_enc = _encode_addr(origin)
    d_enc = _encode_addr(destination)

    # Real Google Maps directions URL (no API key required). This can be
    # opened directly or embedded in an iframe by the UI.
    map_url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={o_enc}&destination={d_enc}&travelmode=driving"
    )

    # Optional Google Static Maps image. This requires a key; for
    # security, the key is read from GOOGLE_MAPS_API_KEY and not
    # hard-coded. If the key is absent, we omit static_map_url and let
    # the UI rely on the interactive map_url instead.
    static_map_url = ""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if api_key:
        static_map_url = (
            "https://maps.googleapis.com/maps/api/staticmap?"
            f"size=640x320&markers=color:blue|{o_enc}&markers=color:red|{d_enc}"
            f"&path=color:0x0000ff|weight:4|{o_enc}|{d_enc}&key={urllib.parse.quote(api_key)}"
        )

    summary = f"Suggested route from {origin} to {destination}. (Google Maps)"

    out = {
        "origin": origin,
        "destination": destination,
        "map_url": map_url,
        "summary": summary,
    }
    if static_map_url:
        out["static_map_url"] = static_map_url
    return out


METHODS = {
    "mcp.list_tools": lambda p: list_tools(),
    "maps.route_with_static_map": maps_route_with_static_map,
}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:  # noqa: BLE001
            _write({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error", "data": str(e)},
            })
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
        except Exception as e:  # noqa: BLE001
            _err(id_, -32000, "Server error", {"message": str(e)})


if __name__ == "__main__":
    main()
