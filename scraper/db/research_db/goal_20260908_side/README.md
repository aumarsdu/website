# 2026-09-08 Goal 的隔离候选与证据

对应 Spec/Plan：`../../../docs/superpowers/specs/2026-09-08-research-project-database-{spec,plan}.md`；当前差距与授权边界见 `../../../docs/superpowers/specs/2026-09-25-research-project-database-{spec,plan}.md`。

本目录仅由当前 Goal Writer（2026-09-25 会话）修改；没有改写旧抓取器、旧暂存或数据库。
任务真实状态见 `task_state.json`；执行结果见 `evidence/`。本目录不是第二份长期计划。

## T01 候选内容

- `inventory.py`：只登记显式输入的相对路径、字节数和 SHA-256，不复制正文；CLI 读取独立 registry（approved_root + 登记哈希），请求路径不充当自身白名单。路径防护用于可信本地批次盘点，不宣称能抵抗具备本机写权限的恶意并发修改；`--dry-run` 不写文件、不连数据库。
- `target_guard.py` + `target_policy.json`（T01-R3）：候选写入目标的只读身份预检——目标必须严格位于隔离区内、组件级 symlink 拒绝、与受保护旧路径（五源目录、旧 schema/预览/共享工具）无交叠；非空目标须有 `.target_ownership.json` 归属标记。旧库端点（/tmp:55432）的数据库隔离策略记录在 policy 中，由 T03/T09 入口检查强制。
- `source_registry.json`（T01-R4）：每源结构化 `capture_time_evidence`（逐文件 `crawled_at` 窗口实测于 `evidence/capture_time_evidence.json`；盐趣/引知区分观察/处理/命名时间，不可靠即 `unknown` 并说明），并显式登记 2026-09-23 后续产物为 excluded_pending_review。
- `pilot_manifest.json`（T01-R1）：已冻结（`frozen_candidate_pending_independent_review`）。盐趣 20 候选原图 20/20 位置核对通过（`evidence/yanqu_position_check.json`）；引知 10 锚点核为页面结构锚（非项目条目）；五源覆盖矩阵见 `evidence/coverage_matrix.json`。T01 的抽样认可不构成 T06/T07 语义准确率。
- `evidence/legacy_to_candidate_mapping.md`（T01-R2）：旧工具/旧 schema/爬虫到新职责的映射清单。
- `contract.py` + `contract_config.json` + `golden/t02_expectations.json` + `contract.md`（T02）：身份编码/内容哈希/字段四态/观察键/可信序投影；golden 冻结于实现之前。
- `pg_candidate.py` + `migrations/` + `run_migrations.py` + `tests/legacy_replica.sql` + `schema_model.md`（T03）：隔离候选 PostgreSQL 集群（仅 TCP 127.0.0.1:55441）、版本化迁移（台账+checksum，`--dry-run` 只读 / `--apply` 应用）、代表性旧 schema 升级桥接（行数对账守卫，不静默丢行）。

在本目录执行：

```bash
python3 -B -m unittest discover -s . -p 'test_*.py' -v
ruff check inventory.py test_inventory.py target_guard.py test_target_guard.py
ruff format --check inventory.py test_inventory.py target_guard.py test_target_guard.py
pyright --project pyrightconfig.json
python3 -B target_guard.py --policy target_policy.json --target candidate_data --dry-run
```

示例（使用合成或已授权显式来源路径）：

```bash
python3 -B inventory.py --root /approved/source --registry /approved/registry.json --input records.jsonl --dry-run
```

独立复核前 T01 保持 WAITING_OWNER，不进行依赖任务写入。复核者需逐项核对 source_registry（含纳入/排除与新产物处置）、baseline、冻结的 pilot_manifest、覆盖矩阵、时间证据、映射清单、目标策略与全部测试证据。复核者可为 Owner 或获授权独立 AI（原 Spec G-R）；当前会话以未参与实现的独立子代理执行复核，其结论原文记录于 `evidence/independent_review_t01.md`，由 Owner 追认。

registry/manifest 读取成功不代表业务批准；哈希记录见 `evidence/candidate_hashes.json` 与 `evidence/validation.json`。

## 全量候选迁移（2026-09-28，Owner 确认申请草案后执行）

- 对象：`source_registry.json` 登记五源全量 10,427 行（jisi_sou 1,344 / jisi_dom 2,276 / zhongke 2,806 / hirep 3,742 / yanqu 195 / yinzhi 64 条目=32 项目×中英，yinzhi 口径经 Owner accept_64 裁决）。
- 命令：`python3 -B full_migration.py`（工作目录本目录；隔离集群 127.0.0.1:55441）。
- 产出：数据库 `candidate_full_1` / `candidate_full_2`（各 24 批次，≤500 行/批；7,972 身份 / 9,453 观察 / 5,181 payload）；双重放 identical=true，digest `e05ebc98…`；rejected=coerced=0。
- 验证：T08 密封（48/48 事后 verify_seal 通过）→ T09 幂等导入（回执 inserted==rows）→ T10 rebuild_consistency 两库 true → 双库 digest 一致；检索冒烟 20/20（p95 0.23s，`fixtures/t11_golden_full.json`）。
- 回退：T12 全量备份 `candidate_data/backups/full-20260928/`（恢复对账零偏差，RTO 1.999s，`evidence/t12_full_drill.json`）；任一批次失败单事务回滚，整库可恢复。
- 证据：`evidence/full_migration_report.json`（authorization 记录 Owner 原话）；申请草案 `evidence/full_migration_application_draft.md`。

## 模型预留空表声明（14 张，首期设计口径）

投影为虚拟计算（`source_record_current` 指针 + winner payload，不物化 `provider_projects`/`offerings`）；素材/OCR 走文件化登记（T05 asset_registry、盐趣原图 20 张、197 项清单核验）；跨源身份合并（identity_links）与冲突记录（conflicts/conflict_members）为二期预留。以下表当前无写入者、行数为 0（与试点库一致，非迁移回归；candidate_full_1 实测 2026-09-28）：
`asset_blobs`、`asset_links`、`asset_locations`、`conflict_members`、`conflicts`、`extractions`、`field_evidence`、`identity_links`、`input_files`、`legacy_id_map`、`manual_overrides`、`offerings`、`project_source_links`、`provider_projects`。
（`quality_issues` 不在此列：它有批次级 not_seen 写入路径，全量库未触发该路径故为 0。）

## 补全收官战役（2026-09-28，审计 A1–A5 闭环）

- 审计：`evidence/state_audit_20260928.md`（只读审计：数据零缺陷，5 项 A 类差距）。
- R1 全量 T12 备份演练：`evidence/t12_full_drill.json`。R2 全量检索 golden+冒烟：`fixtures/t11_golden_full.json` + `evidence/t11_full_smoke.json` + `evidence/independent_review_r2.md`（复核中发现并修复 search.py 分页缺陷：payload 变体致同 identity 多行 → DISTINCT ON 确定性单卡）。
- R3 运行粒度 not_seen：`evidence/r3_not_seen_run.json`（增量运行显式不可作基准；嫌疑分桶只认基准后 sighting）。R5 candidate 身份队列：`evidence/r5_quality_queue.json`（256=192+64）。R3/R5 复核：`evidence/independent_review_r3_r5.md`（两轮，首轮 4 条 NOTE 全采纳后复检 PASS）。
- 任务状态：`task_state.json`（R1–R6D）；命令与回执：`quality_commands.md` + `evidence/r4_command_receipts.log`。
