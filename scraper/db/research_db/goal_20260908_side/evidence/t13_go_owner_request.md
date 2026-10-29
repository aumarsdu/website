# T13 GO 条件裁决请求（提交 Owner）

- 提交：2026-09-27；提交者：goal_20260908_side Writer 会话
- 依据：T13 独立验收 `evidence/independent_review_t13.md`（repair_confirmed=true, go=GO, 附 4 条件）与剩余工作 Spec 第 5 节状态规则
- 状态：**首期 13/13 任务技术验收全部 DONE，但 GO 附带 3 项 Owner 决策未决 → 目标转入 WAITING_OWNER，不冒充完成**

## 决策 (a)：追认 G-R 独立复核

**请求**：追认本会话 12 份独立 AI 复核记录（`evidence/independent_review_t01.md` … `t12.md` + `t13.md` 验收）。

**事实与保留**：其中 `independent_review_t09.md`、`independent_review_t12.md` 为**事后补落盘**——复核结论当时产生于会话中（复核者对两项 blocking 的修复已给出 `repair_confirmed: true` 并独立实测），但记录文件于 2026-09-27 01:36 才按复核者处方写入。复核者声明："内容与既有证据交叉一致、技术断言经本人独立复核为真，但原始复核过程不可密码学复现"，故归入 Owner 追认条件。

**不追认后果**：T09/T12 的 DONE 依据降级 → 需 Owner 指定复核者重做幂等导入与备份恢复的独立复核（预计各一轮复核周期）；其余 11 项复核不受影响。

## 决策 (b)：yinzhi_public 64 条超限批次——接受或回退

**事实**：冻结试点清单 `pilot_manifest.json` 中 yinzhi max_candidates=10；原 Spec 每来源上限 50。实际封存批次（`candidate_data/pilot/yinzhi_public/sealed`）为 **64 条 = 32 个项目 × 中英双语**，系 T07 切分产出的完整入口清单（引知页面全部 32 个项目，无采样缩减）。已按"超限先报告"由 T13 复核者登记（GO 条件①）。

**选项 A（接受 64 条）**——建议选项。
- 理由：64 = 引知页面全部条目；中英成对切除任一语言将静默丢弃 32 份双语互链证据（违背"不得静默丢失"）；数据体积 ~340KB，远低于 2GiB。
- 影响：试点口径与数字上限的偏差成为既成事实，迁移申请中明示。

**选项 B（回退至 ≤50）**——若 Owner 选择此项，Writer 将执行以下已就绪预案：
1. `generate_t13_entries.py` 增加 50 条上限参数（保留 25 个项目的 zh+en 对；14 个无配对语言的落选条目记入 `excluded_pending_review`，不静默丢弃）；
2. 重新封存 `candidate_data/pilot/yinzhi_public/`；
3. 重新导入 `candidate_corpus` 并重跑 `e2e_replay.py` 双重放 → 更新 `evidence/t13_replay.json` digest；
4. 刷新 `candidate_hashes.json`、`t13_evidence.json` 并重请 T13 复核者确认缩减后状态。

## 决策 (c)：接受已登记 P2 项

| # | P2 项 | 影响 | 建议 |
| --- | --- | --- | --- |
| 1 | T11"显式包含未知"未实现（spec 为许可性"可"；未知从未计为匹配） | 无正确性影响；功能留待后续 | 接受 |
| 2 | evidence_location 为批次级粒度（`sealed:<batch_id>`），非行级 | 行级溯源需经 T06/T07 的块级证据 + 封存 batch.jsonl 对账 | 接受 |
| 3 | 检索粒度 = source-record identity（非 provider_project 卡片；期次数组未触发） | 同项目跨源出多卡，与 §3.1"未确认不自动融合"一致 | 接受 |
| 4 | 素材字节不复制进备份，以 sha256+byte_size 清单 + 不可变素材存储核验（缺失/损坏可检出） | 若素材存储本体受损则清单无法恢复内容；如需字节级备份另行复制 | 接受 |

**不接受后果**：对应项转入质量队列或后续任务清单，GO 撤回为 NO-GO 直至处置完毕。

## 附注

- GO 语义：仅指允许向 Owner 提出全量候选迁移申请；全量迁移、真实目标切换、公开发布均需另行授权（D01 另列）。
- 备份/恢复预案（决策 b 选 B 时）：回退后 `evidence/t13_replay.json`、`t13_evidence.json`、`candidate_hashes.json` 三处哈希同步重算，T13 复核者复验。

## Owner 裁决回执格式

```json
{"decision_a": "ratify"|"re-review", "decision_b": "accept_64"|"reduce_50", "decision_c": "accept_all"|"reject:[...]", "note": "…"}
```
