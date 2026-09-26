CREATE TABLE IF NOT EXISTS crawl_batches (
  id TEXT PRIMARY KEY,
  batch_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  config_snapshot TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_uid TEXT UNIQUE NOT NULL,
  source_url TEXT NOT NULL,
  source_domain TEXT,
  source_title TEXT,
  project_name TEXT,
  category TEXT,
  target_grade TEXT,
  start_date TEXT,
  application_deadline TEXT,
  location TEXT,
  organizer TEXT,
  certificate TEXT,
  price TEXT,
  extraction_method TEXT,
  extraction_confidence REAL,
  evidence TEXT,
  content_hash TEXT,
  first_seen_at TEXT,
  last_seen_at TEXT,
  is_active INTEGER DEFAULT 1,
  needs_human_review INTEGER DEFAULT 0
);
