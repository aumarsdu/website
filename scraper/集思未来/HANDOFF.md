# Current Task Handoff

## Status

- Incremental public-source crawl completed on 2026-07-24 in
  `output/incremental/20260724-new-check/`.
- The run found 45 new source records on `sou_tools` and 10 on `domestic`.
- All 55 detail pages completed. Domestic attachments completed; five overseas
  PDF URLs returned source-side HTTP 404 and are recorded as exemptions.
- The Base sync script now resolves coordinates from the supplied URL, excludes
  attachment fields, and validates target field types and select options before
  any write.
- The user reauthorized through an unrestricted terminal. Codex can read that
  session but cannot refresh or save Keychain state itself.
- The sync created 34 missing Base records. Post-write deduplication found 0
  remaining records to create; the table count changed from 1,550 to 1,584.
- Exported the newly collected course posters to `2026年7月24日新增/`.
  The export found 59 course-poster references and copied 50 unique files;
  source and destination hashes match for all 50 files.
- Collected single share page
  `https://sou-m.gecacademy.cn/share?id=23e0ae90-f4e9-11f0-80f8-89a6fba17d1b`
  into `2026年7月28日/`. The run saved live detail data, the mobile share
  HTML shell, 12 asset files, 9 PDF URLs, and the organized topic folder under
  `organized_by_site/计算机与人工智能/MIS信息系统管理/`.
- Added `WORKFLOW.md` as the operational runbook for incremental crawl, single
  share page crawl, full refresh, asset completion, poster export, and Lark Base
  sync. `README.md` now links to the runbook and includes the single-share-page
  command plus acceptance checks.
- Ran scope/completeness audit `20260730-scope-audit-v3` against the current
  allowed source range: overseas `https://sou-tools.gecacademy.cn/` and domestic
  `https://domestic.gecacademy.cn/`. Domestic is complete. Overseas is missing
  two current list IDs in local detail and organized outputs:
  `2bfd4920-8702-11f1-9a2b-43a0396251d8` and
  `0c363700-8702-11f1-9a2b-43a0396251d8`. Existing organized topic folders have
  zero placement issues. Non-scope source count is zero, so no deletion was
  performed.
- Added targeted incremental repair support through `--site`, `--include-id`,
  and `--include-only`. Run `20260730-missing-sou-tools` fetched both missing
  overseas details, reused 7 cached public assets, downloaded 6 assets, and
  created both organized topic directories without asset failures.
- Post-fill scope/completeness audit `20260730-scope-audit-postfill` is fully
  green: overseas 455/455 and domestic 762/762 have local detail and organized
  directories; placement issues and non-scope source items are both zero.
- Audit `20260811-scope-audit` found the current overseas list changed since
  the July 30 snapshot. Of 447 current overseas IDs, 39 are newly listed and
  still need local detail and organized directories; 2 of the 41 newly listed
  IDs were already present locally. The domestic current list has 624 IDs and
  remains complete. Both list crawls completed without page failures; placement
  issues and non-scope source items remain zero, so no deletion was performed.
- Incremental run `20260811-missing-sou-tools` collected all 39 missing
  overseas topics: 39/39 details succeeded, 122 public assets were reused from
  cache, 119 were downloaded, and no asset failed. The post-fill audit
  `20260811-scope-audit-postfill` is green: overseas 447/447 and domestic
  620/620 current IDs are complete, with zero placement issues and zero
  non-scope source items.
- Audit `20260902-scope-audit` found new current-list coverage gaps: 12 of
  418 overseas IDs and 36 of 466 domestic IDs do not yet have local detail or
  organized directories. Both list crawls completed without page failures;
  existing organized directories have zero placement issues and no non-scope
  source items were found, so nothing was deleted.
- Incremental run `20260902-missing-topics` filled all 48 missing site records:
  overseas 12/12 and domestic 36/36 details succeeded. It reused 112 public
  assets and downloaded 125. Three overseas PDF URLs returned source-side 404
  and are recorded as explicit exemptions. Post-fill audit
  `20260902-scope-audit-postfill` is green: overseas 418/418 and domestic
  466/466 current IDs are complete, with zero placement issues and zero
  non-scope source items.
- After explicit user confirmation, the 2026-09-02 incremental topics were
  deduplicated against the Lark Base and synced. Of 47 unique local topics,
  16 already existed and 31 records were created. Post-write validation found
  1,614 existing records and zero remaining records to create.
- Copied the organized content from `20260902-missing-topics` into
  `集思-2026年9月2日/`, preserving separate `海外教授/` and `华人教授/`
  category/direction/topic hierarchies. The target contains 156 overseas and
  322 domestic files; post-copy rsync and SHA-256 list verification found no
  differences from the source.

## Verification Artifacts

- Initial write: `output/incremental/20260724-new-check/lark_sync/`
- Post-write read-only check: `output/incremental/20260724-new-check/lark_sync_postwrite_check/`
- Poster export report: `output/incremental/20260724-new-check/reports/poster_export.json`
- Single share page report: `2026年7月28日/reports/share_collect_summary.json`
- Workflow runbook: `WORKFLOW.md`
- Scope audit report: `output/audit/20260730-scope-audit-v3/scope_completeness_audit.json`
- Targeted repair report: `output/incremental/20260730-missing-sou-tools/incremental_summary.json`
- Post-fill scope audit: `output/audit/20260730-scope-audit-postfill/scope_completeness_audit.json`
- Latest scope audit: `output/audit/20260811-scope-audit/scope_completeness_audit.json`
- Latest post-fill audit: `output/audit/20260811-scope-audit-postfill/scope_completeness_audit.json`
- Latest targeted incremental run: `output/incremental/20260811-missing-sou-tools/incremental_summary.json`
- Latest scope audit: `output/audit/20260902-scope-audit/scope_completeness_audit.json`
- Latest post-fill audit: `output/audit/20260902-scope-audit-postfill/scope_completeness_audit.json`
- Latest targeted incremental run: `output/incremental/20260902-missing-topics/incremental_summary.json`
- Latest Lark sync: `output/incremental/20260902-missing-topics/lark_sync/`
- Latest Lark post-write check: `output/incremental/20260902-missing-topics/lark_sync_postwrite_check/`
- No attachment field was included in the batch payload.
