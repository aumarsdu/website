# 科研项目资料库补全收官 Plan（2026-09-28）

- 对应 Spec：`2026-09-28-research-project-database-completion-spec.md`（同目录）
- 工作目录：`db/research_db/goal_20260908_side/`（沿用唯一 Writer 等效隔离）
- 前置事实（2026-09-28 审计已证）：集群 running（127.0.0.1:55441）；candidate_full_1/2 表级一致（7,972/9,453/7,716/256）；48/48 seal 有效；账本 123/123；163/163 测试全绿。

## 1. 当前起点与优先级

| 优先级 | 任务 | 理由 |
| --- | --- | --- |
| P0 | R1 全量备份演练 | 申请草案承诺未闭环；切换申请的前置条件 |
| P0 | R2 全量 golden 冻结 | 申请草案承诺未闭环；全量语料唯一正确性基线 |
| P1 | R3 not_seen run 粒度 | 下架检测业务口径；工具缺口 |
| P1 | R5 candidate 质量队列 | 256 条候选身份复核抓手；工具缺口 |
| P2 | R4 文档补全 | 必须最后收口（要覆盖本轮全部新命令与文件） |
| P2 | R6D 切换申请草案 | 依赖 R1 在场（备份为前置条件）；纯文本无风险 |

## 2. 执行顺序（DAG）

```text
批 1（并行 READY）：R1 ──┐
                        ├─→ 批 3：R4（文档收口，依赖 R1/R2/R3/R5 全 DONE）
        R2 ──┐          │        │
             ├──────────┤        └─→ R6D（依赖 R1 DONE）
批 2（并行 READY）：R3 ──┤
        R5 ──┘
```

- 批 1 = R1 + R2：闭环申请草案两条未执行承诺，先恢复"账实承诺一致"。
- 批 2 = R3 + R5：两个独立工具增强，互不依赖，可并行。
- 批 3 = R4 + R6D + 终态：文档必须等前四项定型；R6D 引用 R1 备份作为切换前置条件。

## 3. 每批的实际动作

### 批 0：登记（写 task_state，一次性）

1. 只读核对：集群 status、账本 123/123 零偏差、审计文件在、无他人改动。
2. task_state.json 新增任务条目 R1/R2/R3/R5/R4/R6D（CurrentState=READY，R4 依赖 R1–R5，R6D 依赖 R1），新增 `completion_spec_sha256`/`completion_plan_sha256` 两字段钉本两文档；status 置 `IN_PROGRESS`（首期 13 项 DONE 与既有裁决记录不动）。
3. 账本重哈希 task_state.json 并核验零偏差。

### 批 1：R1 + R2

R1（顺序执行，全程回执留档）：
1. `backup_restore.create_backup` 对 `candidate_full_1`（素材清单沿用 T05 登记口径、配置哈希含本轮 spec/plan）→ `candidate_data/backups/full-<date>/`；
2. 新建临时库 `candidate_full_1_drill` → `restore_backup` → 逐表对账（sources 6 / source_records 7,972 / observations 9,453 / content_payload_bodies 5,181 / ingest_batches 24 / current ok 7,716 + unresolved 256）+ digest 复算一致 + `rebuild_consistency` 在恢复库上重跑为 true；
3. 实测 RTO（对照 3600s 预算）；删除 `candidate_full_1_drill`；列出集群库清单佐证无残留；
4. 证据 `evidence/t12_full_drill.json`；task_state R1→DONE；账本登记。

R2（独立性优先）：
1. 直接 SQL（不经 search.py）对 `candidate_full_1` 标注 20 条查询期望（沿用 generate_t11_queries.py 的查询参数集，期望值全部重算）；
2. 冻结 `fixtures/t11_golden_full.json`（sha256 写入文件头部字段并登记账本）；
3. `search.py` 逐条验证 20/20 匹配 + 计时（p95 < 1s）→ `evidence/t11_full_smoke.json`；
4. 新增 ≥8 项测试（载入/结构/一致性）；试点 golden 与迁移报告账本哈希不变（佐证未动）；
5. 独立复核（新会话/子代理自写 SQL 抽验 ≥5 条）→ `evidence/independent_review_r2.md`；不可得 → R2 标 WAITING_OWNER（证据保留），不阻塞批 2；
6. task_state R2→DONE（或 WAITING_OWNER）；账本登记。

批 1 收口：全量测试全绿 + ruff/format/pyright 零违规 + task_state/last_continuation 更新 + 账本零偏差。

### 批 2：R3 + R5

R3：
1. 反例先行：增量运行作基准必须拒绝；zhongke（单次全量刷新）run 基准 not_seen=0；jisi 两代全量刷新存在真实消失身份；
2. `projection.py` 新增 `not_seen_run_report(database, source_code)`（从 source_registry.json 派生运行类型；仅 full_refresh 运作基准；只读不改状态）+ ≥6 项测试；
3. 在 candidate_full_1 实跑 6 源 → `evidence/r3_not_seen_run.json`（数字可复算）；
4. 既有批次级 not_seen_report 回归不变。

R5：
1. `quality_queue` 增 `identity_candidate` 类别（只读 source_records 联 sources 与指针状态，确定序）+ ≥4 项测试；
2. candidate_full_1 实跑 = 256 条（192+64）→ `evidence/r5_quality_queue.json`；
3. 既有 conflicts/quality_issues 类别回归不变。

批 2 收口：同批 1 协议。

### 批 3：R4 + R6D + 终态

R4：quality_commands.md（34 模块 + 本轮新命令五类）与 README（全量迁移章节、预留空表声明、审计闭环索引）补全；文档内命令逐一执行留回执；账本重哈希。
R6D：`evidence/switch_application_draft.md`（对象/冻结写入/前置=R1 备份在场/步骤/验证/回退/显式"不含执行、需单独授权"）。
终态：`evidence/completion_report_20260928.md`（R1–R6D 结果、审计 A1–A5 逐项闭环勾稽、测试与账本终值、两项 Owner 请求：R6 执行授权 + 集群去留）；task_state status→`COMPLETION_DONE`（或如实 WAITING_OWNER 项）；账本零偏差终验。

## 4. 批次 DoD 与证据协议

每批通用 DoD（缺一不标 DONE）：

1. 新增测试全部通过且既有 163+ 项零回归；
2. `ruff check` / `ruff format --check` / `pyright` 对全部涉改模块零违规；
3. 证据文件齐全且内容可复算（命令、参数、输出、哈希）；
4. task_state.json 更新（CurrentState/Evidence/last_continuation）；
5. `candidate_hashes.json` 登记新文件并全量核验零偏差。

冻结纪律：试点 golden、迁移报告、已封存批次、审计文件保持字节不变（账本佐证）；补充证据一律新档。独立性纪律：R2 期望标注与验证分离；R3/R5 为 projection.py 规则变更，完成后由未参与实现者复核（`evidence/independent_review_r3_r5.md`），不可得时标 WAITING_OWNER 不自行签署。

## 5. 权限与资源操作边界

- 允许：隔离候选集群全部操作；新建/删除本轮自建演练临时库；goal 目录内代码/测试/文档/evidence 写入；账本重哈希；只读真实目标与旧库结构（不写入）。
- 禁止：旧库/生产库/真实目标写入；集群 destroy（数据目录必留）；公开发布（R7）；外部系统写入；批量删除；Git 同步（AGENTS §1.1）；修改冻结物。
- R6 执行需 Owner 对切换申请单独授权；R7（D01）独立立项。授权拒绝或未知时不绕过、不盲重试。

## 6. 可直接运行的 Goal 指令

见同目录 `2026-09-28-research-project-database-completion-goal.txt`（Owner 原文粘贴即用）。
