from typing import Dict, Any, List
import time

# Minimal fixture dataset for Patient 123 covering the demo scenario.

TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

patients: Dict[str, Dict[str, Any]] = {
    "123": {
        "resourceType": "Patient",
        "id": "123",
        "identifier": [
            {"system": "urn:mrn", "value": "MRN-123-LOCAL"},
            {"system": "http://ns.electronichealth.net.au/id/hi/ihi/1.0", "value": "8003608166690503"}
        ],
        "name": [{"text": "Jane Doe", "given": ["Jane"], "family": "Doe"}],
        "gender": "female",
        "birthDate": "1989-06-15",
        "address": [{"line": ["1 Demo St"], "city": "Sydney", "state": "NSW", "postalCode": "2000"}],
        "telecom": [{"system": "phone", "value": "+61 2 9000 1111"}, {"system": "email", "value": "jane@example.com"}],
    }
}

# Expand fixture set to include a panel of 20 mock patients with varied issues.
# For IDs containing '5' we will mark suicide risk in the bundle without a safety plan.
for pid in range(101, 121):
    sid = str(pid)
    if sid in patients:
        continue
    patients[sid] = {
        "resourceType": "Patient",
        "id": sid,
        "identifier": [
            {"system": "urn:mrn", "value": f"MRN-{sid}-MOCK"},
        ],
        "name": [{"text": f"Mock Patient {sid}", "given": ["Mock"], "family": sid}],
        "gender": "unknown",
        "birthDate": "1980-01-01",
        "address": [{"line": ["1 Example St"], "city": "Sydney", "state": "NSW", "postalCode": "2000"}],
    }

organizations: Dict[str, Dict[str, Any]] = {
    "org-001": {
        "resourceType": "Organization",
        "id": "org-001",
        "identifier": [{"system": "http://ns.electronichealth.net.au/id/hi/hpio/1.0", "value": "8003620000045562"}],
        "name": "Demo Health Service",
        "type": [{"text": "Hospital"}],
        "address": [{"line": ["100 Hospital Rd"], "city": "Sydney", "state": "NSW", "postalCode": "2000"}],
    }
    ,
    "org-002": {
        "resourceType": "Organization",
        "id": "org-002",
        "identifier": [{"system": "http://ns.electronichealth.net.au/id/hi/hpio/1.0", "value": "8003620000077777"}],
        "name": "City Community Mental Health Centre",
        "type": [{"text": "Community Health"}],
        "address": [{"line": ["200 Community Way"], "city": "Sydney", "state": "NSW", "postalCode": "2000"}],
    }
}

locations: Dict[str, Dict[str, Any]] = {
    "loc-001": {
        "resourceType": "Location",
        "id": "loc-001",
        "name": "Ward 3A",
        "address": {"line": ["100 Hospital Rd"], "city": "Sydney", "state": "NSW", "postalCode": "2000"},
        "managingOrganization": {"reference": "Organization/org-001"},
    }
}

providers: Dict[str, Dict[str, Any]] = {
    "prov-001": {
        "resourceType": "Practitioner",
        "id": "prov-001",
        "identifier": [{"system": "http://ns.electronichealth.net.au/id/hi/hpii/1.0", "value": "8003610000010401"}],
        "name": [{"text": "Dr Alex GP"}],
        "qualification": [{"code": {"text": "General Practitioner"}}],
        "active": True,
    },
    "prov-002": {
        "resourceType": "Practitioner",
        "id": "prov-002",
        "name": [{"text": "Case Manager Kim"}],
        "qualification": [{"code": {"text": "Mental Health Case Manager"}}],
        "active": True,
    },
    "prov-003": {
        "resourceType": "Practitioner",
        "id": "prov-003",
        "name": [{"text": "Pharmacist Pat"}],
        "qualification": [{"code": {"text": "Pharmacist"}}],
        "active": True,
    },
    "prov-004": {
        "resourceType": "Practitioner",
        "id": "prov-004",
        "name": [{"text": "Dr Harper Hospitalist"}],
        "qualification": [{"code": {"text": "Hospital Medicine"}}],
        "active": True,
    },
}

encounters: Dict[str, Dict[str, Any]] = {
    "ENC-456": {
        "resourceType": "Encounter",
        "id": "ENC-456",
        "status": "finished",
        "class": {"code": "inpatient"},
        "subject": {"reference": "Patient/123"},
        "serviceProvider": {"reference": "Organization/org-001"},
        "period": {"start": "2025-11-01T10:00:00Z", "end": TS},
        "location": [{"location": {"reference": "Location/loc-001"}}],
    }
}

care_teams: Dict[str, Dict[str, Any]] = {
    "ct-001": {
        "resourceType": "CareTeam",
        "id": "ct-001",
        "status": "active",
        "name": "Mental Health MDT",
        "subject": {"reference": "Patient/123"},
        "participant": [
            {"member": {"reference": "Practitioner/prov-001"}, "role": [{"text": "GP"}]},
            {"member": {"reference": "Practitioner/prov-002"}, "role": [{"text": "Case Manager"}]},
            {"member": {"reference": "Practitioner/prov-003"}, "role": [{"text": "Pharmacist"}]},
        ],
        "period": {"start": "2025-10-01"},
    }
}

care_plans: Dict[str, Dict[str, Any]] = {
    "cp-1": {
        "resourceType": "CarePlan",
        "id": "cp-1",
        "status": "active",
        "intent": "plan",
        "title": "Post-discharge care plan",
        "subject": {"reference": "Patient/123"},
        "period": {"start": "2025-11-01", "end": "2026-01-01"},
        "activity": [
            {"detail": {"kind": "ServiceRequest", "status": "scheduled", "code": {"text": "Community follow-up"}, "scheduledString": "within 7 days"}},
            {"detail": {"kind": "Task", "status": "scheduled", "code": {"text": "Medication review"}}},
            {"detail": {"kind": "Task", "status": "scheduled", "code": {"text": "GP care-plan update"}}}
        ],
    }
}

medication_requests: Dict[str, Dict[str, Any]] = {
    "med-1": {
        "resourceType": "MedicationRequest",
        "id": "med-1",
        "status": "active",
        "intent": "order",
        "subject": {"reference": "Patient/123"},
        "encounter": {"reference": "Encounter/ENC-456"},
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.healthterminologies.gov.au/amt",
                    "code": "AMT-EXAMPLE-SERTRALINE-50MG",
                    "display": "Sertraline 50 mg tablet"
                }
            ],
            "text": "Sertraline 50mg"
        },
        "authoredOn": "2025-11-01",
        "requester": {"reference": "Practitioner/prov-001"},
        "dosageInstruction": [{"text": "50mg PO daily"}],
    }
}

observations: Dict[str, Dict[str, Any]] = {
    "phq9-obs-1": {
        "resourceType": "Observation",
        "id": "phq9-obs-1",
        "status": "final",
        "category": [{"text": "survey"}],
        "code": {
            "coding": [
                {"system": "http://snomed.info/sct", "code": "PHQ9-TOTAL-DEMO", "display": "PHQ-9 Total Score"}
            ],
            "text": "PHQ-9 Total Score"
        },
        "subject": {"reference": "Patient/123"},
        "effectiveDateTime": TS,
        "valueQuantity": {"value": 16, "unit": "score"},
    }
}

# Problem list as Condition resources (SNOMED-AU typical)
conditions: Dict[str, Dict[str, Any]] = {
    "cond-1": {
        "resourceType": "Condition",
        "id": "cond-1",
        "clinicalStatus": {"text": "active"},
        "verificationStatus": {"text": "confirmed"},
        "category": [{"text": "problem-list-item"}],
        "code": {
            "coding": [
                {"system": "http://snomed.info/sct", "code": "191616006", "display": "Recurrent depressive disorder"}
            ],
            "text": "Recurrent depressive disorder"
        },
        "subject": {"reference": "Patient/123"},
        "onsetDateTime": "2020-01-01T00:00:00Z"
    }
}

questionnaire_responses: Dict[str, Dict[str, Any]] = {
    "qr-1": {
        "resourceType": "QuestionnaireResponse",
        "id": "qr-1",
        "questionnaire": "Questionnaire/phq9",
        "status": "completed",
        "authored": TS,
        "subject": {"reference": "Patient/123"},
        "item": [],
        "extension": [
            {
                "url": "urn:au:mh:score-total",
                "valueInteger": 16
            }
        ],
    }
}

tasks: Dict[str, Dict[str, Any]] = {
    "task-comm-followup": {
        "resourceType": "Task",
        "id": "task-comm-followup",
        "status": "requested",
        "intent": "order",
        "for": {"reference": "Patient/123"},
        "focus": {"reference": "CarePlan/cp-1"},
        "executionPeriod": {"start": TS},
        "restriction": {"period": {"end": "2025-11-08"}},
        "owner": {"reference": "Practitioner/prov-002"},
        "description": "Community follow-up within 7 days",
    },
}

consents: Dict[str, Dict[str, Any]] = {
    "cons-1": {
        "resourceType": "Consent",
        "id": "cons-1",
        "status": "active",
        "scope": {"text": "patient-privacy"},
        "category": [{"text": "Mental health"}],
        "provision": {"type": "permit"},
        "patient": {"reference": "Patient/123"},
        "dateTime": TS,
    }
}

document_references: Dict[str, Dict[str, Any]] = {
    "doc-1": {
        "resourceType": "DocumentReference",
        "id": "doc-1",
        "status": "current",
        "type": {"text": "Discharge summary"},
        "subject": {"reference": "Patient/123"},
        "date": TS,
        "content": [{"attachment": {"contentType": "text/plain", "url": "urn:demo:doc:1", "title": "Discharge Summary"}}],
    }
}

audit_events: List[Dict[str, Any]] = []

# SDOH assessments as profiled Observations
sdoh_observations: Dict[str, Dict[str, Any]] = {
    "sdoh-1": {
        "resourceType": "Observation",
        "id": "sdoh-1",
        "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "social-history"}], "text": "sdoh"}],
        "code": {"text": "Housing insecurity"},
        "subject": {"reference": "Patient/123"},
        "effectiveDateTime": TS,
        "valueString": "Rent overdue; risk of eviction",
    },
    "sdoh-2": {
        "resourceType": "Observation",
        "id": "sdoh-2",
        "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "social-history"}], "text": "sdoh"}],
        "code": {"text": "Food insecurity"},
        "subject": {"reference": "Patient/123"},
        "effectiveDateTime": TS,
        "valueString": "Skipped meals in past week",
    }
}

# Referral as ServiceRequest to community mental health
service_requests: Dict[str, Dict[str, Any]] = {
    "sr-1": {
        "resourceType": "ServiceRequest",
        "id": "sr-1",
        "status": "active",
        "intent": "order",
        "code": {"text": "Community mental health follow-up"},
        "subject": {"reference": "Patient/123"},
        "authoredOn": TS,
        "requester": {"reference": "Practitioner/prov-001"},
        "performer": [{"reference": "Organization/org-001"}],
    }
}


def fhir_bundle_for_patient(patient_id: str) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    p = patients.get(patient_id)
    if p:
        entries.append({"resource": p})
    else:
        # Synthesize a minimal Patient for demo purposes so that odd-numbered
        # patients (allowed to share in the demo policy) have basic context.
        p = {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [
                {"system": "urn:mrn", "value": f"MRN-{patient_id}-MOCK"}
            ],
            "name": [{"text": f"Mock Patient {patient_id}", "given": ["Mock"], "family": f"{patient_id}"}],
            "gender": ("female" if str(patient_id) == "1" else "unknown"),
            "birthDate": "1980-01-01",
            "address": [{"line": ["1 Example St"], "city": "Sydney", "state": "NSW", "postalCode": "2000"}],
        }
        entries.append({"resource": p})
    # include orgs and location referenced
    enc = next((e for e in encounters.values() if e.get("subject", {}).get("reference") == f"Patient/{patient_id}"), None)
    if enc:
        entries.append({"resource": enc})
        loc_ref = enc.get("location", [{}])[0].get("location", {}).get("reference")
        if loc_ref:
            loc = locations.get(loc_ref.split("/")[-1])
            if loc:
                entries.append({"resource": loc})
        sp_ref = enc.get("serviceProvider", {}).get("reference")
        if sp_ref:
            org = organizations.get(sp_ref.split("/")[-1])
            if org:
                entries.append({"resource": org})
    # care team
    for ct in care_teams.values():
        if ct.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": ct})
            for part in ct.get("participant", []):
                mref = part.get("member", {}).get("reference")
                if mref and mref.startswith("Practitioner/"):
                    prov = providers.get(mref.split("/")[-1])
                    if prov:
                        entries.append({"resource": prov})
    # care plan
    for cp in care_plans.values():
        if cp.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": cp})
    # conditions
    for cond in conditions.values():
        if cond.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": cond})
    # meds
    for mr in medication_requests.values():
        if mr.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": mr})
    # observations
    for obs in observations.values():
        if obs.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": obs})
    # sdoh observations
    for obs in sdoh_observations.values():
        if obs.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": obs})
    # tasks
    for t in tasks.values():
        if t.get("for", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": t})
    # questionnaire responses
    for qr in questionnaire_responses.values():
        if qr.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": qr})
    # consent
    for c in consents.values():
        if c.get("patient", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": c})
    # document refs
    for d in document_references.values():
        if d.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": d})
    # Synthesize a discharge DocumentReference and risk Observations.
    # Special case: any patient id containing '5' is flagged with suicide risk and
    # explicitly notes no safety plan in place.
    try:
        mod = (int(patient_id) - 1) % 3
    except Exception:
        mod = 0
    # Add a discharge summary DocumentReference with concise text for LLM
    doc = {
        "resourceType": "DocumentReference",
        "id": f"doc-discharge-{patient_id}",
        "status": "current",
        "type": {"text": "Discharge summary"},
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": TS,
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "url": f"urn:discharge:{patient_id}",
                    "title": "Discharge Summary",
                    "data": None
                }
            }
        ],
    }
    if "5" in str(patient_id):
        # High suicide risk, no safety plan documented
        doc_text = (
            "Discharge Summary: Active suicidal ideation noted. No safety plan documented; urgent mental health follow-up required."
        )
        risk_obs = {
            "resourceType": "Observation",
            "id": f"risk-suicide-{patient_id}",
            "status": "final",
            "category": [{"text": "risk"}],
            "code": {"text": "Suicide risk"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": TS,
            "valueString": "active suicidal ideation; no safety plan in place",
        }
    elif mod == 0:
        doc_text = (
            "Discharge Summary: Major depressive disorder exacerbation. Passive suicidal ideation without plan; safety plan completed."
        )
        risk_obs = {
            "resourceType": "Observation",
            "id": f"risk-suicide-{patient_id}",
            "status": "final",
            "category": [{"text": "risk"}],
            "code": {"text": "Suicide risk"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": TS,
            "valueString": "passive ideation, no plan; safety plan completed",
        }
    elif mod == 1:
        doc_text = (
            "Discharge Summary: Housing instability reported and missed medication doses last week. No active SI."
        )
        risk_obs = {
            "resourceType": "Observation",
            "id": f"risk-housing-{patient_id}",
            "status": "final",
            "category": [{"text": "risk"}],
            "code": {"text": "Housing risk"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": TS,
            "valueString": "housing instability; missed medications",
        }
    else:
        doc_text = (
            "Discharge Summary: Sertraline initiated 25mg; monitor adherence and side effects."
        )
        risk_obs = {
            "resourceType": "Observation",
            "id": f"medication-change-{patient_id}",
            "status": "final",
            "category": [{"text": "risk"}],
            "code": {"text": "Medication change"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": TS,
            "valueString": "sertraline started; monitor adherence",
        }
    # Put doc_text into an extension for quick access and include the resource
    doc["description"] = doc_text
    entries.append({"resource": doc})
    # Include the risk observation
    entries.append({"resource": risk_obs})
    # referrals
    has_sr = False
    for sr in service_requests.values():
        if sr.get("subject", {}).get("reference") == f"Patient/{patient_id}":
            entries.append({"resource": sr})
            has_sr = True
    # If no referral exists for this patient, synthesize a minimal ServiceRequest referral
    if not has_sr:
        sr_auto = {
            "resourceType": "ServiceRequest",
            "id": f"sr-auto-{patient_id}",
            "status": "active",
            "intent": "order",
            "code": {"text": "Community mental health follow-up"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "authoredOn": TS,
            "requester": {"reference": "Practitioner/prov-001"},
            "performer": [{"reference": ("Organization/org-002" if str(patient_id) == "1" else "Organization/org-001")}],
        }
        entries.append({"resource": sr_auto})
        # Include referenced Organization/Practitioner where available
        org_ref = "org-002" if str(patient_id) == "1" else "org-001"
        org = organizations.get(org_ref)
        if org:
            entries.append({"resource": org})
        prov = providers.get("prov-001")
        if prov:
            entries.append({"resource": prov})

    return {"resourceType": "Bundle", "type": "collection", "entry": entries}
