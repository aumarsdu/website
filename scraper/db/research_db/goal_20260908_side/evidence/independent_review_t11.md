# T11 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-26；对象：search.py、generate_t11_queries.py + fixtures/t11_golden.json（sha256 18e1cb04…）、test_search.py、candidate_corpus 语料。
- 复核者声明：全部结论来自其本机独立运行与读取（自写 SQL 复扫 20 查询、自写 p95 脚本、注入与转义探针）。

## 首轮逐项结论（复核者原文摘录）

- **A. Golden 独立复扫 — PASS**：独立 SQL 重算 20/20 与 golden 精确一致；q01 标题全含"人工智能"；q12 窗口独立命中 100（两源 06-02 全量）；q13 无价格语料命中 0 且 total 准确；150 记录/148 bodies 差异=2 个共享 payload。
- **B. 复跑 — PASS**：158/158 OK。
- **C. DoD 语义 — PASS**：分页无重复遗漏；空页 total 准确；中文短词/大小写/注入拒绝/排序白名单；下划线转义探针证实；has_instructor=101 与独立计数一致；49 张无导师卡均带分类；日期/价格构造上排除未知；别名语义有定义。
- **D. 性能 — PASS**：独立复测 100 次串行 p95=0.0685s（<1s）；数据量/DB 版本/硬件已如实登记。
- **E. 质量/范围 — PASS**：ruff/format/pyright 零违规；无 T12 产物；无公开路由；独立性缓解=全部复算用自写 SQL/脚本且 20/20 一致 + 4 项语义抽查。

## 首轮总结论（复核者原文）

```json
{"verdict": "PASS", "golden_confirmed": true, "p95_seconds": 0.0685, "blocking_issues": [], "non_blocking_notes": ["evidence full_suite 149 与实测 158 不符（已更正）", "q17 平凡 0，转义区分力由下划线探针补证", "has_instructor 用 IS NOT NULL（空串导师会计为有，当前语料 0 例）", "显式包含未知未实现（spec 为许可性，未知未计为匹配，不违约）", "taxonomy_aliases 表在候选库不存在，语义以 reserved no-expansion 定义", "检索粒度为 source-record identity；期次数组展示未被本语料触发"]}
```

**T11 状态：DONE（功能/测试/质量/交付/独立复核全部有当前版本证据）。**
