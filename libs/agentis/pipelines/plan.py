from typing import Any, Dict, List


def run(goals: List[str], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {"tasks": [], "next_tool_calls": [], "citations": [], "confidence": 0.0, "caveats": ["mock"]}
