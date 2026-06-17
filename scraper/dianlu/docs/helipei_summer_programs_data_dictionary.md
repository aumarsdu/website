# 河狸陪夏校库数据字典

## 目标

将 DianEdu 采集库 `data/processed/dianedu.sqlite` 转换为河狸陪自有夏校库：

```text
data/processed/helipei_summer_programs.sqlite
```

转换原则：

- `source_projects` 保留源库 1080 条项目快照，便于追溯。
- `summer_programs` 只保留夏校库候选项目。
- 使用 `library_scope` 区分主夏校、插班、探校和相邻项目。
- 保留源 JSON，同时生成河狸陪标准分类、筛选字段、费用、时间批次、标签和质量问题。

## 表结构

### `import_runs`

记录每次转换任务。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER | 转换批次 ID |
| `source_db_path` | TEXT | 输入库路径 |
| `output_db_path` | TEXT | 输出库路径 |
| `started_at` | TEXT | 开始时间 |
| `finished_at` | TEXT | 结束时间 |
| `source_project_count` | INTEGER | 源项目数量 |
| `summer_program_count` | INTEGER | 夏校库候选数量 |
| `session_count` | INTEGER | 时间批次数 |
| `cost_count` | INTEGER | 费用记录数 |
| `tag_count` | INTEGER | 标签记录数 |
| `quality_issue_count` | INTEGER | 数据质量问题数 |

### `source_projects`

保留所有源项目。

| 字段 | 类型 | 说明 |
|---|---|---|
| `source_project_id` | TEXT | 源项目 ID |
| `source_category` | TEXT | 源大类 |
| `source_project_type` | TEXT | 源小类 |
| `source_title` | TEXT | 源标题 |
| `raw_json` | TEXT | 完整源 JSON |

### `summer_programs`

河狸陪夏校库主表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT | 河狸陪内部项目 ID |
| `source_project_id` | TEXT | 源项目 ID |
| `title` | TEXT | 项目名称 |
| `one_line_summary` | TEXT | 一句话摘要 |
| `library_scope` | TEXT | `primary_summer` / `extension_join_class` / `extension_campus_visit` / `adjacent_enrichment` / `summer_related` |
| `standard_category` | TEXT | 河狸陪标准大类 |
| `standard_subcategory` | TEXT | 河狸陪标准小类 |
| `country` | TEXT | 国家 |
| `city_region` | TEXT | 城市 / 区域 |
| `min_grade_name` | TEXT | 最低年级 |
| `max_grade_name` | TEXT | 最高年级 |
| `age_range_text` | TEXT | 年龄范围原文 |
| `residential_type` | TEXT | 住宿类型 |
| `credit_type` | TEXT | 学分类型 |
| `delivery_mode` | TEXT | 授课方式 |
| `application_deadline_raw` | TEXT | 申请截止原文 |
| `application_requirement_text` | TEXT | 申请要求纯文本 |
| `description_text` | TEXT | 项目介绍纯文本 |
| `description_html` | TEXT | 项目介绍 HTML |
| `recommendation_score` | INTEGER | 顾问排序分 |
| `data_quality_status` | TEXT | `ready` / `needs_review` |
| `raw_json` | TEXT | 源 JSON |

### `program_sessions`

项目时间批次。

| 字段 | 类型 | 说明 |
|---|---|---|
| `program_id` | TEXT | 项目 ID |
| `start_date` | TEXT | 开始日期 |
| `end_date` | TEXT | 结束日期 |
| `date_range_raw` | TEXT | 原始时间文本 |
| `duration_days` | INTEGER | 天数 |
| `availability_status` | TEXT | 名额状态，默认 `unknown` |

### `program_costs`

项目费用拆分。

| 字段 | 类型 | 说明 |
|---|---|---|
| `program_id` | TEXT | 项目 ID |
| `fee_type` | TEXT | `tuition` / `service_fee` / `hot_sale_fee` / `early_bird_service_fee` / `late_bird_service_fee` / `current_price` / `tuition_view` |
| `amount` | REAL | 金额 |
| `currency` | TEXT | 币种 |
| `raw_value` | TEXT | 原始值 |
| `normalized_note` | TEXT | 说明 |

### `program_tags`

标签体系。

| 字段 | 类型 | 说明 |
|---|---|---|
| `program_id` | TEXT | 项目 ID |
| `tag_type` | TEXT | 标签类型 |
| `tag_value` | TEXT | 标签值 |
| `confidence` | INTEGER | 置信度 |
| `source` | TEXT | 标签来源 |

### `program_assets`

项目资源。

| 字段 | 类型 | 说明 |
|---|---|---|
| `program_id` | TEXT | 项目 ID |
| `asset_url` | TEXT | 资源 URL |
| `asset_type` | TEXT | image / pdf / video / file |
| `authorized_download_status` | TEXT | 下载状态 |

### `data_quality_issues`

数据质量问题。

| 字段 | 类型 | 说明 |
|---|---|---|
| `program_id` | TEXT | 项目 ID |
| `issue_type` | TEXT | 问题类型 |
| `severity` | TEXT | 严重程度 |
| `field_name` | TEXT | 字段 |
| `message` | TEXT | 说明 |

## 视图

### `advisor_program_search`

顾问检索视图，聚合项目核心字段、时间批次数和质量问题数。

### `primary_summer_programs`

主夏校项目视图，仅包含 `library_scope = 'primary_summer'`。

## 运行

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/dianlu
.venv/bin/python -m dianedu_archiver build-helipei-summer-db
```

也可以直接运行模块：

```bash
.venv/bin/python -m dianedu_archiver.helipei_summer \
  --source-db data/processed/dianedu.sqlite \
  --output-db data/processed/helipei_summer_programs.sqlite
```

或使用独立脚本：

```bash
.venv/bin/python scripts/build_helipei_summer_db.py
```
