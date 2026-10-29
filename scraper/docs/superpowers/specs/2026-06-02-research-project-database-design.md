# Research Project Database Design

Date: 2026-06-02

## 1. Decision Summary

The long-term goal is **Route C: a complete research project operations platform**.
The first development phase is **Route B: an operations and display hybrid database**.

This design is updated to position the system as a **research project SKU
operations system**, not only a project display database. Phase 1 must first
make customer operations and supplier operations effective, then add public
display.

Absolute 100% certainty is not possible at strategy time because partner data,
authorization terms, future operations workflows, and customer-facing display
requirements may change. The strategy is considered high-confidence only under
the explicit assumptions, publication gates, and validation loops in this
document.

Phase 1 must not be a temporary database. It should become the foundation for
later recommendation, CRM integration, automated synchronization, and content
publishing.

Phase 1 acceptance can be summarized as:

- searchable by operations;
- useful for 30-second customer-project matching;
- useful for commercial decisions such as margin, risk, supplier reliability,
  and sales priority;
- reviewable by operations, academic reviewers, and admins;
- publishable to customer-facing project pages;
- traceable back to source records, import batches, raw data, supplier
  authorization, and sales/feedback history.

## 1.1 Business Repositioning

The product should be treated as:

> Research project SKU operations system = supplier SKU standardization +
> customer matching + sales enablement + delivery risk control + operating
> analytics.

It should support five business scenes:

| Scene | Core Question | System Capability |
| --- | --- | --- |
| Customer operations matching | Which project fits this student? | Customer-fit filters, fit rules, sales-ready summaries, not-fit rules. |
| Sales conversion | How should this project be explained? | One-liner, selling points, FAQ, objection handling, case notes, forbidden claims. |
| Supplier management | Is this provider reliable? | Contract, settlement, refund policy, SLA, authorization, rating, risk history. |
| Delivery risk control | What can sales safely promise? | Deliverable claims, prohibited claims, review gates, rights scopes, takedown. |
| Operating decisions | Which categories and providers deserve focus? | GMV/margin/complaint/satisfaction feedback and supplier/project scoring. |

## 1.2 Phase 1 Split

Phase 1 is split into three sub-phases:

| Sub-phase | Goal | Priority |
| --- | --- | --- |
| Phase 1A: internal sales operations MVP | Import, normalize, search, match, commercial fields, supplier fields, sales materials, risk visibility | Must build first |
| Phase 1B: review and public display | Display profiles, field review, publication gates, public API allowlists | Design in parallel, release after 1A |
| Phase 1C: deal and delivery feedback loop | Lightweight recommendation/deal/lost/refund/complaint/satisfaction feedback | Build soon after 1A, without full order system |

Public APIs should not slow down Phase 1A. The first operational validation is:
customer operations can find three reasonable candidate projects within 60
seconds and identify sales risks within 30 seconds.

## 2. Goals

### 2.1 Long-Term Platform Goals

The complete platform should support:

1. Partner research project aggregation.
2. Data quality management and duplicate handling.
3. Internal operations search and project comparison.
4. Customer-facing project cards and detail pages.
5. Future project recommendation based on student needs.
6. Future CRM, automated sync, dashboard, and publishing integration.

### 2.2 Phase 1 Goals

Phase 1 should deliver:

1. A PostgreSQL-backed project master database.
2. Import support for current HIREP, Jisi Future, Jisi Future domestic, and
   Zhongke datasets.
3. Source record retention with raw JSON traceability.
4. Canonical project records for internal search.
5. Candidate duplicate detection without automatic merge.
6. Field-level review and project-level publishing.
7. Customer-facing display profiles that only expose approved published data.
8. Supplier operating records for cooperation, settlement, authorization, SLA,
   refund, and risk.
9. Commercial profiles for provider cost, suggested sale price, minimum price,
   commission, margin, and discount permissions.
10. Sales profiles for one-liners, selling points, FAQ, objection handling,
   scenarios, case notes, and forbidden claims.
11. Customer fit rules for target country, major, degree goal, application stage,
   budget, time window, foundation level, and risk tolerance.
12. Structured deliverable claims separating guaranteed, conditional, and
   prohibited claims.
13. Lightweight deal/delivery feedback records to support supplier and project
   scoring.

## 3. Current Data Context

The current scraper workspace contains these structured datasets:

| Source | Structured Records | Notes |
| --- | ---: | --- |
| HIREP | 2,770 projects | Includes rich categories and 26,307 asset manifest records. |
| Jisi Future output | 627 records | Limited normalized fields, source raw data retained. |
| Jisi Future domestic | 1,041 records | Richest normalized fields: teacher, school, cycle, output, prerequisites, background, outline. |
| Zhongke | 2,722 projects | Has teacher and university text, but some fields need cleanup. |

Existing SQLite files are useful as temporary exports, but not sufficient as the
main operational database because they lack a unified model, review workflow,
source-to-canonical links, candidate merge handling, and customer-facing publish
controls.

## 4. Architecture

The platform should use a layered model:

1. **Source layer**
   Partner sources, import batches, raw records, raw JSON, original URLs, and
   crawler metadata.

2. **Governance layer**
   Normalization, quality reporting, duplicate candidates, merge decisions,
   change events, and source traceability.

3. **Core project layer**
   Canonical project records, instructors, taxonomy, matching fields, operations
   fields, offerings, commercial profiles, sales profiles, supplier records,
   customer-fit rules, deliverable claims, and assets.

4. **Display layer**
   Customer-facing project card and detail fields with review status,
   publication state, and display versions.

5. **Future platform layer**
   Automated sync, recommendation, CRM student profiles, dashboards, content
   publishing, and richer permissions.

## 4.1 Confidence Boundaries

This strategy depends on these assumptions:

1. The organization has authorization to store and operationally use partner
   project data.
2. Customer-facing use of professor bios, avatars, DN-style posters, and other
   assets is allowed by partner agreements or reviewed manually before publish.
3. Price, enrollment status, and start dates can vary by offering/cohort and
   must not be modeled only as project-level fields.
4. Operations users need broad internal visibility, while public users must only
   see reviewed and published display profiles.
5. Future recommendation should be built on structured matching data, not on raw
   crawler JSON alone.

If any assumption is false, the implementation plan must pause and adjust the
schema or workflow before development continues.

## 5. Phase 1 Scope

### 5.1 Included

Phase 1 includes:

- PostgreSQL schema;
- indexes, constraints, and status enums;
- import scripts or import service for existing local datasets;
- data quality report after import;
- source record retention;
- canonical project generation;
- candidate duplicate generation;
- internal operations search API;
- project detail API for operations;
- field review queue;
- project publish, unpublish, and archive states;
- public project list and detail API that only reads published display profiles
  in Phase 1B;
- supplier operating fields;
- commercial pricing and margin fields;
- sales enablement fields;
- customer fit rules;
- structured deliverable claims;
- lightweight deal/delivery feedback.

### 5.2 Deferred

Phase 1 does not include:

- automated scheduled partner API synchronization;
- CRM student profile integration;
- complex recommendation algorithms;
- full CMS implementation;
- payment, order, contract, or enrollment transaction workflows;
- full CRM integration;
- full recommendation engine;
- complex multi-team BPM workflow;
- direct database storage of PDF or image binary content.

## 6. Required Fields

The Phase 1 schema must support at least these business fields:

| Business Field | Recommended Storage |
| --- | --- |
| Project title | `canonical_projects.title` and `project_display_profiles.display_title` |
| Project provider | `providers`, linked from `canonical_projects.provider_id` |
| Supplier cooperation status | `providers.cooperation_status` |
| Supplier contract and settlement | `provider_contracts` |
| Supplier SLA and risk | `providers`, `provider_performance_metrics` |
| Web page URL | `project_links` with `link_type = 'web_page'` |
| Course URL | `project_links` with `link_type = 'course'` |
| Priority | `project_ops.priority` |
| Duration / cycle | `project_offerings.duration` and optional canonical fallback |
| Suitable student direction | `project_match_profiles.suitable_student_directions` |
| DN-style poster | `assets` + `asset_links.link_role = 'dn_poster'` |
| Professor bio | `instructors.bio_raw` |
| Professor bio, edited version | `instructors.bio_edited` or `project_display_profiles.instructor_bio_display` |
| Primary discipline | `taxonomy_terms` and `project_taxonomy_links` with `term_type = 'primary_discipline'` |
| Secondary discipline | `taxonomy_terms` and `project_taxonomy_links` with `term_type = 'secondary_discipline'` |
| Specialization | `taxonomy_terms` and `project_taxonomy_links` with `term_type = 'specialization'` |
| Suitable majors | `major_terms` and `project_major_links`, with optional cached values in `project_match_profiles` |
| Difficulty | `project_match_profiles.difficulty_level` |
| Prerequisite courses | `project_match_profiles.prerequisite_courses` |
| Professor school | `institutions.name`, with `instructors.institution_name_raw` retained when parsing is uncertain |
| Professor level | `instructors.academic_title` |
| Country | `institutions.country` for professor school country; `project_offerings.delivery_country` for delivery/location country when applicable |
| Professor name | `instructors.name` |
| Professor avatar | `assets` + `asset_links.link_role = 'instructor_avatar'` |
| Professor paper guidance scope | `instructors.paper_guidance_scope` |
| Topic information | `canonical_projects.topic_info` |
| Topic summary | `project_display_profiles.project_summary` |
| Start date | `project_offerings.start_date_text` and optional normalized `start_date` |
| Enrollment status | `project_offerings.enrollment_status` |
| Project type | `canonical_projects.project_type` |
| Price | `project_offerings.price_amount`, `project_offerings.price_currency` |
| Suitable grade | `project_match_profiles.suitable_grades` |
| Provider cost | `project_commercial_profiles.provider_cost_amount` |
| Suggested sale price | `project_commercial_profiles.suggested_sale_price` |
| Minimum sale price | `project_commercial_profiles.min_sale_price` |
| Commission and margin | `project_commercial_profiles.commission_rate`, `gross_margin_rate` |
| Sales one-liner | `project_sales_profiles.one_liner` |
| Selling points and FAQ | `project_sales_profiles.key_selling_points`, `faq_json` |
| Forbidden sales claims | `project_sales_profiles.forbidden_claims`, `project_deliverable_claims` |
| Customer fit rules | `project_customer_fit_rules` |
| Deliverable claims | `project_deliverable_claims` |
| Deal and delivery feedback | `project_order_feedback` |

The duplicated "secondary discipline" requirement is represented by one
normalized taxonomy term type: `secondary_discipline`.

## 7. Core Data Model

Phase 1 should use a three-layer entity model:

1. `source_project_records`
   Raw partner records. These remain immutable except for import metadata.

2. `canonical_projects`
   Unified operational project records. These are searchable internally and can
   link to multiple source records after manual merge confirmation.

3. `project_display_profiles`
   Customer-facing display records. Public APIs read this layer only when the
   profile is published.

### 7.1 Main Tables

| Table | Purpose |
| --- | --- |
| `sources` | Partner source registry, such as HIREP, Jisi Future, Zhongke. |
| `providers` | Commercial or academic project provider; separate from raw data source. |
| `ingest_batches` | Import batch metadata, files, stats, imported by, timestamps. |
| `source_project_records` | Logical source record identity: source key, first/last seen, current version, status. |
| `source_project_record_versions` | Immutable raw record snapshots per import batch. |
| `canonical_projects` | Unified project master records for search and display preparation. |
| `project_source_links` | Links canonical projects to one or more source records. |
| `project_links` | Multiple URLs per project: web page, course page, poster page, partner page. |
| `project_offerings` | Cohort-level duration, start date, enrollment status, price, capacity, validity. |
| `instructors` | Professor/instructor profile fields. |
| `institutions` | Normalized professor school or institution records. |
| `project_instructors` | Project-to-instructor relation. |
| `taxonomy_terms` | Controlled vocabulary for primary discipline, secondary discipline, specialization, project type, skills, and output tags. |
| `project_taxonomy_links` | Project-to-taxonomy relation with term type and confidence. |
| `major_terms` | Controlled vocabulary for suitable majors, including aliases and Chinese/English names. |
| `project_major_links` | Project-to-major relation. |
| `project_match_profiles` | Suitable majors, grade, prerequisites, difficulty, and matching fields. |
| `project_ops` | Internal priority, owner, notes, sales positioning, and operational flags. |
| `project_commercial_profiles` | Provider cost, list price, suggested sale price, min price, commission, margin, settlement notes. |
| `project_sales_profiles` | One-liner, selling points, scripts, FAQ, objections, suitable/not-suitable scenarios, forbidden claims. |
| `project_customer_fit_rules` | Target country, degree goal, target major, time window, budget band, foundation and risk tolerance rules. |
| `project_deliverable_claims` | Guaranteed, conditional, and prohibited deliverable claims with evidence and review status. |
| `assets` | Deduplicated asset metadata: poster, avatar, PDF/image, URI, hash, MIME, rights, freshness. |
| `asset_links` | Links assets to projects, instructors, providers, or source records with role and source evidence. |
| `project_display_profiles` | Customer-facing project card and detail fields. |
| `field_review_states` | Field-level review records and status. |
| `field_provenance` | Field source, confidence, source record reference, manual override metadata. |
| `data_quality_issues` | Missing fields, parse ambiguity, low confidence fields, rights gaps, publish blockers. |
| `enrichment_tasks` | Manual cleanup or content completion tasks for operations or academic reviewers. |
| `verification_tasks` | Periodic re-check tasks for stale price, enrollment, offering, provider, instructor, and public-display data. |
| `users`, `roles`, `user_roles` | Minimal RBAC for operations, academic reviewers, and admins. |
| `merge_candidates` | Candidate duplicate links with similarity score and evidence. |
| `provider_contracts` | Contract, authorization scope, settlement, refund, escalation, and file metadata. |
| `provider_performance_metrics` | Complaint, refund, delay, response, satisfaction, and supplier rating metrics. |
| `rights_scopes` | Fine-grained rights such as internal search, private chat, public website, paid ads, AI processing. |
| `taxonomy_aliases` | Alias mapping for taxonomy and major terms. |
| `taxonomy_change_requests` | Governed process for new or changed taxonomy terms. |
| `project_usage_events` | Project viewed, recommended, sent, favorited, or exported events. |
| `project_order_feedback` | Lightweight recommendation, deal, delivery, complaint, refund, satisfaction, and case feedback. |
| `recommendation_logs` | Future recommendation input/output logs for model and rule review. |
| `change_events` | Audit log for important changes and state transitions. |

### 7.2 Key Modeling Rules

1. Raw source records must not be overwritten.
2. A canonical project can link to multiple source project records.
3. Public display fields are derived from display profiles, not raw records.
4. Assets store metadata and file/object paths, not binary payloads.
5. Duplicate detection produces candidates only; it does not automatically merge.
6. Tags support filtering and future recommendation, but matching profiles store
   structured matching fields.
7. Offering fields such as price, enrollment status, duration, capacity, and
   start dates must live in `project_offerings` because the same project can
   have multiple cohorts or sales periods.
8. Every normalized or manually edited field that affects operations or public
   display should have provenance: source-imported, normalized, manually edited,
   generated, reviewed, or published.
9. Current datasets may not contain every required business field. Missing fields
   should create data quality issues or enrichment tasks instead of blocking
   internal import.
10. Country fields must be typed. Institution country, professor nationality,
   and delivery/location country are not interchangeable.
11. Raw immutability has compliance exceptions. If a partner, legal requirement,
   or takedown request requires redaction or removal, the system should keep an
   audit tombstone and remove public/internal exposure of the restricted content.
12. Generated fields, including AI-assisted summaries or recommendation reasons,
   are drafts only. They require provenance and review before public display.
13. Provider operations, commercial pricing, sales materials, customer fit rules,
   and deliverable claims are Phase 1A concerns, not optional future analytics.
14. Public display is Phase 1B. Phase 1A must be useful even if no public API is
   released.

### 7.3 Readiness Levels

Project readiness should be explicit:

| Readiness | Meaning |
| --- | --- |
| `searchable` | Enough normalized fields exist for internal operations search. |
| `display_draft_ready` | Enough fields exist for operations to draft a display profile. |
| `review_ready` | Required high-risk fields are present and can be submitted for review. |
| `publish_ready` | Publication gates pass and a version can become public. |

This prevents the project database from rejecting useful internal records just
because they are not yet suitable for public display.

## 8. Review, Permission, and Publishing

Phase 1 should use **field-level review plus project-level publish**.

### 8.1 Project Statuses

| Status | Meaning |
| --- | --- |
| `imported` | Source data imported and traceable. |
| `normalized` | Basic normalized fields are available for internal search. |
| `draft` | Operations is editing display or operations fields. |
| `review_pending` | Fields are waiting for academic or admin review. |
| `approved` | Required high-risk fields are approved, but not yet published. |
| `published` | Customer-facing display profile can be served by public APIs. |
| `archived` | Project is archived or removed from regular display. |

### 8.2 Field Risk Levels

| Risk Level | Example Fields | Rule |
| --- | --- | --- |
| Low | Provider, URLs, duration, start date, project type, disciplines | Auto-importable, editable by operations. |
| Medium | Priority, enrollment status, price, suitable grades, majors, difficulty, prerequisites | Editable by operations, changes logged. |
| High | Edited professor bio, paper guidance scope, topic summary, topic information, research method, output claims, DN poster, professor avatar | Must be reviewed before public display. |

### 8.3 Roles

| Role | Permissions |
| --- | --- |
| Operations | Edit priority, price, enrollment status, tags, suitable audience, display drafts, recommendation drafts. |
| Academic reviewer | Review professor information, topic summary, research question, method, paper guidance scope, prerequisites, and output claims. |
| Admin | Configure sources, confirm merges, publish, unpublish, archive, manage high-risk changes, and manage permissions. |

Phase 1 does not need a complex BPM system, but it does need enforced RBAC.
Operations, academic reviewer, and admin permissions must be checked by the API
layer, not only by frontend UI.

### 8.4 Publishing Rules

1. Internal operations APIs can show incomplete, unreviewed, and risk-flagged data.
2. Public APIs only return `project_display_profiles.status = 'published'`.
3. High-risk fields cannot enter the published version before approval.
4. Unpublishing or archiving should not delete source records.
5. Each publish action should create a versioned display profile or version event.
6. A project cannot be published unless required publication gates pass.
7. Public APIs must use an explicit allowlist of fields. They must not serialize
   whole database rows or raw JSON.
8. If a published project is merged into another canonical project, the public
   slug should either redirect to the surviving project or be unpublished with a
   recorded admin decision.

### 8.5 Publication Gates

Before a display profile can become `published`, these gates must pass:

| Gate | Requirement |
| --- | --- |
| Source traceability | At least one linked `source_project_record` and import batch. |
| Required public fields | Display title, topic summary, project type, discipline, duration or offering, professor name or provider-approved fallback. |
| High-risk review | Edited bio, topic summary, output claims, DN poster, avatar, and paper guidance scope are approved when present. |
| Asset rights | Public assets and display copy have approved `rights_scopes` for the requested channel or are hidden from public APIs. |
| Offering validity | Public offering is active, not expired, and enrollment status allows display. |
| Price policy | Price is hidden unless explicitly enabled for that display profile. |
| Duplicate conflict | No unresolved high-confidence merge candidate blocks publish. |
| Takedown status | Project, instructor, provider, and assets have no active takedown flag. |
| Data freshness | Public offering, enrollment, and price fields are within their verification window. |

## 9. Operations Search

### 9.1 Required Filters

The operations project list should support filtering by:

- project provider;
- priority;
- enrollment status;
- price range;
- project type;
- primary discipline;
- secondary discipline;
- specialization;
- suitable majors;
- suitable student directions;
- suitable grades;
- difficulty;
- duration;
- start date;
- professor name;
- professor school;
- professor level;
- institution country;
- delivery country when applicable;
- prerequisite courses;
- keyword search across title, topic summary, professor bio, specialization,
  and raw JSON for internal troubleshooting.

Offering filters should query `project_offerings`, not only
`canonical_projects`, because one project can have multiple start dates, prices,
or enrollment statuses.

### 9.2 Operations List Fields

The operations list should show:

- project title;
- project provider;
- priority;
- enrollment status for the current or selected offering;
- price for the current or selected offering;
- project type;
- primary and secondary discipline;
- specialization;
- suitable majors;
- suitable grades;
- difficulty;
- duration;
- start date for the current or selected offering;
- professor name;
- professor school;
- professor level;
- institution country;
- delivery country when applicable;
- web page URL;
- course URL;
- DN poster availability;
- professor avatar availability;
- display status;
- review status;
- duplicate candidate count.

## 10. Customer-Facing Display

### 10.1 Project Card Fields

The public project list should show:

- display title;
- primary and secondary discipline;
- specialization;
- project type;
- difficulty;
- duration;
- start date;
- professor name;
- professor school;
- professor level;
- institution country;
- delivery country when applicable;
- suitable grades;
- suitable majors;
- card summary;
- DN-style poster;
- enrollment status.

Price should not be shown by default. If needed later, display can be controlled
by a field such as `project_display_profiles.show_price`.

### 10.2 Project Detail Fields

The public project detail page should show:

- display title;
- topic summary;
- topic information;
- research question;
- research method;
- professor name;
- professor avatar;
- professor school;
- professor level;
- institution country;
- delivery country when applicable;
- edited professor bio;
- professor paper guidance scope;
- prerequisite courses;
- suitable student directions;
- suitable majors;
- suitable grades;
- duration;
- start date;
- expected outputs;
- course URL;
- web page URL.

## 11. API Plan

### 11.1 Operations APIs

```text
GET /ops/projects
GET /ops/projects/{id}
PATCH /ops/projects/{id}
POST /ops/projects/{id}/submit-review
GET /ops/review-tasks
POST /ops/review-tasks/{id}/approve
POST /ops/review-tasks/{id}/reject
GET /ops/merge-candidates
POST /ops/merge-candidates/{id}/confirm
POST /ops/merge-candidates/{id}/reject
POST /ops/projects/{id}/publish
POST /ops/projects/{id}/unpublish
POST /ops/projects/{id}/archive
```

### 11.2 Public APIs

```text
GET /public/projects
GET /public/projects/{slug}
```

Public APIs must not expose:

- raw JSON;
- internal notes;
- unreviewed high-risk fields;
- internal price unless explicitly enabled;
- source merge evidence;
- unpublished or archived projects.

Public APIs should read from a database view or service-layer projection such as
`public_project_cards` and `public_project_details`. These projections should be
field allowlists and should not include internal columns by default.

## 12. Search and Indexing

PostgreSQL is sufficient for Phase 1.

Recommended capabilities:

- `pg_trgm` for fuzzy text search over titles, topic summaries, professor bios,
  and specialization fields;
- GIN indexes for JSONB raw data for internal troubleshooting;
- GIN indexes or relational tag tables for multi-value filters;
- standard B-tree indexes for provider, status, project type, discipline, start
  date, institution country, delivery country, and priority.

Future Phase 3 can add `pgvector` for semantic recommendation and similarity
search.

For Chinese search quality, Phase 1 should create a normalized
`project_search_documents` view or materialized view that concatenates approved
and internal-searchable text fields. `pg_trgm` is acceptable for Phase 1, but if
operations search quality is poor, Phase 2 should evaluate a dedicated search
engine or Chinese tokenizer.

## 12.1 Import Safety and Sensitive Data

Import jobs must not import browser network logs, cookies, authorization
headers, API keys, or session tokens into project raw records. If discovery logs
are needed for crawler debugging, they must stay outside the operational project
database or be redacted before import.

Each import adapter must:

1. read only project records and asset metadata;
2. preserve source project raw JSON;
3. redact or reject suspicious secret-like fields;
4. record source file path and import batch;
5. report missing required fields;
6. classify fields by provenance and confidence.

## 12.2 Data Freshness

Manual import is acceptable for Phase 1, but data freshness must be visible.
Fields that can change quickly should have verification metadata:

- `last_verified_at`;
- `verified_by`;
- `verification_source`;
- `valid_until`;
- `staleness_status`: fresh / due_for_review / stale / unknown.

Fast-changing fields include price, enrollment status, start date, duration,
capacity, course URL, web page URL, provider availability, and public assets.
Stale public fields should generate `verification_tasks` and should be blocked
from publishing when they fail publication gates.

## 12.3 AI-Generated or AI-Assisted Content

If future phases use AI to draft project summaries, selling points, tags, or
recommendation reasons, generated content must be marked as generated and must
not be public by default.

Rules:

1. Generated content writes to draft fields only.
2. Generated content must have `field_provenance.source_type = 'generated'`.
3. High-risk generated content requires academic or admin approval.
4. AI output must not use raw records that contain unapproved private/internal
   content or rights-restricted assets.
5. Recommendation reasons shown to customers must be based on approved display
   fields and approved matching profile fields.

## 12.4 Rights, Privacy, and Takedown

Because professor bios, avatars, posters, links, and project descriptions may be
reused in customer-facing displays, Phase 1 needs explicit scoped rights and
takedown fields:

- `rights_scopes`: approved/rejected/unknown by usage channel;
- `rights_notes`;
- `takedown_requested_at`;
- `takedown_reason`.

Public APIs must hide assets, links, and display fields whose requested rights
scope is unknown, rejected, expired, revoked, or under takedown.

## 12.5 Rights Scope

Usage rights must be scoped by scenario, not represented only as approved or
unknown.

Recommended rights scopes:

| Scope | Meaning |
| --- | --- |
| `internal_search` | Visible in internal search. |
| `internal_sales` | Usable by customer operations in internal sales workflow. |
| `private_chat_share` | Can be sent in one-to-one private chat. |
| `group_share` | Can be shared in group chat. |
| `public_website` | Can be displayed on a public website or mini-site. |
| `xiaohongshu_content` | Can be adapted for Xiaohongshu content. |
| `paid_ads` | Can be used in paid advertising. |
| `ai_processing` | Can be used as AI context for summaries, tags, or recommendations. |
| `derivative_copywriting` | Can be rewritten as promotional copy. |
| `asset_download` | Can be downloaded by internal users or sent to customers. |

Default policy:

> Unknown authorization means internal search only. It is not public, not
> marketing-ready, and not allowed in AI processing.

## 13. Supplier Operations Layer

Providers are supplier operating entities, not only names. Phase 1A should add
supplier management fields:

| Module | Fields |
| --- | --- |
| Cooperation status | `cooperation_status`: evaluating / trial / active / paused / blacklisted |
| Contract | `contract_status`, `contract_start_at`, `contract_end_at`, `contract_file_uri` |
| Settlement | `settlement_model`, `commission_rate`, `settlement_cycle`, `invoice_supported` |
| Refund and disputes | `refund_policy`, `refund_before_start`, `refund_after_start`, `dispute_policy` |
| SLA | `response_sla_hours`, `issue_escalation_contact`, `delivery_owner` |
| Authorization | `authorized_usage_scope`, `public_display_allowed`, `marketing_allowed`, `ai_summary_allowed` |
| Performance | `complaint_rate`, `refund_rate`, `delay_rate`, `satisfaction_avg`, `supplier_rating` |
| Risk | `academic_compliance_risk`, `overclaim_risk`, `historical_issues`, `blacklist_reason` |
| Review | `last_supplier_reviewed_at`, `reviewed_by`, `next_review_due_at` |

Supplier status should affect sales and publish gates. A paused provider should
not be main-promoted; a blacklisted provider should not be recommended for new
customers.

## 14. Commercial, Sales, Customer Fit, and Claims

### 14.1 Commercial Profiles

`project_commercial_profiles` should support:

| Field | Meaning |
| --- | --- |
| `provider_cost_amount` | Supplier cost or purchase price. |
| `list_price_amount` | External list price. |
| `suggested_sale_price` | Recommended sale price. |
| `min_sale_price` | Lowest allowed sale price. |
| `commission_rate` | Commission percentage. |
| `gross_margin_amount` | Gross margin amount. |
| `gross_margin_rate` | Gross margin percentage. |
| `settlement_model` | Commission, purchase price, tiered commission, or other model. |
| `settlement_cycle` | Settlement timing. |
| `discount_approval_level` | Who can approve discount below suggested price. |
| `refund_liability_owner` | Provider, company, shared, or case-by-case. |
| `package_fit` | Whether it can be bundled with planning, competition, internship, or essays. |
| `commercial_priority` | S / A / B / C priority for business use. |

Public price rule:

```text
public price visible =
  offering allows public price
  AND display profile allows price
  AND price freshness is valid
  AND rights/policy gates pass
```

### 14.2 Sales Profiles

`project_sales_profiles` should support:

| Field | Meaning |
| --- | --- |
| `one_liner` | One-sentence selling point. |
| `customer_pain_points` | Pain points this project solves. |
| `key_selling_points` | Structured selling points. |
| `sales_script_short` | Short private chat pitch. |
| `sales_script_long` | Longer explanation script. |
| `faq_json` | Standard questions and answers. |
| `objection_handling_json` | Objection handling. |
| `successful_case_summary` | Case summary if available. |
| `case_background_tags` | Student background tags from usable cases. |
| `comparison_notes` | Comparison with similar projects. |
| `recommended_scenarios` | When to recommend. |
| `not_recommended_scenarios` | When not to recommend. |
| `forbidden_claims` | Claims sales must not make. |
| `display_materials` | Approved shareable materials. |
| `internal_training_notes` | Training notes for customer operations. |

Forbidden claims must be structured and testable, not buried in free-text notes.

### 14.3 Customer Fit Rules

`project_customer_fit_rules` should support:

| Field | Meaning |
| --- | --- |
| `target_countries` | Target application countries or regions. |
| `degree_goal` | Undergraduate, master, PhD, transfer, or other goal. |
| `application_stage` | Early planning, before season, in season, gap year. |
| `target_major_groups` | Business, CS, psychology, biology, media, etc. |
| `student_grade_band` | High school, lower undergraduate, upper undergraduate, graduate. |
| `time_window_min_days` | Minimum feasible time window. |
| `time_window_max_days` | Maximum or typical time window. |
| `budget_band` | Budget bucket. |
| `required_foundation` | No foundation, course foundation, research foundation. |
| `risk_tolerance_needed` | Low, medium, or high risk tolerance. |
| `best_fit_customer_type` | Best-fit customer description. |
| `poor_fit_customer_type` | Poor-fit customer description. |
| `match_score_weight` | JSON weights for future recommendation. |

These fields are Phase 1A because they drive sales matching even before CRM
integration.

### 14.4 Deliverable Claims

`project_deliverable_claims` should split outputs into:

| Claim Type | Meaning | Sales Handling |
| --- | --- | --- |
| `guaranteed` | Course learning, project report, completion proof, mentor feedback | Can be clearly stated if evidence supports it. |
| `conditional` | Recommendation letter, strong recommendation, paper submission support | Must include conditions and disclaimer. |
| `prohibited` | Guaranteed publication, guaranteed conference acceptance, guaranteed school admission lift | Must not be used in sales or public display. |

Fields:

```text
canonical_project_id
claim_type
claim_category
claim_text
evidence_source
review_status
risk_level
public_allowed
sales_allowed
required_disclaimer
```

Deliverable claims should be part of publish gates and sales material export
gates.

## 15. Project and Supplier Scoring

Readiness answers whether a project can be searched or published. Operations
also need a recommendation/business score.

Recommended score model:

| Dimension | Weight | Meaning |
| --- | ---: | --- |
| Customer fit | 25 | Fit with grade, major, country, budget, and time window. |
| Academic value | 20 | Instructor, topic, method, and output quality. |
| Sales conversion | 15 | Clear selling points, cases, parent-friendly explanation. |
| Delivery stability | 15 | Provider response, complaint, delay, refund history. |
| Commercial value | 10 | Margin, order value, bundling fit. |
| Compliance safety | 10 | Claims, authorization, public display, academic risk. |
| Data completeness | 5 | Completeness, freshness, review status. |

Recommendation levels:

| Score | Level | Strategy |
| ---: | --- | --- |
| 85-100 | S | Main promotion. |
| 70-84 | A | Normal recommendation. |
| 60-69 | B | Conditional recommendation. |
| 50-59 | C | Cautious recommendation. |
| <50 | D | Not recommended or archive. |

Severe compliance risks should be vetoes; they must not be offset by a high
total score.

## 16. C Complete Platform Roadmap

| Phase | Goal | Capabilities |
| --- | --- | --- |
| Phase 1A | Internal sales operations MVP | Import, canonical projects, operations search, supplier operations, commercial fields, sales materials, customer fit rules, deliverable claims. |
| Phase 1B | Review and public display | Field review, publish gates, display profiles, public projections and APIs. |
| Phase 1C | Deal and delivery feedback | Lightweight recommendation/deal/lost/complaint/refund/satisfaction feedback. |
| Phase 2 | Data governance enhancement | Quality scoring, batch cleanup, version rollback, publish audit, taxonomy governance, supplier score trend. |
| Phase 3 | Recommendation and matching | Student need intake, rule-based recommendation, recommendation reasons, operations feedback loop, recommendation logs. |
| Phase 4 | Platform integration | Automated sync, CRM integration, dashboards, content publishing, full permission workflow. |

## 17. B Phase 1 Milestones

### Phase 0: Coding Gates

Before coding, decide:

- backend stack;
- PostgreSQL dev/staging environment;
- unknown rights policy;
- initial taxonomy;
- source/provider correction owner;
- price visibility default;
- freshness windows;
- Phase 1A/1B/1C release boundary.

Default policy:

- unknown rights are internal-search only;
- price is internal only;
- public API ships in Phase 1B;
- high-confidence duplicates block public publish but not internal search.

### Phase 1A: Internal Sales Operations MVP

Deliver:

- PostgreSQL table definitions;
- enums and status fields;
- indexes and constraints;
- required business fields;
- JSONB raw fields;
- provider/source separation;
- offering-level price, start date, duration, and enrollment fields;
- rights and takedown fields for public assets and display content;
- field provenance model;
- data quality issue and enrichment task tables;
- explicit readiness levels for search, display draft, review, and publish.
- source record versioning;
- supplier operating records;
- commercial profiles;
- sales profiles;
- customer fit rules;
- deliverable claims.

Acceptance:

- current four sources import with traceability and quality issues;
- customer operations can find three candidate projects within 60 seconds;
- main-promoted projects have one-liner, selling points, FAQ, and forbidden
  claims;
- sellable projects have cost, suggested price, commission or margin;
- supplier status, refund, settlement, authorization, and risk are visible;
- missing public fields do not block internal search.

### Phase 1B: Review and Public Display

Deliver:

- field-level review states;
- project-level publish states;
- candidate merge handling;
- change event logs;
- publish, unpublish, and archive actions.
- public project list API;
- public project detail API;
- published-only filtering;
- field allowlist projections;
- no raw JSON, internal notes, unapproved assets, or unreviewed high-risk field
  exposure.
- supplier authorization gate;
- sales claim approval gate;

Acceptance:

- public APIs expose only published allowlist fields;
- public and sales materials cannot use prohibited claims;
- unknown rights do not appear in public or marketing outputs;
- high-risk fields require review before publication.

### Phase 1C: Deal and Delivery Feedback

Deliver:

- `project_order_feedback`;
- project usage events for recommended/viewed/sent/favorited/exported;
- supplier/project score inputs;
- basic management dashboard queries.

Acceptance:

- operations can record recommended, deal, lost, complaint, refund, satisfaction,
  and case usability status;
- supplier and project quality can be reviewed from feedback data;
- feedback does not become a full order/payment/contract workflow.

## 18. Strategy Loophole Audit and Fixes

The strategy was audited for likely failure modes. The fixes below are part of
the approved design, not optional implementation suggestions.

| Loophole | Risk | Fix |
| --- | --- | --- |
| Treating price, enrollment, duration, and start date as project-level fields | Same project may have multiple cohorts, dates, prices, or enrollment statuses | Add `project_offerings` and query offering fields from there. |
| Confusing data source with commercial project provider | A project can be imported from one source but sold or supplied by another provider | Add `providers` and keep `sources` only for import/source lineage. |
| Public publish based only on `published` status | Unreviewed fields or assets could leak if status is set incorrectly | Add publication gates and public API field allowlists. |
| Assuming public rights for posters, avatars, bios, and descriptions | Customer-facing reuse may violate partner terms or takedown requests | Add `rights_scopes` and takedown controls; hide assets or copy without approved scope. |
| Importing discovery/network logs into operational raw records | Cookies, authorization headers, or session data could enter the database | Limit imports to project records and asset metadata; redact/reject secret-like fields. |
| Automatic duplicate merging | Similar titles or schools can incorrectly collapse different projects | Keep duplicate handling as candidate-only until admin confirmation. |
| Losing field provenance after manual cleanup | Operations cannot explain why a field differs from source data | Add `field_provenance` for source, normalized, manual, generated, reviewed, and published values. |
| Treating missing public fields as import failures | Useful internal records would be rejected even if they are valuable for operations search | Add readiness levels, `data_quality_issues`, and `enrichment_tasks`. |
| One-to-one taxonomy fields are too rigid | Projects can span multiple disciplines, skills, outputs, and suitable majors | Add controlled vocabulary tables and many-to-many links. |
| Chinese search quality may be weak with only simple indexes | Operations may fail to find projects by natural Chinese queries | Add `project_search_documents`; evaluate stronger search in Phase 2 if needed. |
| Published URLs can break after merges | Customer links may 404 or show wrong project after manual merge | Add stable public slugs and redirect/unpublish decision on merge. |
| Display profile drift from academic truth | Polished copy may overstate professor scope or expected outcomes | Require academic review for high-risk academic and output-claim fields. |
| Sensitive internal pricing or notes leak to public API | Frontend could accidentally serialize internal fields | Public APIs read allowlist projections only, not raw tables. |
| Role boundaries exist only in UI copy | A user could call internal endpoints directly and bypass review/publish rules | Enforce minimal RBAC in backend APIs. |
| Manual imports allow data to become stale | Operations may sell or display projects with outdated price, enrollment, or start dates | Add freshness metadata, verification tasks, and publish gates. |
| AI-generated summaries or recommendations overstate claims | Customers may see inaccurate academic or commercial claims | Treat generated content as draft with provenance and required review. |
| Raw record immutability conflicts with takedown or legal deletion | Restricted content may remain exposed after partner/legal request | Add compliance redaction/tombstone exception to raw immutability. |
| Phase 1 is too engineering-heavy | Customer operations may not use a technically correct system | Split Phase 1A internal operations MVP from Phase 1B public display. |
| Provider is only a name table | Supplier reliability, settlement, refund, authorization, and risk cannot be managed | Add supplier operations fields, provider contracts, and performance metrics. |
| Commercial decision fields are missing | Operations cannot know which projects are profitable or discountable | Add commercial profiles with cost, suggested price, min price, commission, and margin. |
| Sales enablement fields are missing | Operations cannot quickly pitch, compare, or avoid forbidden claims | Add sales profiles and structured forbidden claims. |
| Customer matching is too academic-field based | Operations search may not match actual student decision inputs | Add customer fit rules based on country, major, degree goal, budget, time window, foundation, and risk tolerance. |
| Deliverable claims are only free text | Sales may overpromise outcomes | Add structured guaranteed, conditional, and prohibited claims. |
| Asset rights are too coarse | Same asset can be allowed internally but forbidden for public, ads, or AI | Add rights scopes by usage scenario. |
| No feedback loop | System cannot learn which projects sell, deliver well, or cause complaints | Add lightweight order/delivery feedback and usage events. |

## 19. Acceptance Criteria

Phase 1 is accepted when:

1. Existing four project datasets and HIREP asset manifest can be imported.
2. Every imported source record can be traced to source, source URL, import batch,
   and raw JSON.
3. Required business fields listed in this spec can be stored.
4. Project provider is modeled separately from import source.
5. Price, duration, start date, capacity, and enrollment status are modeled as
   offering-level data.
6. Operations can filter projects by provider, priority, duration, discipline,
   specialization, difficulty, suitable grade, professor school, institution
   country, delivery country, enrollment status, and related fields.
7. High-risk display fields do not appear in public APIs before approval.
8. Public card and detail data can be generated from `project_display_profiles`.
9. Public APIs use allowlist projections and do not expose raw JSON, internal
   notes, unapproved assets, or unreviewed high-risk fields.
10. Candidate duplicates are generated for review and are not automatically merged.
11. Projects can be published, unpublished, archived, and redirected after merge
   with change events.
12. Binary PDF and image data remains outside PostgreSQL; only metadata and paths
   are stored.
13. Import jobs reject or redact cookies, authorization headers, tokens, session
   data, and other secret-like fields.
14. Public assets and display fields can be blocked by rights or takedown status.
15. Records with missing public-display fields can still be imported for internal
   search, while missing data creates quality issues or enrichment tasks.
16. Each canonical project exposes a readiness level so operations can distinguish
   searchable records from publish-ready records.
17. Fast-changing public fields expose freshness metadata and can generate
   verification tasks.
18. AI-generated or AI-assisted public fields remain drafts until reviewed.
19. Takedown or legal redaction can remove exposure while preserving an audit
   tombstone.
20. Backend APIs enforce operations, academic reviewer, and admin permissions.
21. Phase 1A internal operations MVP can be used without public API release.
22. Main-promoted projects have sales-ready fields and forbidden claims.
23. Sellable projects have commercial fields for cost, suggested price,
   commission or margin, and discount constraints.
24. Providers have cooperation, settlement, refund, authorization, SLA, and risk
   fields.
25. Project matching supports customer inputs such as target country, target
   major, degree goal, budget, time window, foundation, and risk tolerance.
26. Deal/delivery feedback can record recommendation, deal/lost, complaint,
   refund, satisfaction, and case usability.

## 20. Risks and Constraints

1. Some source fields are inconsistent. For example, school and professor title
   may be combined in the same text field and require cleanup.
2. Automatic merge is risky because project titles, professor names, and schools
   may be inconsistent across partners.
3. Public display quality depends on review discipline. Without review, polished
   display profiles can drift from source data.
4. Price and enrollment status are operationally sensitive and should not be
   public by default.
5. The first phase should avoid overbuilding CRM and recommendation features
   before the project data model is stable.
6. The organization must confirm partner permissions for public reuse of project
   descriptions, professor bios, avatars, posters, and attachments.
7. Search quality for Chinese project descriptions must be validated with real
   operations queries before adding a dedicated search engine.
8. The strategy remains conditional on operational review discipline. If review
   queues are ignored, public display quality and compliance will degrade.
9. Manual imports require a freshness policy. Without periodic verification,
   price, enrollment, start date, and availability can become unreliable.
10. AI-assisted content can improve drafting speed, but must not bypass review
   or rights checks.
11. Supplier commercial data may be incomplete at import time and will require
   manual supplier operations cleanup.
12. Sales fields are only useful if customer operations maintain them and use
   forbidden-claim rules in real conversations.
13. Feedback metrics will be biased until enough recommendation and delivery
   records are collected.

## 21. Implementation Planning Decisions

1. `institutions` should exist in Phase 1. When a source field combines school,
   department, and professor title, the raw value is retained and the normalized
   institution can be filled manually or by cleanup rules.
2. Display profile versions should be stored as separate
   `project_display_profiles` rows with `version`, `status`, and timestamps.
   `change_events` records why a version changed.
3. Import mapping should be source-specific. Each partner source gets an import
   adapter that maps raw records into the common fields in this spec.
4. Duplicate candidate scoring should use a conservative threshold in Phase 1:
   exact source key matches link directly; fuzzy title plus professor plus
   institution matches create candidates for human review only.
5. `project_offerings` should exist in Phase 1. Price, start date, duration,
   capacity, and enrollment status are offering-level by default.
6. `providers` should exist in Phase 1 and remain separate from `sources`.
   `sources` describe where data came from; `providers` describe who supplies or
   owns the project offering.
7. Public display profiles should have stable `public_slug` values. Merge or
   archive actions must decide whether old slugs redirect, unpublish, or remain
   attached to the surviving canonical project.
8. Taxonomy and suitable majors should use controlled vocabularies with aliases,
   not only free-text fields.
9. Public API implementation must use explicit projections or DTOs. It must not
   serialize ORM/database entities directly.
10. Import adapters must include a secret-field rejection/redaction step before
   writing raw JSON into the operational database.
11. Fast-changing fields must include verification metadata in Phase 1 even if
   scheduled automated re-sync is deferred.
12. Compliance takedown/redaction is the only exception to raw record immutability.
   The system should keep an audit tombstone rather than silently deleting
   history.
13. AI-assisted fields are allowed only as drafts with generated provenance and
   review requirements.
14. Minimal backend RBAC is part of Phase 1. Frontend-only permission checks are
   not sufficient.
15. Phase 1A should prioritize internal operations search, supplier/commercial
   fields, sales materials, customer fit rules, and claims control before public
   API release.
16. `source_project_records` should represent logical source identity, while
   `source_project_record_versions` stores immutable raw snapshots.
17. Use `assets` and `asset_links` as the long-term asset model. A
   `project_assets` compatibility view can be created if useful.
18. Rights must be represented as scoped usage permissions, not only as a single
   approved/unknown status.
19. Business-changing values such as project type, enrollment status, difficulty,
   provider type, and rights scopes should use lookup tables rather than
   PostgreSQL enums when frequent changes are expected.
