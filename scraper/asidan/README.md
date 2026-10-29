# seedasdan-intel-engine

SeedASDAN 留学项目情报引擎 MVP：抓取公开网页，保存原始数据，解析正文，抽取项目字段，生成项目库、小红书选题、CRM 话术和质量报告。

## 授权抓取边界

默认只允许访问 `config/domains.yaml` 中的 SeedASDAN / ASEEDER 白名单域名。以下路径会被阻断：

- `/wp-admin/`
- `/wp-login.php`
- `/login`
- `/register`
- `/cart`
- `/checkout`
- `/payment`
- `/order`
- `/my-account`

禁止绕过登录、验证码、支付、报名表单或任何访问控制。默认 User-Agent 为透明研究用途标识：

```text
HeLiPeiResearchBot/2.0 authorized-contact=aumarsdu@gmail.com
```

正式运行前请在 `config/crawl.yaml` 中替换为真实联系邮箱。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

如果需要 Scrapy/Playwright 扩展：

```bash
pip install -e ".[dev,scrapy]"
playwright install chromium
```

当前 MVP 默认使用普通 HTTP 抓取，不启用浏览器自动化。

## 常用命令

初始化本地 SQLite schema：

```bash
seed-intel init-db
```

只做 dry-run，不保存最终数据：

```bash
seed-intel crawl full --dry-run --max-pages 5
```

小规模合规抓取：

```bash
seed-intel crawl full --max-pages 10 --rate-limit 1.5
```

生成项目 CSV：

```bash
seed-intel extract projects
```

评分：

```bash
seed-intel score projects
```

生成小红书选题：

```bash
seed-intel generate xhs-topics
```

生成 CRM 卡片：

```bash
seed-intel generate crm-cards
```

导出全部报告：

```bash
seed-intel export all
seed-intel report coverage
seed-intel report quality
```

测试：

```bash
pytest
```

## 输出格式

Bronze 原始层：

- `data/bronze/raw_html/{batch_id}/`
- `data/bronze/raw_assets/{batch_id}/`
- `data/bronze/headers/{batch_id}/`

Silver 清洗层：

- `data/silver/cleaned_pages/{batch_id}/`
- `data/silver/markdown_pages/{batch_id}/`
- `data/silver/document_text/{batch_id}/`

Gold 业务层：

- `data/gold/projects/projects_{batch_id}.jsonl`
- `data/gold/projects/projects.csv`
- `data/gold/projects/project_scores.jsonl`
- `data/gold/xhs_topics/xhs_topics.csv`
- `data/gold/crm_cards/crm_cards.csv`
- `data/gold/reports/coverage_report.md`
- `data/gold/reports/quality_report.md`

## 项目字段

当前规则抽取覆盖：

- 项目名称
- 项目类型
- 适合年级
- 项目时间
- 报名截止
- 地点
- 主办方
- 证书/成果
- 价格
- PDF 链接
- 图片链接
- 字段证据
- 字段置信度
- 是否需要人工复核

每个非空关键字段都应带 `evidence`。没有证据的字段保持 `null`，不做推测。

## 人工复核流程

以下情况会进入人工复核：

- 项目名称为空
- 项目类型只能归为“其他”
- 适合年级为空
- 平均抽取置信度低于 `0.75`
- PDF 无法解析或疑似扫描件
- 价格、截止日期、主办方等关键字段缺失

复核入口：

- `data/gold/reports/quality_report.md`
- `data/gold/reports/errors_{batch_id}.jsonl`

## 选择器维护

HTML parser 优先使用语义结构、canonical、正文文本和 JSON-LD。若网站改版导致正文异常：

1. 查看 `data/bronze/raw_html/{batch_id}/` 的原始 HTML。
2. 查看 `data/silver/cleaned_pages/{batch_id}/` 的解析结果。
3. 调整 `src/seed_intel/parsers/html_parser.py` 中的清洗规则。
4. 用 `tests/fixtures/` 增加改版页面 fixture。
5. 跑 `pytest`。

## 已知限制

- 当前 MVP 不调用 LLM；无 API Key 也能运行。
- `detect changes` 目前只生成 baseline 报告，尚未做跨批次字段级 diff。
- Scrapy spider 已留扩展入口，但默认 CLI 使用轻量 HTTP 调度器。
- PostgreSQL/pgvector、Dashboard、FastAPI、飞书导出属于后续 P2。
