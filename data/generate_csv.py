#!/usr/bin/env python3
import csv
import os
import random
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List

OUT_DIR = Path(__file__).parent / "csv"
random.seed(42)

FIRST_NAMES = [
    "Alex","Taylor","Jordan","Casey","Riley","Cameron","Morgan","Jamie","Avery","Quinn",
    "Charlie","Drew","Elliot","Harper","Jesse","Kai","Logan","Micah","Noah","Parker"
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Garcia","Rodriguez","Wilson",
    "Martinez","Anderson","Taylor","Thomas","Hernandez","Moore","Martin","Jackson","Thompson","White"
]
SUBURBS = ["Sydney","Parramatta","Newcastle","Wollongong","Gosford","Penrith","Liverpool","Bondi","Manly","Chatswood"]
STATES = ["NSW","VIC","QLD","WA","SA","TAS","ACT","NT"]
POSTCODES = ["2000","2007","2010","2067","2095","2150","2170","2250","2500","2300"]
ROLES = ["General Practitioner","Case Manager","Pharmacist","Psychiatrist","Psychologist"]
SPECIALTIES = ["Mental Health","General Practice","Pharmacy","Psychiatry","Clinical Psychology"]


def mk_dirs():
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def rand_date(start: date, end: date) -> date:
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def rand_ts(days_back: int = 365) -> datetime:
    now = datetime.utcnow()
    return now - timedelta(days=random.randint(0, days_back), hours=random.randint(0, 23), minutes=random.randint(0, 59))


def phone() -> str:
    return f"+61 2 9{random.randint(100,999)} {random.randint(100,999)}{random.randint(0,9)}{random.randint(0,9)}"


def email(given: str, family: str) -> str:
    return f"{given.lower()}.{family.lower()}@example.com"


def ihi() -> str:
    return "800360" + str(random.randint(10000000, 99999999))


def hpii() -> str:
    return "800361" + str(random.randint(1000000, 9999999))


def hpio() -> str:
    return "800362" + str(random.randint(1000000, 9999999))


def abn() -> str:
    return str(random.randint(10000000000, 99999999999))


def write_patients(n: int = 50) -> List[int]:
    path = OUT_DIR / "patient.csv"
    ids = []
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["patient_id","mrn","ihi","given_name","family_name","dob","sex_at_birth","gender_identity","indigenous_status","address_line1","suburb","state","postcode","phone","email","deceased_bool"])
        for i in range(1, n+1):
            given = random.choice(FIRST_NAMES)
            family = random.choice(LAST_NAMES)
            pid = i
            ids.append(pid)
            w.writerow([
                pid,
                f"MRN-{1000+i}",
                ihi(),
                given,
                family,
                rand_date(date(1950,1,1), date(2010,12,31)).isoformat(),
                random.choice(["male","female","intersex","unknown"]),
                random.choice(["male","female","non-binary","unknown"]),
                random.choice(["Non-Indigenous","Aboriginal","Torres Strait Islander","Aboriginal and Torres Strait Islander","Unknown"]),
                f"{random.randint(1,200)} Example St",
                random.choice(SUBURBS),
                random.choice(STATES),
                random.choice(POSTCODES),
                phone(),
                email(given, family),
                random.choice(["false","false","false","true"])  # bias to false
            ])
    return ids


def write_organizations(n: int = 10) -> List[int]:
    path = OUT_DIR / "organization.csv"
    ids = []
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["org_id","hpio","name","type","abn","state"])
        for i in range(1, n+1):
            oid = i
            ids.append(oid)
            w.writerow([
                oid,
                hpio(),
                f"Org {oid}",
                random.choice(["Hospital","Clinic","Community Health","Pharmacy"]),
                abn(),
                random.choice(STATES),
            ])
    return ids


def write_locations(org_ids: List[int], n: int = 20) -> List[int]:
    path = OUT_DIR / "location.csv"
    ids = []
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["location_id","org_id","name","type","address_line1","suburb","state","postcode"])
        for i in range(1, n+1):
            lid = i
            ids.append(lid)
            w.writerow([
                lid,
                random.choice(org_ids),
                f"Location {lid}",
                random.choice(["Ward","Clinic","Community" ]),
                f"{random.randint(1,300)} Service Rd",
                random.choice(SUBURBS),
                random.choice(STATES),
                random.choice(POSTCODES),
            ])
    return ids


def write_providers(n: int = 30) -> List[int]:
    path = OUT_DIR / "provider.csv"
    ids = []
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["provider_id","hpii","name_given","name_family","role","specialty","status"])
        for i in range(1, n+1):
            pid = i
            ids.append(pid)
            given = random.choice(FIRST_NAMES)
            family = random.choice(LAST_NAMES)
            w.writerow([
                pid,
                hpii(),
                given,
                family,
                random.choice(ROLES),
                random.choice(SPECIALTIES),
                random.choice(["active","inactive"])])
    return ids


def write_encounters(patient_ids: List[int], location_ids: List[int], org_ids: List[int], n: int = 500) -> List[int]:
    path = OUT_DIR / "encounter.csv"
    ids = []
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["encounter_id","patient_id","type_code","class_code","status","start_ts","end_ts","location_id","service_provider_org_id"])
        for i in range(1, n+1):
            eid = i
            ids.append(eid)
            start = rand_ts(180)
            end = start + timedelta(hours=random.randint(1, 72))
            w.writerow([
                eid,
                random.choice(patient_ids),
                random.choice(["psychiatry","general","ed"]),
                random.choice(["inpatient","ambulatory","emergency"]),
                random.choice(["finished","in-progress","onleave"]),
                start.isoformat(sep=" "),
                end.isoformat(sep=" "),
                random.choice(location_ids),
                random.choice(org_ids),
            ])
    return ids


def write_observations(patient_ids: List[int], encounter_ids: List[int], provider_ids: List[int], n: int = 500):
    path = OUT_DIR / "observation.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["observation_id","patient_id","encounter_id","code","code_system","value_string","value_numeric","unit","effective_ts","performer_id"])
        for i in range(1, n+1):
            oid = i
            # PHQ-9 total score simulated 0-27
            score = random.randint(0, 27)
            w.writerow([
                oid,
                random.choice(patient_ids),
                random.choice(encounter_ids),
                "PHQ9-TOTAL",
                "SNOMED-AU",
                None,
                score,
                "score",
                rand_ts(90).isoformat(sep=" "),
                random.choice(provider_ids),
            ])


def write_questionnaire_responses(patient_ids: List[int], n: int = 150):
    path = OUT_DIR / "questionnaire_response.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["qr_id","patient_id","questionnaire_code","authored_ts","score_total","raw_json"])
        questionnaires = ["PHQ9","GAD7","HoNOS"]
        for i in range(1, n+1):
            q = random.choice(questionnaires)
            score = random.randint(0, 27) if q == "PHQ9" else random.randint(0, 21)
            raw = "{}"
            w.writerow([
                i,
                random.choice(patient_ids),
                q,
                rand_ts(120).isoformat(sep=" "),
                score,
                raw
            ])


def write_sdoh_assessments(patient_ids: List[int], n: int = 120):
    path = OUT_DIR / "sdoh_assessment.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sdoh_id","patient_id","domain","code","code_system","value_text","value_code","effective_ts"])
        domains = [
            ("housing","HOU-INSECURE","LOCAL"),
            ("food","FOOD-INSECURE","LOCAL"),
            ("safety","SAFETY-RISK","LOCAL"),
            ("transport","TRANSPORT-LIMIT","LOCAL"),
        ]
        for i in range(1, n+1):
            domain, code, system = random.choice(domains)
            value_text = random.choice([
                "No issues reported",
                "Occasional difficulty",
                "Significant difficulty",
                "Crisis"
            ])
            w.writerow([
                i,
                random.choice(patient_ids),
                domain,
                code,
                system,
                value_text,
                None,
                rand_ts(180).isoformat(sep=" ")
            ])


def write_referrals(patient_ids: List[int], org_ids: List[int], provider_ids: List[int], n: int = 100):
    path = OUT_DIR / "referral.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["referral_id","patient_id","requester_id","recipient_org_id","reason_code","reason_system","status","authored_on"])
        reasons = [("MH-FOLLOWUP","LOCAL"),("PHARM-MED-REVIEW","LOCAL"),("SOCIAL-SUPPORT","LOCAL")]
        for i in range(1, n+1):
            code, system = random.choice(reasons)
            w.writerow([
                i,
                random.choice(patient_ids),
                random.choice(provider_ids),
                random.choice(org_ids),
                code,
                system,
                random.choice(["active","completed","revoked"]),
                rand_ts(180).isoformat(sep=" ")
            ])


def write_document_references(patient_ids: List[int], n: int = 80):
    path = OUT_DIR / "document_reference.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id","patient_id","type_code","type_system","status","indexed_ts","author_ref","content_uri","content_hash"])
        types = [("DISCHARGE-SUMMARY","LOCAL"),("COMMUNITY-LETTER","LOCAL")]
        for i in range(1, n+1):
            code, system = random.choice(types)
            w.writerow([
                i,
                random.choice(patient_ids),
                code,
                system,
                random.choice(["current","superseded"]),
                rand_ts(365).isoformat(sep=" "),
                random.choice(["Practitioner/1","Organization/1"]),
                f"urn:doc:{i}",
                f"hash{i:04d}"
            ])

def write_medication_requests(patient_ids: List[int], encounter_ids: List[int], provider_ids: List[int], n: int = 200):
    path = OUT_DIR / "medication_request.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["med_request_id","patient_id","encounter_id","prescriber_id","med_code","med_system","intent","status","authored_on","dosage_text"])
        meds = [
            ("21497011000036100","AMT","Sertraline 50 mg tablet"),
            ("21498111000036105","AMT","Sertraline 100 mg tablet"),
            ("18767011000036109","AMT","Escitalopram 10 mg tablet"),
        ]
        for i in range(1, n+1):
            code, system, label = random.choice(meds)
            w.writerow([
                i,
                random.choice(patient_ids),
                random.choice(encounter_ids),
                random.choice(provider_ids),
                code,
                system,
                random.choice(["order","plan"]),
                random.choice(["active","completed","stopped"]),
                rand_ts(120).isoformat(sep=" "),
                f"{label} once daily",
            ])


def write_care_plans(patient_ids: List[int], n: int = 80):
    path = OUT_DIR / "care_plan.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["care_plan_id","patient_id","status","intent","title","period_start","period_end","goal_text"])
        for i in range(1, n+1):
            start = rand_date(date.today() - timedelta(days=120), date.today())
            end = start + timedelta(days=random.randint(30, 180))
            w.writerow([
                i,
                random.choice(patient_ids),
                random.choice(["active","completed"]),
                "plan",
                "Post-discharge care plan",
                start.isoformat(),
                end.isoformat(),
                "Engage with community MH services; medication adherence; monitor mood",
            ])


def write_tasks(patient_ids: List[int], n: int = 300):
    path = OUT_DIR / "task.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id","for_patient_id","owner_ref","status","intent","focus_ref","due_ts","last_updated"])
        focuses = ["care_plan/1","observation/PHQ9","service_request/1"]
        owners = ["Practitioner/1","Practitioner/2","Organization/1","Agent/task-delegation"]
        for i in range(1, n+1):
            due = rand_ts(30)
            w.writerow([
                i,
                random.choice(patient_ids),
                random.choice(owners),
                random.choice(["requested","in-progress","completed"]),
                "order",
                random.choice(focuses),
                (due + timedelta(days=random.randint(1, 14))).isoformat(sep=" "),
                datetime.utcnow().isoformat(sep=" ")
            ])


def write_consents(patient_ids: List[int], n: int = 80):
    path = OUT_DIR / "consent.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["consent_id","patient_id","scope","category","provision_type","actors","period_start","period_end"])
        for i in range(1, n+1):
            start = rand_ts(365)
            end = start + timedelta(days=random.randint(30, 365))
            actors = '[{"reference":"Practitioner/1"},{"reference":"Organization/1"}]'
            w.writerow([
                i,
                random.choice(patient_ids),
                "patient-privacy",
                random.choice(["general","mental-health","my-health-record"]),
                random.choice(["permit","deny"]),
                actors,
                start.isoformat(sep=" "),
                end.isoformat(sep=" "),
            ])


def main():
    mk_dirs()
    patient_ids = write_patients(50)
    org_ids = write_organizations(10)
    location_ids = write_locations(org_ids, 20)
    provider_ids = write_providers(30)
    encounter_ids = write_encounters(patient_ids, location_ids, org_ids, 500)
    write_observations(patient_ids, encounter_ids, provider_ids, 500)
    write_medication_requests(patient_ids, encounter_ids, provider_ids, 200)
    write_care_plans(patient_ids, 80)
    write_tasks(patient_ids, 300)
    write_consents(patient_ids, 80)
    write_questionnaire_responses(patient_ids, 150)
    write_sdoh_assessments(patient_ids, 120)
    write_referrals(patient_ids, org_ids, provider_ids, 100)
    write_document_references(patient_ids, 80)
    print(f"CSV files generated in {OUT_DIR}")


if __name__ == "__main__":
    main()
