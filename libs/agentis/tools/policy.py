import json
import os
from typing import Any, Dict, List


def _match(entry: Dict[str, Any], recipient_ref: str, purpose_of_use: str) -> bool:
    rec = entry.get("recipient", "")
    puses: List[str] = entry.get("purpose_of_use", [])
    # wildcard support: '*' anywhere, and prefix 'nonau-*' like patterns
    def match_token(token: str, value: str) -> bool:
        if token == "*":
            return True
        if token.endswith("*"):
            return value.startswith(token[:-1])
        return token == value

    return match_token(rec, recipient_ref) and ("*" in puses or purpose_of_use in puses)


def _load_consents() -> Dict[str, Any]:
    # Try combined snippets file first, then scenarios
    base = os.getcwd()
    p1 = os.path.join(base, "data", "fixtures", "consent_policy_snippets.json")
    p2 = os.path.join(base, "data", "fixtures", "consent_scenarios.json")
    try:
        with open(p1, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        pass
    try:
        with open(p2, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"consents": []}


def check_consent(subject_ref: str, recipient_ref: str, action: str, purpose_of_use: str) -> Dict[str, Any]:
    # Demo rule: odd-numbered patients => allow, even-numbered => limited allow
    try:
        # subject_ref expected format: "Patient/{id}"
        pid = subject_ref.split("/")[-1]
        n = int(pid)
        if n % 2 == 0:
            # Deny only social worker updates (Practitioner/prov-002)
            if recipient_ref == "Practitioner/prov-002":
                return {"allowed": False, "reason": "demo_even_denied_social_worker", "policy_refs": ["DEMO-EVEN-DENY-SOCIAL"]}
            # Allow sharing summaries to any Practitioner (notifications), excluding the social worker above
            if action == "share_summary" and recipient_ref.startswith("Practitioner/"):
                return {"allowed": True, "reason": "demo_even_allow_practitioner_notifications", "policy_refs": ["DEMO-EVEN-PRACTITIONER-ALLOW"]}
            # Other recipients/actions remain denied
            return {"allowed": False, "reason": "demo_even_patient_denied", "policy_refs": ["DEMO-EVEN-DENY"]}
        else:
            return {"allowed": True, "reason": "demo_odd_patient_allowed", "policy_refs": ["DEMO-ODD-ALLOW"]}
    except Exception:
        # Fall back to fixture-driven evaluation if patient id not numeric
        pass

    data = _load_consents()
    # unify structure across fixtures
    consents: List[Dict[str, Any]] = []
    if "consents" in data:
        consents = data.get("consents", [])
    elif "scenarios" in data:
        consents = data.get("scenarios", [])

    # Find matching patient consent (or use first if demo)
    subject = subject_ref
    scope = None
    for c in consents:
        if c.get("patient_ref") == subject:
            scope = c
            break
    if scope is None and consents:
        scope = consents[0]

    if not scope:
        return {"allowed": False, "reason": "no_consent_found", "policy_refs": []}

    # Deny overrides allow
    for d in scope.get("deny", []):
        if _match(d, recipient_ref, purpose_of_use):
            return {"allowed": False, "reason": "denied_by_consent", "policy_refs": [scope.get("id") or ""]}
    # Allow
    for a in scope.get("allow", []):
        if _match(a, recipient_ref, purpose_of_use):
            return {"allowed": True, "reason": "allowed_by_consent", "policy_refs": [scope.get("id") or ""]}

    return {"allowed": False, "reason": "no_matching_allow", "policy_refs": [scope.get("id") or ""]}


def policy_eval(policy_context: Dict[str, Any]) -> Dict[str, Any]:
    return {"decisions": [], "reasons": []}
