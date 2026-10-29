# Research Project Database Implementation Plan

Date: 2026-06-02

Related design:
`docs/superpowers/specs/2026-06-02-research-project-database-design.md`

## 1. Execution Summary

Phase 1 builds Route B as the foundation for Route C, but Phase 1 is split into
three release slices:

1. Phase 1A: internal sales operations MVP.
2. Phase 1B: review and public display.
3. Phase 1C: deal and delivery feedback loop.

The first usable release must help customer operations and sales teams search,
match, compare, explain, and risk-check research project SKUs. Public API work
is intentionally placed after the internal operations MVP.

The implementation must deliver:

1. PostgreSQL DDL and migrations.
2. Source-specific import adapters for current datasets.
3. Internal operations APIs for search, matching, supplier operations,
   commercial pricing, sales materials, rights scope, and claims control.
4. Field-level review, supplier authorization checks, commercial review, and
   project-level publishing flow.
5. Public display APIs that use allowlist projections only, released after
   Phase 1A.
6. Deal, recommendation, usage, and delivery feedback capture for Phase 1C.
7. Data quality, provenance, freshness, source versions, rights, and RBAC
   controls.
8. Tests that prove import safety, query behavior, business rules, review gates,
   and public data isolation.

Implementation should not build automatic partner sync, CRM integration, complex
recommendation, full CMS, payment, enrollment, or full contract workflow
automation in Phase 1. Phase 1A still needs supplier operating records,
commercial pricing, sales materials, customer-fit rules, and deliverable claims
because these are required for internal use.

## 2. Workstreams

| Workstream | Output | Owner Role |
| --- | --- | --- |
| DDL and migrations | PostgreSQL schema, indexes, enums, views | Backend/database |
| Import mapping | Source adapters and quality reports | Data/backend |
| Internal operations MVP | Search, detail, supplier, commercial, sales, fit, claims endpoints | Backend/product |
| Review workflow | Field review, sales claim review, supplier authorization, publish gates, RBAC checks | Backend/product |
| Public APIs | Published-only project list/detail projections after Phase 1A | Backend/frontend |
| Feedback loop | Usage, recommendation, deal/lost, delivery, complaint, refund, satisfaction capture | Backend/ops |
| Testing | Unit, integration, import, business rule, security, API contract tests | QA/backend |
| Documentation | Runbook, import guide, schema notes | Backend/ops |

## 3. DDL Plan

### 3.1 Migration Order

Use small ordered migrations so failures are easy to isolate:

1. `001_extensions_enums.sql`
   PostgreSQL extensions, enum types, common status values.

2. `002_identity_rbac.sql`
   Users, roles, user-role links.

3. `003_sources_providers.sql`
   Sources, providers, ingest batches.

4. `004_core_projects.sql`
   Source records, canonical projects, source links, project links, offerings.

5. `005_people_taxonomy.sql`
   Institutions, instructors, project-instructor links, taxonomy terms, major
   terms, taxonomy links.

6. `006_business_ops.sql`
   Match profiles, operations fields, supplier operations, commercial profiles,
   sales profiles, customer-fit rules, deliverable claims.

7. `007_assets_rights.sql`
   Deduplicated assets, asset links, rights scopes, takedown and freshness
   fields.

8. `008_display_review_workflow.sql`
   Display profiles, field provenance, review states, merge candidates, quality
   issues, enrichment tasks, verification tasks, change events.

9. `009_feedback_analytics.sql`
   Project usage events, recommendation logs, order feedback, provider
   performance metrics.

10. `010_views_indexes.sql`
   Operations search documents, public projections, business dashboards, indexes.

### 3.2 Extensions

Required:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

`pgvector` is deferred to Phase 3.

### 3.3 Core Enums and Lookup Tables

Use PostgreSQL enums only for stable technical states. Use constrained lookup
tables for business-changing values such as supplier cooperation status,
settlement mode, sales scenario, price visibility, claim category, student
stage, and provider risk reason. This avoids migration churn when operations
language changes.

Create enums or constrained lookup tables for:

```text
project_status:
  imported, normalized, draft, review_pending, approved, published, archived

display_status:
  draft, review_pending, approved, published, archived

review_status:
  draft, pending, approved, rejected

risk_level:
  low, medium, high

readiness_level:
  searchable, display_draft_ready, review_ready, publish_ready

asset_type:
  dn_poster, instructor_avatar, pdf, image, document, other

usage_rights_status:
  unknown, internal_only, approved, rejected

staleness_status:
  fresh, due_for_review, stale, unknown

field_source_type:
  source_imported, normalized, manual, generated, reviewed, published

merge_status:
  open, confirmed, rejected, ignored

task_status:
  open, in_progress, completed, cancelled

claim_type:
  guaranteed, conditional, prohibited

rights_scope_status:
  unknown, approved, rejected, expired, revoked

price_visibility_policy:
  internal_only, show_range, show_exact, quote_required
```

### 3.4 Table Definitions

This is the intended DDL shape. Exact SQL can be generated from this plan.

#### `lookup_terms`

Business-changing vocabularies that should not become PostgreSQL enums.

```text
id uuid primary key
term_group text not null
code text not null
label text not null
label_en text
sort_order integer default 0
is_active boolean default true
metadata_json jsonb not null default '{}'
created_at timestamptz
updated_at timestamptz
unique(term_group, code)
```

#### `sources`

Stores import/source lineage, not the commercial project provider.

```text
id uuid primary key
code text unique not null
name text not null
base_url text
source_type text
notes text
created_at timestamptz
updated_at timestamptz
```

Seed values:

```text
hirep
jisi_future
jisi_future_domestic
zhongke
```

#### `providers`

Stores the project provider/supplier. Providers are operating entities, not only
display names.

```text
id uuid primary key
code text unique
name text not null
provider_type text
country text
website_url text
cooperation_status text not null default 'candidate'
authorization_status text not null default 'unknown'
risk_level risk_level default 'medium'
rights_notes text
is_active boolean
owner_user_id uuid references users(id)
created_at timestamptz
updated_at timestamptz
```

#### `provider_contracts`

Stores supplier cooperation, authorization, settlement, refund, and SLA terms.
This is an operating record, not a full legal contract system.

```text
id uuid primary key
provider_id uuid not null references providers(id)
contract_code text
cooperation_status text not null
authorization_scope text[] default '{}'
settlement_mode text
settlement_cycle text
refund_policy text
complaint_policy text
sla_response_hours integer
sla_delivery_notes text
valid_from date
valid_until date
evidence_asset_id uuid
rights_notes text
review_status review_status default 'draft'
created_by uuid references users(id)
reviewed_by uuid references users(id)
reviewed_at timestamptz
created_at timestamptz
updated_at timestamptz
```

#### `provider_performance_metrics`

Stores rolling supplier performance indicators. Phase 1C can populate this from
manual feedback before full order-system integration exists.

```text
id uuid primary key
provider_id uuid not null references providers(id)
metric_period_start date not null
metric_period_end date not null
project_count integer default 0
recommendation_count integer default 0
deal_count integer default 0
refund_count integer default 0
complaint_count integer default 0
average_satisfaction numeric(4,2)
on_time_delivery_rate numeric(5,4)
response_sla_hit_rate numeric(5,4)
gross_margin_amount numeric(12,2)
currency text default 'CNY'
notes text
created_at timestamptz
updated_at timestamptz
unique(provider_id, metric_period_start, metric_period_end)
```

#### `ingest_batches`

```text
id uuid primary key
source_id uuid references sources(id)
batch_code text unique
input_path text not null
input_format text
imported_by uuid references users(id)
started_at timestamptz
finished_at timestamptz
stats_json jsonb not null default '{}'
error_json jsonb not null default '{}'
created_at timestamptz
```

#### `source_project_records`

Logical source record identity. Raw immutable snapshots live in
`source_project_record_versions`.

```text
id uuid primary key
source_id uuid references sources(id)
source_record_key text not null
latest_source_url text
latest_canonical_url text
latest_title_raw text
latest_raw_hash text
latest_version_id uuid
record_status text default 'active'
first_seen_at timestamptz
latest_seen_at timestamptz
created_at timestamptz
updated_at timestamptz
unique(source_id, source_record_key)
```

#### `source_project_record_versions`

Immutable source snapshots when the sanitized raw hash changes, tied to the
import batch where the version was observed. This table is the audit trail for
source changes, import drift, and rollback investigation.

```text
id uuid primary key
source_project_record_id uuid not null references source_project_records(id)
ingest_batch_id uuid not null references ingest_batches(id)
version integer not null
source_url text
canonical_url text
title_raw text
raw_json jsonb not null
raw_hash text not null
redaction_status text default 'none'
redaction_reason text
tombstoned_at timestamptz
crawled_at timestamptz
created_at timestamptz
unique(source_project_record_id, version)
unique(source_project_record_id, raw_hash)
```

#### `canonical_projects`

Main internal project entity.

```text
id uuid primary key
provider_id uuid references providers(id)
title text not null
title_normalized text
project_type text
topic_info text
canonical_summary text
status project_status not null default 'imported'
readiness readiness_level not null default 'searchable'
primary_source_record_id uuid references source_project_records(id)
current_display_profile_id uuid
created_by uuid references users(id)
updated_by uuid references users(id)
created_at timestamptz
updated_at timestamptz
```

`current_display_profile_id` is a nullable service-maintained pointer. Avoid a
hard FK cycle in the initial migrations; validate it in service code or add a
deferred FK after `project_display_profiles` exists if the implementation stack
supports it cleanly.

#### `project_source_links`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
source_project_record_id uuid references source_project_records(id)
link_type text
confidence numeric(5,4)
created_by uuid references users(id)
created_at timestamptz
unique(canonical_project_id, source_project_record_id)
```

#### `project_links`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
link_type text not null
url text not null
label text
rights_notes text
last_verified_at timestamptz
valid_until timestamptz
staleness_status staleness_status default 'unknown'
created_at timestamptz
```

`link_type` examples: `web_page`, `course`, `poster_page`, `partner_page`.
Public visibility for links is controlled by `rights_scopes`, not by a boolean
flag on `project_links`.

#### `project_offerings`

Offering/cohort-level availability and delivery fields. Commercial pricing
visibility is controlled by `project_commercial_profiles`, not directly by the
offering row.

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
offering_code text
duration text
start_date_text text
start_date date
end_date date
delivery_mode text
delivery_country text
capacity integer
enrollment_status text
price_amount numeric(12,2)
price_currency text default 'CNY'
last_verified_at timestamptz
valid_until timestamptz
staleness_status staleness_status default 'unknown'
created_at timestamptz
updated_at timestamptz
```

#### `project_commercial_profiles`

Internal commercial pricing and margin control.

```text
canonical_project_id uuid primary key references canonical_projects(id)
provider_cost_amount numeric(12,2)
list_price_amount numeric(12,2)
suggested_sale_price_amount numeric(12,2)
min_sale_price_amount numeric(12,2)
currency text default 'CNY'
commission_rate numeric(5,4)
gross_margin_rate numeric(5,4)
gross_margin_amount numeric(12,2)
settlement_mode text
settlement_notes text
refund_liability_party text
discount_approval_required boolean default true
price_visibility_policy price_visibility_policy default 'internal_only'
commercial_priority integer
valid_until timestamptz
review_status review_status default 'draft'
created_by uuid references users(id)
updated_by uuid references users(id)
created_at timestamptz
updated_at timestamptz
```

#### `institutions`

```text
id uuid primary key
name text not null
name_normalized text
name_en text
country text
website_url text
created_at timestamptz
updated_at timestamptz
unique(name_normalized, country)
```

#### `instructors`

```text
id uuid primary key
name text not null
name_normalized text
institution_id uuid references institutions(id)
institution_name_raw text
academic_title text
country text
bio_raw text
bio_edited text
paper_guidance_scope text
avatar_asset_id uuid
usage_rights_status usage_rights_status default 'unknown'
takedown_requested_at timestamptz
created_at timestamptz
updated_at timestamptz
```

#### `project_instructors`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
instructor_id uuid references instructors(id)
role text default 'primary'
confidence numeric(5,4)
created_at timestamptz
unique(canonical_project_id, instructor_id, role)
```

#### `taxonomy_terms`

```text
id uuid primary key
term_type text not null
name text not null
name_en text
slug text
parent_id uuid references taxonomy_terms(id)
is_active boolean default true
created_at timestamptz
unique(term_type, name)
```

#### `taxonomy_aliases`

Maps source vocabulary and sales vocabulary into controlled taxonomy terms.

```text
id uuid primary key
taxonomy_term_id uuid references taxonomy_terms(id)
alias text not null
alias_type text
source_id uuid references sources(id)
confidence numeric(5,4)
is_active boolean default true
created_at timestamptz
unique(alias, alias_type, source_id)
```

#### `taxonomy_change_requests`

Allows operations to request new disciplines, specializations, project types, or
major terms without directly changing controlled vocabulary.

```text
id uuid primary key
requested_term_type text not null
requested_name text not null
requested_parent_id uuid references taxonomy_terms(id)
reason text
requested_by uuid references users(id)
review_status review_status default 'pending'
reviewed_by uuid references users(id)
reviewed_at timestamptz
created_at timestamptz
updated_at timestamptz
```

Term types include:

```text
primary_discipline
secondary_discipline
specialization
project_type
skill
output_type
student_direction
```

#### `project_taxonomy_links`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
taxonomy_term_id uuid references taxonomy_terms(id)
term_type text not null
confidence numeric(5,4)
source_type field_source_type
created_at timestamptz
unique(canonical_project_id, taxonomy_term_id, term_type)
```

#### `major_terms`

```text
id uuid primary key
name text not null
name_en text
aliases text[] default '{}'
country_context text
is_active boolean default true
created_at timestamptz
unique(name)
```

#### `project_major_links`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
major_term_id uuid references major_terms(id)
fit_level text
confidence numeric(5,4)
created_at timestamptz
unique(canonical_project_id, major_term_id)
```

#### `project_match_profiles`

```text
canonical_project_id uuid primary key references canonical_projects(id)
suitable_student_directions text[] default '{}'
suitable_grades text[] default '{}'
suitable_majors_cache text[] default '{}'
difficulty_level text
prerequisite_courses text[] default '{}'
programming_requirement text
math_requirement text
lab_requirement text
language_requirement text
application_goal_fit text[] default '{}'
created_at timestamptz
updated_at timestamptz
```

#### `project_customer_fit_rules`

Structured matching rules used by customer operations before a full
recommendation engine exists.

```text
canonical_project_id uuid primary key references canonical_projects(id)
target_countries text[] default '{}'
degree_goals text[] default '{}'
student_stages text[] default '{}'
major_groups text[] default '{}'
grade_band text[] default '{}'
time_window_tags text[] default '{}'
budget_band text
required_foundation text[] default '{}'
risk_tolerance text
best_fit_rules jsonb not null default '{}'
poor_fit_rules jsonb not null default '{}'
weight_json jsonb not null default '{}'
review_status review_status default 'draft'
created_by uuid references users(id)
updated_by uuid references users(id)
created_at timestamptz
updated_at timestamptz
```

#### `project_sales_profiles`

Sales enablement content and forbidden claim controls.

```text
canonical_project_id uuid primary key references canonical_projects(id)
one_liner text
customer_pain_points text[] default '{}'
key_selling_points text[] default '{}'
sales_script text
faq_json jsonb not null default '[]'
objection_handling_json jsonb not null default '[]'
case_notes text
comparison_notes text
recommended_scenarios text[] default '{}'
not_recommended_scenarios text[] default '{}'
forbidden_claims text[] default '{}'
display_material_notes text
training_notes text
review_status review_status default 'draft'
created_by uuid references users(id)
updated_by uuid references users(id)
created_at timestamptz
updated_at timestamptz
```

Sales materials should be linked through `asset_links.link_role =
'sales_material'`, not stored as a UUID array.

#### `project_deliverable_claims`

Controls what sales and public display may promise.

```text
id uuid primary key
canonical_project_id uuid not null references canonical_projects(id)
claim_type claim_type not null
claim_text text not null
condition_text text
evidence_source text
evidence_asset_id uuid
allowed_for_sales boolean default false
allowed_for_public boolean default false
review_status review_status default 'pending'
reviewed_by uuid references users(id)
reviewed_at timestamptz
created_by uuid references users(id)
created_at timestamptz
updated_at timestamptz
```

#### `project_ops`

```text
canonical_project_id uuid primary key references canonical_projects(id)
priority integer
owner_user_id uuid references users(id)
internal_notes text
sales_positioning text
ops_flags text[] default '{}'
created_at timestamptz
updated_at timestamptz
```

#### `assets`

```text
id uuid primary key
asset_type asset_type not null
source_url text
asset_uri text
file_name text
content_type text
bytes bigint
sha256 text
manifest_key text
usage_rights_status usage_rights_status default 'unknown'
rights_notes text
takedown_requested_at timestamptz
takedown_reason text
last_verified_at timestamptz
valid_until timestamptz
staleness_status staleness_status default 'unknown'
raw_json jsonb default '{}'
created_at timestamptz
updated_at timestamptz
unique(sha256)
```

#### `asset_links`

Links a deduplicated asset to a project, instructor, provider, or source record.
One asset can have multiple links; each link should represent one relationship.

```text
id uuid primary key
asset_id uuid not null references assets(id)
canonical_project_id uuid references canonical_projects(id)
instructor_id uuid references instructors(id)
provider_id uuid references providers(id)
source_project_record_id uuid references source_project_records(id)
link_role text not null
is_primary boolean default false
source_evidence_json jsonb not null default '{}'
created_at timestamptz
```

Do not rely on one nullable-column unique constraint for `asset_links`; in
PostgreSQL, nulls do not compare equal. Create partial unique indexes per target
type, for example `(asset_id, canonical_project_id, link_role)` where
`canonical_project_id is not null`.

#### `rights_scopes`

Fine-grained rights for assets, display text, providers, instructors, and
project pages. Unknown scope means not allowed outside internal search.

```text
id uuid primary key
subject_type text not null
subject_id uuid not null
scope_code text not null
scope_status rights_scope_status not null default 'unknown'
evidence_source text
evidence_asset_id uuid references assets(id)
valid_from date
valid_until date
reviewed_by uuid references users(id)
reviewed_at timestamptz
notes text
created_at timestamptz
updated_at timestamptz
unique(subject_type, subject_id, scope_code)
```

Because `rights_scopes` uses a generic subject, implementation must add a
service validator or database trigger that verifies `subject_type` and
`subject_id` point to an existing asset, display profile, instructor, provider,
or project. Business tests must cover invalid subjects.

#### `project_display_profiles`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
version integer not null
public_slug text unique
status display_status not null default 'draft'
display_title text
card_summary text
project_summary text
topic_information_display text
research_question text
research_method text
expected_outputs text
instructor_bio_display text
suitable_for_display text
show_price boolean default false
published_at timestamptz
created_by uuid references users(id)
updated_by uuid references users(id)
created_at timestamptz
updated_at timestamptz
unique(canonical_project_id, version)
```

#### `field_review_states`

```text
id uuid primary key
entity_type text not null
entity_id uuid not null
field_name text not null
proposed_value_json jsonb
current_value_json jsonb
review_status review_status not null default 'draft'
risk_level risk_level not null
reviewer_role text
submitted_by uuid references users(id)
reviewed_by uuid references users(id)
reviewed_at timestamptz
comment text
created_at timestamptz
updated_at timestamptz
```

Because `field_review_states` uses a generic reviewed entity, implementation
must add the same subject integrity validation used by `rights_scopes`.

#### `field_provenance`

```text
id uuid primary key
entity_type text not null
entity_id uuid not null
field_name text not null
source_type field_source_type not null
source_project_record_id uuid references source_project_records(id)
confidence numeric(5,4)
source_path text
notes text
created_by uuid references users(id)
created_at timestamptz
```

#### `merge_candidates`

```text
id uuid primary key
left_project_id uuid references canonical_projects(id)
right_project_id uuid references canonical_projects(id)
similarity_score numeric(5,4)
evidence_json jsonb not null default '{}'
status merge_status not null default 'open'
reviewed_by uuid references users(id)
reviewed_at timestamptz
created_at timestamptz
unique(left_project_id, right_project_id)
```

#### `data_quality_issues`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
source_project_record_id uuid references source_project_records(id)
issue_type text not null
severity text not null
field_name text
description text
status task_status not null default 'open'
created_at timestamptz
resolved_at timestamptz
```

#### `enrichment_tasks`

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
task_type text not null
field_name text
assigned_role text
assigned_user_id uuid references users(id)
status task_status not null default 'open'
due_at timestamptz
created_at timestamptz
completed_at timestamptz
```

#### `verification_tasks`

```text
id uuid primary key
entity_type text not null
entity_id uuid not null
field_name text
verification_reason text
status task_status not null default 'open'
assigned_user_id uuid references users(id)
due_at timestamptz
created_at timestamptz
completed_at timestamptz
```

#### `change_events`

```text
id uuid primary key
entity_type text not null
entity_id uuid not null
action text not null
actor_id uuid references users(id)
before_json jsonb
after_json jsonb
created_at timestamptz
```

#### `project_usage_events`

Lightweight internal usage analytics for Phase 1C.

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
user_id uuid references users(id)
event_type text not null
event_context_json jsonb not null default '{}'
created_at timestamptz
```

#### `recommendation_logs`

Records when an operations or sales user recommends a project to a customer
scenario. This is not a full CRM object.

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
recommended_by uuid references users(id)
customer_context_json jsonb not null default '{}'
recommendation_reason text
fit_score numeric(5,2)
risk_notes text
outcome_status text default 'pending'
created_at timestamptz
updated_at timestamptz
```

#### `project_order_feedback`

Manual deal and delivery feedback loop before CRM/order integration.

```text
id uuid primary key
canonical_project_id uuid references canonical_projects(id)
provider_id uuid references providers(id)
recommendation_log_id uuid references recommendation_logs(id)
feedback_type text not null
deal_status text
lost_reason text
delivery_status text
complaint_flag boolean default false
refund_flag boolean default false
satisfaction_score integer
public_case_allowed boolean default false
feedback_notes text
created_by uuid references users(id)
created_at timestamptz
updated_at timestamptz
```

### 3.5 Views and Indexes

Create views:

```text
project_search_documents
ops_project_cards
ops_project_comparison
ops_supplier_scorecards
public_project_cards
public_project_details
```

Important indexes:

```text
source_project_records(source_id, source_record_key)
canonical_projects(provider_id, status, readiness)
canonical_projects using gin(title gin_trgm_ops)
project_offerings(canonical_project_id, enrollment_status, start_date)
project_offerings(price_amount)
project_commercial_profiles(commercial_priority, gross_margin_rate)
project_sales_profiles using gin(key_selling_points)
project_customer_fit_rules using gin(target_countries)
project_customer_fit_rules using gin(major_groups)
project_deliverable_claims(canonical_project_id, claim_type, review_status)
assets(asset_type)
assets(sha256)
asset_links(canonical_project_id, link_role)
asset_links(instructor_id, link_role)
rights_scopes(subject_type, subject_id, scope_code, scope_status)
project_display_profiles(public_slug)
project_display_profiles(status, published_at)
field_review_states(review_status, risk_level)
merge_candidates(status, similarity_score)
taxonomy_terms(term_type, name)
taxonomy_aliases(alias, alias_type)
project_taxonomy_links(canonical_project_id, term_type)
project_major_links(canonical_project_id, major_term_id)
project_usage_events(canonical_project_id, event_type, created_at)
recommendation_logs(canonical_project_id, outcome_status)
project_order_feedback(canonical_project_id, feedback_type, created_at)
```

## 4. Import Mapping Plan

### 4.1 Import Pipeline

Each import run should follow the same sequence:

1. Create `ingest_batches` row.
2. Read source file rows.
3. Reject or redact secret-like fields before writing raw JSON.
4. Upsert `source_project_records` as logical source identities.
5. Insert immutable `source_project_record_versions` when the sanitized raw hash
   changes.
6. Create or update `canonical_projects`.
7. Link source records to canonical projects.
8. Map provider, links, offerings, instructors, institutions, taxonomy, majors,
   match profile, ops fields, assets, asset links, and display draft.
9. Create enrichment tasks for missing supplier, commercial, sales,
   customer-fit, and deliverable-claim fields.
10. Generate `field_provenance`.
11. Generate `data_quality_issues`, `enrichment_tasks`, and duplicate
    candidates.
12. Emit an import quality report.

The import should support dry-run mode:

```text
--dry-run
--source
--input-path
--batch-code
--strict-secrets
--max-records
--report-path
```

### 4.2 Secret Redaction Rules

Reject or redact keys containing:

```text
token
secret
password
cookie
authorization
session
apikey
api_key
access_key
private_key
credential
```

If found in project rows:

- do not print values;
- write a redacted placeholder;
- create a `data_quality_issues` row with `issue_type = secret_like_field`;
- fail the import if `--strict-secrets` is enabled.

### 4.3 Source Mapping: HIREP

Input files:

```text
HIREP/output_pbl_full_20260602/processed/projects.jsonl
HIREP/output_pbl_full_20260602/processed/asset_manifest.jsonl
```

Mapping:

| Target | Source |
| --- | --- |
| `source_project_records.source_record_key` | `business_id`, fallback raw hash |
| `source_project_record_versions.raw_json` | sanitized full row |
| `canonical_projects.title` | `title` |
| `canonical_projects.project_type` | PBL or mapped from raw |
| `providers.name` | HIREP unless explicit provider exists in raw |
| `project_links.web_page` | `source_url`, `canonical_url` |
| `project_offerings.duration` | raw duration if present, otherwise quality issue |
| `project_taxonomy_links.primary_discipline` | `category` |
| `project_taxonomy_links.specialization` | `direction`, `major_name` |
| `instructors.name` | `professor` |
| `institutions.name` | `university` |
| `assets` + `asset_links` | `asset_urls`, `assets`, `direct_assets`, `asset_manifest` |
| `project_display_profiles.display_title` | `title` draft |
| `project_display_profiles.project_summary` | `description` draft |

Special handling:

- `asset_manifest.jsonl` rows map to `assets` and `asset_links`.
- DN poster must only be public if rights are approved.
- Missing duration, price, suitable grade, and offering fields should create
  enrichment tasks, not block import.

### 4.4 Source Mapping: Jisi Future Output

Input:

```text
集思未来/output/processed/records.jsonl
```

Mapping:

| Target | Source |
| --- | --- |
| `source_project_records.source_record_key` | `record_key`, fallback `id`, fallback raw hash |
| `source_project_record_versions.raw_json` | sanitized full row |
| `canonical_projects.title` | `name`, fallback raw title |
| `providers.name` | 集思未来 |
| `project_links.web_page` | `source_url`, `canonical_url` |
| `assets` + `asset_links` | `asset_urls` |

Special handling:

- This source has limited normalized fields.
- Import should create many quality issues and enrichment tasks.
- Records can be `searchable` but usually not `display_draft_ready`.

### 4.5 Source Mapping: Jisi Future Domestic

Input:

```text
集思未来/output_domestic/processed/records.jsonl
```

Mapping:

| Target | Source |
| --- | --- |
| `source_project_records.source_record_key` | `id` |
| `source_project_record_versions.raw_json` | sanitized full row |
| `canonical_projects.title` | `name` |
| `providers.name` | 集思未来 |
| `canonical_projects.project_type` | `types`, `typeId` |
| `project_links.web_page` | `source_share_url` |
| `project_offerings.start_date_text` | `schoolBegins` |
| `project_offerings.duration` | `cycle` |
| `project_taxonomy_links` | `categories`, `types`, `typeId` |
| `project_match_profiles.prerequisite_courses` | `suggestBasics` |
| `project_match_profiles.suitable_grades` | parse from raw/suggest fields where possible |
| `project_match_profiles.difficulty_level` | derived only if explicit or rules exist |
| `instructors.name` | `teacherName` |
| `instructors.academic_title` | `teacherLevel` |
| `institutions.name` | `teacherSchool` |
| `canonical_projects.topic_info` | `courseOutlineDetail`, `projectBackground` |
| `project_display_profiles.project_summary` | `projectBackground` draft |
| `project_display_profiles.expected_outputs` | `output` |
| `assets` + `asset_links` | `asset_urls`, professor avatar if present in raw |

Special handling:

- This is the strongest source for display drafts.
- `schoolBegins` and `cycle` still need freshness metadata.
- `output` can be high-risk if it implies guaranteed publication or acceptance.

### 4.6 Source Mapping: Zhongke

Input:

```text
中科/output/processed/projects.jsonl
```

Mapping:

| Target | Source |
| --- | --- |
| `source_project_records.source_record_key` | `id`, fallback `uuid`, fallback `record_hash` |
| `source_project_record_versions.raw_json` | sanitized full row |
| `canonical_projects.title` | `title` |
| `providers.name` | 中科 |
| `project_links.web_page` | `source_url`, `canonical_url` |
| `project_taxonomy_links` | `category` if non-empty |
| `instructors.name` | `teacher` |
| `institutions.name` | parsed from `university` when clean |
| `instructors.institution_name_raw` | `university` |
| `canonical_projects.topic_info` | `description` |
| `assets` + `asset_links` | `asset_urls` |

Special handling:

- The `university` field may combine school, department, and title.
- Create low-confidence provenance and quality issues for ambiguous parsing.
- Category is currently often empty; missing taxonomy should create enrichment
  tasks.

### 4.7 Duplicate Candidate Rules

Create candidate only, never automatic merge.

Candidate signals:

```text
exact source key match within same source
normalized title similarity
professor name similarity
institution similarity
same provider
same asset URL/hash
same course/web URL
same topic keywords
```

Suggested scoring:

```text
title similarity >= 0.85: +0.35
professor exact/similar: +0.25
institution exact/similar: +0.20
same provider: +0.05
same URL or asset hash: +0.30
same taxonomy: +0.05
```

Rules:

- Score >= 0.75 creates high-confidence candidate and blocks publish until
  reviewed.
- Score 0.55-0.75 creates normal candidate.
- Score below 0.55 is ignored in Phase 1.
- Store candidate project IDs in canonical order using
  `least(left_project_id, right_project_id)` and
  `greatest(left_project_id, right_project_id)` to prevent duplicate pairs.

### 4.8 Business Enrichment Mapping

Most Phase 1A business fields will come from internal operations input, provider
confirmation, or controlled manual review rather than crawled source pages.

| Target | Initial Source |
| --- | --- |
| `provider_contracts` | supplier cooperation sheet or manual admin entry |
| `project_commercial_profiles` | pricing sheet or operations-maintained fields |
| `project_sales_profiles` | sales enablement draft maintained by operations |
| `project_customer_fit_rules` | operations matching rules plus controlled taxonomy |
| `project_deliverable_claims` | provider confirmation and academic/compliance review |
| `rights_scopes` | provider authorization evidence and manual review |

Import behavior:

- missing business fields create enrichment tasks and do not block internal
  search;
- projects cannot be marked `review_ready` for sales promotion until commercial
  profile, sales profile, fit rules, and deliverable claims pass the configured
  minimum checks;
- public display cannot use an asset, bio, poster, or generated copy unless the
  relevant rights scope is approved.

## 5. API Implementation Plan

### 5.1 API Boundaries

Use separate namespaces:

```text
/ops/*
/public/*
```

Rules:

- `/ops/*` requires backend RBAC.
- `/public/*` does not expose internal tables directly.
- Phase 1A ships `/ops/*` first.
- Public responses come from `public_project_cards` and `public_project_details`
  projections and ship in Phase 1B.
- Internal operations responses may include raw/provenance only for authorized
  roles.

### 5.2 Operations APIs

#### `GET /ops/projects`

Purpose:
operations list and combined filtering.

Query parameters:

```text
provider_id
source_id
priority
enrollment_status
price_min
price_max
gross_margin_min
commercial_priority
project_type
primary_discipline
secondary_discipline
specialization
suitable_major
suitable_grade
target_country
degree_goal
student_stage
budget_band
difficulty_level
duration
start_date_from
start_date_to
professor_name
institution_id
institution_country
delivery_country
provider_cooperation_status
provider_authorization_status
provider_risk_level
has_sales_profile
has_commercial_profile
has_fit_rules
has_deliverable_claims
has_forbidden_claims
readiness
display_status
review_status
rights_scope_status
has_dn_poster
has_instructor_avatar
has_merge_candidates
q
page
page_size
sort
```

Response fields:

```text
project id
title
provider
current offering summary
priority
commercial summary
supplier risk summary
sales-ready flags
customer-fit summary
taxonomy summary
match summary
instructor summary
asset flags
readiness
display status
review status
duplicate candidate count
```

#### `GET /ops/projects/{id}`

Includes:

```text
canonical project
source links
raw record references
offerings
instructors
taxonomy
majors
match profile
customer fit rules
commercial profile
sales profile
deliverable claims
provider contracts summary
provider performance summary
ops fields
assets
rights scopes
display profiles
review states
quality issues
merge candidates
change events
usage and feedback summary
```

Raw JSON should require admin or explicit data role.

#### `PATCH /ops/projects/{id}`

Editable by operations:

```text
project_ops.priority
project_ops.internal_notes
project_ops.sales_positioning
project_match_profiles draft fields
project_customer_fit_rules draft fields
project_commercial_profiles draft fields
project_sales_profiles draft fields
project_deliverable_claims draft rows
display profile draft fields
offering operational fields
```

High-risk fields create `field_review_states` instead of going straight to
sales-ready or published output. Price changes below minimum sale price, public
claims, prohibited claims, and supplier authorization changes require reviewer
or admin approval.

#### Phase 1A Business APIs

```text
GET /ops/providers
GET /ops/providers/{id}
PATCH /ops/providers/{id}
POST /ops/providers/{id}/contracts
PATCH /ops/provider-contracts/{id}
GET /ops/providers/{id}/performance

GET /ops/projects/{id}/commercial-profile
PATCH /ops/projects/{id}/commercial-profile
GET /ops/projects/{id}/sales-profile
PATCH /ops/projects/{id}/sales-profile
GET /ops/projects/{id}/customer-fit-rules
PATCH /ops/projects/{id}/customer-fit-rules
GET /ops/projects/{id}/deliverable-claims
POST /ops/projects/{id}/deliverable-claims
PATCH /ops/deliverable-claims/{id}
GET /ops/projects/{id}/rights-scopes
POST /ops/rights-scopes
PATCH /ops/rights-scopes/{id}
```

Rules:

- Commercial profile updates write `change_events` and recalculate margin.
- Sales profile updates cannot remove existing forbidden claims without review.
- Customer-fit rules should be testable against a sample student context.
- Deliverable claims default to `pending` and cannot be used in public display
  until approved.
- Unknown rights scope is treated as internal-search only.

#### Phase 1C Feedback APIs

```text
POST /ops/projects/{id}/usage-events
POST /ops/projects/{id}/recommendation-logs
PATCH /ops/recommendation-logs/{id}/outcome
POST /ops/projects/{id}/order-feedback
GET /ops/projects/{id}/feedback-summary
GET /ops/providers/{id}/feedback-summary
```

Rules:

- Feedback endpoints capture lightweight operating signals only.
- Do not model full customer PII or full order/payment data in Phase 1C.
- Customer context must be minimized to matching attributes such as target
  country, major group, grade, budget band, time window, and goal.

#### Review APIs

```text
POST /ops/projects/{id}/submit-review
GET /ops/review-tasks
POST /ops/review-tasks/{id}/approve
POST /ops/review-tasks/{id}/reject
```

Rules:

- Review tasks are field-level.
- Approving a field updates the draft/display profile or marks it publishable.
- Rejecting a field creates an enrichment task with reviewer comments.
- Academic fields require academic reviewer or admin.
- Sales claims, deliverable claims, price visibility, and supplier authorization
  each require their own review category.

#### Merge APIs

```text
GET /ops/merge-candidates
POST /ops/merge-candidates/{id}/confirm
POST /ops/merge-candidates/{id}/reject
```

Rules:

- Only admin can confirm merges.
- Confirming merge links source records to the surviving canonical project.
- Published slugs must be redirected, retained, or unpublished by explicit admin
  decision.

#### Publish APIs

```text
POST /ops/projects/{id}/publish
POST /ops/projects/{id}/unpublish
POST /ops/projects/{id}/archive
```

Rules:

- Publish runs all publication gates.
- Publish creates a new display version or promotes an approved version.
- Unpublish and archive do not delete source records.

### 5.3 Public APIs

#### `GET /public/projects`

Reads `public_project_cards`.

Filters:

```text
primary_discipline
secondary_discipline
specialization
project_type
difficulty
duration
start_date_from
start_date_to
suitable_major
suitable_grade
institution_country
delivery_country
q
page
page_size
```

Must not expose:

```text
raw_json
internal_notes
price unless show_price is true
review states
merge evidence
unapproved assets
source debug fields
```

#### `GET /public/projects/{slug}`

Reads `public_project_details`.

Rules:

- Return 404 for unpublished/archived profiles.
- Hide fields/assets without approved rights.
- If slug is redirected after merge, return redirect metadata or HTTP redirect
  depending on the web stack.

## 6. Review Flow Implementation

### 6.1 State Flow

```text
imported
  -> normalized
  -> draft
  -> review_pending
  -> approved
  -> published
  -> archived
```

Reject flow:

```text
review_pending -> draft
review_pending -> enrichment_task open
```

Unpublish flow:

```text
published -> approved
published -> archived
```

### 6.2 Publication Gate Function

Create a service function:

```text
evaluate_publication_gates(canonical_project_id, display_profile_id)
```

Returns:

```text
gate_name
status: pass / fail / warning
reason
blocking: true / false
```

Blocking gates:

```text
source traceability
required public fields
high-risk review
rights scope for assets, bios, posters, and display copy
supplier authorization
sales/deliverable claims review
price visibility approval
offering validity
duplicate conflict
takedown status
data freshness
RBAC permission
```

### 6.3 Field Risk Classification

Default high-risk fields:

```text
project_display_profiles.project_summary
project_display_profiles.topic_information_display
project_display_profiles.research_question
project_display_profiles.research_method
project_display_profiles.expected_outputs
project_display_profiles.instructor_bio_display
instructors.bio_edited
instructors.paper_guidance_scope
assets linked as dn_poster or instructor_avatar
project_deliverable_claims
project_sales_profiles.forbidden_claims
rights_scopes where scope_code is public_website, group_share, paid_ads, or ai_processing
```

Medium-risk fields:

```text
project_offerings.price_amount
project_commercial_profiles.suggested_sale_price_amount
project_commercial_profiles.min_sale_price_amount
project_commercial_profiles.price_visibility_policy
project_offerings.enrollment_status
project_offerings.start_date_text
project_match_profiles.suitable_grades
project_match_profiles.suitable_majors_cache
project_match_profiles.difficulty_level
project_customer_fit_rules
project_sales_profiles.key_selling_points
```

Low-risk fields:

```text
links
taxonomy drafts
duration text
provider
source metadata
```

## 7. Testing Plan

### 7.1 Database Tests

Validate:

- migrations apply cleanly from empty DB;
- stable enum values exist and business-changing values use lookup tables where
  appropriate;
- foreign keys prevent orphan records;
- source/project uniqueness constraints work;
- `source_project_record_versions` preserves immutable snapshots;
- offering-level fields allow multiple offerings per project;
- commercial profile exists independently from offering availability;
- asset deduplication and `asset_links` support one asset linked to multiple
  subjects;
- `rights_scopes` unique constraints prevent duplicate scope rows;
- generic review or rights subjects pass service/trigger integrity validation;
- merge candidate project pairs are stored in canonical pair order;
- public slug uniqueness works;
- indexes exist for key filters.

### 7.2 Import Tests

Use fixture JSONL samples, not live websites.

Test cases:

- HIREP project row maps to source record, canonical project, provider,
  taxonomy, instructor, and assets.
- HIREP asset manifest maps to `assets` and `asset_links`.
- Jisi output imports with missing-field quality issues.
- Jisi domestic maps offering, instructor, prerequisites, output, and topic
  fields.
- Zhongke ambiguous university field creates low-confidence provenance and
  quality issue.
- Secret-like fields are redacted or rejected.
- Dry-run does not persist final rows.
- Duplicate import is idempotent.
- Re-import with changed raw content creates a new
  `source_project_record_versions` row and updates latest source metadata.
- Missing supplier, commercial, sales, customer-fit, rights, or claim data
  creates enrichment tasks instead of blocking internal search.

### 7.3 Duplicate Candidate Tests

Test:

- same URL creates candidate;
- same title/professor/institution creates high-confidence candidate;
- similar title but different professor does not block publish;
- confirmed merge links source records and records change event;
- rejected candidate does not re-open in the same batch unless evidence changes.

### 7.4 Review and Publishing Tests

Test:

- operations can edit medium-risk fields;
- operations cannot approve academic high-risk fields;
- academic reviewer can approve academic high-risk fields;
- admin can publish only after gates pass;
- missing public fields block publish but not internal search;
- stale offering blocks publish;
- unapproved DN poster is hidden from public API;
- takedown flag hides project or asset.
- unknown public-website rights scope hides poster, avatar, bio, and generated
  display copy;
- deliverable claims cannot be used in sales or public display until approved;
- prohibited claims remain visible to internal users as warnings and never appear
  in public responses;
- supplier authorization missing or expired blocks sales-ready and publish-ready
  status.

### 7.5 Business Rule Tests

Test:

- price below `min_sale_price_amount` requires approval;
- `gross_margin_rate` recalculates when cost or sale price changes;
- public price is visible only when `price_visibility_policy` and display
  profile `show_price` both allow it;
- sales profile cannot remove a forbidden claim without review;
- customer-fit rules return expected match/not-match results for sample student
  contexts;
- operations can find three candidate projects for 50 real or realistic Chinese
  search queries, including mixed discipline, professor, school, country, grade,
  and budget terms;
- provider risk level and cooperation status are visible in operations list and
  detail;
- recommendation and order feedback update project and provider summary metrics
  without requiring full CRM/order records.

### 7.6 Public API Isolation Tests

Test public API responses never include:

```text
raw_json
internal_notes
source merge evidence
review comments
unapproved assets
unreviewed high-risk fields
secret-like fields
price when visibility policy or display profile forbids it
internal supplier cost, margin, settlement notes, refund liability, sales script,
forbidden claims, customer context, recommendation logs, or order feedback
```

### 7.7 Search Tests

Test:

- operations keyword search finds Chinese titles and professor names;
- taxonomy filters combine correctly;
- offering filters return projects with matching active offerings;
- supplier, margin, customer-fit, and sales-ready filters combine correctly;
- public search only searches published display profiles.

### 7.8 Frontline Usability Tests

Use internal operations scenarios, not only API assertions:

- Given a student profile, operations can find three reasonable candidate
  projects within 60 seconds.
- Given one project, operations can identify sales risks, forbidden claims,
  rights warnings, supplier status, and price floor within 30 seconds.
- Sales can copy a reviewed one-liner and selling points without seeing
  prohibited public claims.
- Academic reviewer can see exactly which claims or display fields need review.

### 7.9 Performance Smoke Tests

Use current scale plus headroom:

```text
10,000 source records
10,000 canonical projects
50,000 assets
20,000 offerings
20,000 usage/recommendation/feedback events
```

Targets:

```text
ops list p95 < 800 ms with common filters
ops detail p95 < 500 ms for commercial/sales/fit/claims sections
public list p95 < 400 ms
public detail p95 < 200 ms
import dry-run 10,000 rows < 2 minutes
```

## 8. Milestone Plan

### M0: Coding Gates and Business Decisions

Deliverables:

- Phase 1A/1B/1C release boundary;
- backend stack decision;
- staging database decision;
- initial roles and permission matrix;
- supplier, commercial, rights, and sales-claim ownership;
- minimum field set for sales-ready projects;
- migration rollback standard.

Acceptance:

- engineering and operations agree that public API is not required for Phase 1A;
- unknown rights default to internal-search only;
- price defaults to internal-only;
- business-changing statuses use lookup tables unless they are stable technical
  workflow states.

### M1: Schema Foundation

Deliverables:

- migrations `001` to `010`;
- seeded sources, roles, and core taxonomy placeholders;
- source/provider separation;
- `source_project_record_versions`;
- supplier operation tables;
- commercial, sales, customer-fit, and deliverable-claim tables;
- `assets`, `asset_links`, and `rights_scopes`;
- operations and public projection views;
- migration tests.

Acceptance:

- migrations apply cleanly from an empty database;
- schema supports the required field list and Phase 1A business fields;
- source versioning, rights scope, freshness, provenance, RBAC, and change event
  tables exist;
- no binary assets are stored in PostgreSQL.

### M2: Import Adapters and Quality Reports

Deliverables:

- `hirep` adapter;
- `jisi_future` adapter;
- `jisi_future_domestic` adapter;
- `zhongke` adapter;
- dry-run mode;
- import report output;
- quality issue generation;
- duplicate candidate generation;
- source version creation;
- enrichment tasks for supplier, commercial, sales, fit, rights, and claims.

Acceptance:

- current four datasets import without secret leakage;
- import is idempotent;
- changed raw source rows create new source versions;
- missing fields produce quality issues or enrichment tasks, not failed imports;
- ambiguous Zhongke institution fields are marked low confidence.

### M3: Phase 1A Internal Operations MVP

Deliverables:

- `GET /ops/projects`;
- `GET /ops/projects/{id}`;
- supplier list/detail and contract summary;
- commercial profile read/write;
- sales profile read/write;
- customer-fit rule read/write;
- deliverable-claim read/write;
- rights scope read/write;
- operations comparison view;
- business rule tests;
- frontline usability test script.

Acceptance:

- operations can filter by provider, supplier status, priority, offering status,
  price range, margin, discipline, specialization, major, grade, difficulty,
  professor, institution country, delivery country, sales readiness, customer-fit
  attributes, rights warnings, and keyword;
- operations can find three candidate projects within 60 seconds for realistic
  student scenarios;
- operations can identify sales risks, forbidden claims, supplier status, and
  price floor within 30 seconds on a project detail page;
- raw JSON is visible only to authorized internal users;
- the system is useful even if no public API has shipped.

### M4: Phase 1B Review and Public Display

Deliverables:

- review task APIs;
- field approval/rejection;
- sales claim review;
- supplier authorization gate;
- merge candidate APIs;
- publish/unpublish/archive APIs;
- publication gate evaluator;
- public card/detail projections;
- `GET /public/projects`;
- `GET /public/projects/{slug}`;
- slug redirect/unpublish handling;
- public API isolation tests.

Acceptance:

- high-risk fields cannot publish without review;
- high-confidence merge candidate blocks publish until reviewed;
- stale offering blocks publish;
- supplier authorization and rights scope gates block unsafe publishing;
- unapproved assets and unapproved display copy stay hidden;
- only published profiles are returned by public APIs;
- raw, internal, commercial cost, margin, sales script, forbidden claim, and
  feedback fields are absent from public responses.

### M5: Phase 1C Deal and Delivery Feedback Loop

Deliverables:

- usage event logging;
- recommendation logs;
- recommendation outcome update;
- project order feedback capture;
- provider and project feedback summaries;
- supplier performance metric rollup job or query;
- feedback-based project/provider scoring draft.

Acceptance:

- recommendation, deal/lost, complaint, refund, satisfaction, and delivery
  feedback can be captured without CRM/order integration;
- feedback does not store unnecessary customer PII;
- project and provider summary metrics can be reviewed by operations;
- feedback can influence commercial priority and supplier risk review.

### M6: Hardening and Handoff

Deliverables:

- runbook for imports;
- schema reference;
- role/permission guide;
- data quality dashboard query examples;
- operations search examples;
- business rule test report;
- rollback plan for migrations;
- release checklist.

Acceptance:

- operations can run import dry-run and read quality report;
- engineering can validate migration rollback plan;
- API, import, business rule, and public isolation tests pass;
- 50 Chinese search queries are validated against imported data.

## 9. 30-Day Execution Rhythm

| Days | Focus | Output |
| --- | --- | --- |
| 1-3 | Decisions and data audit | Confirm stack, staging DB, roles, business owners, rights default, price visibility default, minimum sales-ready fields. |
| 4-10 | DDL and migrations | Build migrations `001`-`010`, seed core vocabularies, run migration/database tests. |
| 11-15 | Import and quality | Build four adapters, source versions, secret checks, quality report, duplicate candidates, enrichment tasks. |
| 16-20 | Internal search MVP | Build `/ops/projects`, detail, operations filters, source traceability, rights warnings, quality/readiness display. |
| 21-25 | Business fields MVP | Build supplier, commercial, sales, customer-fit, deliverable-claim, rights-scope editing and business rule tests. |
| 26-30 | Review, feedback, handoff | Add review gates needed for sales-ready status, lightweight feedback capture, 50-query validation, frontline usability test, runbook. |

Day 30 target is Phase 1A usable by internal operations. Phase 1B public API can
start earlier in design, but should not block Phase 1A acceptance.

## 10. Delivery Sequence

Recommended order:

1. Lock Phase 1A/1B/1C release boundaries and business owners.
2. Build schema and migration tests.
3. Build import adapters with dry-run, secret checks, and source versions.
4. Import current data into a local/staging database.
5. Generate initial quality report, enrichment tasks, and duplicate candidates.
6. Build internal operations search and detail APIs.
7. Build supplier, commercial, sales, customer-fit, claims, and rights-scope APIs.
8. Run business rule tests and frontline usability checks.
9. Build review and publish workflow for Phase 1B.
10. Build public projections and public APIs.
11. Run public API isolation/security tests.
12. Build lightweight Phase 1C feedback capture.
13. Produce handoff docs and release checklist.

## 11. Release Checklist

Before Phase 1A internal operations release:

- all migrations tested from empty database;
- all import adapters pass fixture tests;
- current datasets import successfully;
- source versions are created;
- quality report generated;
- enrichment tasks generated for missing business fields;
- RBAC tests pass;
- rights/takedown tests pass;
- supplier, commercial, sales, customer-fit, and deliverable-claim business tests
  pass;
- no binary assets stored in PostgreSQL;
- no secrets imported into raw JSON;
- 50 realistic Chinese operations queries are validated;
- frontline users can complete the 60-second matching and 30-second risk-check
  scenarios.

Before Phase 1B public release:

- publication gate tests pass;
- public API isolation tests pass;
- public asset and display copy rights scopes are approved;
- no raw, internal, supplier cost, margin, sales script, forbidden claim,
  customer context, recommendation, or order feedback fields leak to public API.

Before Phase 1C feedback release:

- feedback endpoints minimize customer context;
- recommendation, deal/lost, complaint, refund, satisfaction, and delivery
  feedback can be captured;
- provider and project summary metrics can be queried by operations.

## 12. Open Decisions Before Coding

These should be answered at implementation kickoff:

1. Which backend stack will host APIs: existing Python service, new FastAPI
   service, or another stack?
2. Which PostgreSQL environment is used for staging?
3. Who owns source/provider mapping corrections?
4. Who owns supplier contract, authorization, and performance fields?
5. Who owns commercial price, minimum sale price, and discount approval?
6. Who owns sales profile, forbidden claims, and deliverable-claim review?
7. What is the initial controlled vocabulary for disciplines, project types,
   and majors?
8. What verification window should apply to price, enrollment, start dates,
   supplier status, and rights scopes?
9. What public asset rights policy should be assumed when rights are unknown?
10. What exact 50 Chinese search queries will be used for Phase 1A validation?

Default assumptions if unanswered:

1. Use Python + FastAPI + SQLAlchemy/Alembic for backend implementation.
2. Treat unknown rights as internal-search only and not public.
3. Treat price as internal-only unless both commercial profile and display
   profile allow public visibility.
4. Treat high-confidence duplicate candidates as publish blockers.
5. Treat missing public fields as enrichment tasks, not import blockers.
6. Treat missing supplier/commercial/sales/customer-fit/claims data as not
   sales-ready, but still searchable internally.
