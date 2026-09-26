# SOU Authorized Crawler

这是一个面向“海外教授”站 `sou-tools.gecacademy.cn` 和“华人教授”站 `domestic.gecacademy.cn` 的授权全量数据采集项目。项目默认不做传统 HTML 递归抓取，而是先通过 Playwright 打开 SPA/H5 页面并捕获 Network/XHR/Fetch，再用 `httpx` 直接请求已发现的公开接口，保存 raw JSON、清洗结构化数据、下载公开附件并生成报告。

## 能力

- Network / XHR / Fetch 接口发现
- 分类、筛选、列表、详情、附件接口候选识别
- raw JSONL 保存
- 列表分页抓取与详情抓取
- PDF、图片、海报、syllabus 等公开附件下载
- JSONL / CSV / SQLite 结构化输出
- 抓取统计和错误分类报告

## 工作流入口

日常操作优先查看 [WORKFLOW.md](./WORKFLOW.md)。该文档按场景说明：

- 范围与完整性审计：检查当前范围是否采全、目录位置是否正确、是否存在非范围来源。
- 增量采集：发现官网新增课题，只采集本地不存在的 ID。
- 单分享页采集：采集一个 `https://sou-m.gecacademy.cn/share?id=...`。
- 全量刷新：重建两个站点的完整基线。
- 附件补齐与目录整理：补下载公开附件后重建 `organized_by_site/`。
- 海报导出：只导出新增课程海报，不导出头像、缩略图或 PDF。
- 飞书同步：先 dry-run 比对本地和多维表格，确认后再写入。

当前采集来源范围：

- 海外教授：`https://sou-tools.gecacademy.cn/`
- 华人教授：`https://domestic.gecacademy.cn/`

## 合规边界

- User-Agent 默认：`AuthorizedResearchCrawler/1.0`
- 默认并发：`2`
- 默认请求间隔：`1.5` 秒
- 默认重试：`2` 次，仅用于超时、429、部分 5xx 和网络瞬断
- 遇到 403 会停止相关请求路径并记录 `http_403_forbidden`
- 不实现验证码破解、登录绕过、代理池、UA 轮换、风控规避或暴力枚举
- Cookie、Authorization、token、session、secret-like 请求头在落盘前会被替换为 `[REDACTED]`

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
playwright install chromium
```

## Dry Run

```bash
python -m sou_crawler discover --dry-run
python -m sou_crawler crawl-lists --dry-run
python -m sou_crawler crawl-details --dry-run
python -m sou_crawler download-assets --dry-run
```

默认发现入口会同时覆盖：

- 海外教授：`https://sou-tools.gecacademy.cn/`
- 华人教授：`https://domestic.gecacademy.cn/`

## 运行

分步骤运行：

```bash
python -m sou_crawler discover
python -m sou_crawler analyze-apis
python -m sou_crawler crawl-lists --max-pages 100 --rate-limit 1.5 --concurrency 2
python -m sou_crawler crawl-details --max-details 10000
python -m sou_crawler download-assets
python -m sou_crawler organize-assets
python -m sou_crawler normalize
python -m sou_crawler report
```

一键运行：

```bash
python -m sou_crawler all --max-pages 100 --rate-limit 1.5 --concurrency 2
```

只采集新增课题：

```bash
PYTHONPATH=. uv run python scripts/incremental_refresh.py --dry-run
PYTHONPATH=. uv run python scripts/incremental_refresh.py \
  --run-id 20260724-new-check \
  --rate-limit 1.0 \
  --concurrency 2
```

该脚本会先抓取两个公开站点的列表快照，并与既有本地输出按课题 ID
去重。只有新增 ID 会进入详情、附件下载、归一化和 `organized_by_site/`
整理流程；完整的本次列表快照也会保留在运行目录中，便于复核。

补齐已存在列表但缺少详情或目录的指定课题：

```bash
PYTHONPATH=. uv run python scripts/incremental_refresh.py \
  --run-id 20260730-missing-sou-tools \
  --site sou_tools \
  --include-id <topic-id> \
  --include-only \
  --rate-limit 1.0 \
  --concurrency 2
```

`--include-id` 只接受当前官网列表中的课题 ID；配合 `--include-only` 时只补采
指定 ID。报告会单独标记显式补采的 ID。

采集单个分享页：

```bash
PYTHONPATH=. uv run python scripts/crawl_share_page.py \
  'https://sou-m.gecacademy.cn/share?id=<course-id>' \
  --output-dir '/Users/liujunliang/Workspace/knowledge-legacy/scraper/集思未来/2026年7月30日' \
  --rate-limit 1.0 \
  --concurrency 2 \
  --timeout 25 \
  --retries 2
```

该脚本会保存移动分享页 HTML shell、详情接口 raw JSON、公开附件、
归一化数据和 `organized_by_site/一级分类/方向/课题/`。如果目标详情缺少
网站目录字段，脚本会用本地历史列表记录补全；仍缺失时按标题和详情关键词
生成保守目录标签。

当前数据全量刷新与验收报告：

```bash
python -m sou_crawler.full_refresh \
  --run-id 20260602-full-refresh \
  --rate-limit 0.5 \
  --concurrency 3 \
  --timeout 25 \
  --retries 2
```

该命令会同时刷新 `sou-tools.gecacademy.cn` 和 `domestic.gecacademy.cn`
的列表分页、详情、结构化输出和附件下载状态，并生成：

- `output/full_refresh/<run-id>/refresh_summary.md`
- `output/full_refresh/<run-id>/<site>/reports/coverage_report.md`
- `output/full_refresh/<run-id>/<site>/reports/acceptance.json`
- `output/full_refresh/<run-id>/<site>/reports/asset_failure_triage.json`
- `output/full_refresh/<run-id>/<site>/organized_by_site/`：按网站层级整理后的素材和详情信息

验收口径：

- `pages_failed = 0`
- `detail_missing_ids = 0`
- `missing_asset_downloads = 0`，或存在明确的 `asset_exemptions.json`
  豁免清单

如需半自动观察页面交互，可使用可视浏览器：

```bash
python -m sou_crawler discover --headed --discovery-wait-ms 8000
```

## 输出文件

- `output/discovery/network_logs.jsonl`：脱敏后的 request / response / JSON 响应 / POST payload / headers
- `output/discovery/api_candidates.json`：接口候选清单
- `output/discovery/api_inventory.md`：人工可读接口盘点
- `output/discovery/api_classification.json`：接口分类结果
- `output/discovery/api_classification.md`：接口分类说明
- `output/raw/list_responses.jsonl`：列表接口 raw 响应
- `output/raw/list_records.jsonl`：列表记录拆分结果
- `output/raw/detail_responses.jsonl`：详情接口 raw 响应
- `output/assets/`：下载的公开附件
- `output/organized_by_site/`：按网站结构整理后的素材目录，默认层级为
  `一级分类/方向/课题/`
- `output/processed/records.jsonl`：归一化 JSONL
- `output/processed/records.csv`：归一化 CSV
- `output/processed/records.sqlite`：归一化 SQLite
- `output/reports/crawl_report.md`：抓取报告

整理后的每个课题目录会包含：

- 课程海报、教授头像、列表缩略图、PDF 等已下载公开附件
- `metadata.json`：目录、文件复制状态、列表记录和详情记录
- `详情页信息.json`：完整详情页结构化数据、附件 URL、PDF URL 和文件清单
- `详情页信息.md`：便于人工查看的详情页摘要和完整详情 JSON

## 验收标准

每次采集完成后至少确认：

- 列表阶段没有非预期失败：`pages_failed = 0`。
- 详情阶段没有缺失：`detail_missing_ids = 0`。
- 附件阶段没有缺失下载，或 `asset_exemptions.json` 中有明确来源侧豁免。
- `organized_by_site/` 已按 `一级分类/方向/课题/` 生成目录。
- 每个课题目录包含 `metadata.json`、`详情页信息.json` 和 `详情页信息.md`。
- 相关测试通过；无法运行测试时记录原因和人工复验步骤。

## 目标字段

项目会优先抽取以下常见字段，其他字段保留在 `raw` / `raw_json` 中：

- `id`, `uuid`, `projectId`, `courseId`
- `title`, `name`
- `teacher`, `instructor`, `professor`
- `university`, `major`
- `prerequisite`, `intro`, `description`
- `asset_urls`
- `source_url`, `canonical_url`, `crawled_at`

## 接口识别逻辑

`analyze-apis` 会读取 `network_logs.jsonl`，基于 URL、query、POST body 和 JSON 字段进行启发式分类。识别特征包括：

- `list`, `detail`, `project`, `course`, `category`, `classify`, `level`, `search`, `share`, `sou`, `subject`, `page`
- `total`, `records`, `rows`, `data`, `id`, `uuid`
- `title`, `name`, `teacher`, `instructor`, `professor`, `university`, `major`, `prerequisite`, `intro`, `description`
- `oss-cn`, `aliyuncs`, `pdf`, `jpg`, `png`, `jpeg`, `webp`

## 已知限制

- 自动分类是启发式结果，首次运行后应人工检查 `output/discovery/api_inventory.md`，必要时调整候选接口。
- 若接口分页参数不在常见命名中，可能需要手工修改 `api_classification.json` 或扩展 `choose_page_param`。
- 若详情接口 ID 参数不叫 `id/uuid/projectId/courseId/itemId/detailId`，需要扩展 `choose_id_param`。
- 单元测试不访问 live 网站；真实接口抓取应在授权网络环境中执行。

## 选择器与接口变更维护

本项目不依赖页面 CSS 选择器。若网站布局或接口变更：

1. 重新运行 `python -m sou_crawler discover --headed`
2. 查看 `output/discovery/api_inventory.md`
3. 如分类不准确，调整 `sou_crawler/classifier.py` 中的 hint 列表或字段识别逻辑
4. 重新运行 `analyze-apis`、`crawl-lists`、`crawl-details`
