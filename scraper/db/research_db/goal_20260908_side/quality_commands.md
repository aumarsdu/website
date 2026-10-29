# T01 质量基线与执行命令

工作目录：本文件所在目录。版本锁定值见 `environment.json`；未安装新依赖。
补全收官战役（2026-09-28，Spec `../../../docs/superpowers/specs/2026-09-28-research-project-database-completion-spec.md`）新增模块与命令已并入本表；命令回执见 `evidence/r4_command_receipts.log` 与各任务证据文件。

| 检查 | 精确命令 | 范围 / 完成规则 |
| --- | --- | --- |
| 单元 / 反例 | `python3 -B -m unittest discover -s . -p 'test_*.py' -v` | 186 项用例（inventory 17 + target_guard 17 + contract 20 + migrations 10 + staging 15 + adapters 12 + assets 13 + ocr 10 + yinzhi 10 + importer 12 + projection 12 + search 9 + backup 5 + 全量检索 golden 9 + R3/R5 补全 14，含冻结 golden 对比、真实 PG 迁移/导入/投影、并发断连恢复、双语互链、海报提取、64 条目切分、20 查询 golden/p95、备份恢复切换演练、全量语料分页确定性与运行粒度 not_seen 反例）全部通过 |
| lint | `ruff check inventory.py test_inventory.py target_guard.py test_target_guard.py contract.py test_contract.py generate_golden.py pg_candidate.py run_migrations.py test_migrations.py stage_validator.py test_stage_validator.py generate_t08_fixtures.py adapters.py test_adapters.py generate_t04_samples.py run_t04_pilot.py asset_registry.py test_asset_registry.py ocr_extract.py test_ocr_extract.py yinzhi_segment.py test_yinzhi_segment.py generate_t07_golden.py importer.py test_importer.py projection.py test_projection.py search.py test_search.py generate_t11_queries.py backup_restore.py test_backup_restore.py full_migration.py generate_t11_golden_full.py test_search_full_golden.py test_projection_completion.py` | 三十七个模块零违规 |
| format | `ruff format --check inventory.py test_inventory.py target_guard.py test_target_guard.py contract.py test_contract.py generate_golden.py pg_candidate.py run_migrations.py test_migrations.py stage_validator.py test_stage_validator.py generate_t08_fixtures.py adapters.py test_adapters.py generate_t04_samples.py run_t04_pilot.py asset_registry.py test_asset_registry.py ocr_extract.py test_ocr_extract.py yinzhi_segment.py test_yinzhi_segment.py generate_t07_golden.py importer.py test_importer.py projection.py test_projection.py search.py test_search.py generate_t11_queries.py backup_restore.py test_backup_restore.py full_migration.py generate_t11_golden_full.py test_search_full_golden.py test_projection_completion.py` | 三十七个模块均通过 |
| typecheck | `pyright --project pyrightconfig.json` | 零 error |
| 候选集群管理 | `python3 -B pg_candidate.py init` / `status` / `stop` / `destroy` | 仅 TCP 127.0.0.1:55441；数据目录 candidate_pg/（归属标记 T03）；旧端点 /tmp:55432 永不连接 |
| 候选库迁移 | `python3 -B run_migrations.py --database <db> --dry-run`（只读） / `--apply`（应用） | 默认迁移目录 migrations/；台账+checksum；重复执行 no-op；checksum 冲突 exit 2；失败整体回滚 |
| 候选目标预检（T01-R3，真实目标） | `python3 -B target_guard.py --policy target_policy.json --target candidate_data --dry-run` | `target_ok` 且 `empty: true`（或带有效归属标记）；试点建库前必须重跑 |

## 全量候选迁移与补全战役命令（2026-09-28）

| 命令 | 说明 | 回执 |
| --- | --- | --- |
| `python3 -B full_migration.py` | 六源全量 10,427 行 → T08 密封（≤500 行/批）→ T09 幂等导入 → 双库（candidate_full_1/2）重放 + digest 对比 + rebuild_consistency。Owner 确认申请草案后执行，耗时 8,018.5s；identical=true | `evidence/full_migration_report.json` |
| `python3 -B generate_t11_golden_full.py` | 对 candidate_full_1 以直接 SQL 独立标注 20 条查询期望并冻结 `fixtures/t11_golden_full.json`（sha256 06fe38ca…；重跑确定性输出，字节不变） | `evidence/t11_full_smoke.json`；回执日志 |
| `python3 -B -c "import projection; ..."`（R1 备份演练，见 evidence 内调用） | T12 `create_backup`（candidate_full_1，197 项资产清单）→ `restore_backup` 至演练库 → 逐表+扩展对账（digest e05ebc98… 一致）→ 删演练库；RTO 1.999s ≪ 3600s | `evidence/t12_full_drill.json` |
| `python3 -B -c "import projection; print(projection.not_seen_run_report('candidate_full_1', '<source>'))"` | 运行粒度 not_seen 报告（只读）：仅 full_refresh/单输入源可作基准，增量显式排除；嫌疑分桶只认基准后 sighting | `evidence/r3_not_seen_run.json` |
| `python3 -B -c "import projection; print(projection.quality_queue('candidate_full_1'))"` | 质量队列（只读）：conflicts + open quality_issues + identity_candidate（256 = yanqu 192 + yinzhi 64） | `evidence/r5_quality_queue.json` |
| `python3 -B -m unittest test_search_full_golden -v` / `python3 -B -m unittest test_projection_completion -v` | 补全战役专项测试（9 + 14 项） | `evidence/r4_command_receipts.log` |

现有验证器基线（历史记录）：旧验证器对空输入和缺供应商父表返回 0（FAIL_BASELINE），已由 T08 重写修复并冻结证据 `evidence/legacy_baseline.json`。

输入登记只说明文件在清单内、哈希稳定，不说明输入为业务全量、数据正确、归档仍最新或已独立确认。未知观察顺序保持 unknown。试点样本 manifest 已冻结（`pilot_manifest.json` status `frozen_candidate_pending_independent_review`，哈希记录于 `candidate_hashes.json`）；冻结后任何编辑都使样本冻结失效，须重走 T01-R1。全量 golden（`fixtures/t11_golden_full.json`）与迁移报告 `evidence/full_migration_report.json` 同为冻结物，哈希见 `candidate_hashes.json`。
