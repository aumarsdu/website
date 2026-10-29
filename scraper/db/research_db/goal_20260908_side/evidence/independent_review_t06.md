# T06 独立复核结论（G-R，含 golden 图像核对）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-25；对象：ocr_extract.py、test_ocr_extract.py、evidence/t06_extractions.json、pilot_manifest.json 20 个冻结海报候选。
- 复核者声明：全部结论来自其本机独立运行与读取（含用 Read 直接打开 6 张原始海报 PNG 的视觉核对、polygon 裁剪放大目录海报表格区、程序化核查全部字段证据）。

## 首轮逐项结论（复核者原文摘录）

- **单元测试 — PASS**：114/114（ocr 10 项含 20 张真实海报覆盖与登记哈希断言）。
- **视觉核对（核心）— PASS**：row 1/82/143/195 打开原图，底部开课日期与提取值逐项一致（2026-07-25/08-15/08-05/10-10），导师（F.B./P.T./A.A./G.G.）与院校可见，全图无价格 → price=not_provided 属实；row 41/103 目录式长图确认无导师姓名、无价格，但表格区存在 MM/DD 斜杠日期。
- **存在性 golden 与召回 — PASS（≥90%）**：严口径 36/38=94.7%（row 41/103 的 MM/DD 目录日期计为存在）；宽口径 36/36=100%；无法判断项 2。
- **证据完整性 — PASS**：36 value + 20 pending 每条 evidence 含 block_index+confidence+text，24 not_provided 无伪证据，0 违规；value 态全部 ≥0.99 且无冲突；pending 正确覆盖低置信（最低 0.676）。
- **质量命令 — PASS**：ruff/format/pyright 复跑全绿。
- **范围与改绑 — PASS**：20/20 原图哈希一致；集合副本 CSV=0ff1a345… 与登记一致；外部重组事件属实，amendments[0] 如实；未写主库、无 T07 产物。

## 首轮总结论（复核者原文）

```json
{"verdict": "PASS", "golden_confirmed": true, "recall": {"numerator": 36, "denominator": 38, "undetermined": 2}, "blocking_issues": [], "non_blocking_notes": ["row 41/103 目录海报的 MM/DD 斜杠日期未被 DATE_NO_YEAR 覆盖…建议后续为目录式海报增加 MM/DD 缺年模式或在切分阶段显式隔离", "title 候选混入顶部口号/领域标签行…人工复核时可裁剪", "字段状态词表…pending_review 承担 T06 复核队列语义，终态由 T03 schema 约束，不阻塞", "test 中 block_index<500 为宽松界"]}
```

## 建议采纳（Writer，复核后）

1. **MM/DD 缺年模式已加入** DATE_NO_YEAR（斜杠式 → pending_review + missing_year），row 41/103 现产出 `--07-18`、`--07-14` pending 候选（与复核者图上所见 07/18、07/14 一致）→ 严口径召回 38/38=100%；新增 test_slash_date_missing_year_pending；20 张覆盖断言更新 dates=20。
2. title 恒 pending_review 语义维持；复核阶段裁剪。
3. 字段状态词表映射：T06 pending_review → 导入层 pending/review 队列（T03 field_evidence.review_status），T09 落实。
4. block_index 界限断言放宽维持（sanity bound）。

处置后：115/115 通过；ruff/format/pyright 全绿。PASS + golden_confirmed=true 结论不受影响。
