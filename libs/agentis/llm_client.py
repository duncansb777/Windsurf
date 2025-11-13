import os
import json
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error
import ssl
import certifi


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("AGENTIS_LLM_PROVIDER", "mock")
        self.model = os.getenv("AGENTIS_LLM_MODEL", "mock-small")
        self.api_key = os.getenv("AGENTIS_LLM_API_KEY", "")

    def complete(self, system: str, user: str, tools: Optional[List[Dict[str, Any]]] = None, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.provider == "mock":
            return {"text": "", "json": {"mock": True}, "model": self.model}

        if self.provider == "openai":
            if not self.api_key:
                return {"text": "", "json": {"error": "missing_api_key"}, "model": self.model}
            try:
                payload: Dict[str, Any] = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system or ""},
                        {"role": "user", "content": user or ""},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 600,
                }
                # Prefer JSON schema when provided
                if schema:
                    payload["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {"name": "agentis_schema", "schema": schema, "strict": True},
                    }
                else:
                    payload["response_format"] = {"type": "text"}

                def _call(payload: Dict[str, Any]) -> Dict[str, Any]:
                    req = urllib.request.Request(
                        url="https://api.openai.com/v1/chat/completions",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {self.api_key}",
                        },
                        method="POST",
                    )
                    ctx = ssl.create_default_context(cafile=certifi.where())
                    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                        raw = resp.read().decode("utf-8")
                    return json.loads(raw)

                try:
                    data = _call(payload)
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8") if hasattr(e, "read") else ""
                    # Fallback: if we asked for json_schema, retry with json_object
                    if schema:
                        payload_fallback = {
                            **payload,
                            "response_format": {"type": "json_object"},
                        }
                        # Reinforce JSON requirement in messages
                        payload_fallback["messages"] = [
                            {"role": "system", "content": (system or "") + "\nRespond strictly with a single JSON object only."},
                            {"role": "user", "content": user or ""},
                        ]
                        try:
                            data = _call(payload_fallback)
                        except Exception as e2:
                            return {"text": "", "json": {"error": str(e2), "http_error": err_body}, "model": self.model}
                    else:
                        return {"text": "", "json": {"error": str(e), "http_error": err_body}, "model": self.model}

                choice = (data.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                text = msg.get("content") or ""
                out: Dict[str, Any] = {"text": text, "raw": data, "model": self.model}
                if schema and text:
                    try:
                        out["json"] = json.loads(text)
                    except Exception:
                        out["json"] = None
                return out
            except Exception as e:
                return {"text": "", "json": {"error": str(e)}, "model": self.model}

        return {"text": "", "json": {"error": "unsupported_provider"}, "model": self.model}
