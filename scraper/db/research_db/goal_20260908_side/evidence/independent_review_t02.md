# T02 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-25；对象：contract.py + golden/t02_expectations.json（sha256 `db3c1bfa…`）+ contract_config.json + test_contract.py + contract.md。
- 复核者声明：所有结论来自其本机独立运行命令与抽查文件，未采信候选自身声明。

## 逐项结论（复核者原文摘录）

- **A. Golden 独立性 — PASS**：golden birth(06:53:19) 早于 contract.py birth(06:55:51)，mtime==birth 未改动；在 /tmp 重跑 generate_golden.py 产出与冻结文件逐字节相同；11 个 case 全部有具体期望值；算法块逐条对应 Spec §3.2/§3.3。
- **B. 实现一致性 — PASS**：52/52 用例通过；复核者另写独立脚本（不 import contract.py）按 golden 算法块重算 46 项期望值，全部与 golden 一致。
- **C. 反例覆盖 — PASS**：对照 Spec T02 测试清单逐项指认到具体测试函数（A→B→A、六排列、同序冲突、分隔符 ID、0/001、Unicode、字段四态、hash_version 升级、观察键上下文、manifest 三反例、新 adapter、unknown-only），无缺项。
- **D. 来源配置边界 — PASS**：yanqu/yinzhi 候选身份不固化；集思两入口 namespace 独立；无标题/路径派生身份；白名单并集无采集时间/路径/日志字段（程序化核验）。
- **E. 质量/交付 — PASS**：ruff/format/pyright 复跑通过；contract.md 有版本化与兼容策略；无吞异常、无秘密、公共接口全类型标注。
- **F. 范围 — PASS**：无 SQL/无库连接/无 T03 产物；candidate_data 为空。

## 总结论（复核者原文）

```json
{"verdict": "PASS", "blocking_issues": [], "non_blocking_notes": ["contract.md 'no-fallback => unresolved' wording diverges from code (returns status=conflict, payload=None) in an untested edge; align doc and add a case", "order_key comparability semantics (lexicographic str max) unpinned; must be fixed before T09/T10 consume it", "decimal fixed-point amounts and date precision/timezone from Spec 3.3 not modeled in contract layer; deferred to T04/T06 whitelist freeze and must bump hash_version then", "validate_manifest is shape-level only (no input_files subfields or capture_mode/coverage enums); state this limit in contract.md", "evidence/t02_golden_freeze.json written post-implementation; freeze rests on birth/mtime order + hash match, which hold"]}
```

## 非阻塞备注处置（Writer，复核后）

1. contract.md §2 措辞已对齐代码：无可回退时 `payload=null` 且状态保持 `conflict`；新增 `test_top_conflict_falls_back_to_last_verified` 与 `test_top_conflict_without_fallback_stays_conflict` 两个边界用例。
2. order_key 类型约定已钉入 contract.md §2：ISO-8601 UTC 字符串，字典序即时间序，T09/T10 前不得更改。
3. 金额/日期表达推迟与 hash_version 升级要求已写入 contract.md §5。
4. validate_manifest 形状级限度与 T08 分工已写入 contract.md §5。
5. golden 冻结证据依赖 birth/mtime 顺序 + 哈希一致（复核者已确认成立）；t02_golden_freeze.json 的角色为声明性记录。

处置后重跑：54/54 通过，lint/format/pyright 全绿。备注均为非阻塞，不影响 PASS 结论。
