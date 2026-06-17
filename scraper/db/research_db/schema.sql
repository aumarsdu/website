-- Research project database schema.
-- PostgreSQL DDL aligned with the Design Spec and Implementation Plan.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_status') THEN
    CREATE TYPE project_status AS ENUM ('imported', 'normalized', 'draft', 'review_pending', 'approved', 'published', 'archived');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'display_status') THEN
    CREATE TYPE display_status AS ENUM ('draft', 'review_pending', 'approved', 'published', 'archived');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_status') THEN
    CREATE TYPE review_status AS ENUM ('draft', 'pending', 'approved', 'rejected');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_level') THEN
    CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'readiness_level') THEN
    CREATE TYPE readiness_level AS ENUM ('searchable', 'display_draft_ready', 'review_ready', 'publish_ready');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'asset_type') THEN
    CREATE TYPE asset_type AS ENUM ('dn_poster', 'instructor_avatar', 'pdf', 'image', 'document', 'other');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'usage_rights_status') THEN
    CREATE TYPE usage_rights_status AS ENUM ('unknown', 'internal_only', 'approved', 'rejected');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'staleness_status') THEN
    CREATE TYPE staleness_status AS ENUM ('fresh', 'due_for_review', 'stale', 'unknown');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'field_source_type') THEN
    CREATE TYPE field_source_type AS ENUM ('source_imported', 'normalized', 'manual', 'generated', 'reviewed', 'published');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'merge_status') THEN
    CREATE TYPE merge_status AS ENUM ('open', 'confirmed', 'rejected', 'ignored');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_status') THEN
    CREATE TYPE task_status AS ENUM ('open', 'in_progress', 'completed', 'cancelled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'claim_type') THEN
    CREATE TYPE claim_type AS ENUM ('guaranteed', 'conditional', 'prohibited');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rights_scope_status') THEN
    CREATE TYPE rights_scope_status AS ENUM ('unknown', 'approved', 'rejected', 'expired', 'revoked');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'price_visibility_policy') THEN
    CREATE TYPE price_visibility_policy AS ENUM ('internal_only', 'show_range', 'show_exact', 'quote_required');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY,
  email text UNIQUE,
  name text,
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_roles (
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  role_id uuid REFERENCES roles(id) ON DELETE CASCADE,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS lookup_terms (
  id uuid PRIMARY KEY,
  term_group text NOT NULL,
  code text NOT NULL,
  label text NOT NULL,
  label_en text,
  sort_order integer DEFAULT 0,
  is_active boolean DEFAULT true,
  metadata_json jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (term_group, code)
);

CREATE TABLE IF NOT EXISTS sources (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,
  name text NOT NULL,
  base_url text,
  source_type text,
  notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS providers (
  id uuid PRIMARY KEY,
  code text UNIQUE,
  name text NOT NULL,
  provider_type text,
  country text,
  website_url text,
  cooperation_status text NOT NULL DEFAULT 'candidate',
  authorization_status text NOT NULL DEFAULT 'unknown',
  risk_level risk_level DEFAULT 'medium',
  rights_notes text,
  is_active boolean DEFAULT true,
  owner_user_id uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provider_contracts (
  id uuid PRIMARY KEY,
  provider_id uuid NOT NULL REFERENCES providers(id),
  contract_code text,
  cooperation_status text NOT NULL,
  authorization_scope text[] DEFAULT '{}',
  settlement_mode text,
  settlement_cycle text,
  refund_policy text,
  complaint_policy text,
  sla_response_hours integer,
  sla_delivery_notes text,
  valid_from date,
  valid_until date,
  evidence_asset_id uuid,
  rights_notes text,
  review_status review_status DEFAULT 'draft',
  created_by uuid REFERENCES users(id),
  reviewed_by uuid REFERENCES users(id),
  reviewed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provider_performance_metrics (
  id uuid PRIMARY KEY,
  provider_id uuid NOT NULL REFERENCES providers(id),
  metric_period_start date NOT NULL,
  metric_period_end date NOT NULL,
  project_count integer DEFAULT 0,
  recommendation_count integer DEFAULT 0,
  deal_count integer DEFAULT 0,
  refund_count integer DEFAULT 0,
  complaint_count integer DEFAULT 0,
  average_satisfaction numeric(4,2),
  on_time_delivery_rate numeric(5,4),
  response_sla_hit_rate numeric(5,4),
  gross_margin_amount numeric(12,2),
  currency text DEFAULT 'CNY',
  notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (provider_id, metric_period_start, metric_period_end)
);

CREATE TABLE IF NOT EXISTS ingest_batches (
  id uuid PRIMARY KEY,
  source_id uuid REFERENCES sources(id),
  batch_code text UNIQUE,
  input_path text NOT NULL,
  input_format text,
  imported_by uuid REFERENCES users(id),
  started_at timestamptz,
  finished_at timestamptz,
  stats_json jsonb NOT NULL DEFAULT '{}',
  error_json jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_project_records (
  id uuid PRIMARY KEY,
  source_id uuid REFERENCES sources(id),
  source_record_key text NOT NULL,
  latest_source_url text,
  latest_canonical_url text,
  latest_title_raw text,
  latest_raw_hash text,
  latest_version_id uuid,
  record_status text DEFAULT 'active',
  first_seen_at timestamptz,
  latest_seen_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (source_id, source_record_key)
);

CREATE TABLE IF NOT EXISTS source_project_record_versions (
  id uuid PRIMARY KEY,
  source_project_record_id uuid NOT NULL REFERENCES source_project_records(id),
  ingest_batch_id uuid NOT NULL REFERENCES ingest_batches(id),
  version integer NOT NULL,
  source_url text,
  canonical_url text,
  title_raw text,
  raw_json jsonb NOT NULL,
  raw_hash text NOT NULL,
  redaction_status text DEFAULT 'none',
  redaction_reason text,
  tombstoned_at timestamptz,
  crawled_at timestamptz,
  created_at timestamptz DEFAULT now(),
  UNIQUE (source_project_record_id, version),
  UNIQUE (source_project_record_id, raw_hash)
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'source_project_records_latest_version_fk'
  ) THEN
    ALTER TABLE source_project_records
      ADD CONSTRAINT source_project_records_latest_version_fk
      FOREIGN KEY (latest_version_id)
      REFERENCES source_project_record_versions(id)
      DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS canonical_projects (
  id uuid PRIMARY KEY,
  provider_id uuid REFERENCES providers(id),
  title text NOT NULL,
  title_normalized text,
  project_type text,
  topic_info text,
  canonical_summary text,
  status project_status NOT NULL DEFAULT 'imported',
  readiness readiness_level NOT NULL DEFAULT 'searchable',
  primary_source_record_id uuid REFERENCES source_project_records(id),
  current_display_profile_id uuid,
  created_by uuid REFERENCES users(id),
  updated_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_source_links (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  source_project_record_id uuid REFERENCES source_project_records(id),
  link_type text,
  confidence numeric(5,4),
  created_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  UNIQUE (canonical_project_id, source_project_record_id)
);

CREATE TABLE IF NOT EXISTS project_links (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  link_type text NOT NULL,
  url text NOT NULL,
  label text,
  rights_notes text,
  last_verified_at timestamptz,
  valid_until timestamptz,
  staleness_status staleness_status DEFAULT 'unknown',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_offerings (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  offering_code text,
  duration text,
  start_date_text text,
  start_date date,
  end_date date,
  delivery_mode text,
  delivery_country text,
  capacity integer,
  enrollment_status text,
  price_amount numeric(12,2),
  price_currency text DEFAULT 'CNY',
  last_verified_at timestamptz,
  valid_until timestamptz,
  staleness_status staleness_status DEFAULT 'unknown',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_commercial_profiles (
  canonical_project_id uuid PRIMARY KEY REFERENCES canonical_projects(id),
  provider_cost_amount numeric(12,2),
  list_price_amount numeric(12,2),
  suggested_sale_price_amount numeric(12,2),
  min_sale_price_amount numeric(12,2),
  currency text DEFAULT 'CNY',
  commission_rate numeric(5,4),
  gross_margin_rate numeric(5,4),
  gross_margin_amount numeric(12,2),
  settlement_mode text,
  settlement_notes text,
  refund_liability_party text,
  discount_approval_required boolean DEFAULT true,
  price_visibility_policy price_visibility_policy DEFAULT 'internal_only',
  commercial_priority integer,
  valid_until timestamptz,
  review_status review_status DEFAULT 'draft',
  created_by uuid REFERENCES users(id),
  updated_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS institutions (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  name_normalized text,
  name_en text,
  country text,
  website_url text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (name_normalized, country)
);

CREATE TABLE IF NOT EXISTS instructors (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  name_normalized text,
  institution_id uuid REFERENCES institutions(id),
  institution_name_raw text,
  academic_title text,
  country text,
  bio_raw text,
  bio_edited text,
  paper_guidance_scope text,
  avatar_asset_id uuid,
  usage_rights_status usage_rights_status DEFAULT 'unknown',
  takedown_requested_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_instructors (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  instructor_id uuid REFERENCES instructors(id),
  role text DEFAULT 'primary',
  confidence numeric(5,4),
  created_at timestamptz DEFAULT now(),
  UNIQUE (canonical_project_id, instructor_id, role)
);

CREATE TABLE IF NOT EXISTS taxonomy_terms (
  id uuid PRIMARY KEY,
  term_type text NOT NULL,
  name text NOT NULL,
  name_en text,
  slug text,
  parent_id uuid REFERENCES taxonomy_terms(id),
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  UNIQUE (term_type, name)
);

CREATE TABLE IF NOT EXISTS taxonomy_aliases (
  id uuid PRIMARY KEY,
  taxonomy_term_id uuid REFERENCES taxonomy_terms(id),
  alias text NOT NULL,
  alias_type text,
  source_id uuid REFERENCES sources(id),
  confidence numeric(5,4),
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  UNIQUE (alias, alias_type, source_id)
);

CREATE TABLE IF NOT EXISTS taxonomy_change_requests (
  id uuid PRIMARY KEY,
  requested_term_type text NOT NULL,
  requested_name text NOT NULL,
  requested_parent_id uuid REFERENCES taxonomy_terms(id),
  reason text,
  requested_by uuid REFERENCES users(id),
  review_status review_status DEFAULT 'pending',
  reviewed_by uuid REFERENCES users(id),
  reviewed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_taxonomy_links (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  taxonomy_term_id uuid REFERENCES taxonomy_terms(id),
  term_type text NOT NULL,
  confidence numeric(5,4),
  source_type field_source_type,
  created_at timestamptz DEFAULT now(),
  UNIQUE (canonical_project_id, taxonomy_term_id, term_type)
);

CREATE TABLE IF NOT EXISTS major_terms (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  name_en text,
  aliases text[] DEFAULT '{}',
  country_context text,
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS project_major_links (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  major_term_id uuid REFERENCES major_terms(id),
  fit_level text,
  confidence numeric(5,4),
  created_at timestamptz DEFAULT now(),
  UNIQUE (canonical_project_id, major_term_id)
);

CREATE TABLE IF NOT EXISTS project_match_profiles (
  canonical_project_id uuid PRIMARY KEY REFERENCES canonical_projects(id),
  suitable_student_directions text[] DEFAULT '{}',
  suitable_grades text[] DEFAULT '{}',
  suitable_majors_cache text[] DEFAULT '{}',
  difficulty_level text,
  prerequisite_courses text[] DEFAULT '{}',
  programming_requirement text,
  math_requirement text,
  lab_requirement text,
  language_requirement text,
  application_goal_fit text[] DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_customer_fit_rules (
  canonical_project_id uuid PRIMARY KEY REFERENCES canonical_projects(id),
  target_countries text[] DEFAULT '{}',
  degree_goals text[] DEFAULT '{}',
  student_stages text[] DEFAULT '{}',
  major_groups text[] DEFAULT '{}',
  grade_band text[] DEFAULT '{}',
  time_window_tags text[] DEFAULT '{}',
  budget_band text,
  required_foundation text[] DEFAULT '{}',
  risk_tolerance text,
  best_fit_rules jsonb NOT NULL DEFAULT '{}',
  poor_fit_rules jsonb NOT NULL DEFAULT '{}',
  weight_json jsonb NOT NULL DEFAULT '{}',
  review_status review_status DEFAULT 'draft',
  created_by uuid REFERENCES users(id),
  updated_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_sales_profiles (
  canonical_project_id uuid PRIMARY KEY REFERENCES canonical_projects(id),
  one_liner text,
  customer_pain_points text[] DEFAULT '{}',
  key_selling_points text[] DEFAULT '{}',
  sales_script text,
  faq_json jsonb NOT NULL DEFAULT '[]',
  objection_handling_json jsonb NOT NULL DEFAULT '[]',
  case_notes text,
  comparison_notes text,
  recommended_scenarios text[] DEFAULT '{}',
  not_recommended_scenarios text[] DEFAULT '{}',
  forbidden_claims text[] DEFAULT '{}',
  display_material_notes text,
  training_notes text,
  review_status review_status DEFAULT 'draft',
  created_by uuid REFERENCES users(id),
  updated_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_deliverable_claims (
  id uuid PRIMARY KEY,
  canonical_project_id uuid NOT NULL REFERENCES canonical_projects(id),
  claim_type claim_type NOT NULL,
  claim_text text NOT NULL,
  condition_text text,
  evidence_source text,
  evidence_asset_id uuid,
  allowed_for_sales boolean DEFAULT false,
  allowed_for_public boolean DEFAULT false,
  review_status review_status DEFAULT 'pending',
  reviewed_by uuid REFERENCES users(id),
  reviewed_at timestamptz,
  created_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_ops (
  canonical_project_id uuid PRIMARY KEY REFERENCES canonical_projects(id),
  priority integer,
  owner_user_id uuid REFERENCES users(id),
  internal_notes text,
  sales_positioning text,
  ops_flags text[] DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assets (
  id uuid PRIMARY KEY,
  asset_type asset_type NOT NULL,
  source_url text,
  asset_uri text,
  file_name text,
  content_type text,
  bytes bigint,
  sha256 text,
  manifest_key text,
  usage_rights_status usage_rights_status DEFAULT 'unknown',
  rights_notes text,
  takedown_requested_at timestamptz,
  takedown_reason text,
  last_verified_at timestamptz,
  valid_until timestamptz,
  staleness_status staleness_status DEFAULT 'unknown',
  raw_json jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS assets_sha256_unique_idx ON assets (sha256) WHERE sha256 IS NOT NULL;

CREATE TABLE IF NOT EXISTS asset_links (
  id uuid PRIMARY KEY,
  asset_id uuid NOT NULL REFERENCES assets(id),
  canonical_project_id uuid REFERENCES canonical_projects(id),
  instructor_id uuid REFERENCES instructors(id),
  provider_id uuid REFERENCES providers(id),
  source_project_record_id uuid REFERENCES source_project_records(id),
  link_role text NOT NULL,
  is_primary boolean DEFAULT false,
  source_evidence_json jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS asset_links_project_unique_idx
  ON asset_links (asset_id, canonical_project_id, link_role)
  WHERE canonical_project_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS asset_links_instructor_unique_idx
  ON asset_links (asset_id, instructor_id, link_role)
  WHERE instructor_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS asset_links_provider_unique_idx
  ON asset_links (asset_id, provider_id, link_role)
  WHERE provider_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS asset_links_source_record_unique_idx
  ON asset_links (asset_id, source_project_record_id, link_role)
  WHERE source_project_record_id IS NOT NULL AND canonical_project_id IS NULL;

CREATE TABLE IF NOT EXISTS rights_scopes (
  id uuid PRIMARY KEY,
  subject_type text NOT NULL,
  subject_id uuid NOT NULL,
  scope_code text NOT NULL,
  scope_status rights_scope_status NOT NULL DEFAULT 'unknown',
  evidence_source text,
  evidence_asset_id uuid REFERENCES assets(id),
  valid_from date,
  valid_until date,
  reviewed_by uuid REFERENCES users(id),
  reviewed_at timestamptz,
  notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (subject_type, subject_id, scope_code)
);

CREATE TABLE IF NOT EXISTS project_display_profiles (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  version integer NOT NULL,
  public_slug text UNIQUE,
  status display_status NOT NULL DEFAULT 'draft',
  display_title text,
  card_summary text,
  project_summary text,
  topic_information_display text,
  research_question text,
  research_method text,
  expected_outputs text,
  instructor_bio_display text,
  suitable_for_display text,
  show_price boolean DEFAULT false,
  published_at timestamptz,
  created_by uuid REFERENCES users(id),
  updated_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (canonical_project_id, version)
);

CREATE TABLE IF NOT EXISTS field_review_states (
  id uuid PRIMARY KEY,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  field_name text NOT NULL,
  proposed_value_json jsonb,
  current_value_json jsonb,
  review_status review_status NOT NULL DEFAULT 'draft',
  risk_level risk_level NOT NULL,
  reviewer_role text,
  submitted_by uuid REFERENCES users(id),
  reviewed_by uuid REFERENCES users(id),
  reviewed_at timestamptz,
  comment text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS field_provenance (
  id uuid PRIMARY KEY,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  field_name text NOT NULL,
  source_type field_source_type NOT NULL,
  source_project_record_id uuid REFERENCES source_project_records(id),
  confidence numeric(5,4),
  source_path text,
  notes text,
  created_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS merge_candidates (
  id uuid PRIMARY KEY,
  left_project_id uuid REFERENCES canonical_projects(id),
  right_project_id uuid REFERENCES canonical_projects(id),
  similarity_score numeric(5,4),
  evidence_json jsonb NOT NULL DEFAULT '{}',
  status merge_status NOT NULL DEFAULT 'open',
  reviewed_by uuid REFERENCES users(id),
  reviewed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  UNIQUE (left_project_id, right_project_id),
  CHECK (left_project_id IS NULL OR right_project_id IS NULL OR left_project_id < right_project_id)
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  source_project_record_id uuid REFERENCES source_project_records(id),
  issue_type text NOT NULL,
  severity text NOT NULL,
  field_name text,
  description text,
  status task_status NOT NULL DEFAULT 'open',
  created_at timestamptz DEFAULT now(),
  resolved_at timestamptz
);

CREATE TABLE IF NOT EXISTS enrichment_tasks (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  task_type text NOT NULL,
  field_name text,
  assigned_role text,
  assigned_user_id uuid REFERENCES users(id),
  status task_status NOT NULL DEFAULT 'open',
  due_at timestamptz,
  created_at timestamptz DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS verification_tasks (
  id uuid PRIMARY KEY,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  field_name text,
  verification_reason text,
  status task_status NOT NULL DEFAULT 'open',
  assigned_user_id uuid REFERENCES users(id),
  due_at timestamptz,
  created_at timestamptz DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS change_events (
  id uuid PRIMARY KEY,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  action text NOT NULL,
  actor_id uuid REFERENCES users(id),
  before_json jsonb,
  after_json jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_usage_events (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  user_id uuid REFERENCES users(id),
  event_type text NOT NULL,
  event_context_json jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendation_logs (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  recommended_by uuid REFERENCES users(id),
  customer_context_json jsonb NOT NULL DEFAULT '{}',
  recommendation_reason text,
  fit_score numeric(5,2),
  risk_notes text,
  outcome_status text DEFAULT 'pending',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_order_feedback (
  id uuid PRIMARY KEY,
  canonical_project_id uuid REFERENCES canonical_projects(id),
  provider_id uuid REFERENCES providers(id),
  recommendation_log_id uuid REFERENCES recommendation_logs(id),
  feedback_type text NOT NULL,
  deal_status text,
  lost_reason text,
  delivery_status text,
  complaint_flag boolean DEFAULT false,
  refund_flag boolean DEFAULT false,
  satisfaction_score integer,
  public_case_allowed boolean DEFAULT false,
  feedback_notes text,
  created_by uuid REFERENCES users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_project_records_source_key_idx ON source_project_records(source_id, source_record_key);
CREATE INDEX IF NOT EXISTS canonical_projects_provider_status_idx ON canonical_projects(provider_id, status, readiness);
CREATE INDEX IF NOT EXISTS canonical_projects_title_trgm_idx ON canonical_projects USING gin(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS project_offerings_project_status_start_idx ON project_offerings(canonical_project_id, enrollment_status, start_date);
CREATE INDEX IF NOT EXISTS project_offerings_price_idx ON project_offerings(price_amount);
CREATE INDEX IF NOT EXISTS project_commercial_profiles_priority_margin_idx ON project_commercial_profiles(commercial_priority, gross_margin_rate);
CREATE INDEX IF NOT EXISTS project_deliverable_claims_project_type_status_idx ON project_deliverable_claims(canonical_project_id, claim_type, review_status);
CREATE INDEX IF NOT EXISTS assets_asset_type_idx ON assets(asset_type);
CREATE INDEX IF NOT EXISTS asset_links_project_role_idx ON asset_links(canonical_project_id, link_role);
CREATE INDEX IF NOT EXISTS asset_links_instructor_role_idx ON asset_links(instructor_id, link_role);
CREATE INDEX IF NOT EXISTS rights_scopes_subject_scope_status_idx ON rights_scopes(subject_type, subject_id, scope_code, scope_status);
CREATE INDEX IF NOT EXISTS project_display_profiles_status_published_idx ON project_display_profiles(status, published_at);
CREATE INDEX IF NOT EXISTS field_review_states_status_risk_idx ON field_review_states(review_status, risk_level);
CREATE INDEX IF NOT EXISTS merge_candidates_status_similarity_idx ON merge_candidates(status, similarity_score);
CREATE INDEX IF NOT EXISTS taxonomy_terms_type_name_idx ON taxonomy_terms(term_type, name);
CREATE INDEX IF NOT EXISTS taxonomy_aliases_alias_type_idx ON taxonomy_aliases(alias, alias_type);
CREATE INDEX IF NOT EXISTS project_taxonomy_links_project_type_idx ON project_taxonomy_links(canonical_project_id, term_type);
CREATE INDEX IF NOT EXISTS project_major_links_project_major_idx ON project_major_links(canonical_project_id, major_term_id);
CREATE INDEX IF NOT EXISTS project_usage_events_project_type_created_idx ON project_usage_events(canonical_project_id, event_type, created_at);
CREATE INDEX IF NOT EXISTS recommendation_logs_project_outcome_idx ON recommendation_logs(canonical_project_id, outcome_status);
CREATE INDEX IF NOT EXISTS project_order_feedback_project_type_created_idx ON project_order_feedback(canonical_project_id, feedback_type, created_at);

CREATE OR REPLACE VIEW ops_project_cards AS
SELECT
  p.id,
  p.title,
  p.status,
  p.readiness,
  p.provider_id,
  pr.name AS provider_name,
  o.duration,
  o.start_date_text,
  o.enrollment_status,
  d.status AS display_status,
  COALESCE(array_length(pm.suitable_grades, 1), 0) AS suitable_grade_count
FROM canonical_projects p
LEFT JOIN providers pr ON pr.id = p.provider_id
LEFT JOIN project_offerings o ON o.canonical_project_id = p.id
LEFT JOIN project_display_profiles d ON d.canonical_project_id = p.id AND d.version = 1
LEFT JOIN project_match_profiles pm ON pm.canonical_project_id = p.id;

CREATE OR REPLACE VIEW public_project_cards AS
SELECT
  d.public_slug,
  d.display_title,
  d.card_summary,
  p.project_type,
  p.provider_id,
  d.published_at
FROM project_display_profiles d
JOIN canonical_projects p ON p.id = d.canonical_project_id
WHERE d.status = 'published' AND p.status = 'published';

CREATE OR REPLACE VIEW public_project_details AS
SELECT
  d.public_slug,
  d.display_title,
  d.project_summary,
  d.topic_information_display,
  d.research_question,
  d.research_method,
  d.expected_outputs,
  d.instructor_bio_display,
  d.suitable_for_display,
  d.published_at
FROM project_display_profiles d
JOIN canonical_projects p ON p.id = d.canonical_project_id
WHERE d.status = 'published' AND p.status = 'published';
