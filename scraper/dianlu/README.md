# DianEdu Archiver

授权范围内的点路教育 / DianEdu 主站归档与结构化采集项目。

默认目标：

- `https://www.dianedu.com/`
- `https://www.dianedu.com/Search`
- 主站公开页面、搜索页、项目列表、项目详情、文章 / 知识内容、图片、PDF、文件、视频等静态资源

明确排除：

- `https://admin.dianedu.com/`
- 非授权外域
- 登录绕过、验证码绕过、接口暴力枚举、代理池、UA 轮换、状态变更表单提交

## 合规说明

- User-Agent: `AuthorizedDianEduArchiveCrawler/1.0`
- 默认并发限制在 1-3；CLI 中即使传入更高值也会被收敛到 3。
- 默认单请求间隔 2 秒，可通过 `--rate-limit` 调整，最小为 1 秒。
- 默认超时 30 秒，失败最多重试 2 次。
- `401 / 403` 会记录并停止对应 URL，不尝试绕过。
- `429` 会自动退避并降低请求节奏。
- GraphQL 仅记录页面实际 observed operations，不做 introspection。
- 不读取、打印或保存 cookie、token、账号密码。

## 安装

```bash
cd /Users/liujunliang/Workspace/knowledge-legacy/scraper/dianlu
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

如果本机默认 `python` 已经是 3.11+，也可以直接使用 `python`。

## CLI

所有数据默认写入当前项目目录：

```bash
python -m dianedu_archiver check-site
python -m dianedu_archiver discover-static
python -m dianedu_archiver discover-browser
python -m dianedu_archiver analyze-apis
python -m dianedu_archiver crawl-routes
python -m dianedu_archiver crawl-search
python -m dianedu_archiver crawl-lists
python -m dianedu_archiver crawl-details
python -m dianedu_archiver crawl-articles
python -m dianedu_archiver download-assets
python -m dianedu_archiver normalize
python -m dianedu_archiver export
python -m dianedu_archiver report
python -m dianedu_archiver all
```

常用参数：

```bash
python -m dianedu_archiver crawl-routes --max-pages 500 --rate-limit 2 --timeout 30 --retries 2
python -m dianedu_archiver discover-static --dry-run
python -m dianedu_archiver all --max-pages 1000 --rate-limit 2
```

## 输出结构

```text
dianlu/
  data/raw/
    pages_raw.jsonl
    errors.jsonl
    html/
  data/processed/
    dianedu.sqlite
    projects.json
    articles.json
    filters.json
    hot_search_terms.json
    asset_manifest.json
    *.normalized.jsonl
    *.normalized.csv
    data_quality_summary.json
  data/assets/
  discovery/
    static_pages.json
    static_api_candidates.json
    network_logs.jsonl
    api_candidates.json
    api_inventory.md
  reports/
    summary.json
    summary.md
  archives/
    export/
    dianedu_archive_report.zip
```

## 结构化字段

项目详情会尽量抽取：

- `source_url`
- `canonical_url`
- `title`
- `category`
- `location`
- `grade`
- `project_type`
- `summary`
- `fields`
- `assets`
- `crawled_at`

文章 / 知识内容会尽量抽取：

- `source_url`
- `canonical_url`
- `title`
- `category`
- `published_at`
- `author`
- `summary`
- `body_markdown`
- `assets`
- `crawled_at`

搜索页会抽取：

- 筛选条件：`filter_name`, `option_text`, `option_value`
- 热门搜索词：`term`, `weight`, `source_url`

## 推荐运行顺序

```bash
python -m dianedu_archiver check-site
python -m dianedu_archiver discover-static
python -m dianedu_archiver discover-browser
python -m dianedu_archiver analyze-apis
python -m dianedu_archiver crawl-routes --max-pages 500
python -m dianedu_archiver crawl-search
python -m dianedu_archiver crawl-lists
python -m dianedu_archiver crawl-details
python -m dianedu_archiver crawl-articles
python -m dianedu_archiver download-assets
python -m dianedu_archiver normalize
python -m dianedu_archiver export
python -m dianedu_archiver report
```

`all` 会串行执行上述流程。首次建议先用较小 `--max-pages` 验证输出质量，再扩大范围。

## 选择器维护

当前解析器优先使用稳定信号：

- canonical link
- semantic tags: `article`, `main`, `h1`
- form/select/input
- JSON-LD
- 页面文本中的键值对

如果站点改版导致字段缺失，优先修改：

- `dianedu_archiver/parser.py`
- `tests/fixtures/*.html`
- `tests/test_parser.py`

不要直接在抓取流程中硬编码脆弱的深层 CSS 选择器。

## 测试

```bash
cd /Users/liujunliang/Workspace/knowledge-legacy/scraper/dianlu
python -m pytest
python -m dianedu_archiver check-site --dry-run
```

## 2026-10-14 公开内容续抓

独立批次位于 `task_runs/20261014/`，原有归档保留。

```bash
python -m dianedu_archiver crawl-lists --root-dir task_runs/20261014 --max-pages 20000
python -m dianedu_archiver.complete
python -m dianedu_archiver.complete_assets
python -m dianedu_archiver crawl-search --root-dir task_runs/20261014
python -m dianedu_archiver normalize --root-dir task_runs/20261014
python -m dianedu_archiver report --root-dir task_runs/20261014
python -m dianedu_archiver export --root-dir task_runs/20261014
```

`complete` 仅使用前端中已发现的公开 Project、Article、School 搜索/详情接口。
旧项目详情按 ID 复用，保留原采集时间；因此本批次不是所有详情的当前版本快照。
文章正文与国际学校详情单独采集；成功列表与服务器 Count 不一致、详情 ID 不匹配、
鉴权拒绝或持续限流时停止。请求间隔 2 秒，上限 20,000 条/类型。
详情输出支持续跑；以 `reports/completion_coverage.json` 的覆盖率和停止原因验收，
不能以旧 `summary.md` 或单纯 CLI 零退出码认定全站完整。

`complete_assets` 递归归档同域 JS/CSS 依赖，资源发现上限 2,000，
输出 `reports/asset_coverage.json`。后台、账户、学生、订单、支付、申请接口不采集。
外域图片/文件仅记录排除数量，不下载；不访问后台资源。
学校详情保存完整公开响应到 `schools.json`，当前不并入原 SQLite 的项目/文章表。

本聊天已扩展到主站直接引用的公开外域内容，并确认资源阶段上限20 GB、6小时，包含视频：

```bash
python -m dianedu_archiver.referenced_archive --max-gb 20 --max-hours 6 --include-video
python -m dianedu_archiver.finalize_completion
```

`referenced_archive` 补充无扩展名的公开 `_file/GetFile/{id}` 引用、FAQ 和首页公开响应。
不枚举 ID，只处理主站数据中已出现的文件 ID 和引用。
下载按每2秒一次、公开DNS连接绑定、robots规则和鉴权停止执行，文件流式写入并记录SHA-256。
首次运行的截止时间和累计传输字节持久化，续跑不重置额度；20 GB 使用十进制。
资源拒绝/错误保留在 `referenced_manifest.json`，进度在 `referenced_progress.json`。
大媒体在 `data/assets/`，ZIP仅封装结构化数据与回执，不重复占用视频空间。
最终验收与学校SQLite/JSONL/CSV导出由 `finalize_completion` 执行。

抓取达到 `finished` 或 `stopped`、且上述验收完成后，运行：

```bash
python -m dianedu_archiver.acceptance_inventory
```

此命令只读取本地归档，重建已发现的唯一引用集合，不发网络请求、不修改抓取额度。
输出 `reports/pending_references.json`、未处理引用 CSV 和失败引用 CSV，
更新验收报告及 ZIP。尚未抓到的响应内部可能存在的未知引用不在此清单中。

Owner 于2026-10-14明确将本批次总时长扩展为12小时，20 GB不变；
截止为同日23:03（Asia/Taipei），从原始起点累计，已用流量不重置。
仅在获得明确时长扩展授权后使用 `python -m dianedu_archiver.extend_resource_limit --total-hours 12`，
再用 `python -m dianedu_archiver.referenced_archive --max-gb 20 --max-hours 12 --include-video` 续跑。

本批次已授权当前项目快照刷新：`python -m dianedu_archiver.refresh_projects`。
该命令重新核对公开列表并刷新计划内项目详情，API和后续资源共用原20 GB、12小时额度，
输出 `project_refresh_progress.json`、`project_reference_changes.json` 和原始刷新回执。
原项目档案在 `reports/before_project_refresh/` 保留；刷新成功后更新SQLite、JSON/CSV与验收包。

2026-10-14 项目详情已经全量重采1097条（原旧详情1071条及本轮26条），
并补充正文 HTML 中的媒体 `src/data-src/poster/data` 引用发现。
相对地址按公开主站根路径解析，保留原 `/_Framework/GetFile?...` 地址，不改写端点。
文件端点返回 HTML/JSON 时记录 `file_endpoint_returned_nonfile`，不计为图片保存成功。
`python -m dianedu_archiver.finish_richtext` 使用同一额度续跑正文媒体引用并自动做本地验收；
原固定截止已过后不继续下载。最新验收以 `reports/completion_acceptance.md` 为准，
正文资源专项结果在 `reports/project_richtext_resource_audit.json`，未处理与失败分别列出。

本轮网络阶段已于2026-10-14 23:03:34（Asia/Taipei）因累计12小时截止停止，
累计传输11,033,052,884 bytes。截止后纯离线核对补入正文附件链接及CSS背景图，
最终未处理3319个引用；资源不完整，后续网络续跑需新的时长授权。
实际网络代码保存在 `reports/runtime_code_richtext/`；原项目详情1071条已全部重采，
最新完整结果和失败原因以本批次 `reports/completion_acceptance.md` 为准。

Owner随后将原起点累计时长延长至24小时，20 GB不变，固定截止为2026-10-15 11:03:34台北时间。
本轮续抓已于同日03:06:25完成网络队列，累计传输12,122,596,034 bytes。
原3319个未处理引用全部处理：3265个有效非空保存，54个失败或排除；最终无未处理引用和分片。
累计有效资源文件9718个，保留996个失败/排除/质量异常；完整离线归档仍受这些缺口限制。
续抓目标专项核对见 `reports/resource_24h_resume_audit.json`，运行代码快照见 `reports/runtime_code_24h/`。
12小时阶段的验收和断点保存在 `reports/acceptance_12h/`，累计流量未重置。

### 2026-10-15 独立补抓

本轮已授权新增最多1 GB、4小时，累计20 GB上限不变。
`python -m dianedu_archiver.supplement --prepare` 只创建一次补抓预算；
再次运行会读取原预算，保留起点、截止、原累计传输、诊断响应体和搜索通信预留。
`python -m dianedu_archiver.supplement --pilot 1` 用于首个公开资源验证，
随后 `python -m dianedu_archiver.supplement` 按已保存回执继续；
资源队列结束后运行 `python -m dianedu_archiver.supplement_articles` 核验已发现的正文候选。
这些命令仅适用于本轮已确认的对象和预算；过期或触及上限后不新增网络请求。

透明User-Agent沿用 `AuthorizedDianEduArchiveCrawler/1.0`，请求间隔至少2秒，
逐跳检查公开地址和robots，继承原阻断主机；不请求后台、登录和受限微信正文。
公开转载仅记为带证据的同文候选，缺少原文比对时不伪称原文完全恢复。

新数据、预算、追加回执和报告位于 `task_runs/20261014/supplements/20261015/`。
`scripts/supplement_research_index.py` 核对96篇各两轮、共192次检索回执；
`scripts/verify_supplement_images.py` 使用带Pillow的Python进行完整图像解码，
`python -m dianedu_archiver.finalize_supplement` 做离线对账并更新完整验收报告。
原资源清单、失败记录、SQLite和流量账本保留原样；合并结果另存JSON及SQLite视图。
新版报告包另存 `dianedu_archive_report_with_supplement_20261015.zip`，大媒体仍保留在磁盘。

本轮相关测试：`python -m pytest -q tests/test_supplement.py tests/test_supplement_articles.py`。
