-- Health Agentic Use-Case Flow - PostgreSQL schema

create table if not exists patient (
  patient_id bigint primary key,
  mrn varchar(64) unique,
  ihi varchar(16),
  given_name varchar(100),
  family_name varchar(100),
  dob date,
  sex_at_birth varchar(32),
  gender_identity varchar(64),
  indigenous_status varchar(32),
  address_line1 varchar(200),
  suburb varchar(100),
  state varchar(10),
  postcode varchar(10),
  phone varchar(32),
  email varchar(120),
  deceased_bool boolean default false
);

create table if not exists provider (
  provider_id bigint primary key,
  hpii varchar(16),
  name_given varchar(100),
  name_family varchar(100),
  role varchar(64),
  specialty varchar(128),
  status varchar(24)
);

create table if not exists organization (
  org_id bigint primary key,
  hpio varchar(16),
  name varchar(200),
  type varchar(64),
  abn varchar(16),
  state varchar(10)
);

create table if not exists location (
  location_id bigint primary key,
  org_id bigint references organization(org_id),
  name varchar(200),
  type varchar(64),
  address_line1 varchar(200),
  suburb varchar(100),
  state varchar(10),
  postcode varchar(10)
);

create table if not exists encounter (
  encounter_id bigint primary key,
  patient_id bigint references patient(patient_id),
  type_code varchar(64),
  class_code varchar(32),
  status varchar(24),
  start_ts timestamp,
  end_ts timestamp,
  location_id bigint references location(location_id),
  service_provider_org_id bigint references organization(org_id)
);

create table if not exists problem (
  problem_id bigint primary key,
  patient_id bigint references patient(patient_id),
  code varchar(64),
  code_system varchar(64),
  clinical_status varchar(24),
  verification_status varchar(24),
  onset_ts timestamp,
  abatement_ts timestamp
);

create table if not exists observation (
  observation_id bigint primary key,
  patient_id bigint references patient(patient_id),
  encounter_id bigint references encounter(encounter_id),
  code varchar(64),
  code_system varchar(64),
  value_string varchar(4000),
  value_numeric decimal(12,4),
  unit varchar(32),
  effective_ts timestamp,
  performer_id bigint references provider(provider_id)
);

create table if not exists medication_request (
  med_request_id bigint primary key,
  patient_id bigint references patient(patient_id),
  encounter_id bigint references encounter(encounter_id),
  prescriber_id bigint references provider(provider_id),
  med_code varchar(64),
  med_system varchar(64),
  intent varchar(24),
  status varchar(24),
  authored_on timestamp,
  dosage_text varchar(1000)
);

create table if not exists care_plan (
  care_plan_id bigint primary key,
  patient_id bigint references patient(patient_id),
  status varchar(24),
  intent varchar(24),
  title varchar(200),
  period_start date,
  period_end date,
  goal_text varchar(2000)
);

create table if not exists task (
  task_id bigint primary key,
  for_patient_id bigint references patient(patient_id),
  owner_ref varchar(64),
  status varchar(24),
  intent varchar(24),
  focus_ref varchar(64),
  due_ts timestamp,
  last_updated timestamp
);

create table if not exists consent (
  consent_id bigint primary key,
  patient_id bigint references patient(patient_id),
  scope varchar(64),
  category varchar(64),
  provision_type varchar(16),
  actors jsonb,
  period_start timestamp,
  period_end timestamp
);

-- Optional mental-health extensions
create table if not exists questionnaire_response (
  qr_id bigint primary key,
  patient_id bigint references patient(patient_id),
  questionnaire_code varchar(64),
  authored_ts timestamp,
  score_total integer,
  raw_json jsonb
);

create table if not exists sdoh_assessment (
  sdoh_id bigint primary key,
  patient_id bigint references patient(patient_id),
  domain varchar(64), -- housing, food, safety, transport
  code varchar(64),
  code_system varchar(64),
  value_text varchar(500),
  value_code varchar(64),
  effective_ts timestamp
);

create table if not exists referral (
  referral_id bigint primary key,
  patient_id bigint references patient(patient_id),
  requester_id bigint references provider(provider_id),
  recipient_org_id bigint references organization(org_id),
  reason_code varchar(64),
  reason_system varchar(64),
  status varchar(24),
  authored_on timestamp
);

create table if not exists document_reference (
  doc_id bigint primary key,
  patient_id bigint references patient(patient_id),
  type_code varchar(64),
  type_system varchar(64),
  status varchar(24),
  indexed_ts timestamp,
  author_ref varchar(64),
  content_uri varchar(400),
  content_hash varchar(128)
);

-- AuditEvent table mirroring Epic MCP audit schema
create table if not exists audit_event (
  audit_id text primary key,
  actor_ref text,
  action text,
  entity_ref text,
  timestamp timestamptz,
  outcome text,
  source text
);

-- Indexes and constraints
-- Unique AU identifiers (nullable unique)
create unique index if not exists ux_patient_ihi on patient(ihi) where ihi is not null;
create unique index if not exists ux_provider_hpii on provider(hpii) where hpii is not null;
create unique index if not exists ux_org_hpio on organization(hpio) where hpio is not null;

-- Foreign key indexes for performance
create index if not exists ix_encounter_patient on encounter(patient_id);
create index if not exists ix_encounter_location on encounter(location_id);
create index if not exists ix_encounter_org on encounter(service_provider_org_id);

create index if not exists ix_observation_patient on observation(patient_id);
create index if not exists ix_observation_encounter on observation(encounter_id);
create index if not exists ix_observation_performer on observation(performer_id);

create index if not exists ix_medreq_patient on medication_request(patient_id);
create index if not exists ix_medreq_encounter on medication_request(encounter_id);
create index if not exists ix_medreq_prescriber on medication_request(prescriber_id);

create index if not exists ix_careplan_patient on care_plan(patient_id);
create index if not exists ix_task_patient on task(for_patient_id);
create index if not exists ix_consent_patient on consent(patient_id);
create index if not exists ix_qr_patient on questionnaire_response(patient_id);
create index if not exists ix_sdoh_patient on sdoh_assessment(patient_id);
create index if not exists ix_referral_patient on referral(patient_id);
create index if not exists ix_referral_requester on referral(requester_id);
create index if not exists ix_referral_org on referral(recipient_org_id);
create index if not exists ix_docref_patient on document_reference(patient_id);
