from typing import Dict
from .policy import check_consent


def send_message(channel: str, to_ref: str, purpose_of_use: str, content: str, patient_ref: str) -> Dict[str, str]:
    consent = check_consent(subject_ref=patient_ref, recipient_ref=to_ref, action="share_summary", purpose_of_use=purpose_of_use)
    if not consent.get("allowed"):
        return {"status": "denied", "message_id": "", "reason": consent.get("reason", "consent_denied")}
    return {"status": "queued", "message_id": "msg-mock"}
