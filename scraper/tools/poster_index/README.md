# poster_index — 供应商课题海报统一索引

三家供应商（集思未来、HIREP、中科浩博）课题与海报的统一索引工具。**素材库只读**；
原入口直接写正式目录。本次使用独立副本，先生成候选，再验收发布。

需求来源（`07_产品与研发/01_产品策划/20260928_科研内容AI产线/`）：
海报索引需求、细分方向标签需求（§4+§8 决议 D1-D8）、索引修正需求（2026-09-29）。

## 命令

```bash
cd /Users/liujunliang/Workspace/knowledge-legacy/scraper/task_runs/20261013-index-posters
PYTHONPATH=. python3 -m poster_index index --supplier all   # 默认仅写本任务 candidates/
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

- `direction_overrides.json`：`{"description":"...","format":"...","overrides":{"<供应商>:<recordId>":"<细分方向>"}}`（保留现存包装格式，也兼容直接映射），重建时优先；
- `军亮_抽检30条_20260929.json`：方向 90% 验收抽检包；
- `军亮_待确认清单_20260929.json`：43 条待人工定向；
- 各家 `<供应商>.report.json`：direction/format 分布（含可报名）、待确认清单、
  标签→方向映射表、projectType 回填来源。

## 维护注意

- 集思新课题 projectType 回填链：清单 → raw.types → typeId 反推（歧义进待确认）；
- HIREP 用 `pageIndex`、固定 pageSize=200；重复页停止，不自动改用大页请求；
- 中科同名课题多次抓取（uuid 是记录标识），去重键=标题；
- 重建可重复（除 generatedAt）；本次索引测试 39 例、发布漂移与故障测试 5 例离线通过；数量以执行结果为准。

## 2026-10-13 修复与验收入口

独立副本：`/Users/liujunliang/Workspace/knowledge-legacy/scraper/task_runs/20261013-index-posters/`。原工具源码保留，其 index 命令仍会直接写正式目录；使用独立副本生成候选。

集思保留两份固定全量基线，增量目录仅接纳有完成时间、列表分页成功、详情/素材完整、ID 与清单一致的批次；已证实素材 404 可作为明确例外。失败和未完成批次排除。本批 7 个 ID 验证：6 个入索引，1 个缺课程海报列例外。中科按标题去重，当前 raw.startTime 优先于历史目录日期；旧 ID、原路径及备份位置见替换回执。缺日期保持 null。

海报入口为本批 prepare_plans.py 与本地 poster-background-redaction renderer；先逐图识别目标、确认版式样张，再生成暂存副本，以 verify_posters.py、OCR、QR 与视觉复核验收，Finish 文件名不代表合格。

本批 update_indexes.py 默认仅准备候选；--publish 校验候选、原图、正式基线，备份后逐文件原子替换并回读。所有候选及恢复文件在替换前写入并 fsync，故障使用已落盘文件恢复。六文件不具跨文件整体原子性，断电或强制终止恢复未实测。此发布器绑定本批，未来批次需重新建立范围和验收证据。

其他历史完整重建差异单列暂缓，未经素材验收不发布。overrides 保留，不自动填充待确认方向。


## 2026-10 合并说明

task_runs/20261013-index-posters 独立副本的改进（增量批次自动发现+完成门禁、
中科 raw.startTime 日期优先、--output-dir 门控、update_indexes 晋升流水线）
已于 2026-10-23 回并入本工具，副本保留于 scraper/task_runs/ 作历史记录。
验收：重建候选与正式索引逐条一致 + 两套测试（39+5）全绿。
