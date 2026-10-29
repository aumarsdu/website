# T01 GPT-6 Sol 外部复核 — 非阻塞备注处置记录（Writer）

- 日期：2026-09-26；处置者：Owner 授权的外围 Writer 会话（非 goal 侧对话）
- 复核来源：`evidence/independent_review_t01_gpt6sol_20260926.md`（第一轮，NEEDS_CHANGES）
  与 `evidence/independent_review_t01_rebind_gpt6sol_20260926.md`（聚焦重绑定核验，PASS，
  `rebind_confirmed=true`、blocking_issues 空）。两份报告由复核者（GPT-6 Sol via Codex CLI）
  独立写入，本文件只做处置登记，不改动复核结论。

## 阻断项闭环

第一轮唯一 blocking issue（pilot_manifest 冻结的 20 个 yanqu_ocr CSV 引用原路径
`盐趣/盐趣海报-2026年9月4日/海报文字识别_PP-OCRv6.csv` 不存在）已由第二轮聚焦复核
确认闭环：`source_registry.json` 的 rebound_to 指向逐字节相同副本（sha256 `0ff1a345…`
实测一致），保留交付 zip 亦可按字节复原原文件；冻结 manifest 未动（sha256 仍为
`1bbf64e9…`）。路径失效与 2026-09-26 授权的 scraper 工作区 Tier A 冗余清理相关，
已在 source_registry amendments 与两份复核报告中如实登记。

## 四条非阻塞备注的处置

1. **candidate_data/ 现有 17 个 T04 归属文件（旧"0 文件"快照不再适用）**
   处置：接受为 T04 完成后的预期进展。后续任何引用 T01 时代"candidate_data 为空"
   的证据必须重新生成对应时点快照，不得复用旧回执。
2. **target_guard 当前预检 owned=true / empty=false（与旧空目录回执不同）**
   处置：接受为当前真实状态。旧 `evidence/target_check.json` 是空目录时代的快照；
   现行预检以 `evidence/target_check_candidate_pg.json` 等最新回执为准。
3. **T03 账本记录未含 PHD/、data_staging/、docs/ 三路径入口检查备注**
   处置：本文件登记的同时，已在 task_state.json 的 T03 Evidence 追加一行显式备注：
   三路径不在 target_policy.json protected_roots 中，但 guard 强制 target 必须解析于
   side_root 内、构造上不可达；任何 T03 重新进入（如迁移重放）前仍须先补列再执行。
4. **baseline.json 中 tools/research_db_admin_server.py 哈希漂移（a6d44d67… → 953f349f…）**
   处置：漂移来自 Owner 授权的 scraper 工作区提交 `1316694d`（SQL 加固：LIKE 转义 +
   UUID 校验），独立于 goal、可归因、不涉及 T01 候选越界写入（第一轮复核已作同一
   归属判定）。baseline.json 是冻结的旧实现基线，**有意不重基**；本条记录即 drift 的
   权威解释。后续 T09+ 若以 baseline.json 做工具级对照，应以本备注为准。

## 账本与哈希

task_state.json 本次变更 = T01 Evidence 追加 3 行（两份复核报告 + 本处置文件）、
T03 Evidence 追加 1 行；candidate_hashes.json 已同步重算 task_state.json 项并登记
三份新证据文件；全账本（84+3 项）已逐项与磁盘实测核对一致（结果见执行记录）。
