from typing import Dict
from .policy import check_consent


def create_task(owner_ref: str, description: str, due_ts: str, patient_ref: str, purpose_of_use: str) -> Dict[str, str]:
    consent = check_consent(subject_ref=patient_ref, recipient_ref=owner_ref, action="task_assignment", purpose_of_use=purpose_of_use)
    if not consent.get("allowed"):
        return {"task_id": "", "status": "denied", "reason": consent.get("reason", "consent_denied")}
    # mock created
    return {"task_id": "task-mock", "status": "created"}
