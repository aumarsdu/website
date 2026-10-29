# 科研项目资料库补全收官 Spec（2026-09-28）

- 依据：`db/research_db/goal_20260908_side/evidence/state_audit_20260928.md`（只读审计，差距编号沿用其 R 系列）
- 前置状态：T01–T13 首期 FIRST_PHASE_COMPLETE（Owner 裁决 ratify/accept_64/accept_all）；全量候选迁移已按 Owner 确认执行，双重放 identical=true（digest e05ebc98…）
- 性质：本 Spec 只覆盖审计认定的 A 类差距（可修缺口）与 R6 申请草案；R6 执行、R7 发布不在本 Spec 范围

## 1. 目标与完成含义

把候选科研项目数据库从"首期验收完整"补齐到"可提请真实目标切换的完备状态"：

1. 闭环全量迁移申请草案（`evidence/full_migration_application_draft.md`）已承诺但未执行的验证项（备份、检索冒烟）；
2. 修复审计认定的工具粒度与可见性缺口（not_seen 运行粒度、candidate 身份复核队列）；
3. 补全文档与账本登记，使仓库自身文档要求（AGENTS §11、quality_commands 完成规则）重新成立；
4. 产出真实目标切换申请草案（仅草案，不含执行）。

完成含义：task_state.json 中 R1–R6D 全部 DONE 且每项有本会话证据；全量测试套件全绿（基线 163 项 + 本轮新增）；`candidate_hashes.json` 零偏差；审计 A 类 5 项差距逐项闭环勾稽；完成报告已提交 Owner（含 R6 执行授权请求与候选集群去留决策请求）。R6 执行与 R7（D01）等待 Owner 另行单独授权，不冒充完成。

## 2. 本轮授权与不可扩大范围

本轮（Goal 命令）默认授权全部非高危本地操作，包括：隔离候选集群（127.0.0.1:55441）上的全部读写与演练、新建及删除本轮自建的演练临时库、goal_20260908_side 目录内代码/测试/文档/evidence/fixtures 写入、账本重哈希。

不可扩大范围（与既往边界一致）：

- 旧库/生产库/真实目标库写入（R6 仅允许产出申请草案文本）；
- 候选集群 `pg_candidate.py destroy`（数据目录必须保留；`stop` 仅在 Owner 要求时执行）；
- 外部系统写入、公开发布（R7/D01）、资金/权限安全策略操作、批量删除、commit/push/PR/merge/deploy；
- 修改已封存迁移报告 `evidence/full_migration_report.json` 与已冻结试点 golden `fixtures/t11_golden.json`（补充证据一律另立新档）；
- B 类已接受口径（13 张预留空表、T11 显式未知、批次级 evidence_location、检索粒度=identity、跨源身份合并）——除非 Owner 变更裁决，本轮只做文档声明，不做实现；
- 改共享抓取器、旧库、他人脏文件；`scraper/` 目录 Git 同步动作。

## 3. 差距基线（引用审计，不重复论证）

| 编号 | 差距 | 严重度 |
| --- | --- | --- |
| A1 | candidate_full_1/2（9,453 观察）无 T12 备份、无恢复演练，RTO 证据仅试点规模 | 高（申请草案 §4 承诺未闭环） |
| A2 | 申请草案 §3 第 6 条检索冒烟未执行；全量语料无冻结的检索正确性基线 | 高（同上） |
| A3 | not_seen 以 ≤500 行批次为基准，多批次源数字全为噪音，下架检测无业务口径 | 中 |
| A4 | quality_commands.md（33 模块）与 README 未登记 full_migration.py；预留空表未声明 | 中（违反仓库文档要求） |
| A5 | 256 条 identity_status='candidate' 不进任何复核队列，身份复核无抓手 | 中 |

## 4. 任务需求与可客观判定的 DoD

### R1 全量库 T12 备份与恢复演练（闭环 A1）

需求：对 `candidate_full_1` 执行既有 `backup_restore.create_backup` 流程；恢复到本轮自建临时库（如 `candidate_full_1_drill`）；按 T12 对账口径核验（表计数、按源身份/观察分布、投影指针状态、摘要 digest 一致）；记录实测 RTO 与 1 小时预算比较；演练完成后删除自建临时库；备份产物落 `candidate_data/backups/`。candidate_full_2 与 full_1 digest 已证一致，不重复演练，在证据中说明。

DoD：
- `evidence/t12_full_drill.json`：备份清单（含 pg_dump 哈希门禁）、恢复计数对账零偏差、RTO 实测值、恢复后 `rebuild_consistency=true`；
- 临时库已删除，集群内无演练残留（列出库清单佐证）；
- 既有 163 项测试不回归。

反例（实现前先证伪）：对试点备份流程直接套用全量库若无逐表对账，视为不满足——必须有 9,453 观察、7,972 身份、256 unresolved 的逐项匹配记录。

### R2 全量检索 golden 冻结与冒烟补证（闭环 A2）

需求：沿用 `generate_t11_queries.py` 的独立性模式——20 条查询的期望值必须由直接 SQL 扫描（不经 `search.py`）在 `candidate_full_1` 上标注，先冻结再以 `search.py` 验证匹配；产出 `fixtures/t11_golden_full.json`（含 sha256，登记入账本）；冒烟性能与正确性结果落 `evidence/t11_full_smoke.json`（20/20 匹配、p95 < 1s）。不得修改已封存迁移报告与试点 golden。

DoD：
- golden_full 冻结后由未参与标注的复核（新会话/子代理）自写 SQL 抽验 ≥5 条一致，复核记录落 `evidence/independent_review_r2.md`；复核不可得时标 WAITING_OWNER，不得自行签署；
- 试点 golden（t11_golden.json）与迁移报告哈希在账本中保持不变（零偏差佐证）；
- 新增 ≥8 项单元测试（golden 载入、期望结构、与 search.py 一致性）。

### R3 not_seen 运行（run）粒度口径（闭环 A3）

需求：新增以"采集运行"为基准的 not_seen 报告：输入文件→运行类型（full_refresh / incremental，由 `source_registry.json` 登记路径派生）→该运行覆盖的身份集合；只有 full_refresh 运行可作 not_seen 基准（增量运行仅含新增，不具全集语义，报告中显式排除并说明）；对照候选库该源身份集合，输出"在库但不在最新全量刷新运行"清单（疑似下架，不自动改状态、不删除）。已封存批次与已导入数据不重放、不修改。

DoD：
- `projection.py` 新增函数（如 `not_seen_run_report`）+ ≥6 项单元测试（含反例：增量运行作基准必须报口径错误；zhongke 单次全量刷新基准 not_seen=0；jisi 旧全量 vs 新全量能列出真实消失身份）；
- 在 `candidate_full_1` 实跑各 full_refresh 源并输出结果到 `evidence/r3_not_seen_run.json`（数字可复算）；
- 既有批次级 `not_seen_report` 行为不变（回归测试佐证）。

### R4 文档补全与账本收口（闭环 A4）

需求：`quality_commands.md` 模块清单补 full_migration.py（第 34 模块）及本轮新增/变更命令（全量迁移、全量备份演练、全量 golden、run 粒度 not_seen、candidate 队列）；`README.md` 增补：全量迁移章节（对象、命令、输出、验证、回退）、预留空表声明（B 类口径：虚拟投影 + 文件化素材登记，13 张表暂无写入者）、审计与本轮闭环索引；所有写入文档的命令必须实际可运行并留回执。

DoD：文档中每条新命令有执行回执日志；`candidate_hashes.json` 重哈希后零偏差；文档不含与实现不符的描述（复核抽查）。

### R5 candidate 身份进入质量队列（闭环 A5）

需求：`projection.quality_queue` 新增类别 `identity_candidate`：只读 `source_records WHERE identity_status='candidate'`，联源编码与当前指针状态，确定序输出；为身份复核工作流提供唯一 surfaced 抓手。不改库表、不写状态。

DoD：`candidate_full_1` 上队列返回 256 条（yanqu_192 + yinzhi_64，与审计一致）并落 `evidence/r5_quality_queue.json`；≥4 项单元测试；既有 conflicts/quality_issues 类别行为不变。

### R6D 真实目标切换申请草案（仅草案）

需求：按 Owner 既定模式（先出申请、后授权、不捆绑）起草切换申请：具体对象（candidate_full_1 → 真实目标）、冻结写入方案、前置条件（R1 备份在场 + 账本零偏差）、切换步骤、验证口径（对账零偏差 + 双库 digest）、回退方案（T12 恢复 + 失败回退路径）、显式声明"本草案不含任何执行动作、需 Owner 单独授权"。

DoD：`evidence/switch_application_draft.md` 成稿并在 task_state 登记；无任何切换执行动作（集群内目标侧无写入）。

## 5. 状态、批次进度与停止条件

- task_state.json 为唯一状态真相：新增任务条目 R1、R2、R3、R5、R4、R6D（CurrentState 初始 READY，依赖见 Plan），钉 `completion_spec_sha256` / `completion_plan_sha256`；首期 13 项 DONE 记录与既有字段不动。
- 每完成一批：更新 task_state（CurrentState/Evidence/last_continuation）、登记新证据文件入 `candidate_hashes.json` 并全量核验零偏差、回读 diff。
- 停止条件（任一即停并如实报告）：R1–R6D 全部 DONE 且完成报告 `evidence/completion_report_20260928.md` 已提交 Owner（含 R6 执行授权与集群去留两项请求）→ 本轮完成；需要 Owner 决策而无法推进 → 标 WAITING_OWNER 并给出唯一下一步；高危边界被要求跨越 → 拒绝并记录。
- 不把未复核任务标 DONE；不把等待授权的 R6/R7 冒充完成。
