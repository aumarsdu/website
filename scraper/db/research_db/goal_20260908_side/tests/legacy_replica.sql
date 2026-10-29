-- tests/legacy_replica.sql — representative copy of the pre-2026-09-08 schema (subset)
-- Loads into schema legacy_replica so the new model (public) never collides.
-- Documented deviations from db/research_db/schema.sql: users FK columns kept as plain
-- uuid columns (no users table in the representative subset); enums recreated locally.

CREATE SCHEMA IF NOT EXISTS legacy_replica;

CREATE TYPE legacy_replica.risk_level AS ENUM ('low','medium','high');
CREATE TYPE legacy_replica.project_status AS ENUM ('imported','searchable','published');
CREATE TYPE legacy_replica.readiness_level AS ENUM ('raw','cleaned','searchable');
CREATE TYPE legacy_replica.staleness_status AS ENUM ('fresh','stale','unknown');

CREATE TABLE legacy_replica.providers (
  id uuid PRIMARY KEY,
  code text UNIQUE,
  name text NOT NULL,
  provider_type text,
  cooperation_status text NOT NULL DEFAULT 'candidate',
  risk_level legacy_replica.risk_level DEFAULT 'medium',
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE legacy_replica.sources (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  base_url text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE legacy_replica.ingest_batches (
  id uuid PRIMARY KEY,
  source_id uuid REFERENCES legacy_replica.sources(id),
  batch_code text UNIQUE,
  input_path text NOT NULL,
  input_format text,
  started_at timestamptz,
  finished_at timestamptz,
  stats_json jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE legacy_replica.source_project_records (
  id uuid PRIMARY KEY,
  source_id uuid REFERENCES legacy_replica.sources(id),
  source_record_key text NOT NULL,
  latest_title_raw text,
  record_status text DEFAULT 'active',
  first_seen_at timestamptz,
  latest_seen_at timestamptz,
  UNIQUE (source_id, source_record_key)
);

CREATE TABLE legacy_replica.source_project_record_versions (
  id uuid PRIMARY KEY,
  source_project_record_id uuid NOT NULL REFERENCES legacy_replica.source_project_records(id),
  ingest_batch_id uuid NOT NULL REFERENCES legacy_replica.ingest_batches(id),
  version integer NOT NULL,
  source_url text,
  title_raw text,
  raw_hash text NOT NULL,
  crawled_at timestamptz,
  UNIQUE (source_project_record_id, version),
  UNIQUE (source_project_record_id, raw_hash)
);

CREATE TABLE legacy_replica.canonical_projects (
  id uuid PRIMARY KEY,
  provider_id uuid REFERENCES legacy_replica.providers(id),
  title text NOT NULL,
  status legacy_replica.project_status NOT NULL DEFAULT 'imported',
  readiness legacy_replica.readiness_level NOT NULL DEFAULT 'searchable',
  primary_source_record_id uuid REFERENCES legacy_replica.source_project_records(id)
);

CREATE TABLE legacy_replica.project_source_links (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES legacy_replica.canonical_projects(id),
  source_project_record_id uuid REFERENCES legacy_replica.source_project_records(id),
  created_at timestamptz DEFAULT now()
);

CREATE TABLE legacy_replica.project_offerings (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES legacy_replica.canonical_projects(id),
  offering_code text,
  duration text,
  start_date_text text,
  start_date date,
  delivery_mode text,
  price_amount numeric(12,2),
  price_currency text DEFAULT 'CNY',
  staleness_status legacy_replica.staleness_status DEFAULT 'unknown'
);

-- representative rows: 1 provider, 2 sources, 2 batches, 3 records, 4 versions (A→B→A on rec 1)
INSERT INTO legacy_replica.providers (id, code, name, provider_type, cooperation_status, risk_level)
VALUES ('00000000-0000-0000-0000-000000000001', 'jisi', '集思未来', 'agency', 'active', 'low');

INSERT INTO legacy_replica.sources (id, code, name, base_url) VALUES
  ('10000000-0000-0000-0000-000000000001', 'jisi_sou_tools', '集思海外', 'https://example.com/sou'),
  ('10000000-0000-0000-0000-000000000002', 'jisi_domestic', '集思国内', 'https://example.com/dom');

INSERT INTO legacy_replica.ingest_batches (id, source_id, batch_code, input_path, input_format, started_at, finished_at, stats_json) VALUES
  ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'batch-20260602-sou', '/data/20260602/sou.jsonl', 'jsonl', '2026-06-02T07:52:16Z', '2026-06-02T07:53:00Z', '{"rows": 3}'),
  ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'batch-20260703-sou', '/data/20260703/sou.jsonl', 'jsonl', '2026-07-03T09:55:05Z', '2026-07-03T09:56:00Z', '{"rows": 3}');

INSERT INTO legacy_replica.source_project_records (id, source_id, source_record_key, latest_title_raw, first_seen_at, latest_seen_at) VALUES
  ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'JS-001', '项目A', '2026-06-02T07:52:16Z', '2026-07-03T09:55:05Z'),
  ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 'JS-002', '项目B', '2026-06-02T07:52:16Z', '2026-06-02T07:52:16Z'),
  ('30000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000002', 'DM-001', '国内项目', '2026-06-02T08:12:22Z', '2026-06-02T08:12:22Z');

INSERT INTO legacy_replica.source_project_record_versions
  (id, source_project_record_id, ingest_batch_id, version, source_url, title_raw, raw_hash, crawled_at) VALUES
  ('40000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 1, 'https://example.com/p/1', '项目A', 'hashA1', '2026-06-02T07:52:16Z'),
  ('40000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 2, 'https://example.com/p/1', '项目B', 'hashB',  '2026-07-03T09:55:05Z'),
  ('40000000-0000-0000-0000-000000000003', '30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 3, 'https://example.com/p/1', '项目A', 'hashA1b','2026-07-03T09:55:30Z'),
  ('40000000-0000-0000-0000-000000000004', '30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000001', 1, 'https://example.com/p/2', '项目B', 'hashA2', '2026-06-02T07:52:16Z');

INSERT INTO legacy_replica.canonical_projects (id, provider_id, title, status, readiness, primary_source_record_id) VALUES
  ('50000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '项目A', 'searchable', 'searchable', '30000000-0000-0000-0000-000000000001'),
  ('50000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', '国内项目', 'imported', 'raw', '30000000-0000-0000-0000-000000000003');

INSERT INTO legacy_replica.project_source_links (id, canonical_project_id, source_project_record_id) VALUES
  ('60000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001'),
  ('60000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000002'),
  ('60000000-0000-0000-0000-000000000003', '50000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000003');

INSERT INTO legacy_replica.project_offerings
  (id, canonical_project_id, offering_code, duration, start_date_text, start_date, delivery_mode, price_amount, price_currency) VALUES
  ('70000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 'OFF-A1', '10-12周', '2026-06-15', '2026-06-15', 'online', 12000.00, 'CNY'),
  ('70000000-0000-0000-0000-000000000002', '50000000-0000-0000-0000-000000000001', 'OFF-A2', '10-12周', '2026年7月', NULL, 'onsite', NULL, 'CNY');
