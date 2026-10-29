# T01 独立复核结论（G-R）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发，原 Spec G-R 允许"获授权独立 AI"）。
- 复核时间：2026-09-25；对象：2026-09-25 R1–R4 整改后的候选（冻结 manifest sha256 `1bbf64e9…`）。
- 复核方法声明（复核者原文）：所有结论均来自其本机独立运行命令与抽查文件，未采信候选自身声明。

## 首轮逐项结论（复核者原文摘录）

- **A. T01-R1 — PASS**：覆盖矩阵五要素齐全；自抽盐趣 CSV 第 1/11/52/103/154/195 行，poster_path 对应原图全部存在且 sha256 与 `yanqu_position_check.json` 一致；引知 10 锚点逐一核实存在、如实归类为页面结构锚；manifest 175 个样本引用位置逐文件流式计数与登记 unit_count 全部吻合；冻结哈希 `1bbf64e9…` 实测吻合；三处明确"T01 抽样认可≠T06/T07 语义准确率"。
- **B. T01-R2 — PASS**：映射覆盖 baseline 全部 4 工具+DDL（引用哈希与 baseline 一致）+五家爬虫+交付副本边界+非公开面+中科 tests；明文不做 T03 物理迁移；实测 candidate_data 0 文件。
- **C. T01-R3 — PASS**：复核者亲跑 target_guard 真实预检，输出与 `evidence/target_check.json` 逐字一致；protected_roots 覆盖旧库产物/五源/共享工具/隔离区内部 evidence；17 项反例齐全。
- **D. T01-R4 — PASS**：复核者流式复测 3 个 jsonl（中科 2806、HIREP full 2825、集思 sou_tools 633），min/max 与覆盖率同登记完全一致；HIREP mtime 晚一个月被如实标注为处理时间；盐趣观察时间如实 unknown；observed_order 保持 unknown；盐趣 7月10日 CSV 与登记 CSV byte-identical 属实。
- **E. 原 Spec T01 测试 — PASS**：34/34 通过；路径穿越/越界 symlink/输入变更（含中途替换）/空输入/交付副本误入/前后哈希变化检测各有测试；复核者还独立复现了两个旧 FAIL_BASELINE。
- **F. G-Q/G-E — PASS，一处账本缺陷**：类型标注、stdout 只含元数据、环境可复现（复跑全过）、隔离区外无代码写入、baseline 25 项哈希一致。**缺陷**：candidate_hashes.json 中 `evidence/validation.json` 哈希为采集旧值（c5eec2c7…），实测 c30c5004…，账本与交付物不一致。
- **G. 独立性 — PASS**：结论全部来自复核者独立执行。

## 首轮总结论（复核者原文）

```json
{"verdict": "NEEDS_CHANGES", "blocking_issues": ["candidate_hashes.json 第 22 行记录 evidence/validation.json 的 sha256 为 c5eec2c7f8073b0ecfc7602b6c708759ba37ff7d33db57fc1827e76683321972，但实测当前文件为 c30c50045ad4d2a89e7ba5e2974af0873acfc4c79c252d71546e82e36ca45e66：validation.json 在哈希采集后仍被改写而账本未重算，G-E 要求的候选文件哈希账本与交付物不一致"], "non_blocking_notes": ["修复仅需在 validation.json 定稿后重算并更新 candidate_hashes.json 该项（其余 24 项哈希经我核验全部一致，pilot_manifest 冻结哈希 1bbf64e9… 实测吻合），修复后无需重审实质内容", "environment.json 记录 ruff 0.16.6，当前环境为 0.16.8（lint/format 仍通过）；建议下批刷新记录", "target_policy.json protected_roots 未含 PHD/、data_staging/、docs/，但 guard 强制 target 必须解析于 side_root 内，构造上不可达，可在 T03 前按需补列", "pilot_manifest.json 中 jisi/hirep/zhongke/yanqu 的 asset_manifest 均为 not yet selected，属 T05/T06 范围，与 T01 冻结不冲突"]}
```

## 修复记录（Writer）

1. validation.json 定稿后再重算 candidate_hashes.json（账本改为最后生成，杜绝自引用与后写）。
2. environment.json 的 ruff 版本刷新为实测 0.16.8，并标注 recheck 日期。
3. 复核者非阻塞备注（PHD/、data_staging/、docs/ 未列 protected_roots）记入 T03 入口前检查项，不改 T01 冻结物。

## 复核确认

复核者对修复的最终确认（2026-09-25，原文）：

- 25/25 项 sha256 账本与磁盘一致（含 validation.json=809250fc…、pilot_manifest=1bbf64e9… 冻结未动、task_state=720fb1d3…、candidate.patch=07f52d04…）；首轮唯一 blocking issue 已解决，无新实质问题。
- environment.json ruff 0.16.8 刷新、PHD/data_staging/docs 记入 T03 入口检查、本文件如实记录首轮结论，均核对属实。

```json
{"repair_confirmed": true, "note": "25/25 哈希账本与磁盘一致（含 validation.json=809250fc…、pilot_manifest=1bbf64e9… 冻结未动、task_state=720fb1d3…、candidate.patch=07f52d04…），ruff 0.16.8 已刷新，PHD/data_staging/docs 事项已记入 T03 入口检查，independent_review_t01.md 如实记录首轮结论；首轮唯一 blocking issue 已解决，无新实质问题"}
```

**T01 状态：DONE（功能/测试/质量/交付/独立复核全部有当前版本证据）。**
