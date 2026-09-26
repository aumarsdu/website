# HIREP PBL 授权采集器

状态：PBL 专项采集链路可用于本地全量建基线、日常增量更新和范围审计。采集对象严格限于 `https://pbl.hirepglobal.com/` 公开展示的课题及其公开详情和附件。

## 目录

- [采集边界](#采集边界)
- [环境准备](#环境准备)
- [标准工作流程](#标准工作流程)
- [输出与验收](#输出与验收)
- [恢复与故障处理](#恢复与故障处理)
- [高级接口发现](#高级接口发现)
- [维护脚本与测试](#维护脚本与测试)

## 采集边界

### 采集内容

- 仅以 PBL 公开课题列表为入口；每个项目记录的 `source_url` 必须为 `https://pbl.hirepglobal.com/Professor?courseExtendId=...`；
- 该课题的完整详情页数据，原始详情负载保存在 `详情页信息.json` 和 `projects.jsonl` 的 `raw.detail`；
- 该课题详情明确引用的专业附件、公共附件、详情页直链图片、海报、Banner、教授头像和 PDF；
- 原始接口响应、标准化项目记录、资源清单和质量报告。

### 范围判定与删除门槛

- PBL 课程页是唯一内容范围；PBL 调用的公开接口和对象存储/CDN 只是该课程页的技术资源来源，不是独立采集范围；
- 附件 URL 只允许 PBL 已批准的 API 主机，以及 `*.aliyuncs.com`、`*.alicdn.com`、`*.hirepglobal.com`、`*.neoschool.com` 等配置中的资源主机；
- 覆盖、范围和目录审计只检查包含 `output_pbl*/processed/projects.jsonl` 的课题批次。`Poster/` 下的交付副本和仅含接口发现结果的目录不作为课题数据删除对象；
- `audit-pbl` 会列出精确的范围外目录或文件候选，但**不会删除**。删除候选必须在当前对话逐项确认后才能执行。

### 合规规则

- 默认 User-Agent：`AuthorizedResearchCrawler/1.0`；
- 默认每次请求最少间隔 2 秒，并发参数限制在 1-3；
- 仅请求已批准的 PBL/API 主机；附件仅允许指定的对象存储和站点域名；
- 列表接口按常规分页拉取（`pageSize=200` 逐页推进），不使用超大批次单请求；
- 429、超时与瞬时网络错误按安全策略重试；401/403 会停止相关任务；
- 不绕过登录、验证码、付费墙或访问控制，不使用代理池或身份伪装；
- 回放课程页调用的公开接口时会附带 `Origin`/`Referer: https://pbl.hirepglobal.com`
  请求头，以匹配浏览器访问同一公开接口时的请求形态；仅用于公开接口，不用于任何
  需要鉴权的资源；
- 不读取或保存 cookie、Authorization、token、密码或其他凭据。

## 环境准备

从此目录执行命令。仓库已使用 `.venv` 时优先使用其中的 Python，避免系统 Python 缺少依赖。

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
```

每次运行前先查看计划，不会发起网络请求或写入采集结果：

```bash
./.venv/bin/python -m sou_crawler --output-dir output_pbl_incremental_YYYYMMDD --dry-run crawl-pbl-incremental
```

## 标准工作流程

日常流程始终是“建立基线一次 -> 增量采集 -> 本地校验 -> 按需交付”。不要把通用接口发现命令作为每日采集入口。

### 0. 覆盖、范围与目录审计

在判断“是否已采全”或清理范围外数据前，先运行审计。它只请求一次当前 PBL 公开列表，不下载详情或附件；随后将公开 `courseExtendId` 与全部本地 `output_pbl*/processed/projects.jsonl` 比对，并检查详情负载、三级课题目录和 manifest 资源路径。

```bash
./.venv/bin/python -m sou_crawler \
  --output-dir output_pbl_audit_YYYYMMDD \
  --rate-limit 2 \
  --timeout 60 \
  --retries 2 \
  --concurrency 1 \
  audit-pbl
```

查看 `output_pbl_audit_YYYYMMDD/reports/pbl_coverage_audit.json`：

- `coverage.complete=true`：当前公开列表中的每个课题都能在本地 PBL 批次中找到；
- `details.complete=true` 和 `layout.complete=true`：每个范围内课题已保存详情负载，并位于 `assets/一级目录/方向/课题名称/`；
- `scope_validation.clean=true`：未发现非 PBL 课题或非批准资源来源；
- `scope_validation.deletion_candidates`：仅供人工确认的删除候选，不会被命令自动处理。

### 1. 首次全量建基线

首次采集或需要重建历史基线时使用 `crawl-pbl`。请使用新的带日期目录，避免覆盖已有批次。

```bash
./.venv/bin/python -m sou_crawler \
  --output-dir output_pbl_full_YYYYMMDD \
  --rate-limit 2 \
  --timeout 60 \
  --retries 2 \
  --concurrency 1 \
  crawl-pbl

./.venv/bin/python scripts/verify_pbl_output.py \
  --output-dir output_pbl_full_YYYYMMDD \
  --strict
```

`crawl-pbl` 会请求当前公开列表，下载全部课题详情与附件。它适合首批建库，不适合每日重复执行。

### 2. 日常增量采集

日常运行使用 `crawl-pbl-incremental`。命令会强制刷新公开列表，并自动发现当前目录下其他 `output_pbl*/processed/projects.jsonl` 作为历史基线；以 `business_id`（网站 `courseExtendId`）去重，只请求新增课题的详情与资源。

```bash
./.venv/bin/python -m sou_crawler \
  --output-dir output_pbl_incremental_YYYYMMDD \
  --rate-limit 2 \
  --timeout 60 \
  --retries 2 \
  --concurrency 1 \
  crawl-pbl-incremental

./.venv/bin/python scripts/verify_pbl_output.py \
  --output-dir output_pbl_incremental_YYYYMMDD \
  --strict
```

如果历史输出不在当前目录，显式提供一个或多个历史项目文件：

```bash
./.venv/bin/python -m sou_crawler \
  --output-dir output_pbl_incremental_YYYYMMDD \
  --known-projects /path/to/other/projects.jsonl \
  --rate-limit 2 \
  --timeout 60 \
  crawl-pbl-incremental
```

没有任何可用历史 `business_id` 时，增量命令会停止。此时应先运行一次全量建基线，而不是把增量误用为全量。

### 3. 断点续跑

同一批次因网络、电脑休眠或进程中断而未完成时，使用完全相同的 `--output-dir` 和命令重新运行。

- 已保存的详情、专业附件、公共附件和附件元数据会跳过；
- 已处于正确课题目录的资源清单项会跳过；
- 下载缓存会被复用，已成功下载的文件不需要再次请求；
- 增量命令仍会刷新公开课题列表，但只处理不在历史基线中的课题。

不要删除 `raw/`、`processed/asset_manifest.jsonl` 或 `assets/_download_cache/` 来“重试”。如确需重新建批次，请新建一个输出目录并保留旧批次用于追溯。

### 4. 本地验收与归档

每个批次结束后，必须运行严格校验：

```bash
./.venv/bin/python scripts/verify_pbl_output.py \
  --output-dir output_pbl_incremental_YYYYMMDD \
  --strict
```

校验器会检查：

- `projects.jsonl` 与 `asset_manifest.jsonl` 是否存在；
- 每个项目目录是否存在，且包含 `详情页信息.json`；
- 每个课题是否含有原始详情页负载；
- 目录是否严格对应 `assets/一级目录/方向/课题名称/`，同名业务记录是否使用 `__business_id` 后缀；
- manifest 中的资源文件是否都实际存在，且位于所属课题目录内；
- 是否出现重复 `business_id` 或重复 manifest key；历史公开列表中的同课题重复会以警告列出，不阻断文件完整性校验。

校验通过后再进行海报复制、数据导入或其他下游交付。下游写入外部系统不属于采集器的自动步骤，应先执行目标系统去重与写入确认。

## 输出与验收

每个批次独立存放，不覆盖历史批次。推荐目录命名：

```text
output_pbl_full_YYYYMMDD/           # 首次或重建基线
output_pbl_incremental_YYYYMMDD/    # 当日新增课题
output_pbl_audit_YYYYMMDD/           # 当前公开列表与本地数据的审计报告
```

目录结构：

```text
output_pbl_incremental_YYYYMMDD/
  raw/
    pbl_ais_cis_page.json                 # 当前公开列表原始响应
    list_items.jsonl                      # 本批次课题列表
    pbl_details.jsonl                     # 详情接口响应
    pbl_major_attachments.jsonl           # 专业附件响应
    pbl_public_attachments.jsonl          # 公共附件响应
    pbl_attachment_metadata.jsonl         # 附件元数据
    pbl_*_failures.jsonl                  # 可恢复失败明细（如有）
  processed/
    projects.jsonl                        # 标准化课题记录，主事实源
    projects.csv
    projects.sqlite
    asset_manifest.jsonl                  # 资源文件清单，主事实源
    asset_manifest.json
    data_quality_summary.json
  assets/
    一级目录/
      方向/
        课题名称/
          详情页信息.json
          海报.jpg
          缩略图.jpg
          Banner.jpg
          教授名称.png
          专业附件.pdf
          公共附件.pdf
  reports/
    incremental_summary.json              # 仅增量批次
    summary.json
    summary.md
    pbl_*_stats.json
```

同一“一级目录/方向/课题名称”下的不同业务记录会自动在目录名末尾追加 `__business_id`，防止详情和附件相互覆盖。

重点验收文件与判断标准：

| 文件 | 用途 | 通过条件 |
| --- | --- | --- |
| `reports/incremental_summary.json` | 记录网站列表总量、去重后课题量、基线量和新增量 | `new_projects` 符合预期 |
| `processed/data_quality_summary.json` | 记录项目、附件和分类统计 | 无异常的缺失/重复趋势 |
| `reports/pbl_*_stats.json` | 请求、成功、失败和错误分类 | `pages_failed` 与 `errors` 已处理或可解释 |
| `reports/pbl_coverage_audit.json` | 当前公开列表覆盖、范围和目录位置审计 | `valid=true`；删除候选为空或已逐项确认 |
| `processed/asset_manifest.jsonl` | 资源与本地路径对应关系 | 每项 `file` 存在 |
| `scripts/verify_pbl_output.py --strict` | 全批次完整性检查 | 退出码为 0，`valid=true`；`warnings` 需人工知悉 |

## 恢复与故障处理

| 现象 | 处理方式 | 不应做的事 |
| --- | --- | --- |
| 429、超时、网络中断 | 查看对应 `pbl_*_stats.json` 与 `pbl_*_failures.jsonl`，使用同一输出目录重跑 | 提高并发、缩短限速或切换代理 |
| 401/403 | 停止任务，确认网站的公开访问范围与授权方式 | 重试登录接口、伪造请求头或绕过访问控制 |
| `verify-pbl-output --strict` 失败 | 根据 JSON 中的缺失项重跑同一批次；仍失败时保留报告再排查 | 删除 manifest 或成功资源后从头混跑 |
| 增量提示没有历史基线 | 先运行一次 `crawl-pbl`，或通过 `--known-projects` 指定可信历史文件 | 直接用增量执行首次全量 |
| 网站接口字段变化 | 走高级接口发现流程，重新确认配置与测试 | 直接猜测接口参数或批量枚举 ID |

## 高级接口发现

仅当网站前端或公开接口发生变化时执行。日常 PBL 增量采集不需要运行这些命令。

```bash
./.venv/bin/python -m sou_crawler discover
./.venv/bin/python -m sou_crawler analyze-apis
```

发现产物：

- `output/discovery/network_logs.jsonl`；
- `output/discovery/api_candidates.json`；
- `output/discovery/api_inventory.md`；
- `output/discovery/api_classification.md`。

对于通用抓取配置，先参考生成的 `config/api_targets.example.json`，人工确认公开接口和字段后才创建 `config/api_targets.json`。随后可按需运行 `crawl-lists`、`crawl-details`、`normalize`、`download-assets` 与 `report`。这些命令服务于接口维护和实验，不替代 PBL 专项的 `crawl-pbl` / `crawl-pbl-incremental`。

## 维护脚本与测试

历史输出目录重排，保留旧文件并优先使用硬链接：

```bash
./.venv/bin/python scripts/reorganize_pbl_outputs.py --dry-run
./.venv/bin/python scripts/reorganize_pbl_outputs.py output_pbl_full_YYYYMMDD
```

从一个已验证批次复制海报，保持目录结构且不覆盖目标已有文件：

```bash
./.venv/bin/python scripts/copy_pbl_posters.py \
  --output-dir output_pbl_incremental_YYYYMMDD \
  --destination /path/to/poster-delivery \
  --dry-run
```

运行测试：

```bash
./.venv/bin/python -m unittest discover -s tests
./.venv/bin/python -m compileall -q sou_crawler scripts
```

测试不依赖线上网站，覆盖请求限速与错误分类、URL 去重、接口发现、PBL 目录与附件命名、增量基线保护、导入映射、海报复制和输出校验。
