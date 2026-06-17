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
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/dianlu
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
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/dianlu
python -m pytest
python -m dianedu_archiver check-site --dry-run
```
