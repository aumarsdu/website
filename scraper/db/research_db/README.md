# Research Project Database

This folder contains the PostgreSQL DDL and importer for the local research
project SKU database.

## Files

- `schema.sql`: PostgreSQL schema aligned with the Design Spec and
  Implementation Plan.
- `../../tools/research_db_prepare_staging.py`: prepares database-shaped staging
  JSONL from crawler outputs.
- `../../tools/research_db_validate_staging.py`: validates staging JSONL primary
  keys and key foreign keys.
- `../../tools/research_db_import_staging.py`: creates tables and imports
  staging JSONL into PostgreSQL.

## Local Database

The local staging Postgres cluster is stored at:

```text
data_staging/research_db/postgres_cluster
```

It was started on:

```text
host=/tmp
port=55432
user=research_ops
database=research_projects_clean
```

Connection command:

```bash
psql 'postgresql://research_ops@/research_projects_clean?host=/tmp&port=55432'
```

Start local server:

```bash
pg_ctl -D data_staging/research_db/postgres_cluster -o "-p 55432 -k /tmp" -l data_staging/research_db/postgres_cluster.log start
```

Stop local server:

```bash
pg_ctl -D data_staging/research_db/postgres_cluster stop
```

## Rebuild Staging

```bash
python3 tools/research_db_prepare_staging.py
python3 tools/research_db_validate_staging.py data_staging/research_db/20260602
```

## Import To PostgreSQL

```bash
createdb -h /tmp -p 55432 -U research_ops research_projects_clean
python3 tools/research_db_import_staging.py \
  --database-url 'postgresql://research_ops@/research_projects_clean?host=/tmp&port=55432' \
  --batch-size 250
```

The importer runs `schema.sql`, imports JSONL in the documented order, defers
foreign-key checks inside one transaction, and uses `ON CONFLICT DO NOTHING` for
idempotent inserts.

## Verification Queries

Source distribution:

```sql
select s.code, count(*)
from source_project_records r
join sources s on s.id = r.source_id
group by s.code
order by s.code;
```

Provider distribution:

```sql
select provider_name, count(*)
from ops_project_cards
group by provider_name
order by count(*) desc;
```

Quality issues:

```sql
select issue_type, count(*)
from data_quality_issues
group by issue_type
order by count(*) desc;
```

Chinese keyword smoke test:

```sql
select count(*)
from canonical_projects
where title ilike '%人工智能%';
```
