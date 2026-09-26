# 集思未来采集工作流

本文是面向日常操作的 runbook。`README.md` 说明项目能力和命令入口；本文说明什么时候使用哪个流程、如何验收、何时停止和何时升级。

## 0. 基线原则

- 默认只采集公开页面和公开接口返回的数据。
- 采集来源范围只包含：
  - 海外教授：`https://sou-tools.gecacademy.cn/`
  - 华人教授：`https://domestic.gecacademy.cn/`
- 支撑接口和附件来源允许包括 `sou-m.gecacademy.cn`、`gec-api.gecacademy.cn`
  以及详情页公开返回的 OSS/CDN/PDF 阅读材料链接；这些不能作为新采集入口扩展。
- 默认 User-Agent 为 `AuthorizedResearchCrawler/1.0`。
- 默认低并发、低速率：`--concurrency 2`，`--rate-limit 1.0` 到 `1.5`。
- 不实现验证码绕过、登录绕过、代理池、UA 轮换或风控规避。
- 不把 Cookie、Authorization、token、session、secret 写入报告或日志。
- 飞书多维表格写入属于外部真实服务写入；没有当前对话明确确认时，只能 dry-run 或只读检查。

## 1. 输出目录约定

常规输出目录结构：

```text
<run-root>/
  raw/
    list_records.jsonl
    list_responses.jsonl
    detail_responses.jsonl
  assets/
  processed/
    records.jsonl
    records.csv
    records.sqlite
  reports/
  organized_by_site/
    一级分类/
      方向/
        课题/
          metadata.json
          详情页信息.json
          详情页信息.md
          海报、头像、PDF、附件...
```

多站点运行输出：

```text
output/full_refresh/<run-id>/
  sou_tools/
  domestic/

output/incremental/<run-id>/
  sou_tools/
  domestic/
```

单分享页运行输出：

```text
2026年7月28日/
  raw/
  assets/
  processed/
  reports/
  organized_by_site/
```

## 2. 工作流选择

| 场景 | 首选流程 | 输出位置 |
| --- | --- | --- |
| 检查是否采全、位置是否正确、是否越界 | 范围与完整性审计 | `output/audit/<run-id>/` |
| 判断官网是否有新增课题 | 增量采集 | `output/incremental/<run-id>/` |
| 只采集一个 `sou-m` 分享页 | 单分享页采集 | 用户指定目录 |
| 重新建立全量基线 | 全量刷新 | `output/full_refresh/<run-id>/` |
| 附件下载不完整或目录没整理 | 附件补齐与整理 | 原运行目录 |
| 只导出新增海报 | 海报导出 | 用户指定目录 |
| 写入飞书多维表格 | 飞书同步 | `output/.../lark_sync/` |

## 3. 范围与完整性审计

Loop type: `goal`

Done when:

- `scope_completeness_audit.json` 和 `scope_completeness_audit.md` 已生成。
- 两个范围站点当前列表快照已保存到 `current_scope/`。
- 报告明确给出 `all_topics_collected`、`all_topics_correctly_placed`、`non_scope_count`。

Stop after:

- 任一范围站点返回 401/403。
- 列表分页连续失败。
- 报告中的 `non_scope_count > 0` 且无法确定是否为生成目录。

Verification:

- `non_scope_count = 0` 时无需删除。
- `placement_issue_count = 0` 表示 `organized_by_site/一级分类/方向/课题/`
  与 `详情页信息.json` 一致。
- 如果 `missing_detail_count` 或 `missing_organized_count` 大于 0，进入增量采集流程补齐。

命令：

```bash
PYTHONPATH=. uv run python scripts/audit_scope_and_completeness.py \
  --run-id 20260730-scope-audit \
  --rate-limit 1.0 \
  --concurrency 2 \
  --timeout 25 \
  --retries 2
```

删除非范围内容：

```bash
PYTHONPATH=. uv run python scripts/audit_scope_and_completeness.py \
  --run-id 20260730-scope-audit-delete \
  --delete-non-scope
```

只有报告中出现明确的非范围生成课题目录时才使用 `--delete-non-scope`。
详情页返回的外部 PDF、阅读材料或 OSS/CDN 附件不是新的采集入口，不应删除。

## 4. 增量采集

Loop type: `goal`

Done when:

- `incremental_summary.json` 存在。
- 两个站点的列表快照都已保存。
- 新增 ID 的详情页全部完成，`detail_missing_ids = 0`。
- 附件下载 `missing_asset_downloads = 0`，或 `asset_exemptions.json` 中有明确来源侧豁免。
- 每个新增课题都生成 `organized_by_site/一级分类/方向/课题/详情页信息.json`。

Stop after:

- 同一网络/接口错误连续失败 2 次。
- 目标站返回 401/403。
- 新增数量异常偏大，超过近期基线 2 倍且无法解释。

Verification:

- 查看 `output/incremental/<run-id>/incremental_summary.md`。
- 查看每个站点 `reports/new_topics.json`、`reports/detail_coverage.json`、`reports/asset_download_stats.json`。
- 运行相关测试。

命令：

```bash
PYTHONPATH=. uv run python scripts/incremental_refresh.py --dry-run

PYTHONPATH=. uv run python scripts/incremental_refresh.py \
  --run-id 20260730-new-check \
  --rate-limit 1.0 \
  --concurrency 2 \
  --timeout 25 \
  --retries 2
```

验收检查：

```bash
PYTHONPATH=. uv run python - <<'PY'
import json
from pathlib import Path

run = Path("output/incremental/20260730-new-check")
summary = json.loads((run / "incremental_summary.json").read_text(encoding="utf-8"))
print("new_topics_total", summary["new_topics_total"])
for site in summary["sites"]:
    details = site.get("details") or {}
    assets = site.get("assets") or {}
    print(site["site"], "new", site["new_topics"],
          "detail_missing", details.get("detail_missing_ids", 0),
          "missing_assets", assets.get("missing_asset_downloads", 0))
PY
```

## 5. 单分享页采集

Loop type: `goal`

适用于用户给出 `https://sou-m.gecacademy.cn/share?id=...` 并指定输出目录的场景。

Done when:

- `raw/share_page.html` 已保存。
- `raw/detail_responses.jsonl` 保存详情接口返回。
- `processed/records.jsonl`、`records.csv`、`records.sqlite` 已生成。
- `assets/` 中素材数量等于报告中的成功下载或缓存复制数量。
- `organized_by_site/` 中生成课题目录、`metadata.json`、`详情页信息.json`、`详情页信息.md`。
- `reports/share_collect_summary.json` 中 `missing_asset_downloads = 0`。

Stop after:

- 分享 URL 缺少 `id`。
- 详情接口返回 401/403/404。
- 详情接口不返回可用 `data.id` 或 `data.name`。

Verification:

- 查看 `reports/share_collect_summary.json`。
- 查看 `organized_by_site/**/详情页信息.json` 的 `pdf_urls` 和 `files`。

命令：

```bash
PYTHONPATH=. uv run python scripts/crawl_share_page.py \
  'https://sou-m.gecacademy.cn/share?id=<course-id>' \
  --output-dir '/Users/liujunliang/Workspace/knowledge-legacy/scraper/集思未来/2026年7月30日' \
  --rate-limit 1.0 \
  --concurrency 2 \
  --timeout 25 \
  --retries 2
```

验收检查：

```bash
PYTHONPATH=. uv run python - <<'PY'
import json
from pathlib import Path

root = Path("/Users/liujunliang/Workspace/knowledge-legacy/scraper/集思未来/2026年7月30日")
summary = json.loads((root / "reports/share_collect_summary.json").read_text(encoding="utf-8"))
print(summary["id"])
print(summary["title"])
print("asset_urls_found", summary["asset_urls_found"])
print("missing_asset_downloads", summary["asset_report"]["missing_asset_downloads"])
print("failed", summary["asset_report"]["failed"])
print("attachments", summary["attachments"])
PY
```

## 6. 全量刷新

Loop type: `goal`

使用场景：

- 需要重建完整本地基线。
- 增量判断异常，需要完整列表对照。
- 站点接口或分类逻辑发生变化。

Done when:

- `output/full_refresh/<run-id>/refresh_summary.md` 生成。
- `sou_tools` 和 `domestic` 都完成列表、详情、附件、归一化和整理。
- 每个站点 `reports/acceptance.json` 为 `pass`，或为有明确附件豁免的 `pass_with_asset_exemptions`。

Stop after:

- 401/403。
- 列表页连续失败。
- 同一附件主机大量 404/timeout，需要先判断是否来源侧变化。

命令：

```bash
PYTHONPATH=. uv run python -m sou_crawler.full_refresh \
  --run-id 20260730-full-refresh \
  --rate-limit 1.0 \
  --concurrency 2 \
  --timeout 25 \
  --retries 2
```

验收检查：

```bash
PYTHONPATH=. uv run python - <<'PY'
import json
from pathlib import Path

run = Path("output/full_refresh/20260730-full-refresh")
for site in ("sou_tools", "domestic"):
    acceptance = json.loads((run / site / "reports/acceptance.json").read_text(encoding="utf-8"))
    print(site, acceptance)
PY
```

## 7. 附件补齐与目录整理

Loop type: `goal`

适用于已有 `raw/list_records.jsonl` 和 `raw/detail_responses.jsonl`，但附件或 `organized_by_site/` 不完整的目录。

Done when:

- `reports/asset_download_stats.json` 存在。
- `missing_asset_downloads = 0`，或 `asset_exemptions.json` 有明确豁免。
- `reports/organized_assets_manifest.json` 和 `reports/organized_assets_stats.json` 存在。

命令：

```bash
PYTHONPATH=. uv run python -m sou_crawler download-assets \
  --output-dir '<run-dir>' \
  --rate-limit 1.0 \
  --concurrency 2 \
  --timeout 25 \
  --retries 2

PYTHONPATH=. uv run python -m sou_crawler organize-assets \
  --output-dir '<run-dir>'
```

注意：`organize-assets` 会重建该运行目录下的 `organized_by_site/`。不要把它指向不属于本次采集的目录。

## 8. 海报导出

Loop type: `turn`

适用于把增量采集中的课程海报复制到一个单独目录。脚本只导出 `role = 课程海报` 且 `copied = true` 的素材；按内容哈希去重，不导出头像、缩略图或 PDF。

Done when:

- 报告中的 `copied` 数量等于目标目录文件数。
- 没有 hash mismatch。

命令：

```bash
PYTHONPATH=. uv run python scripts/export_incremental_posters.py \
  --source-root output/incremental/20260730-new-check \
  --destination '2026年7月30日新增' \
  --report output/incremental/20260730-new-check/reports/poster_export.json
```

## 9. 飞书多维表格同步

Loop type: `goal`，但写入阶段是 L4 外部真实服务写入。

默认策略：

- 先读取本地 `organized_by_site/**/详情页信息.json`。
- 再读取飞书表格已有记录。
- 按课题标题、教授姓名、网页链接、课程链接构造去重键。
- 表格已有的课题跳过。
- 不上传海报，不写附件字段。
- 写入前验证字段类型和单选字段选项。

Dry-run / 只读检查：

```bash
PYTHONPATH=. uv run python scripts/sync_lark_base_topics.py \
  --wiki-url 'https://shuzimumin.feishu.cn/wiki/TSwJwfaxqi4vVHkWo3kcUm0Rn7d?table=tbl1zOSLAGq6NT89&view=vew620fOmi' \
  --root output/incremental/20260730-new-check/sou_tools \
  --root output/incremental/20260730-new-check/domestic \
  --output-dir output/incremental/20260730-new-check/lark_sync
```

写入前确认点：

- `sync_summary.json` 中 `pending_create` 是否符合预期。
- `field_validation.json` 无字段类型错误。
- batch payload 不包含附件字段。
- 当前对话中用户明确确认“授权写入飞书表格”。

写入命令：

```bash
PYTHONPATH=. uv run python scripts/sync_lark_base_topics.py \
  --wiki-url 'https://shuzimumin.feishu.cn/wiki/TSwJwfaxqi4vVHkWo3kcUm0Rn7d?table=tbl1zOSLAGq6NT89&view=vew620fOmi' \
  --root output/incremental/20260730-new-check/sou_tools \
  --root output/incremental/20260730-new-check/domestic \
  --output-dir output/incremental/20260730-new-check/lark_sync \
  --write
```

Post-write 验证：

```bash
PYTHONPATH=. uv run python scripts/sync_lark_base_topics.py \
  --wiki-url 'https://shuzimumin.feishu.cn/wiki/TSwJwfaxqi4vVHkWo3kcUm0Rn7d?table=tbl1zOSLAGq6NT89&view=vew620fOmi' \
  --root output/incremental/20260730-new-check/sou_tools \
  --root output/incremental/20260730-new-check/domestic \
  --output-dir output/incremental/20260730-new-check/lark_sync_postwrite_check
```

Done when:

- 写入命令成功返回。
- `created_record_ids.json` 数量等于写入前 `pending_create`。
- post-write 检查中 `pending_create = 0`。

## 10. 异常处理

| 异常 | 判断 | 处理 |
| --- | --- | --- |
| 401/403 | 访问被拒绝 | 停止当前路径；确认授权和合规边界 |
| 404 附件 | 单个 PDF/图片不存在 | 记录到 `asset_exemptions.json`；如果大量出现，暂停分析 |
| 429 | 频率过高 | 降低 `--concurrency`，提高 `--rate-limit` |
| timeout / incomplete_read | 网络或源站传输中断 | 保持低并发重试；超过 2 次后记录 triage |
| parse_error | JSON 或结构变化 | 重新运行 discovery，检查接口返回结构 |
| detail_missing_ids > 0 | 列表有 ID 但详情缺失 | 保留 raw 响应，单独复采缺失 ID |
| 新增数量异常 | 可能是基线不完整或接口变化 | 不写飞书；先全量刷新或人工抽查 |

## 11. 测试与质量门

常规文档或脚本变更后：

```bash
PYTHONPATH=. uv run python -m pytest
PYTHONPATH=. uv run ruff check sou_crawler scripts tests
```

只改单页采集脚本时：

```bash
PYTHONPATH=. uv run python -m pytest tests/test_crawl_share_page.py tests/test_organizer.py tests/test_full_refresh.py
PYTHONPATH=. uv run ruff check scripts/crawl_share_page.py tests/test_crawl_share_page.py
```

只改飞书同步脚本时：

```bash
PYTHONPATH=. uv run python -m pytest tests/test_incremental_refresh.py
PYTHONPATH=. uv run ruff check scripts/sync_lark_base_topics.py tests/test_incremental_refresh.py
```

## 12. 交接记录

长任务完成后更新 `HANDOFF.md`，只记录：

- 当前状态。
- 重要输出路径。
- 验证结果。
- 未完成问题或来源侧豁免。

不要在 `HANDOFF.md` 中写入 token、Cookie、密钥、私人凭据或飞书认证状态的具体值。
