# 候选集群库去留处置（2026-09-28，Owner 决定框架 + Writer 建议方案）

- 依据：Owner 2026-09-28 去留指令（五项决定框架）；行数均取自账本核验过的证据文件（集群现处 stopped，本文件生成过程未连接、未启动任何集群）
- 协议：被指示删除的库在执行前逐项列库名与行数由 Owner 最终确认；删除后留集群库清单佐证并落账；candidate_data/ 下备份与封存批次不在处置范围，全部保留

## 1. 逐项状态与建议

| # | 库 | 行数（账本证据） | Owner 框架 | Writer 建议 | 当前动作 |
| --- | --- | --- | --- | --- | --- |
| 1 | candidate_full_1 | source_records 7,972 / observations 9,453 / payloads 5,181 / batches 24（t12_full_drill.json） | 保留至 R6 完成验收（已定） | — | 保留 |
| 2 | candidate_full_2 | 与 full_1 完全一致（双重放 identical=true，full_migration_report.json） | 验收后删除／永久保留〈二选一〉 | **验收后删除**：digest 一致性已永久记录于账本与迁移报告，留一份源库（full_1）+ 全量备份足以支撑回溯 | 无（两选项均保留至 R6 验收后） |
| 3 | candidate_corpus | 150 / 150 / bodies 148（试点） | 保留／删除〈二选一〉 | **保留**：试点 frozen golden（fixtures/t11_golden.json）的回归测试绑定此库（test_search 9 项）；删除将使基线测试跳转 SKIP，冻结证据链少一个可复核实物 | 无 |
| 4 | t13_replay_1 / t13_replay_2 | 各 observations 234 / current 234 / bodies 232 / batches 6（t13_replay.json） | 删除／保留〈二选一，Owner 倾向删除〉 | **删除**：T13 双重放属验收过程产物，结论已固化于证据；测试套件未来运行会按需重建同名库，删除可重复执行 | **待 Owner 最终确认后执行** |
| 4b | t12_test_post_backup_rows_not_counted_as_snapshot_loss_restored | 测试夹具级（test_backup_restore 产物；精确行数待集群在线后枚举） | 同上（t12_test_* 通配） | **删除**：同 4 | **待 Owner 最终确认后执行** |
| 5 | 集群状态 | — | 继续运行／停止〈二选一〉 | **维持 stopped**（现状即停止态，零动作零风险）；R6-A/B 执行前由 Writer 按窗口顺序重启（runbook §1.1），或 Owner 亲自重启均可 | 无 |

## 2. 待 Owner 最终确认的删除清单（确认前不执行）

1. `t13_replay_1`（observations 234）
2. `t13_replay_2`（observations 234）
3. `t12_test_post_backup_rows_not_counted_as_snapshot_loss_restored`（行数待枚举：需集群在线，枚举动作本身将在你确认后与删除同窗口执行）

确认后执行顺序：集群在线（或确认时说明由谁启动）→ 逐项枚举行数 → 逐项 drop database → 全集群库清单留证 → 落账（task_state + candidate_hashes）。

## 3. 知会事项

- 测试套件每次运行会重建 `t12_test_*`（test_backup_restore）与 `t13_replay_1/2`（若 e2e 重跑）同名库——删除是可重复的清理动作，非一次性永久状态，后续测试运行后可再次清理。
- `postgres` 系统库不在处置范围。
- R6-A/B 仍缺的三项输入（端点、窗口、读路径配置点）与本处置互不阻塞；集群重启时点按 runbook §1。
