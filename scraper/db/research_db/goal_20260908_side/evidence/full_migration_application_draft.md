# 全量候选迁移申请（草案，待 Owner 确认后执行）

- 起草：2026-09-27；起草者：goal_20260908_side Writer 会话
- 依据：T13 独立验收 GO（`evidence/independent_review_t13.md`）+ Owner 裁决回执（`evidence/t13_owner_adjudication.md`，ratify/accept_64/accept_all）
- 性质：**本文件为申请草案。迁移执行需 Owner 确认本申请并另行单独授权；本草案不含任何执行动作。**

## 1. 具体对象（源与条数）

以 `source_registry.json`（2026-09-25 版 + amendments）登记的全部主事实输入为准，五源全量：

| 源 | 登记输入文件 | 全量行数（已核验 unit_count） |
| --- | --- | --- |
| jisi_future_sou_tools | 6 个 JSONL（20260602→20260902 六次运行） | 1,344 |
| jisi_future_domestic | 4 个 JSONL（20260602/0703/0724/0902） | 2,276 |
| zhongke | 1 个 JSONL（20260902 全量刷新） | 2,806 |
| hirep | 5 个 JSONL（20260602/0703/0724/0811/0902） | 3,742 |
| yanqu_ocr | 海报文字识别 CSV（盐趣7-9月项目合集，195 行 ok） | 195 |
| yinzhi_public | content.md 公开归档（T07 切分） | 64 条目（32 项目×中英） |
| **合计** | | **≈ 10,427** |

素材：盐趣原图 20 张已登记（T05），全量迁移阶段素材清单按 T12 备份中的 197 项资产清单口径核验。

## 2. 范围上限

- 单批次 ≤ 500 行（T09 importer 既有上限）；全量按源拆分为多批次顺序导入。
- 素材 ≤ 300 项 / 2 GiB（沿用试点上限；本次迁移不含素材字节复制，仅清单核验——Owner 已 accept 口径）。
- yinzhi 64 条口径（GO 条件①，Owner accept_64）：32 项目 × 中英双语，全量即全量，无缩减；迁移申请与回执中均按此明示。

## 3. 验证方案（对账口径沿用已验证机制）

1. **封存**：全量批次经 T08 `stage_validator.py` 逐批校验并原子封存（seal.json 含 batch/manifest/row 哈希），任何校验后变更使资格失效。
2. **导入**：T09 `importer.py` 幂等导入——before/after 已提交计数差值回执；同批重放零增量；batch_id 重用拒绝（identity_conflict）；advisory lock 串行。
3. **对账**：批次回执行数 = 封存行数 = 导入观察数；源行数守恒（accepted+duplicate+quarantined+rejected = rows_read）；不删不覆盖。
4. **投影一致性**：T10 `rebuild_consistency` 重算全部 current 指针 == 在线指针（零 mismatch）。
5. **端到端双重放**：全量语料库两库独立重放，规范摘要一致（沿用 T13 e2e_replay 流程，规模扩至全量）。
6. **检索冒烟**：T11 search 在全量语料上跑 20 条冻结 golden（p95 预算 1s，实测余量大）。

## 4. 回退方案（沿用 T12 已验证流程）

- 迁移前对目标候选库执行 T12 `create_backup`（pg_dump + 计数 + 197 项资产清单 + 配置哈希，实测 RTO 1.44s）。
- 任一批次失败：单事务回滚，批前备份可整库恢复（`restore_backup`，对账零偏差实测）；切换失败走 `switch_drill` 已验证的失败回退路径。
- 回退不删数据目录；恢复后重跑对账确认零偏差方可视为回退完成。

## 5. 授权边界（重申）

- 本申请经 Owner 确认后，方启动迁移执行；执行本身还需 Owner 对"启动迁移"的单独授权确认。
- 真实目标切换、公开发布（D01）不在本申请范围，分别单独立项。
