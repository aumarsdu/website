# T10 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-26；对象：projection.py、migrations/0003_content_payload_bodies.sql、test_projection.py、importer.py（bodies 写入扩展）。
- 复核者声明：自建 t10_review_* 临时库独立构造混合历史与反例；全套测试与质量命令独立复跑；临时库已 drop。

## 首轮逐项结论（复核者原文摘录）

- **A. 全套复跑 — PASS**：144/144（当时）。
- **B. DoD 语义 — PASS**：来源与人工值并列、撤销恢复+审计保留、同序冲突 conflict、未知顺序 unresolved 不假装确定、两期次独立、跨来源同 ID 不串——全部独立复现。
- **C. rebuild 一致性 — FAIL**：混合历史 consistent 且篡改 status 被检出，但 (1) 指针漂移指向旧观察（status 仍 ok）时报 consistent=true（只比 status）；(2) 仅未知顺序观察的记录 absent≠unresolved 误报。
- **D. 边界 — PASS**：0003 仅加表；importer 写 bodies 幂等；认证/审计如实记录未虚标。
- **E. 质量/范围 — PASS**：ruff/format/pyright 零违规；未越权 T11；旧库未触碰。

## 首轮总结论（复核者原文）

```json
{"verdict": "NEEDS_CHANGES", "blocking_issues": [
  "rebuild_consistency 对仅含未知顺序观察的记录误报 mismatch（importer 在线语义=无 current 行，rebuild 重算=unresolved，absent≠unresolved）",
  "rebuild_consistency 仅比对 status，不比对 source_record_current 的观察指针/载荷：指针漂移指向旧观察且 status 不变时报 consistent=true",
  "G-E 交付缺口：candidate_hashes.json 未随 T10 刷新"
], "non_blocking_notes": ["test_two_offerings_distinct 为 schema 级直插/直查", "apply_override 仅对 source_record 校验实体存在性", "project_record 的 shown_value/active_manual_value 仅合成 title 字段", "T10 功能全集中 not_seen 与质量队列尚未实现（不得据此标 DONE）"]}
```

## 修复记录（Writer，按评审意见逐项）

1. **unknown-order 误报**：importer 为全 NULL order_key 身份写入显式 `unresolved` current 行；rebuild 将 absent≡unresolved 视为一致；新增测试。
2. **指针漂移**：rebuild_consistency 比较 status 与 winner payload hash（pointer_drift kind）；漂移可检出、重放可治愈；新增测试。
3. **台账**：candidate_hashes.json 加入全部 T10 文件并重算陈旧项（96→97 项零偏差）。
4. **not_seen/质量队列**：not_seen_report（仅接受 complete 快照，缺席记录写 P2 去重 issue，观察与指针保留）与 quality_queue（conflicts + open issues）实现并测试。
5. apply_override 校验 provider_project/offering 实体存在性；project_record 仅渲染 title 的限制已记录。

修复后：149/149 通过；ruff/format/pyright 全绿。复核确认见文末。

## 复核确认

复核者对修复的最终确认（2026-09-26，原文）：三项 blocking 独立复核全部修复——149/149 独立复跑 OK；混合历史+覆盖+撤销 consistent；仅未知顺序记录现写显式 unresolved current 行且 rebuild 不再误报（absent≡unresolved）；指针漂移（status 不变）被检出 kind=pointer_drift 且重放治愈后 consistent=true；candidate_hashes.json 实测 96 项零偏差；not_seen 恰标 1 条且去重（1→1）、P2 open、观察与指针保留，partial 批次抛 not_a_complete_snapshot；quality_queue 列出 conflict+not_seen；apply_override 对 offering/provider_project 校验 reference_missing 且合法覆盖可用；跨来源同 ID 与 bodies 幂等无回归。唯一遗留（非语义）：修复新引入 G-Q 违规——ruff 格式机械修复。

```json
{"repair_confirmed": true, "note": "三项 blocking 独立复核全部修复（unresolved current 行、pointer_drift 检出、台账 96 项零偏差）；not_seen 与 quality_queue 新功能验证通过；G-Q 格式遗留已由 Writer 机械修复"}
```

**T10 状态：DONE（功能/测试/质量/交付/独立复核全部有当前版本证据；not_seen 与质量队列已实现）。**
