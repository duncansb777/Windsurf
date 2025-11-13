-- Deterministic demo seed matching the Epic MCP mock scenario.
-- Uses high ID ranges to avoid collisions with CSV loader.
\set ON_ERROR_STOP on

-- Patient 123 equivalent (DB-side uses high ID 100123)
insert into patient (
  patient_id, mrn, ihi, given_name, family_name, dob, sex_at_birth, gender_identity,
  indigenous_status, address_line1, suburb, state, postcode, phone, email, deceased_bool
) values (
  100123, 'MRN-123-LOCAL', '8003608166690503', 'Jane', 'Doe', '1989-06-15', 'female', 'female',
  'Non-Indigenous', '1 Demo St', 'Sydney', 'NSW', '2000', '+61 2 9000 1111', 'jane@example.com', false
) on conflict do nothing;

-- Organization (HPI-O)
insert into organization (org_id, hpio, name, type, abn, state) values
(100001, '8003620000045562', 'Demo Health Service', 'Hospital', '12345678901', 'NSW')
on conflict do nothing;

-- Location under org
insert into location (location_id, org_id, name, type, address_line1, suburb, state, postcode) values
(100001, 100001, 'Ward 3A', 'Ward', '100 Hospital Rd', 'Sydney', 'NSW', '2000')
on conflict do nothing;

-- Providers (HPI-I)
insert into provider (provider_id, hpii, name_given, name_family, role, specialty, status) values
(100001, '8003610000010401', 'Alex', 'GP', 'General Practitioner', 'General Practice', 'active'),
(100002, null, 'Kim', 'CaseManager', 'Case Manager', 'Mental Health', 'active'),
(100003, null, 'Pat', 'Pharmacist', 'Pharmacist', 'Pharmacy', 'active')
on conflict do nothing;

-- Encounter (maps to ENC-456)
insert into encounter (
  encounter_id, patient_id, type_code, class_code, status, start_ts, end_ts, location_id, service_provider_org_id
) values (
  100456, 100123, 'psychiatry', 'inpatient', 'finished', '2025-11-01 10:00:00', now(), 100001, 100001
) on conflict do nothing;

-- MedicationRequest (AMT code)
insert into medication_request (
  med_request_id, patient_id, encounter_id, prescriber_id, med_code, med_system, intent, status, authored_on, dosage_text
) values (
  100001, 100123, 100456, 100001, '21497011000036100', 'AMT', 'order', 'active', '2025-11-01 00:00:00', 'Sertraline 50 mg PO daily'
) on conflict do nothing;

-- Observation (PHQ-9 total)
insert into observation (
  observation_id, patient_id, encounter_id, code, code_system, value_string, value_numeric, unit, effective_ts, performer_id
) values (
  100001, 100123, 100456, 'PHQ9-TOTAL', 'SNOMED-AU', null, 16, 'score', now(), 100002
) on conflict do nothing;

-- Care plan and a goal summary
insert into care_plan (
  care_plan_id, patient_id, status, intent, title, period_start, period_end, goal_text
) values (
  100001, 100123, 'active', 'plan', 'Post-discharge care plan', '2025-11-01', '2026-01-01', 'Follow-up within 7 days; medication review; GP care-plan update'
) on conflict do nothing;

-- Task materialised from care plan
insert into task (
  task_id, for_patient_id, owner_ref, status, intent, focus_ref, due_ts, last_updated
) values (
  100001, 100123, 'Practitioner/100002', 'requested', 'order', 'CarePlan/100001', now() + interval '7 days', now()
) on conflict do nothing;

-- Consent record (mental health)
insert into consent (
  consent_id, patient_id, scope, category, provision_type, actors, period_start, period_end
) values (
  100001, 100123, 'patient-privacy', 'mental-health', 'permit', '[{"reference":"Practitioner/100002"}]', now() - interval '30 days', now() + interval '180 days'
) on conflict do nothing;

-- QuestionnaireResponse summary (PHQ-9)
insert into questionnaire_response (
  qr_id, patient_id, questionnaire_code, authored_ts, score_total, raw_json
) values (
  100001, 100123, 'PHQ9', now(), 16, '{}'
) on conflict do nothing;

-- SDOH assessments
insert into sdoh_assessment (sdoh_id, patient_id, domain, code, code_system, value_text, value_code, effective_ts) values
(100001, 100123, 'housing', 'HOU-INSECURE', 'LOCAL', 'Rent overdue; risk of eviction', null, now()),
(100002, 100123, 'food', 'FOOD-INSECURE', 'LOCAL', 'Skipped meals in past week', null, now())
on conflict do nothing;

-- Referral to community mental health (maps to ServiceRequest)
insert into referral (
  referral_id, patient_id, requester_id, recipient_org_id, reason_code, reason_system, status, authored_on
) values (
  100001, 100123, 100001, 100001, 'MH-FOLLOWUP', 'LOCAL', 'active', now()
) on conflict do nothing;

-- DocumentReference (discharge summary)
insert into document_reference (
  doc_id, patient_id, type_code, type_system, status, indexed_ts, author_ref, content_uri, content_hash
) values (
  100001, 100123, 'DISCHARGE-SUMMARY', 'LOCAL', 'current', now(), 'Practitioner/100001', 'urn:demo:doc:1', 'hash0001'
) on conflict do nothing;
