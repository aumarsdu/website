# R6-B 切换执行 Runbook（待两项 Owner 输入后按此执行）

- 起草：2026-09-28；依据：Owner R6-B 授权指令 + `evidence/switch_application_draft.md` §3/§4
- 状态：**未执行任何切换步骤**。两项执行必需输入缺失（见 §0），本文件把可准备部分全部固化，输入到位后按序执行。
- 纪律：验证失败即回滚并停止，重试需 Owner 新授权；全程逐批回执落 `evidence/switch_execution.json`。

## 0. 执行必需输入（缺失，等待 Owner）

| 输入 | 状态 | 影响 |
| --- | --- | --- |
| 目标端点与访问方式（host:port/db + 连接方式） | **缺失**（Owner 指令两次均为占位符或未含此项） | 四项只读预检未执行过；无端点则预检与导入均无法进行 |
| 切换窗口时间 | **缺失**（占位符〈Owner 指定时间窗〉未填） | 无窗口则不能声明冻结写入、不能执行五步 |

附带澄清（如实报告）：Owner「确认 switch_precheck.json 预检结果无异常」——该确认对文件级前置条件①②（备份在场、账本零偏差）成立；但该文件的连接预检部分（连通性/schema 台账/表行数快照/磁盘空间）明确记录为**未执行**（`connection_attempts: []`，`blocked_on: target_endpoint`）。端点提供后将先补执行四项预检，预检异常即停。

## 1. 窗口前准备（端点+窗口到位后、声明窗口前）

1. 重启候选集群：`python3 -B pg_candidate.py init`（现为 stopped；重启属本地非高危操作，数据目录保留）。
2. 补执行 R6-A 四项只读预检（对目标端点）→ 结果补录 `switch_precheck.json`。
3. 预检通过 + Owner 确认窗口后进入 §2。

## 2. 五步执行（草案 §3）

1. **窗口声明/冻结写入**：记录窗口起止时刻与双侧（真实目标、候选集群）冻结声明；此后窗口内禁止一切写入（候选侧仅 create_backup 只读快照）。
2. **窗口时点快照**：`backup_restore.create_backup('candidate_full_1', candidate_data/backups/switch-<date>)`；sha 记录入 execution 证据。
3. **T09 幂等导入**：复用 `candidate_data/full_migration_1/` 的 24 个密封批次，经 `importer.import_sealed` 导入目标库；目标侧如已有数据，先按 legacy bridge 0002 迁移口径对账（`legacy_id_map`/行数守卫），**存在不可对账数据即停止并报告，不静默覆盖**。逐批回执（inserted==rows）记录。
4. **验证**（全过才算成功）：
   - 目标库 digest == `e05ebc98123cee35636d805c19e2318986a367be1ad83ca80d9b0c382205d44e`（复用 full_migration.py 的摘要 SQL）；
   - `projection.rebuild_consistency(目标库)` consistent=true；
   - 逐表计数 == candidate_full_1（sources 6 / source_records 7,972 / observations 9,453 / content_payloads 5,181 / content_payload_bodies 5,181 / ingest_batches 24 / current ok 7,716 + unresolved 256）；
   - T11 全量 golden 20/20 且 p95<1s（`search.search(目标库, …)` 对照 `fixtures/t11_golden_full.json`）。
5. **指针切换**：应用层读路径指向目标库；旧读路径保留只读 ≥7 天（观察期后退役由 Owner 决定）。
   2026-09-28 只读排查已定位读路径两处（待 Owner 追认）：
   a) `tools/research_db_admin_server.py:19` `DEFAULT_DATABASE_URL = postgresql://research_ops@/research_projects_clean?host=/tmp&port=55432`——切换点为启动参数 `--database-url`（或修改默认值）；旧路径保留只读即指该服务可继续以旧 URL 跑观察期；
   b) `db/research_db/web_preview/` 走静态快照（`data/summary.json` + `data/projects.jsonl`，app.js fetch 本地文件）——切换 = 从新目标库重生成两份快照文件（生成脚本待 Owner 指认或由 Writer 沿用 admin server 导出路径）。

## 3. 回滚（草案 §4，任一验证失败即执行）

1. 导入未提交部分回滚（T09 单事务批级）；
2. 应用层指回旧读路径；
3. 目标库按窗口快照/旧库快照恢复，对账零偏差方视为回滚完成；
4. 失败现场保留，**重试需 Owner 新授权，不盲重试**。

## 4. 证据协议

`evidence/switch_execution.json` 记录：窗口时刻、冻结声明、快照 sha、逐批回执、四项验证结果、指针切换时刻、（如触发）回滚记录；完成后更新 task_state 与账本并报告 Owner。
