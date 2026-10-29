# T03 独立复核结论（G-R 迁移评审）

- 复核者：未参与候选实现的独立 AI 审查代理（本会话派发）。
- 复核时间：2026-09-25；对象：migrations/0001、0002、run_migrations.py、tests/legacy_replica.sql、test_migrations.py、pg_candidate.py、schema_model.md。
- 复核者声明：全部结论来自其本机独立运行命令与抽查文件（含在自建临时库的独立探针）。

## 首轮逐项结论（复核者原文摘录）

- **A. 功能验收 — PASS**：来源键 UNIQUE+NOT NULL、幂等观察键含 context+payload、跨记录当前指针被复合 FK 真实阻断（探针实测报错）、非法 FK/非法 field_state/batch UPDATE 拒绝、同 batch_id 不同 digest 被 PK 拒绝、重跑 no-op 与 checksum 冲突 exit 2 均由复核者复跑证实。
- **B. 测试 — PASS**：复核者自跑全套 64/64 OK（含 10 项真实 PG 用例）。
- **C. 桥接对账 — PASS（带缺口）**：八类计数与 legacy_replica 行数一致；legacy_id_map 0 未映射；A→B→A 保留 3 观察；孤儿来源触发 RAISE 整体回滚。缺口：守卫只覆盖 5/8 实体（同名 provider 合并、NULL source 批次静默）。
- **D. 安全/隔离 — PASS**：listen_addresses 仅 127.0.0.1、unix socket 禁用、数据目录在隔离区内、55432 仅出现于注释、无凭据硬编码。
- **E. 质量 — PASS（文档瑕疵）**：六表字典与 DDL 一致；schema_model.md 一处 ER 边错误；全仓无全局 DO NOTHING（5 处定向 ON CONFLICT 仅限 legacy_id_map 登记属实）；ruff/format/pyright 复跑 0 违规。
- **F. 范围 — PASS**：旧 schema.sql 哈希与 T01 baseline 一致（未动）；无旧库连接；无越权交付。

## 首轮总结论（复核者原文）

```json
{"verdict": "NEEDS_CHANGES", "blocking_issues": ["run_migrations.py:101 `--dir` 默认值为脚本所在根目录（无任何 *.sql），导致文档命令 `python3 -B run_migrations.py --database <db> --dry-run`（quality_commands.md:12、schema_model.md:65/87）实际不应用任何迁移：建空库后静默 exit 0，与候选自称的'不静默跳过'直接矛盾；修复：默认改为 `<脚本目录>/migrations` 或同步修正两处文档命令"], "non_blocking_notes": ["schema_model.md:32 ER 边 providers→identity_links 错误，应为 provider_projects→identity_links", "0002 对账守卫仅覆盖 5/8 实体：legacy providers 同名 2→1 静默合并与 ingest_batches source_id 为 NULL 的批次静默丢弃 exit 0（建议补守卫或文档注明偏差）", "run_migrations.py 必填的 `--dry-run` 实际执行真实写入，命名与 spec §3.4 只读语义倒置", "候选集群残留调试库 t03_debug、t03_debug2 未清理", "manual_overrides/quality_issues 为多态 (entity_kind, entity_id) 设计，无 DB 级 FK，非法实体引用只能靠应用层拒绝"]}
```

## 修复记录（Writer，按评审意见逐项）

1. **blocking**：`--dir` 默认值改为 `<脚本目录>/migrations`；CLI 重构为 `--dry-run`（真只读预览）/ `--apply`（实际应用）互斥必填。临时库实测：--dry-run 后 0 张表，--apply 后 24 张表，scratch 用后即删。
2. schema_model.md ER 边修正（provider_projects → identity_links）。
3. 0002 对账补全：`providers_merged_by_name`、`ingest_batches_unmigrated_null_source` 显式计数写入 legacy_bridge_status；新增 ingest_batches 守卫（v_batches + null_source = 总数，否则 RAISE 整体回滚）；测试期望同步更新。
4. t03_debug / t03_debug2 已 drop。
5. 多态引用的应用层拒绝职责写入 schema_model.md 数据字典（T09 落实）。

修复后：64/64 通过；ruff/format/pyright 全绿。复核确认见文末。

## 复核确认

复核者对修复的最终确认（2026-09-25，原文）：

- 五项处置全部以其自己的命令实测通过：`--dir` 默认修复且 `--dry-run` 真只读（对不存在的库名不建库、对空库 0 张表）/ `--apply` 应用 2 迁移 24 表；ER 边已更正；0002 静默丢弃场景重放现显式计数 `providers_merged_by_name=1` 与 `ingest_batches_unmigrated_null_source=1` 且守卫 RAISE 在位（0002:98-102），"因 legacy FK 使 source_id 只能为 NULL 或有效引用，该划分是完备的，无剩余静默路径"；调试库已清；多态引用已注明；64/64、ruff/format/pyright 复跑全绿；审查临时库已全部 drop。

```json
{"repair_confirmed": true, "note": "五项处置全部实测通过：--dir 默认修复且 --dry-run 真只读（不建库不建表，exit 0）/ --apply 应用 2 迁移 24 表；ER 边已更正；0002 静默丢弃场景现显式计数 providers_merged_by_name=1 与 ingest_batches_unmigrated_null_source=1 且守卫 RAISE 在位；调试库已清；多态引用已注明；64/64、ruff/format/pyright 复跑全绿；审查临时库已全部 drop"}
```

**T03 状态：DONE（功能/测试/质量/交付/独立迁移评审全部有当前版本证据）。**
