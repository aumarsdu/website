# T09 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-26；对象：importer.py、test_importer.py（12 项真实 PG 用例）。
- 复核者声明：全部结论来自其本机独立运行与读取（自建 23 个临时库、4 线程并发、pg_terminate_backend 中断、注入探测）。

## 首轮逐项结论（复核者原文摘录）

- **A. 全套复跑 — PASS**：137/137 OK（importer 12 项，真实 PG 16.15，server_version_num 160015）。
- **B. 幂等/重放 — PASS**：二次导入 inserted=0/unchanged=2，11 张表计数逐一不变；同 batch_id 仅改 digest 与改行内容两种复用均 identity_conflict 且零写入。
- **C. 排列/冲突/回退 — PASS**：六库六顺序终态一致；同序不同 payload → conflicts 行 + current status=conflict + 指针 payload 不变（复核者自行加断言）；旧批次后到指针保持且不清除既有 conflict。
- **D. 事务/恢复 — PASS（列表项）+ 一项阻断发现**：篡改/超限零写入；kill 导入连接 → transaction_failed + 服务器回滚零写入 + 重导一致；提交后 kill → commit_unknown + 重查 + 幂等重试；pg_terminate_backend 幽灵行消失；4 线程 advisory lock 同批全部 committed、计数不重复。**阻断：输家回执虚报 inserted——before 快照在 advisory lock 等待之前读取，4 线程 inserted 合计 20 ≠ 实际 5，违反 §3.4"不能把尝试行数当 inserted"；修法为锁后取快照。**
- **E. 质量 — PASS**：计数来自已提交差值；ON CONFLICT 全部定向；importer 零引用 manual_overrides；无吞异常；注入探测被 dollar-quoting 挡下；ruff/format/pyright 零违规。
- **F. 范围 — PASS（边界）**：current 指针更新属 T09 契约（复用 T02 冻结 resolve_projection）；无 T10 投影重建；无旧端点/旧工具引用。**台账发现：stage_validator.py（T08 交付物）在 T09 窗口被改而 candidate_hashes.json 未刷新（G-E）。**

## 首轮总结论（复核者原文）

```json
{"verdict": "NEEDS_CHANGES", "blocking_issues": ["D4回执失真：并发同批等待方inserted虚报（before快照先于advisory lock读取，4线程inserted合计20 vs 实际5），违反§3.4'不能把尝试行数当inserted'，修法为锁后取快照", "G-E台账：stage_validator.py在T09窗口被无归属改动且candidate_hashes.json过期（0f66ac5b…≠25bd67f5…），需补归属说明或回退并重登记哈希"], "non_blocking_notes": ["identity_conflict以transaction_failed前缀+截断尾部文本识别，建议事务外预检或结构化分类", "伪造 seal（跨源 identity_key）会静默丢行且回执伪造 unchanged=1（真实 T08 校验器不可能产出，属防御纵深）", "batch_id 含 '$batch$' tag 时语法错误安全失败（零写入、库可用）", "指针更新阶段（COMMIT 后）无结构化失败回执", "t09_evidence.json 的 full_suite:125 与实际 137 不符", "advisory lock 无显式超时；hashtext 32 位键碰撞仅致额外串行化", "importer 层无 FK 用例（结构上不可触发，schema 级已由 T03 迁移测试覆盖）", "evidence_location 为批次级（候选已自报为已知限制）"]}
```

## 修复记录（Writer）

1. before 计数 SELECT 移入事务内、紧随 advisory lock（psql stdout 首个非空行解析）；并发测试强化为逐回执 inserted+unchanged==rows_read 且两线程 sum(inserted)==行数。
2. stage_validator.py 的 context_key 扩展归属说明登记（本 T09 Writer 所为，行级提供、默认 default，T08 全部 fixture/测试不变且通过）；candidate_hashes.json 重登记（91 项零偏差）。
3. 非阻塞处置：identity_conflict 事务前结构化预检（_batch_digest_mismatch）；伪造跨源 seal 行 → seal_invalid；指针更新失败产生结构化 error（commit_unknown 由重导治愈）；t09_evidence full_suite 更正 137。

## 复核确认

复核者最终确认（2026-09-26，原文）：

```json
{"repair_confirmed": true, "note": "两项 blocking 均独立复核通过：FIX1 自跑 4 线程同批重放 per-receipt inserted=[0,0,0,5]、sum(inserted)=5=行数、inserted+unchanged==rows_read 逐份成立（另加 3 轮 7 行×4 线程抗竞态均通过；stdout 确认为空行+'0|0|0|0' 计数行，void lock 解析正确），全套 137/137 OK；FIX2 candidate_hashes.json 91/91 逐项重算零偏差（stage_validator.py 已登记当前哈希 25bd67f5…），review_dispositions 已登记 context_key 扩展归属，T08 冻结 fixture b564da78 未动。非阻塞处置亦验证：identity_conflict 事务前结构化预检、伪造跨源 seal → seal_invalid 零写入、指针失败结构化字段且重导治愈、中断两路径均正常。唯一遗留（非语义）：importer.py before_line 解析一行 ruff format 重排，已由 Writer 执行。"}
```

**T09 状态：DONE（功能/测试/质量/交付/独立复核全部有当前版本证据）。**
