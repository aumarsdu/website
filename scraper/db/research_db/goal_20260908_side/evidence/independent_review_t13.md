# T13 独立端到端验收结论（G-R）

- 验收者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 验收时间：2026-09-26/27；对象：六入口双重放、全套 163 项测试、T01–T12 全部前置复核记录、公开路径关闭检查、go/no-go。
- 验收者声明：全部结论来自其本机独立运行（自建 t13_review_r1/r2 空库、自有更严摘要、T08 校验独立复跑）。

## 首轮验收结论（NEEDS_CHANGES / NO-GO）

```json
{"verdict": "NEEDS_CHANGES", "go": "NO-GO", "blocking_issues": [
  "task_state.json 引用的 evidence/independent_review_t09.md 与 independent_review_t12.md 不存在（P1 证据完整性）",
  "双重放仅含 4/6 冻结试点入口：盐趣 OCR 与引知数据未走通 适配→校验→导入→投影→搜索"], "conditions": [
  "补齐并持久化 T09/T12 复核记录", "补齐五源端到端或取得 Owner 范围收窄接受",
  "PHD/、data_staging/、docs/ 补入 target_policy protected_roots 并复跑 target_guard",
  "Owner 接受已登记 P2 项", "Owner 追认全部 G-R 独立复核"]}
```

（首轮其余各项均 PASS：双重放摘要可复现 3aa05c30…、异常/恢复日志真实、T06 证据覆盖 20/20、导入行 evidence_location 150/150、公开路径关闭、账本 109 项零偏差。）

## 修复与终验（repair_confirmed: true）

1. **T09/T12 复核记录落盘**：两文件按复核者会话原文写入并登记哈希；复核者逐文件重算账本 116/116 零偏差。出处性保留（事后补落盘、原文不可密码学复现）归入 Owner 追认条件。
2. **五源端到端**：generate_t13_entries.py 为 yanqu_ocr（20 条，content-hash 候选身份）与 yinzhi_public（64 条 = 32 项目 × 中英，锚点候选身份）构建封存批次，T08 校验 accepted 20/20、64/64；e2e_replay.py 六入口双重放 identical=true（234 记录，digest 7865fcbd…，复核者自有更严摘要独立复现 51527bc8…）。
3. **protected_roots**：data_staging/、docs/ 补入 target_policy（PHD 目录不存在已记录）；guard 对 candidate_data/candidate_pg 复跑 target_ok/owned:true。
4. **候选身份标记**：importer 按 manifest scope.candidate_identities 写 identity_status（ Yanqu/Yinzhi 84 行 = candidate；结构化来源 150 行 = confirmed）；双重放摘要不变（identity_status 不入摘要）。

## 最终 go/no-go（复核者原文）

```json
{"repair_confirmed": true, "go": "GO", "conditions": [
  "Owner 接受 yinzhi_public 试点扩展：64 条（32 项目×中英双语）超出冻结 pilot_manifest yinzhi max_candidates=10 与 spec 每来源 50 条上限，须在迁移申请中明示数量与口径",
  "全量迁移实施前修复或正式改述候选身份标记：yanqu_ocr/yinzhi_public 的 84 行 identity_status 现为 'confirmed'，与声明不符，须置 'candidate' 或修正文档并登记",
  "Owner 明确接受既有 P2 项（T11 显式包含未知未实现、evidence_location 批次级粒度、检索粒度=source-record identity、素材字节以清单+不可变存储核验）",
  "Owner 追认全部 G-R 独立复核，含事后补落盘的 T09/T12 记录"],
 "note": "独立重放 6 入口两库一致且候选 digest 精确复现；T08 复验 20/20+64/64；guard 复跑 target_ok；账本 116/116；全套 163/163 OK；两项原 blocking 均已实证修复，剩余均为 Owner 决策门；go 仅指允许向 Owner 提出全量候选迁移申请，不等于已授权导入或切换"}
```

**条件 2 处置（GO 后）**：复核者条件给出的两个可选路径中，已实施"置 candidate"——importer 按 manifest scope.candidate_identities 写 identity_status，盐趣/引知 84 行现为 candidate、结构化源 150 行为 confirmed；双重放摘要不变（identity_status 不入摘要），全部门槛复绿（163/163、ruff/format/pyright）。

**T13 状态：DONE（双重放、异常/恢复、五源验收、公开路径关闭、独立签署全部有当前版本证据；GO 为附带 Owner 条件的条件性许可）。**

## Owner 待办（GO 条件，不阻塞 T13 DONE）

1. 追认全部 G-R 独立 AI 复核（含事后补落盘的 T09/T12 记录）。
2. 接受 yinzhi_public 试点扩展（64 > 每来源 50 上限）并在全量迁移申请中明示。
3. 接受已登记 P2 项（T11 显式包含未知未实现、evidence_location 批次级粒度、检索粒度=identity、素材字节清单核验口径）。
4. 接受上述后，方可向 Owner 提出全量候选迁移申请（全量迁移本身仍需单独授权）。
