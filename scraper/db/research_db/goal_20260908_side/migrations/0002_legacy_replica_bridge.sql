-- 0002_legacy_replica_bridge.sql — migrate representative legacy schema (legacy_replica)
-- into the candidate model. Explicit column mapping only; no global DO NOTHING.
-- Records what it did in legacy_bridge_status; maps every legacy row in legacy_id_map.
-- Requires the pgcrypto contrib extension for the legacy manifest digest (created
-- explicitly here; a cluster without contrib fails loudly at this statement).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE legacy_bridge_status (
    bridge text PRIMARY KEY,
    legacy_replica_present boolean NOT NULL,
    migrated_counts jsonb NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

DO $$
DECLARE
    present boolean;
    v_providers bigint;
    v_sources bigint;
    v_batches bigint;
    v_records bigint;
    v_versions bigint;
    v_projects bigint;
    v_links bigint;
    v_offerings bigint;
    v_provider_rows_merged bigint;
    v_null_source_batches bigint;
BEGIN
    present := to_regnamespace('legacy_replica') IS NOT NULL
        AND to_regclass('legacy_replica.providers') IS NOT NULL;
    IF NOT present THEN
        INSERT INTO legacy_bridge_status (bridge, legacy_replica_present, migrated_counts)
        VALUES ('0002', false, '{"status": "no_legacy_replica_present"}'::jsonb);
        RETURN;
    END IF;

    INSERT INTO providers (provider_name)
    SELECT DISTINCT ON (name) name FROM legacy_replica.providers ORDER BY name, id;
    GET DIAGNOSTICS v_providers = ROW_COUNT;

    INSERT INTO legacy_id_map (legacy_table, legacy_id, new_table, new_id)
    SELECT 'providers', p.id::text, 'providers', n.provider_id::text
    FROM legacy_replica.providers p
    JOIN providers n ON n.provider_name = p.name
    ON CONFLICT DO NOTHING;

    -- explicit, non-silent accounting for rows that cannot map 1:1
    v_provider_rows_merged := (SELECT count(*) FROM legacy_replica.providers)
        - v_providers;
    v_null_source_batches := (SELECT count(*) FROM legacy_replica.ingest_batches
        WHERE source_id IS NULL);

    -- legacy sources carry no provider FK; the association exists through
    -- canonical_projects → source_project_records, resolved here per source.
    -- namespace = legacy source code keeps entries distinct under one provider.
    INSERT INTO sources (source_code, provider_id, namespace)
    SELECT s.code, pm.new_id::bigint, s.code
    FROM legacy_replica.sources s
    JOIN legacy_id_map pm ON pm.legacy_table = 'providers'
        AND pm.legacy_id = (
            SELECT cp.provider_id::text
            FROM legacy_replica.canonical_projects cp
            JOIN legacy_replica.source_project_records r
              ON r.id = cp.primary_source_record_id
            WHERE r.source_id = s.id
            LIMIT 1);
    GET DIAGNOSTICS v_sources = ROW_COUNT;

    INSERT INTO legacy_id_map (legacy_table, legacy_id, new_table, new_id)
    SELECT 'sources', s.id::text, 'sources', n.source_id::text
    FROM legacy_replica.sources s
    JOIN sources n ON n.source_code = s.code
    ON CONFLICT DO NOTHING;

    INSERT INTO ingest_batches (batch_id, source_id, manifest_digest, contract_version,
                                capture_mode, captured_at, observed_order, coverage,
                                adapter_version, mapping_version, hash_version)
    SELECT b.batch_code,
           sm.new_id::bigint,
           encode(digest(b.id::text || b.stats_json::text, 'sha256'), 'hex'),
           'legacy-bridge',
           'full',
           COALESCE(b.started_at, b.created_at, now()),
           NULL,
           'unknown',
           'legacy',
           'legacy',
           'legacy'
    FROM legacy_replica.ingest_batches b
    JOIN legacy_id_map sm
      ON sm.legacy_table = 'sources' AND sm.legacy_id = b.source_id::text;
    GET DIAGNOSTICS v_batches = ROW_COUNT;

    -- batches without a legacy source cannot be attributed and are NEVER
    -- silently dropped: they are counted and fail reconciliation when absent
    -- from the explicit counter below.
    IF v_batches + v_null_source_batches
        <> (SELECT count(*) FROM legacy_replica.ingest_batches) THEN
        RAISE EXCEPTION 'bridge reconciliation failed: ingest_batches % migrated, % null-source, % total',
            v_batches, v_null_source_batches,
            (SELECT count(*) FROM legacy_replica.ingest_batches);
    END IF;

    INSERT INTO legacy_id_map (legacy_table, legacy_id, new_table, new_id)
    SELECT 'ingest_batches', b.id::text, 'ingest_batches', n.batch_id
    FROM legacy_replica.ingest_batches b
    JOIN ingest_batches n ON n.batch_id = b.batch_code
    ON CONFLICT DO NOTHING;

    INSERT INTO source_records (source_id, identity_key, identity_status)
    SELECT sm.new_id::bigint,
           '{"native_id":' || to_jsonb(r.source_record_key)::text
             || ',"source":' || to_jsonb((SELECT code FROM legacy_replica.sources
                                          WHERE id = r.source_id))::text || '}',
           'confirmed'
    FROM legacy_replica.source_project_records r
    JOIN legacy_id_map sm
      ON sm.legacy_table = 'sources' AND sm.legacy_id = r.source_id::text;
    GET DIAGNOSTICS v_records = ROW_COUNT;

    INSERT INTO legacy_id_map (legacy_table, legacy_id, new_table, new_id)
    SELECT 'source_project_records', r.id::text, 'source_records', n.source_record_id::text
    FROM legacy_replica.source_project_records r
    JOIN source_records n
      ON n.identity_key = '{"native_id":' || to_jsonb(r.source_record_key)::text
           || ',"source":' || to_jsonb((SELECT code FROM legacy_replica.sources
                                        WHERE id = r.source_id))::text || '}'
    ON CONFLICT DO NOTHING;

    INSERT INTO content_payloads (payload_hash, hash_version)
    SELECT DISTINCT v.raw_hash, 'legacy'
    FROM legacy_replica.source_project_record_versions v;

    INSERT INTO observations (source_record_id, payload_id, batch_id, context_key,
                              order_key, evidence_location)
    SELECT rm.new_id::bigint,
           c.payload_id,
           bm.new_id,
           'legacy',
           CASE WHEN v.crawled_at IS NULL THEN NULL
                ELSE to_char(v.crawled_at AT TIME ZONE 'UTC',
                             'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') END,
           COALESCE(v.source_url, 'legacy:' || v.id::text)
    FROM legacy_replica.source_project_record_versions v
    JOIN legacy_id_map rm ON rm.legacy_table = 'source_project_records'
        AND rm.legacy_id = v.source_project_record_id::text
    JOIN legacy_id_map bm ON bm.legacy_table = 'ingest_batches'
        AND bm.legacy_id = v.ingest_batch_id::text
    JOIN content_payloads c ON c.payload_hash = v.raw_hash AND c.hash_version = 'legacy';
    GET DIAGNOSTICS v_versions = ROW_COUNT;

    INSERT INTO provider_projects (provider_id, native_project_key, display_title)
    SELECT pm.new_id::bigint, cp.id::text, cp.title
    FROM legacy_replica.canonical_projects cp
    JOIN legacy_id_map pm ON pm.legacy_table = 'providers'
        AND pm.legacy_id = cp.provider_id::text;
    GET DIAGNOSTICS v_projects = ROW_COUNT;

    INSERT INTO legacy_id_map (legacy_table, legacy_id, new_table, new_id)
    SELECT 'canonical_projects', cp.id::text, 'provider_projects', n.provider_project_id::text
    FROM legacy_replica.canonical_projects cp
    JOIN provider_projects n ON n.native_project_key = cp.id::text
    ON CONFLICT DO NOTHING;

    INSERT INTO project_source_links (provider_project_id, source_record_id, link_basis)
    SELECT ppm.new_id::bigint, srm.new_id::bigint, 'confirmed'
    FROM legacy_replica.project_source_links l
    JOIN legacy_id_map ppm ON ppm.legacy_table = 'canonical_projects'
        AND ppm.legacy_id = l.canonical_project_id::text
    JOIN legacy_id_map srm ON srm.legacy_table = 'source_project_records'
        AND srm.legacy_id = l.source_project_record_id::text;
    GET DIAGNOSTICS v_links = ROW_COUNT;

    INSERT INTO offerings (provider_project_id, offering_key, start_date_raw, start_precision,
                           duration_raw, price_amount, price_raw, currency,
                           enrollment_status_raw, field_state)
    SELECT ppm.new_id::bigint,
           COALESCE(o.offering_code, o.id::text),
           o.start_date_text,
           CASE WHEN o.start_date IS NOT NULL THEN 'day' ELSE 'unknown' END,
           o.duration,
           o.price_amount,
           o.price_amount::text,
           o.price_currency,
           NULL,
           CASE WHEN o.price_amount IS NULL AND o.start_date_text IS NULL
                THEN 'not_provided' ELSE 'value' END
    FROM legacy_replica.project_offerings o
    JOIN legacy_id_map ppm ON ppm.legacy_table = 'canonical_projects'
        AND ppm.legacy_id = o.canonical_project_id::text;
    GET DIAGNOSTICS v_offerings = ROW_COUNT;

    -- reconciliation: the bridge must not silently drop any legacy row
    IF v_sources <> (SELECT count(*) FROM legacy_replica.sources) THEN
        RAISE EXCEPTION 'bridge reconciliation failed: sources % of % migrated',
            v_sources, (SELECT count(*) FROM legacy_replica.sources);
    END IF;
    IF v_records <> (SELECT count(*) FROM legacy_replica.source_project_records) THEN
        RAISE EXCEPTION 'bridge reconciliation failed: source_records % of % migrated',
            v_records, (SELECT count(*) FROM legacy_replica.source_project_records);
    END IF;
    IF v_versions <> (SELECT count(*) FROM legacy_replica.source_project_record_versions) THEN
        RAISE EXCEPTION 'bridge reconciliation failed: versions % of % migrated',
            v_versions, (SELECT count(*) FROM legacy_replica.source_project_record_versions);
    END IF;
    IF v_links <> (SELECT count(*) FROM legacy_replica.project_source_links) THEN
        RAISE EXCEPTION 'bridge reconciliation failed: links % of % migrated',
            v_links, (SELECT count(*) FROM legacy_replica.project_source_links);
    END IF;
    IF v_offerings <> (SELECT count(*) FROM legacy_replica.project_offerings) THEN
        RAISE EXCEPTION 'bridge reconciliation failed: offerings % of % migrated',
            v_offerings, (SELECT count(*) FROM legacy_replica.project_offerings);
    END IF;

    INSERT INTO legacy_bridge_status (bridge, legacy_replica_present, migrated_counts)
    VALUES ('0002', true, jsonb_build_object(
        'providers', v_providers, 'providers_merged_by_name', v_provider_rows_merged,
        'sources', v_sources, 'ingest_batches', v_batches,
        'ingest_batches_unmigrated_null_source', v_null_source_batches,
        'source_records', v_records, 'observations', v_versions,
        'provider_projects', v_projects, 'project_source_links', v_links,
        'offerings', v_offerings));
END;
$$;
