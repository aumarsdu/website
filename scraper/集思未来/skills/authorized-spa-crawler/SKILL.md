---
name: authorized-spa-crawler
description: Build or run a compliant full-crawl project for an explicitly authorized public SPA/H5 website. Use this skill whenever the user says they have permission to crawl a JavaScript app, asks for full-site scraping, API discovery, Network/XHR capture, raw JSON preservation, attachment or poster downloads, structured CSV/JSONL/SQLite output, or organizing scraped assets by the website's category/topic structure. This skill should also trigger when the user mentions Playwright-based interface discovery, mobile share/detail pages, course/project list/detail APIs, or wants downloaded materials renamed and sorted into folders.
---

# Authorized SPA Crawler

Use this skill to turn an explicitly authorized public SPA/H5 site into a maintainable crawler project. The goal is not a quick recursive HTML scraper; the goal is a production-style workflow:

1. discover public APIs by observing the browser;
2. classify list/detail/filter/asset endpoints;
3. crawl API data conservatively;
4. preserve raw responses;
5. normalize records into structured outputs;
6. download public assets;
7. verify important asset classes such as posters;
8. organize material into human-friendly folders that match the website's structure.

Default language for user-facing explanations: Simplified Chinese.

## Safety Boundary

Proceed only when the user states or strongly implies authorization for the target site. Even with authorization:

- Do not bypass login, CAPTCHA, paywalls, private APIs, signatures, access controls, or bot defenses.
- Do not use proxy pools, IP rotation, UA rotation, browser fingerprint spoofing, credential harvesting, token extraction, or brute-force enumeration.
- Do not collect private user/account/customer/lead data.
- Crawl only public frontend-displayed data and public API responses in scope.
- Use a transparent User-Agent such as `AuthorizedResearchCrawler/1.0`.
- Default to conservative traffic: concurrency 1-3, per-request delay 1-3 seconds, max 2 retries, exponential backoff on 429/5xx, and stop or quarantine paths on 401/403.
- Redact `Cookie`, `Authorization`, `token`, `session`, `secret`, `password`, and CSRF-like headers before writing logs.

If authorization or legality is unclear, build only a dry-run discovery scaffold and document the risk.

## First Response Pattern

Start with the conclusion and scope:

- Confirm whether this is an authorized public SPA/H5 crawl.
- State that Playwright will be used only for API discovery and direct HTTP will be used for bulk crawling.
- State the conservative defaults for rate limit, retries, and User-Agent.
- Mention that raw outputs will be preserved and normalized outputs generated separately.

Then inspect the workspace before editing:

```bash
pwd
git status --short --branch || true
git rev-parse --show-toplevel || true
rg --files -g 'AGENTS.md' -g 'pyproject.toml' -g 'requirements*.txt' -g 'README*' -g '*.py'
```

If there is a project-level `AGENTS.md`, read and follow it.

## Architecture To Create

Use the existing repo style if one exists. For a new Python project, create:

```text
sou_crawler/
  __init__.py
  __main__.py
  cli.py
  config.py
  discovery.py
  classifier.py
  fetcher.py
  parser.py
  crawler.py
  asset_downloader.py
  normalizer.py
  organizer.py
  reporter.py
  utils.py
tests/
  fixtures/
  test_classifier.py
  test_dedup.py
  test_normalizer.py
  test_storage.py
output/
  discovery/
  raw/
  assets/
  processed/
  reports/
pyproject.toml
README.md
```

Keep responsibilities separate:

- `discovery.py`: Playwright browser API discovery.
- `classifier.py`: endpoint inventory and classification.
- `fetcher.py`: direct HTTP client, throttling, retry, error classification.
- `crawler.py`: list/detail crawl orchestration.
- `asset_downloader.py`: public asset download and retry.
- `normalizer.py`: JSONL/CSV/SQLite outputs.
- `organizer.py`: human-friendly folder structure and renamed materials.
- `reporter.py`: final crawl report.

## Required CLI

Implement or preserve these commands:

```bash
python -m sou_crawler discover
python -m sou_crawler analyze-apis
python -m sou_crawler crawl-lists
python -m sou_crawler crawl-details
python -m sou_crawler download-assets
python -m sou_crawler normalize
python -m sou_crawler report
python -m sou_crawler organize-assets
python -m sou_crawler all
```

Common options:

```text
--dry-run
--max-pages
--max-details
--rate-limit
--timeout
--retries
--concurrency
--user-agent
--output-dir
--headed
```

`--dry-run` should validate scope and print planned URLs/endpoints without persisting final data.

## Discovery Workflow

Use Playwright to open the user-provided entry pages. For SPA/H5 apps, include:

- home/list pages;
- category tabs or URLs;
- filter states if user identifies them;
- mobile share/detail pages if list items link there;
- poster/gallery pages if clicking images opens extra resources.

Capture:

- request URL, method, resource type;
- query params;
- POST payload;
- request headers with sensitive values redacted;
- response status and headers;
- Fetch/XHR classification;
- JSON response bodies when content type is JSON.

Write:

```text
output/discovery/network_logs.jsonl
output/discovery/api_candidates.json
output/discovery/api_inventory.md
```

The inventory must be human-readable and include:

- endpoint URL and method;
- query params and POST body sample;
- response shape summary;
- suspected purpose: category/filter/list/detail/asset/other;
- auth requirement indicators;
- pagination indicators;
- page/pageSize parameter names;
- item ID field names;
- asset URL field names.

If discovery fails because browser launch is blocked by local sandbox permissions, explain the exact failure and ask for permission to run Playwright outside the sandbox. Do not switch to fragile HTML recursion.

## API Classification Heuristics

Classify endpoints using URL, payload, and response fields. Useful hints:

- list/search/page: `list`, `search`, `page`, `total`, `records`, `rows`, `course`, `project`, `data`;
- detail/share: `detail`, `share`, `id`, `uuid`, rich text fields, description fields;
- category/filter: `category`, `classify`, `level`, `subject`, `type`, `tag`, `option`;
- assets: `oss-cn`, `aliyuncs`, `pdf`, `jpg`, `jpeg`, `png`, `webp`, `poster`, `cover`, `image`, `syllabus`, `attachment`;
- content fields: `title`, `name`, `teacher`, `instructor`, `professor`, `university`, `major`, `prerequisite`, `intro`, `description`.

Write:

```text
output/discovery/api_classification.json
output/discovery/api_classification.md
```

Do a manual sanity pass over `api_inventory.md`; automatic classification is a starting point, not proof.

## Crawling Workflow

For bulk data, use direct HTTP (`httpx`, `aiohttp`, or standard library fallback) instead of browser automation.

List crawling:

- Use distinct discovered POST bodies as seeds so different categories/filters are preserved.
- Rewrite pagination in POST body if pagination is body-based (`page`, `pageNo`, `pageNum`, `current`, `limit`, `size`, `pageSize`).
- Deduplicate by stable item ID when present, otherwise canonical URL/content hash.
- Store raw list responses and extracted list records separately.

Detail crawling:

- Prefer a discovered public detail/share endpoint.
- If details are served by a mobile share page, open one representative item in Playwright, discover the detail API, then call that API directly for all IDs.
- Do not infer private endpoints or bypass signatures.
- Store raw detail responses separately from normalized records.

Write:

```text
output/raw/list_responses.jsonl
output/raw/list_records.jsonl
output/raw/detail_responses.jsonl
output/reports/crawl_lists_stats.json
output/reports/crawl_details_stats.json
```

Track:

- pages requested/succeeded/failed;
- records extracted;
- duplicates;
- error categories.

Error categories:

```text
http_401_unauthorized
http_403_forbidden
http_404_not_found
http_429_rate_limited
http_5xx_server_error
timeout
parse_error
schema_validation_error
storage_error
unknown_error
```

## Asset Download Workflow

Extract asset URLs from list and detail raw JSON, including nested arrays and rich text strings. Download public assets into:

```text
output/assets/
```

Requirements:

- Preserve a deterministic filename based on URL hash plus source basename.
- Skip existing files on reruns.
- Handle URL encoding for non-ASCII paths.
- Classify partial downloads (`IncompleteRead`), timeouts, 403, 404, and unknown network errors.
- Retry failed transient assets with lower concurrency and longer timeout.
- Generate missing asset reports.

Write:

```text
output/reports/download_assets_stats.json
output/reports/missing_assets.json
```

If the user asks about posters or any critical asset class, explicitly verify that class rather than relying on generic asset totals.

## Poster And Gallery Verification

For course/project sites, poster assets may come from multiple places:

- list item popup poster fields such as `courseImgUrl`, `poster`, `cover`, `imageHeader`;
- detail page fields;
- gallery or summary poster endpoints triggered by clicking homepage/list images;
- mobile share pages.

Do this verification:

1. Identify the frontend field that powers the visible poster popup.
2. Count total items, items with poster URL, downloaded posters, and missing poster downloads.
3. Inspect the frontend JS or network logs for separate gallery/summary poster APIs.
4. Call those public APIs and download all returned poster URLs.
5. Write a poster-specific report.

Suggested outputs:

```text
output/reports/poster_coverage.md
output/reports/poster_assets.json
output/reports/poster_assets.csv
output/reports/summary_poster_assets.json
output/reports/summary_poster_assets.csv
```

The report should distinguish:

- data missing because the API has no poster URL;
- download missing because the file could not be fetched.

## Normalization Workflow

Normalize to one row per primary business object, not one row per nested attachment. Keep nested raw JSON available.

Write:

```text
output/processed/records.jsonl
output/processed/records.csv
output/processed/records.sqlite
output/reports/normalize_stats.json
```

Include:

- `record_key`;
- `source_url`;
- `canonical_url`;
- `crawled_at`;
- primary title/name fields;
- teacher/professor fields;
- university/school fields;
- description/intro fields;
- `asset_urls`;
- raw JSON.

If normalization accidentally expands nested attachments into separate primary rows, fix it before reporting success.

## Organizing Materials By Website Structure

When the user wants collected materials organized like the website:

1. Build category membership from list response seeds or category/filter metadata.
2. Create a top-level folder per website category, e.g. `计算机与人工智能`.
3. Under each category, create one folder per topic/project using the topic title.
4. If the same topic appears in multiple categories, include it under each relevant category.
5. Rename the main poster to the topic title.
6. Rename professor headshots to the professor name.
7. Rename attachments using the attachment label when available, e.g. `项目大纲 Syllabus.pdf`.
8. Write `metadata.json` into every topic folder with original list/detail JSON and file mappings.
9. Generate a global manifest and stats report.

Suggested output:

```text
output/organized_by_site/
output/reports/organized_assets_manifest.json
output/reports/organized_assets_stats.json
```

Implementation notes:

- Prefer hard links for local organization when source and target are on the same filesystem. This gives renamed files in topic folders without duplicating gigabytes of data.
- Fall back to `shutil.copy2` if hard links fail.
- Rebuild the organization output directory on rerun so stale partial results do not remain.
- Sanitize `/`, `:`, NUL, trailing spaces, and other filesystem-hostile characters.
- Preserve suffixes from source files.
- For very long topic names, truncate safely to filesystem limits and keep the full title in `metadata.json` and the global manifest.
- Ensure unique filenames preserve their numeric suffix; avoid truncating away `_2`, `_3`, etc.

## Documentation

Update or create `README.md` with:

- what the crawler does;
- target fields;
- compliance notes;
- setup;
- dry-run commands;
- production run commands;
- output formats;
- known limitations;
- how to update endpoint selectors/classification;
- how to run asset organization.

## Testing

Before final response, run the smallest relevant checks:

```bash
python -m compileall sou_crawler tests
python -m pytest
```

If `pytest` is unavailable, say so and run a minimal manual test runner that imports and exercises the test functions.

Minimum tests:

- API classifier with fixture `network_logs.jsonl`;
- canonical URL/content-hash dedup;
- normalization output;
- storage serialization;
- organizer naming/unique-path behavior if organizing assets.

Tests must not depend on live websites.

## Final Response Template

Use this structure:

```text
## 完成内容
- ...

## 关键设计
- ...

## 合规处理
- rate limit:
- user-agent:
- data minimization:
- access-control handling:

## 如何运行
```bash
...
```

## 测试结果
```bash
...
```

## 输出位置
- ...

## 风险与后续建议
- ...
```

Keep the final concise but include exact counts, output paths, failed/missing asset counts, and any known boundaries.

## Examples

**User request:**
“我已授权抓取这个 SPA 网站，请全量采集课程数据、附件和海报。”

**Expected approach:**
Build/run discovery, classify APIs, direct-crawl list/detail endpoints, download assets, verify posters, normalize outputs, generate report.

**User request:**
“列表页点图片会弹出海报，确认这些海报都采到了。”

**Expected approach:**
Find the popup poster field from records/frontend JS, count poster URLs, verify local files, discover gallery endpoints if any, download missing posters, write poster coverage report.

**User request:**
“把采集到的素材按网站栏目和课题名称整理，教授头像用教授名。”

**Expected approach:**
Build category membership from list responses, create `output/organized_by_site/<栏目>/<课题>/`, link/copy poster as topic name, teacher image as teacher name, attachments by label, and write manifests.

