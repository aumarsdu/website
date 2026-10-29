# T05 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-25；对象：asset_registry.py、test_asset_registry.py、evidence/t05_evidence.json。
- 复核者声明：全部结论来自其本机独立运行命令与读取文件（含盐趣真图三样本抽验与 20 项全量扫描零偏差）。

## 首轮逐项结论（复核者原文摘录）

- **A. 全套复跑 — PASS**：104/104 OK；盐趣真图用例实际执行（非 skip）。
- **B. DoD 逐条指认 — PASS**：重命名不加 blob、一 blob 多项目、缺文件/未知位置双 sentinel、derived_from 链可追溯、越界拒绝（另实测绝对路径与中间 symlink 目录组件也被拒）、链环与自环检出、硬链接两位置一 blob、损坏复查检出——逐条指认到具体测试。
- **C. 真实样本 — PASS**：索引 0/9/19 三样本文件真实存在，sha256_stream 与 manifest image_sha256/字节数逐项一致；20 项全量零偏差；manifest 内 20 哈希互不相同，20/20/20/0 断言成立。
- **D. 语义 — PASS**：按内容哈希去重（非路径/inode）；location/blob/link 分离；counts 分项；1MiB 流式；输出仅元数据无绝对路径。
- **E. 质量/范围 — PASS**：ruff/format/pyright 复跑通过（19 模块）；无写 DB/写文件/删除/下载/解压代码；无 T06/T07 越权。

## 总结论（复核者原文）

```json
{"verdict": "PASS", "blocking_issues": [], "non_blocking_notes": ["candidate_hashes.json/task_state.json 待登记 T05 候选哈希与证据（收账时补）", "绝对路径与中间 symlink 目录拒绝已实现但缺单测断言（审查者执行验证通过）", "损坏复查为调用方原语，无专门 recheck 函数/完整性报告字段", "目录误报 missing、同路径重复登记产生 blob.locations 重复条目（计数不受影响）", "t05_evidence.json 日志位置措辞与实际文件路径不符"]}
```

## 非阻塞备注处置（Writer）

1. T05 候选文件/哈希/证据已在收账时登记（candidate_hashes.json、task_state.json）。
2. 绝对路径与中间 symlink 目录拒绝断言已补入 test_traversal_and_symlink_rejected。
3. 损坏复查为调用方原语，完整完整性报告属 T09/T12 范围；已记录。
4. 目录误报 missing、重复登记重复条目为外观问题，计数不受影响；已记录供 T09 导入时规范化。
5. t05_evidence.json 日志路径措辞已修正。

处置后：104/104 通过；ruff/format/pyright 全绿。PASS 结论不受影响。
