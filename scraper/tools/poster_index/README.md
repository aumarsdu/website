# poster_index — 供应商课题海报统一索引

三家供应商（集思未来、HIREP、中科浩博）课题与海报的统一索引工具。**素材库只读**；
索引与报告原子写入 `~/Workspace/_private-tasks/xhs-cover-gen/posters/`。

需求来源（`07_产品与研发/01_产品策划/20260928_科研内容AI产线/`）：
海报索引需求、细分方向标签需求（§4+§8 决议 D1-D8）、索引修正需求（2026-09-29）。

## 命令

```bash
cd scraper/tools && PYTHONPATH=. python3 -m poster_index index --supplier all   # 重建索引+报告（原子写）
PYTHONPATH=. python3 -m poster_index find --supplier all \
  --direction 人工智能与机器学习 --open-only --limit 10                        # 条件筛选
# find 过滤项：--subject --direction --type --begins-from/--begins-to --open-only --limit --json
```

## item 字段（契约）

基础：supplier/recordId/title/projectType/format/schoolBegins(ISO|null)/instructors/
corpus(供应商原字段)/posterPath/posterVariant(processed|raw)/posterSha256/
posterCandidates/sourceFile/crawledAt。

细分方向（D1-D8）：`subject`（由 direction 推出）、`subjectOriginal`（供应商原口径）、
`subjectSource`（label|title|corpus|override）、`direction`/`directionSecondary`
（受控词表）、`directionBasis{source,keyword,rawLabel}`。

format 四值：小组科研|班课科研|1V1|其他（RA 类=其他，军亮 2026-09-29）。

## 配置文件（改配置不改代码）

| 文件 | 作用 |
|---|---|
| `direction_taxonomy.json` | 24+2 细分方向词表；数组顺序=匹配优先级（D6）；abbrev 关键词需佐证（D4） |
| `typeid_map.json` | 集思 typeId→project_type 反推表（源自 20260703 批次；ambiguous 条目命中即降级待确认） |
| `format_map.json` | projectType→format 映射；fallback=其他 |

## 军亮人工入口（均在 posters/ 输出目录）

- `direction_overrides.json`：`{"<供应商>:<recordId>": "<细分方向>"}`，重建时优先；
- `军亮_抽检30条_20260929.json`：方向 90% 验收抽检包；
- `军亮_待确认清单_20260929.json`：43 条待人工定向；
- 各家 `<供应商>.report.json`：direction/format 分布（含可报名）、待确认清单、
  标签→方向映射表、projectType 回填来源。

## 维护注意

- 集思新课题 projectType 回填链：清单 → raw.types → typeId 反推（歧义进待确认）；
- HIREP 列表接口可能忽略 `current` 分页参数，爬虫已带单请求回退；
- 中科同名课题多次抓取（uuid 是记录标识），去重键=标题；
- 重建可重复（除 generatedAt）；单测 `poster_index/tests/`（33 例，离线）。
