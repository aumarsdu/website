# 科研项目数据库状态审计（2026-09-28，只读）

- 审计者：goal_20260908_side Writer 会话（全量迁移执行后）
- 性质：只读审计，无写入、无修复执行；本文件为审计结论与修复方案
- 范围：goal_20260908_side 账本、证据链、candidate_full_1/2 数据层、T10/T11 工具层、申请草案承诺 vs 实际执行

## 1. 合格面（已验证，零缺陷）

| 检查项 | 结果 |
| --- | --- |
| 账本 task_state.json | 13/13 DONE，D01 WAITING_OWNER，无待决 Owner 项 |
| 独立复核证据 | T01–T13 共 13 份 independent_review_*.md 齐全 |
| 测试/质量门 | 163/163 通过；full_migration.py ruff/format/pyright 零违规 |
| 哈希账本 | candidate_hashes.json 122/122 零偏差 |
| 行数守恒 | 收集 10,427 = 24 批回执行数合计 10,427；rejected=coerced=0 |
| 封存完整性 | 48/48 批次（两库各 24）verify_seal 事后验证全部通过 |
| 双库一致性 | digest 一致（e05ebc98…）且表级一致：source_records 7,972 / observations 9,453 / current ok 7,716 / unresolved 256 两库完全相同 |
| 身份层 | confirmed 7,716；candidate 256（yanqu 192 + yinzhi 64，与 accept_64 口径一致） |
| 顺序防护 | 未知顺序 256 条 current 指针标 unresolved，未静默推断下架（符合 T02 语义） |
| 观察不丢失 | 10,427 输入行 → 9,453 观察（多版本 payload 全保留）→ 7,972 身份（幂等去重仅在 identity_key 层） |
| 投影一致性 | rebuild_consistency 两库均 true |
| 检索性能（事后补测） | 全量语料 20/20 golden 查询零错误，p95=0.088s ≪ 1s 预算 |
| 授权链 | T13 GO → Owner 裁决（ratify/accept_64/accept_all）→ 申请草案确认（"确认，继续执行"）→ 执行，链路完整 |

## 2. 差距清单（未达"完美"的具体项）

### A 类：流程/覆盖缺口（可修，本地低危）

1. **T12 备份未覆盖全量库**。备份目录仅有 corpus-20260926（试点 150 条）。candidate_full_1/2（9,453 观察）无备份、无恢复演练；RTO 1.44s 证据只对试点规模有效。申请草案 §4 承诺的备份流程未在迁移后闭环。
2. **申请草案 §3 第 6 条"检索冒烟"迁移时未执行**。full_migration.py 不含 search 冒烟，迁移报告无该项。本审计事后补测性能合格，但属事后证据；且**全量语料的检索 golden 基线未冻结**——现有 fixtures/t11_golden.json 期望值是试点语料口径（20 条中 16 条与全量结果分歧，属规模差异而非缺陷），全量语料无冻结的正确性基线。
3. **not_seen 报告粒度失真**。以 ≤500 行批次为基准：zhongke 单次全量刷新拆 6 批，末批 not_seen=2,500/2,806 全为噪音；jisi_dom 末批 1,066 同理。下架检测在"采集运行（run）"粒度才有业务含义，当前无按 run 聚合口径。
4. **文档未更新**。quality_commands.md 模块清单（33 项）与 README.md 均未登记 full_migration.py（第 34 个模块）及全量迁移的运行方法/输出格式/验证口径，违反仓库自身文档要求（AGENTS §11、quality_commands 完成规则）。
5. **candidate 身份不进复核队列**。quality_queue 仅读 conflicts/quality_issues（均 0 行），256 条 identity_status='candidate' 无任何 surfaced 途径——标记存在但身份复核工作流无抓手。

### B 类：首期设计口径内的预留（已接受，二期范围）

6. 13 张模型表 0 行（provider_projects、offerings、asset_blobs/links/locations、extractions、field_evidence、identity_links、conflicts、conflict_members、input_files、legacy_id_map）：投影为虚拟计算（current 指针 + winner payload），素材/OCR 走文件化登记；与试点库行为一致（非迁移回归），但"预留无写入者"未在文档声明。
7. T13 GO 已接受的 P2 项：T11 显式未知未实现、evidence_location 批次级粒度、检索粒度=identity、素材字节以清单+不可变存储核验。
8. 跨源身份合并（identity_links）未实现——同一项目跨源在检索中为多条记录（per-source 命名空间）。

### C 类：需 Owner 另行授权的阶段推进（非缺陷）

9. 真实目标切换（第 2 步）：数据仍在隔离候选集群（legacy_bridge_status=no_legacy_replica_present）。
10. D01 公开发布（第 3 步）：WAITING_OWNER。
11. 候选集群运行中含 4 个库（candidate_corpus、pilot、candidate_full_1/2），停机/清理为 Owner 决策。

## 3. 修复方案

| 编号 | 修复内容 | 动作 | 风险 | 前置 |
| --- | --- | --- | --- | --- |
| R1 | 全量库 T12 备份+恢复演练 | 对 candidate_full_1 执行 create_backup → restore 到临时库 → 计数/摘要对账零偏差 → 写 evidence/t12_full_drill.json（含 RTO） | 低（只读源库+新建临时库） | 无 |
| R2 | 冻结全量检索 golden + 补迁移验证项 | 沿用 generate_t11_queries.py 独立标注流程，对全量语料重注 20 条期望 → fixtures/t11_golden_full.json（sha256 入账本）→ 检索冒烟结果补录迁移报告附录 | 低 | 无 |
| R3 | not_seen 增加 run 粒度 | manifest 增加 run 分组（按封存输入文件归组），not_seen_report 支持 run 基准；zhongke 类单次刷新源 run 基准预期 not_seen=0 | 低（新口径不改旧行为） | 无 |
| R4 | 文档补全 | quality_commands.md 补 full_migration.py 命令行；README 补全量迁移章节（对象/命令/输出/验证/回退）；账本重哈希 | 无 | 无 |
| R5 | candidate 身份入质量队列 | quality_queue 增加 kind='identity_candidate'（只读 source_records WHERE identity_status='candidate'），为身份复核提供抓手 | 低 | 无 |
| R6 | 第 2 步真实目标切换 | 沿用 T12 冻结写入+回退演练流程 | 高危 | **Owner 单独授权** |
| R7 | 第 3 步 D01 公开发布 | 独立立项 | 高危 | **Owner 单独授权** |

优先级：R1 > R2 > R4 > R3 > R5 >（R6/R7 待授权）。R1/R2 直接闭环申请草案已承诺但未执行的验证项。

## 4. 结论

候选库范围内技术验收完整、账实一致、数据零丢失——**没有发现任何数据级缺陷**。但距"完美"存在 5 项 A 类差距：其中 2 项为申请草案自身承诺未闭环（全量备份、检索冒烟 golden），3 项为工具/文档完善项。B 类为首期已接受口径，C 类为阶段推进。建议按 R1→R5 顺序补齐后再向 Owner 提请第 2 步切换授权。
