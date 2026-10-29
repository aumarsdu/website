# 补全收官战役完成报告（2026-09-28）

- 依据：Spec/Plan `../../../docs/superpowers/specs/2026-09-28-research-project-database-completion-{spec,plan}.md`（sha256 钉于 task_state.json `completion_spec_sha256` / `completion_plan_sha256`）
- 审计基线：`evidence/state_audit_20260928.md`（差距 A1–A5）
- 结论：**R1–R6D 六项全部 DONE；审计 A 类 5 项差距逐项闭环；186/186 测试全绿；账本零偏差。** R6 执行与 R7（D01）等待 Owner 另行单独授权（两项请求见文末）。

## 1. 审计差距 → 闭环证据勾稽

| 审计差距 | 闭环任务 | 闭环证据 | 状态 |
| --- | --- | --- | --- |
| A1 全量库（9,453 观察）无 T12 备份、无恢复演练 | R1 | `evidence/t12_full_drill.json`：create_backup（dump sha 425b694a…，197 项资产清单）→ 恢复至演练库 → 10 表计数对账零偏差 → 扩展对账（sources 6 / ok 7,716 / unresolved 256 / confirmed 7,716 / candidate 256）→ digest 与迁移一致 → 恢复库 rebuild_consistency=true → RTO 1.999s ≪ 3600s → 演练库删除无残留 | ✅ |
| A2 申请草案 §3 第 6 条检索冒烟未执行；全量语料无冻结检索基线 | R2 | `fixtures/t11_golden_full.json`（20 条查询直接 SQL 独立标注，sha256 06fe38ca…）+ `evidence/t11_full_smoke.json`（20/20 集合等值；单调用 p95=0.2322s < 1s）+ `evidence/independent_review_r2.md`（独立复核者自写 SQL 全量重推 20/20 PASS）。**附带修复**：验证暴露 search.py 分页缺陷（payload 变体致同 identity 多行、ORDER BY 不确定 → 分页重复/遗漏），改为 DISTINCT ON (identity_key) 确定性单卡；试点 9/9 回归通过，回归测试固化 | ✅ |
| A3 not_seen 以 ≤500 行批次为基准，多批次源数字全为噪音 | R3 | `projection.not_seen_run_report`（run 粒度：仅 full_refresh/单输入源可作基准，增量显式排除；嫌疑分桶只认基准后 sighting）+ `evidence/r3_not_seen_run.json`（jisi_sou 187/98/89、jisi_dom 298/46/252、hirep 747/747/0、zhongke/yanqu/yinzhi 0）+ `evidence/independent_review_r3_r5.md`（两轮独立复核：首轮 PASS_WITH_NOTES，4 条 NOTE 全部采纳——split("\n") 防 U+2028、嫌疑分桶改基准后 sighting 使 hirep 强嫌疑 274→0 归真、baseline_staged_rows 口径、缺 unit_count 结构化报错——修复后复核 PASS，六源数字独立复算一致） | ✅ |
| A4 quality_commands.md（33 模块）与 README 未登记 full_migration.py；预留空表未声明 | R4 | `quality_commands.md`（37 模块 lint/format；用例 163→186；全量迁移/备份演练/全量 golden/运行粒度报告/质量队列命令行 + 回执列）+ `evidence/r4_command_receipts.log`（lint/format/typecheck 37 模块零违规；golden 重跑字节不变 IDENTICAL=true；只读抽查 zhongke/hirep/队列数字复现；专项测试 9+14 OK）+ README 增补全量迁移章节、**14 张**预留空表声明（实测精确清单，修正审计的 13 计数）、补全战役索引 | ✅ |
| A5 256 条 identity_status='candidate' 不进任何复核队列 | R5 | `quality_queue` 增 identity_candidate 类别 + `evidence/r5_quality_queue.json`（candidate_full_1 实跑 = 256 条，yanqu_ocr 192 + yinzhi_public 64，与审计精确一致）+ 4 项测试（surfacing/confirmed 排除/状态携带/既有类别不变）；复核同 R3 | ✅ |

R6D（切换申请草案）：`evidence/switch_application_draft.md` 成稿——对象（candidate_full_1 → 真实目标）、前置条件（R1 备份在场+账本零偏差+Owner 确认完成报告+目标侧只读预检）、冻结写入窗口五步、T12 回滚方案；显式声明"仅草案、不含任何执行动作、需 Owner 单独授权"。起草过程零写入。

## 2. 批次与纪律执行

- 批 0：task_state 登记 R1/R2/R3/R5/R4/R6D（依赖 R4←R1–R5、R6D←R1），钉 completion spec/plan sha256，status=IN_PROGRESS。
- 批 1（R1+R2）、批 2（R3+R5）、批 3（R4+R6D+本报告）按 Plan DAG 顺序完成；每批收口：全量测试零回归、ruff/format/pyright 涉改模块零违规、task_state 更新、账本登记并全量核验零偏差。
- 冻结纪律：试点 golden（t11_golden.json）、迁移报告（full_migration_report.json）、审计文件、R1 演练证据全程字节不变（账本逐批佐证；R2 生成器重跑 IDENTICAL=true）。
- 独立复核：R2（20/20 集合级）、R3/R5（两轮）均由未参与实现的独立 AI 复核者完成并落盘原文；无 WAITING_OWNER 遗留。
- 测试：186/186（163 基线 + R2 九项 + R3/R5 十四项）；三批收口时点分别 172/172、185/185、186/186 全绿。

## 3. 账本与状态终值

- `candidate_hashes.json`：133 项，全量核验零偏差（含本战役新增：全量 golden、两个生成/测试模块、六份证据文件、改动的 projection.py/search.py/task_state/quality_commands/README）。
- `task_state.json`：R1–R6D 全部 DONE；status=COMPLETION_DONE；waiting_owner=两项 Owner 请求（下节）。

## 4. 提请 Owner 的两项请求（不阻塞本轮完成判定）

1. **R6 执行授权**：请审阅 `evidence/switch_application_draft.md`；确认后另行对"启动切换"单独授权（切换执行将重跑窗口快照备份并按第 3 节步骤进行）。
2. **候选集群去留**：集群现含 candidate_corpus（试点）、candidate_full_1/2（全量）、t13_replay_1/2 与 t12 演留库（测试产物）。切换授权前建议保留 candidate_full_1/2 与备份；其余库去留请指示（涉及删除动作将另行逐项确认，不在默认授权内）。

## 5. 风险与后续

- search.py 分页修复改变了多 payload 记录的卡片取值（确定性最小元组胜出）；试点语料输出不变（9/9 回归），全量语料行为由冻结 golden 固化。
- hirep 基准为 0602 full_refresh（0703 new 运行无 full_refresh 路径标记，规格上不可作基准）——其 747 条"基准后 sighting"含 0703 new 新增，无强下架嫌疑；若 Owner 认为 0703 new 应视为全量刷新，可在 registry 路径或规格中显式归类，属一行口径变更。
- 审计 B 类口径（跨源身份合并、T11 显式未知等）与 C 类阶段推进（R6/R7）维持首期裁决不变。
