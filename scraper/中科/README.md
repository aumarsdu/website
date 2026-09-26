# 授权 SPA 全量抓取项目

这是一个面向授权网站的 Python 数据采集项目，用于对 SPA/H5 应用进行 Network/API 发现、接口候选分类、公开接口抓取、附件下载、数据清洗和报告生成。

默认采集范围仅包含以下两个 `jf.cas-harbour.cn` SPA：

- 双教授课题（鲸鱼座）：`https://jf.cas-harbour.cn/mini/#/`
- 中方课题（研途有果）：`https://jf.cas-harbour.cn/avocado/#/`

默认授权域名仅为 `jf.cas-harbour.cn`。与这两个页面无关的接口、历史快照和课题记录不属于本项目采集范围。

项目不会实现登录绕过、验证码破解、代理池、UA 轮换、签名破解、接口暴力枚举或任何反风控规避能力。

## 目标数据

清洗后的记录尽量输出以下字段：

- `source_url`
- `crawled_at`
- `canonical_url`
- `id` / `uuid`
- `title`
- `category`
- `teacher`
- `university`
- `description`
- `direction`
- `asset_urls`
- `raw`

字段来自公开接口返回；缺失字段保持为空，不伪造。

## 目录结构

```text
sou_crawler/
  cli.py              # python -m sou_crawler 入口
  discovery.py        # Playwright Network/XHR/Fetch/JSON 发现
  api_analyzer.py     # 接口候选自动分类
  fetcher.py          # httpx 请求、限速、重试、错误分类
  pipeline.py         # 列表/详情/附件/清洗/报告流水线
  refresh.py          # 已验证公开源的增量快照采集
  audit.py            # 范围、完整性与目录位置审计
  schema.py           # 结构化记录校验
  storage.py          # JSONL/CSV/SQLite 写入
  utils.py            # URL、脱敏、文件名等工具
config/
  api_overrides.example.json
tests/
output/
```

## 合规处理

- User-Agent：默认 `AuthorizedResearchCrawler/1.0`。
- 速率限制：默认单请求间隔 `1.5s`，可通过 `--rate-limit` 调整。
- 并发：配置项默认 `2`，当前核心请求按保守串行节流执行。
- 重试：默认最多 `2` 次，只对超时、429、部分 5xx 等安全失败退避重试。
- 403/401：不重试突破，记录错误并停止当前接口任务。
- 附件归档：每个唯一 URL 只联网下载一次，内容按 SHA-256 缓存到 `output/cache/assets/`；共享附件在各课题目录中优先以硬链接呈现，不支持硬链接时复制。
- 敏感信息：发现阶段会对 `cookie`、`authorization`、`token`、`session`、`password` 等请求头或 payload 字段脱敏后再落盘。
- 鉴权判断：普通 Cookie 只脱敏记录，不单独视为需要鉴权；`authorization`、`x-api-key`、token 类 header 或敏感 POST payload 会让接口标记为 `requires_auth` 并跳过回放。
- 静态 token 边界：如果前端 JS 中出现写入请求头的 token 字段，本项目只记录字段类型和风险，不输出值、不复制值、不用它回放接口。需要这类接口时，应改用你明确提供的合法服务端授权方式。
- 数据最小化：只处理前端公开展示或公开接口返回的数据，不采集用户隐私、账号、客户线索或后台数据。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 命令

```bash
python -m sou_crawler discover
python -m sou_crawler analyze-apis
python -m sou_crawler crawl-lists
python -m sou_crawler crawl-details
python -m sou_crawler refresh-public-topics --snapshot-id 20260730 --dry-run
python -m sou_crawler audit-archive --snapshot-id 20260730
python -m sou_crawler download-assets
python -m sou_crawler normalize
python -m sou_crawler report
python -m sou_crawler all
```

所有命令支持全局保守参数：

```bash
python -m sou_crawler --rate-limit 2 --timeout 20 --retries 2 --max-pages 10 crawl-lists
```

附件下载的 `--max-assets` 限制的是唯一 URL 数量，而不是课题目录中的引用数量；同一 URL 成功缓存后会同步写入本批涉及的所有课题目录。

如果 discovery 发现的公开 API 使用了新的授权域名，先人工确认它属于授权范围，再显式加入：

```bash
python -m sou_crawler --allowed-domain api.example.com crawl-lists --dry-run
```

## 发现接口

默认打开以下入口：

- `https://jf.cas-harbour.cn/mini/#/`
- `https://jf.cas-harbour.cn/avocado/#/`

运行：

```bash
python -m sou_crawler discover --headed --interactive
```

输出：

- `output/discovery/network_logs.jsonl`
- `output/discovery/api_candidates.json`
- `output/discovery/api_inventory.md`

`--interactive` 会在每个入口打开后暂停，方便手动点击筛选项、分页、详情入口，继续捕获 Network 请求。

## 分析接口

```bash
python -m sou_crawler analyze-apis
```

输出：

- `output/discovery/api_classification.json`
- `output/discovery/api_classification.md`

自动识别：

- 分类/筛选接口
- 项目列表接口
- 项目详情接口
- 附件资源接口
- 分页参数
- ID 字段
- 附件 URL 字段
- 是否出现 401/403 或敏感请求头

## 抓取与清洗

### 推荐的中科增量刷新

常规更新优先使用 `refresh-public-topics`。它只调用两个指定页面使用的公开课题列表、课题分类和课题详情接口，不依赖自动候选分类；每次运行保存为不可覆盖的原始快照，并仅补充相对本地基线新增的课题详情。

```bash
python -m sou_crawler --max-pages 100 --max-details 200 refresh-public-topics --snapshot-id 20260730 --dry-run
python -m sou_crawler --rate-limit 1.5 --max-pages 100 --max-details 200 refresh-public-topics --snapshot-id 20260730
python -m sou_crawler audit-archive --snapshot-id 20260730
python -m sou_crawler normalize
python -m sou_crawler download-assets
python -m sou_crawler report
```

若审计显示当前列表存在历史缺失详情，使用同一快照补采。该命令会跳过已有公开详情，可重复运行至 `remaining_after` 为 `0`：

```bash
python -m sou_crawler --rate-limit 1.5 --max-details 200 backfill-details --snapshot-id 20260730
```

先检查 `output/reports/refresh_<批次>.json` 与 `scope_audit_<批次>.json`：只有刷新无失败/截断、当前列表无缺失、目录无错位且范围外清单为空时，才继续 `normalize`。审计只生成清单，不删除文件；范围外内容的批量删除必须在当前对话单独确认。完整执行、海报归档、飞书去重写入与异常处理见 [增量采集工作流程](docs/refresh-workflow.md)。飞书写入属于外部真实服务操作，必须在当前对话获得明确确认后才能执行。

自动分类不可避免会遇到漏判或复杂 POST body。需要人工指定接口时，复制 `config/api_overrides.example.json`：

```bash
cp config/api_overrides.example.json config/api_overrides.json
```

然后在 `list_apis` / `detail_apis` 中补充经你确认的公开接口、分页参数和详情 ID 参数。`crawl-lists` 和 `crawl-details` 会自动合并这些人工映射。

先做 dry-run 看会请求哪些接口：

```bash
python -m sou_crawler crawl-lists --dry-run
python -m sou_crawler crawl-details --dry-run
python -m sou_crawler download-assets --dry-run
```

正式运行：

```bash
python -m sou_crawler crawl-lists
python -m sou_crawler crawl-details
python -m sou_crawler normalize
python -m sou_crawler download-assets
python -m sou_crawler report
```

已有 `output/assets` 素材需要按新目录结构重排时：

```bash
python3 scripts/rebuild_site_mirror.py --output-dir output
```

分类/方向来源：`jf.cas-harbour.cn/zhongkehaobo/v2/topic/category` 的课题分类树；缺失时使用项目内置的可审计关键词映射，并在记录中写入 `taxonomy_source`。
- 当接口字段缺失时，使用项目内置的可审计关键词兜底映射，并在记录中写入 `taxonomy_source`。

## 输出格式

- 原始列表 JSON：`output/raw/lists/**/page_*.json`
- 原始详情 JSON：`output/raw/details/**/*.json`
- 原始分类字典：`output/raw/taxonomy/**/*.json`
- 结构化 JSONL：`output/processed/projects.jsonl`
- 结构化 CSV：`output/processed/projects.csv`
- SQLite：`output/processed/projects.sqlite`
- 网站目录镜像：`output/site/<一级目录>/<方向>/<课题名称>/`
- 报告：`output/reports/crawl_report.md` 和 `output/reports/crawl_report.json`
- 范围审计：`output/reports/scope_audit_<批次>.json` 及范围外清单

素材命名规则：

- 课题按 `output/site/<一级目录>/<方向>/<课题名称>/` 建目录；例如 `output/site/计算机与人工智能/深度学习/<课题名称>/`。
- 每个课题目录会写入 `details.json`，包含规范化字段和原始详情页接口返回的完整 `raw` 数据。
- 海报、封面类字段优先命名为 `<课题名称>.<ext>`。
- 教授头像类字段优先从同级对象读取教授/教师名称，命名为 `<教授名称>.<ext>`。
- PDF 和其他附件用字段名或原始语义名兜底。

## 已知限制

- SPA 接口需要先通过 `discover --interactive` 尽量覆盖筛选、分页、详情点击，自动发现质量取决于操作覆盖度。
- 未知接口的业务字段无法 100% 自动推断；若详情接口需要复杂 body，可在分析结果基础上人工补充映射。
- 当前不会使用登录态、Authorization、token 或 Cookie 回放；如果接口必须鉴权，程序会跳过并记录原因。
- 不做接口枚举，只基于 Network 发现到的公开请求进行回放。
- `jf.cas-harbour.cn` 的部分前端接口可能带静态 token header；根据本项目边界，这类接口默认不回放，因此“全量”会受合法授权方式约束。

## 选择器/接口变更维护

这个项目主线不是 HTML 选择器，而是接口发现和回放。网站改版后建议：

1. 重新运行 `python -m sou_crawler discover --headed --interactive`。
2. 查看 `output/discovery/api_inventory.md` 和 `api_classification.md`。
3. 确认新的列表、详情、附件字段是否被识别。
4. 再运行 `crawl-lists --dry-run`、`crawl-details --dry-run`。
5. dry-run 无异常后执行正式抓取。

## 测试

离线单元测试不访问真实网站：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

如果已安装 `pytest`，也可以运行：

```bash
python3 -m pytest
```
