import json
import os
from typing import Any, Dict, List

from libs.common.mcp_client import make_epic_client


def retrieve_minimal_context(patient_id: str) -> Dict[str, Any]:
    client = make_epic_client()
    bundle = client.call("epic.patient_bundle.get", {"patient_id": patient_id})
    return {"patient_bundle": bundle}


def load_fixture(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def preprocess_for_prompt(data: Dict[str, Any]) -> Dict[str, Any]:
    return data


def assemble_prompt(system: str, policy: str, task: str, facts: Dict[str, Any], exemplars: List[str]) -> Dict[str, Any]:
    return {"system": system, "policy": policy, "task": task, "facts": facts, "exemplars": exemplars}
