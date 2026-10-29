-- 0001_candidate_model.sql — T03 candidate model v1 (contract v1 / hash h1)
-- Checked against spec §3.1/§3.3; no global DO NOTHING; explicit columns only.

CREATE TABLE schema_migrations (
    version text PRIMARY KEY,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE providers (
    provider_id bigserial PRIMARY KEY,
    provider_name text NOT NULL UNIQUE
);

CREATE TABLE sources (
    source_id bigserial PRIMARY KEY,
    source_code text NOT NULL UNIQUE,
    provider_id bigint NOT NULL REFERENCES providers,
    namespace text NOT NULL,
    UNIQUE (provider_id, namespace)
);

CREATE TABLE ingest_batches (
    batch_id text PRIMARY KEY,
    source_id bigint NOT NULL REFERENCES sources,
    manifest_digest text NOT NULL,
    contract_version text NOT NULL,
    capture_mode text NOT NULL CHECK (capture_mode IN ('full','incremental','archive','ocr')),
    captured_at timestamptz NOT NULL,
    observed_order text,
    coverage text NOT NULL CHECK (coverage IN ('complete','partial','unknown')),
    adapter_version text NOT NULL,
    mapping_version text NOT NULL,
    hash_version text NOT NULL
);

CREATE FUNCTION reject_batch_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ingest_batches is immutable (batch_id %)', OLD.batch_id;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER batch_immutable
    BEFORE UPDATE OR DELETE ON ingest_batches
    FOR EACH ROW EXECUTE FUNCTION reject_batch_mutation();

CREATE TABLE input_files (
    input_file_id bigserial PRIMARY KEY,
    batch_id text NOT NULL REFERENCES ingest_batches,
    relative_path text NOT NULL,
    sha256 text NOT NULL,
    byte_size bigint NOT NULL,
    row_count bigint NOT NULL,
    format text NOT NULL,
    role text NOT NULL,
    UNIQUE (batch_id, relative_path)
);

CREATE TABLE source_records (
    source_record_id bigserial PRIMARY KEY,
    source_id bigint NOT NULL REFERENCES sources,
    identity_key text NOT NULL,
    identity_status text NOT NULL DEFAULT 'confirmed'
        CHECK (identity_status IN ('confirmed','candidate')),
    UNIQUE (source_id, identity_key)
);

CREATE TABLE content_payloads (
    payload_id bigserial PRIMARY KEY,
    payload_hash text NOT NULL,
    hash_version text NOT NULL,
    UNIQUE (payload_hash, hash_version)
);

CREATE TABLE observations (
    observation_id bigserial PRIMARY KEY,
    source_record_id bigint NOT NULL REFERENCES source_records,
    payload_id bigint NOT NULL REFERENCES content_payloads,
    batch_id text NOT NULL REFERENCES ingest_batches,
    context_key text NOT NULL DEFAULT 'default',
    order_key text,
    evidence_location text NOT NULL,
    UNIQUE (batch_id, source_record_id, context_key, payload_id),
    UNIQUE (observation_id, source_record_id)
);

CREATE INDEX idx_observations_record_order
    ON observations (source_record_id, order_key);

CREATE TABLE source_record_current (
    source_record_id bigint PRIMARY KEY REFERENCES source_records,
    observation_id bigint NOT NULL,
    status text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','conflict','unresolved')),
    FOREIGN KEY (observation_id, source_record_id)
        REFERENCES observations (observation_id, source_record_id)
);

CREATE TABLE provider_projects (
    provider_project_id bigserial PRIMARY KEY,
    provider_id bigint NOT NULL REFERENCES providers,
    native_project_key text NOT NULL,
    display_title text,
    UNIQUE (provider_id, native_project_key)
);

CREATE TABLE project_source_links (
    project_source_link_id bigserial PRIMARY KEY,
    provider_project_id bigint NOT NULL REFERENCES provider_projects,
    source_record_id bigint NOT NULL REFERENCES source_records,
    link_basis text NOT NULL CHECK (link_basis IN ('native_id','confirmed','candidate')),
    UNIQUE (provider_project_id, source_record_id)
);

CREATE TABLE offerings (
    offering_id bigserial PRIMARY KEY,
    provider_project_id bigint NOT NULL REFERENCES provider_projects,
    offering_key text NOT NULL,
    start_date_raw text,
    start_precision text CHECK (start_precision IN ('day','month','year','unknown')),
    duration_raw text,
    price_amount numeric(14,2),
    price_raw text,
    currency text,
    enrollment_status_raw text,
    field_state text NOT NULL
        CHECK (field_state IN ('value','explicitly_empty','not_provided','extraction_failed')),
    UNIQUE (provider_project_id, offering_key)
);

CREATE TABLE asset_blobs (
    blob_id bigserial PRIMARY KEY,
    sha256 text NOT NULL UNIQUE,
    byte_size bigint NOT NULL
);

CREATE TABLE asset_locations (
    location_id bigserial PRIMARY KEY,
    blob_id bigint NOT NULL REFERENCES asset_blobs,
    relative_path text NOT NULL UNIQUE,
    state text NOT NULL CHECK (state IN ('downloaded','original','processed','delivery'))
);

CREATE TABLE asset_links (
    asset_link_id bigserial PRIMARY KEY,
    blob_id bigint NOT NULL REFERENCES asset_blobs,
    provider_project_id bigint REFERENCES provider_projects,
    source_record_id bigint REFERENCES source_records,
    derived_from_location_id bigint REFERENCES asset_locations,
    role text NOT NULL,
    CHECK (provider_project_id IS NOT NULL OR source_record_id IS NOT NULL)
);

CREATE TABLE extractions (
    extraction_id bigserial PRIMARY KEY,
    source_record_id bigint NOT NULL REFERENCES source_records,
    extraction_version text NOT NULL,
    UNIQUE (source_record_id, extraction_version)
);

CREATE TABLE field_evidence (
    field_evidence_id bigserial PRIMARY KEY,
    extraction_id bigint NOT NULL REFERENCES extractions,
    field_name text NOT NULL,
    raw_value text,
    normalized_value text,
    field_state text NOT NULL
        CHECK (field_state IN ('value','explicitly_empty','not_provided','extraction_failed')),
    confidence numeric(6,5),
    evidence_location text NOT NULL,
    review_status text NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending','confirmed','rejected')),
    UNIQUE (extraction_id, field_name)
);

CREATE TABLE manual_overrides (
    override_id bigserial PRIMARY KEY,
    entity_kind text NOT NULL CHECK (entity_kind IN ('source_record','provider_project','offering')),
    entity_id bigint NOT NULL,
    field_name text NOT NULL,
    old_value text,
    new_value text NOT NULL,
    basis_version text NOT NULL,
    reason text NOT NULL,
    author text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    reverted_by bigint REFERENCES manual_overrides
);

CREATE TABLE conflicts (
    conflict_id bigserial PRIMARY KEY,
    source_record_id bigint NOT NULL REFERENCES source_records,
    order_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conflict_members (
    conflict_id bigint NOT NULL REFERENCES conflicts,
    observation_id bigint NOT NULL REFERENCES observations,
    UNIQUE (conflict_id, observation_id)
);

CREATE TABLE quality_issues (
    issue_id bigserial PRIMARY KEY,
    entity_kind text NOT NULL,
    entity_id bigint NOT NULL,
    severity text NOT NULL CHECK (severity IN ('P0','P1','P2')),
    description text NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','wontfix'))
);

CREATE TABLE identity_links (
    identity_link_id bigserial PRIMARY KEY,
    action text NOT NULL CHECK (action IN ('merge','split')),
    from_provider_project_id bigint REFERENCES provider_projects,
    to_provider_project_id bigint REFERENCES provider_projects,
    basis text NOT NULL,
    author text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE legacy_id_map (
    legacy_table text NOT NULL,
    legacy_id text NOT NULL,
    new_table text NOT NULL,
    new_id text NOT NULL,
    PRIMARY KEY (legacy_table, legacy_id, new_table)
);
