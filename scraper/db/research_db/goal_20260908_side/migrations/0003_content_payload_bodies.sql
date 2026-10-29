-- 0003_content_payload_bodies.sql — T10: sanitized business bodies for payloads
-- The hash-only payload table cannot render projections; the sanitized body
-- (whitelisted business fields + field states) is stored alongside its digest.

CREATE TABLE content_payload_bodies (
    payload_id bigint PRIMARY KEY REFERENCES content_payloads,
    business jsonb NOT NULL,
    field_states jsonb NOT NULL
);
