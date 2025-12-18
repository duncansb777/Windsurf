import json
import os
import subprocess
import threading
import uuid
from typing import Any, Dict, Optional


class MCPClient:
    def __init__(self, cmd: str):
        self.proc = subprocess.Popen(
            cmd.split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        self.lock = threading.Lock()

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        req_id = str(uuid.uuid4())
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        line = json.dumps(req)
        with self.lock:
            assert self.proc.stdin is not None
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
            assert self.proc.stdout is not None
            resp_line = self.proc.stdout.readline()
        resp = json.loads(resp_line)
        if "error" in resp:
            raise RuntimeError(resp["error"])
        return resp["result"]

    def list_tools(self) -> Dict[str, Any]:
        return self.call("mcp.list_tools")


def make_epic_client() -> MCPClient:
    cmd = os.getenv("MCP_EPIC_CMD", "python3 mcp/mcp-epic-mock/main.py")
    return MCPClient(cmd)


def make_hca_client() -> MCPClient:
    cmd = os.getenv("MCP_HCA_CMD", "python3 mcp/mcp-hca-mock/main.py")
    return MCPClient(cmd)


def make_coo_client() -> MCPClient:
    cmd = os.getenv("MCP_COO_CMD", "python3 mcp/mcp-coo-mock/main.py")
    return MCPClient(cmd)


def make_maps_client() -> MCPClient:
    """Create an MCP client for Google Maps / routing tools.

    The underlying command is configurable via MCP_MAPS_CMD so that
    different environments can point to real or mock Maps MCP servers.
    If MCP_MAPS_CMD is not set, this function raises RuntimeError so
    callers can fall back gracefully.
    """
    cmd = os.getenv("MCP_MAPS_CMD")
    if not cmd:
        raise RuntimeError("MCP_MAPS_CMD is not configured for Maps MCP")
    return MCPClient(cmd)
