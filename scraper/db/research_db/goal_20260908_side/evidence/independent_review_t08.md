# T08 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-25；对象：stage_validator.py、generate_t08_fixtures.py + fixtures/t08*（冻结期望 sha256 `b564da78…`）、test_stage_validator.py。
- 复核者声明：全部结论来自其本机独立运行命令与抽查文件（含 CLI 复跑负例、独立手判 case_ok 分类、独立验证 verify_seal 的 manifest 篡改检出）。

## 首轮逐项结论（复核者原文摘录）

- **A. 冻结独立性 — PASS**：expected 文件 birth 早于校验器；冻结哈希与 evidence 登记一致；期望值具体；复核者按 §3.4 口径对 5 行原始数据逐行手判，与冻结期望完全一致。
- **B. 反例覆盖 — PASS**：10 类反例逐一指认齐全；复核者补测了单元测试未覆盖的 manifest 单独篡改场景（verify_seal 同样判 input_changed）。
- **C. 复跑 — PASS**：76/76 OK（当时）；CLI 输出仅 verdict 计数无原始行内容；封存输出无 url/internal_note/crawled_at 字段；seal.json 无时间戳、字节级确定。
- **D. 语义正确性 — PASS**：四类互斥单分支计数+终局对账双保险；清洗为白名单制；verify_seal 三方比对（manifest_digest+输入哈希+batch 哈希）非桩实现。
- **E. 质量/范围 — PASS**：ruff/format/pyright 复跑通过；无原始行/大 SQL 输出；未越权 T04/T09。

## 首轮总结论（复核者原文）

```json
{"verdict": "PASS", "blocking_issues": [], "non_blocking_notes": ["冻结时序：expected.json 实现后被重生成（mtime 07:45:52>校验器 birth 07:45:09），生成器与 fixtures 晚于校验器诞生，冻结主张靠 birth+sha+独立手判闭环", "错误名 observation_record_unknown/observation_payload_unknown 与 §3.4 reference_missing 命名不一致（语义等价）", "order_key 保留 crawled_at 值（字段名已清洗），scrub 测试只断言字段名", "未做 §3.2 路径穿越/越界 symlink 校验（不在 T08 必测清单）", "pyrightconfig include/quality_commands.md/candidate_hashes.json 未纳入 T08 新模块，quality_commands.md 仍写 64 项", "--dry-run 必填但非只读，总是封存", "观察文件仅负例，无合法观察正例对照"]}
```

## 非阻塞备注处置（Writer，复核后全部落实）

1. 冻结时序：原因系 case_bad_json fixture 修复触发重生成，期望文件内容哈希跨重生成不变（b564da78…）；处置记录写入 evidence/t08_staging_evidence.json；后续冻结产物不再原地重写。
2. 错误命名：保留冻结期望中的名称；§3.4 reference_missing 的映射在 T09 导入层落实。
3. order_key 值保留为设计语义（§3.3 最近观察）；已在处置中记录。
4. 路径穿越/越界 symlink：`_input_path` 已实现拒绝（abs/../symlink → contract_invalid），新增 `test_traversal_and_symlink_inputs_rejected`。
5. 配置/账本：pyrightconfig、quality_commands（79 项）、candidate_hashes 均已纳入 T08 模块。
6. `--dry-run` 重构为真只读（validate_only，不建目标），封存改由 `--seal --target` 承担；新增 `test_dry_run_creates_no_target`。
7. 新增 `test_valid_observations_pass` 正例对照（从 case_ok 派生，未触碰冻结 fixture）。

处置后：79/79 通过；ruff/format/pyright 全绿。备注均为非阻塞，PASS 结论不受影响。
