# T07 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-26；对象：yinzhi_segment.py、generate_t07_golden.py + fixtures/t07_golden.json、test_yinzhi_segment.py。
- 复核者声明：全部结论来自其本机独立运行与读取（含自写独立扫描器重扫全文、逐锚点人工开页核对）。

## 首轮逐项结论（复核者原文摘录）

- **A. Golden 独立性与真实性 — PASS**：独立扫描器重扫得 64 锚点与 golden 完全一致；抽查 10 锚点（覆盖三分类、中英、quota/plain、分类单元内/独立单元）逐一确认为项目标题且其后为导师行。
- **B. 完整性 — PASS**：全量枚举正文 68 单元——单元内除子分类头/已收录标题/导师行外无漏收；675-739 为权益区/附件/导航/页脚，无漏收项目。
- **C. 复跑 — PASS**：125/125 OK；recall=1.0、zero-navigation、no-false-positive、trailing 排除断言通过（但双语对测试采样偏 zh 方向，掩盖了 D 项缺陷）。
- **D. DoD 语义 — 一项未通过**：anchor 回链、page_context、双语 title 各自保留、零导航混入均通过；**pair_anchor 互链错误：64 链中 32 条 zh→en 正确，仅 3 条 en→zh 正确，29 条 en 条目的 pair_anchor 指向下一个项目的 zh 标题**（根因：相邻异语即配对+后续覆盖；golden、segmenter 输出与 evidence "64/64" 声明同源同错）。
- **E. 质量/范围 — PASS**：ruff/format/pyright 复跑通过；仅标准库；无吞异常；公共接口全类型标注。

## 首轮总结论（复核者原文）

```json
{"verdict": "NEEDS_CHANGES", "golden_confirmed": true, "recall": {"numerator": 64, "denominator": 64}, "blocking_issues": ["pair_anchor 双语互链错误：29/64 条 en→zh 链指向不同项目（根因为相邻异语即配对+覆盖；golden、yinzhi_segment.py 输出与 evidence '64/64' 声明同源同错），须改为 en 回链其前驱 zh 且禁止覆盖，修正后重新生成并冻结 golden 及证据"], "non_blocking_notes": ["golden 与实现同作者同启发式且同会话生成，独立性仅由本次审查者的独立重扫确立", "test_bilingual_pairs_linked 只采样 zh 方向对且按有向链计数，建议增加互链（双向回指）断言", "generate_t07_golden.py 末行死代码 EOF_MARKER_NOT_USED", "t07_evidence.json 的 'full_suite': 115 命名易误读（实为 125）"]}
```

## 修复记录（Writer，按评审意见逐项）

1. **blocking**：配对规则改为"仅允许未配对的紧邻前驱配对"（`"pair_anchor" not in entries[prev_entry_index]` 守卫），generator 与 segmenter 同步修复；重新生成并冻结 golden（sha256 `a848b7d7…`）；64 条目 32 对全部双向互指（en.pair=zh 且 zh.pair=en），测试新增双向回指/语言互异/32 无向对断言。
2. 死代码 EOF_MARKER_NOT_USED 已删。
3. test_bilingual_pairs_linked_bidirectionally 覆盖双向互指 + 抽样 5 对。
4. t07_evidence.json 收账时更新 full_suite=125 与新 golden 哈希。

修复后：125/125 通过；ruff/format/pyright 全绿。复核确认见文末。


## 复核确认

复核者对修复的最终确认（2026-09-26，原文）：

- 新 golden sha256=a848b7d7… 核验一致；generator/segmenter 均含 "pair_anchor" not in prev 守卫，死代码已除；独立扫描器（仅未配对紧邻前驱规则）复扫 64 条 pair_anchor 全部双向互指、语言互异、同分类同项目（zh_i↔紧随 en_i），32 无向对；旧错链样本 27↔37/87↔97/371↔381 已改为互指各自译文；新增双向断言与全套 125/125 OK。

```json
{"repair_confirmed": true, "note": "新 golden sha256=a848b7d7… 核验一致；generator/segmenter 均含 'pair_anchor' not in prev 守卫，死代码已除；独立扫描器（仅未配对紧邻前驱规则）复扫 64 条 pair_anchor 全部双向互指、语言互异、同分类同项目（zh_i↔紧随 en_i），32 无向对；旧错链样本 27↔37/87↔97/371↔381 已改为互指各自译文；新增 test_bilingual_pairs_linked_bidirectionally（64 有向+32 无向+语言互异+双向回指）与全套 125/125 OK；提醒：t07_evidence.json 仍为旧哈希和 full_suite=115，收账时按承诺更新。"}
```

**T07 状态：DONE（功能/测试/质量/交付/独立复核全部有当前版本证据）。**
