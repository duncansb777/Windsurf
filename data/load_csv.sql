-- Load generated CSVs into Postgres. Assumes files mounted at /data/csv
\set ON_ERROR_STOP on

\echo 'Loading patient.csv'
COPY patient FROM '/data/csv/patient.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading organization.csv'
COPY organization FROM '/data/csv/organization.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading location.csv'
COPY location FROM '/data/csv/location.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading provider.csv'
COPY provider FROM '/data/csv/provider.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading encounter.csv'
COPY encounter FROM '/data/csv/encounter.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading observation.csv'
COPY observation FROM '/data/csv/observation.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading medication_request.csv'
COPY medication_request FROM '/data/csv/medication_request.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading care_plan.csv'
COPY care_plan FROM '/data/csv/care_plan.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading task.csv'
COPY task FROM '/data/csv/task.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading consent.csv'
COPY consent FROM '/data/csv/consent.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading questionnaire_response.csv'
COPY questionnaire_response FROM '/data/csv/questionnaire_response.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading sdoh_assessment.csv'
COPY sdoh_assessment FROM '/data/csv/sdoh_assessment.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading referral.csv'
COPY referral FROM '/data/csv/referral.csv' WITH (FORMAT csv, HEADER true);

\echo 'Loading document_reference.csv'
COPY document_reference FROM '/data/csv/document_reference.csv' WITH (FORMAT csv, HEADER true);
