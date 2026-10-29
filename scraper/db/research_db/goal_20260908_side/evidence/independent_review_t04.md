# T04 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-25；对象：adapters.py、fixtures/t04（冻结样本与期望 sha256 `940e7305…`）、test_adapters.py、run_t04_pilot.py、candidate_data/pilot/。
- 复核者声明：全部结论来自其本机独立运行命令与读取文件（含独立重抽样本脚本、原始行人工语义核对、verify_seal 独立复核四份封存）。

## 首轮逐项结论（复核者原文摘录）

- **A. 样本冻结与真实性 — PASS**：独立脚本按声明位置从四个注册源重抽 40 行与 samples.jsonl 逐字节一致；expected sha256 与登记一致；birth fixtures(08:03:37) < adapters.py(08:04:46)；生成器不 import adapters，期望独立产出。
- **B. 映射语义抽查 — PASS**：逐行人工核对源样本，jisi/zhongke/hirep 映射字段均真实存在且语义对应；jisi 样本 0 导师/学校 None 被正确标 not_provided 未编造；zhongke 身份决议有全量依据（2806/2806 行 id 有值、0 行 uuid 有值），已记入 contract_config identity_resolution。
- **C. 复跑 — PASS**：91/91 OK；test_frozen_expectations_matched_item_by_item 逐条比对 native_id、field_states、order_key 及 value 态业务字段值。
- **D. DoD 语义 — PASS**：namespace 分离、同入口两批次单身份可追溯、乱序不变、counts 和=rows_in、缺字段不编造、同名导师不合并、未知字段不影响 payload、无 id 行计入 unmapped——九个专项测试通过。
- **E. 试点与隔离 — PASS**：只读源文件、仅写 candidate_data/pilot/（限额 25/25/50/50，209KiB ≪ 2GiB）；四份 seal counts 与 staging 行数一致，verify_seal 独立复核全部匹配；target_guard owned:true。
- **F. 质量/范围 — PASS**：ruff/format/pyright 复跑零违规；无 SQL/psycopg/sqlite/DB 连接（走 T08 封存路径）；公共逻辑与每源配置数据分离；公开接口有类型与 AdapterError。

## 总结论（复核者原文）

```json
{"verdict": "PASS", "blocking_issues": [], "non_blocking_notes": ["fixtures 最终 mtime 晚于 adapters.py 最后编辑，'期望先于实现'仅由 birth 时间和相同 sha256 证明（重生成内容逐字节未变）", "generate_t04_samples.py 的 ADAPTER_CONFIG 是 adapters.py 的文本副本（设计如此，靠 test_config_matches_frozen 锁定实现）", "test_disorder_invariant 只比 identity_key 集合与 rows_in（payload 级乱序不变已由 T02 覆盖）", "quality_commands.md 命令表未纳入四个 T04 文件", "t04_evidence.json bytes_total 与 target_guard 文件字节数口径不同（均远低于 2GiB）", "run_t04_pilot.py 另写 evidence/t04_pilot.json 属任务自有交付物，非越界"]}
```

## 非阻塞备注处置（Writer）

1. 双份 ADAPTER_CONFIG 文本副本以 test_config_matches_frozen 锁定；语义正确性已由复核者人工核对原始行缓解。
2. quality_commands.md lint/format/typecheck 行已更新为 17 模块并复跑通过；测试计数 79→91。
3. 其余备注（birth+sha 冻结证明、payload 级乱序由 T02 覆盖、字节数口径、evidence 写入归属）记录在案，无需代码变更。

处置后：91/91 通过；ruff/format/pyright 全绿。PASS 结论不受影响。
