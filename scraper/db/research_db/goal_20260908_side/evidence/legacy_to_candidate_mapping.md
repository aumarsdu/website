# 旧到新候选映射清单（T01-R2）

- 生成：2026-09-25；Writer：goal_20260908_side 当前会话。
- 旧实体哈希见 `baseline.json` 的 `code_entries`；本清单只做职责映射，不提前执行 T03 物理迁移。
- 状态：候选，待独立复核（G-R）。

## 1. 旧工具 → 新职责

| 旧实体 | 旧职责（实测 docstring/行为） | 新职责归属 | 处置 | 依据 | 未知项 | 后续任务 |
| --- | --- | --- | --- | --- | --- | --- |
| `tools/research_db_prepare_staging.py` | 读最新 processed 爬虫 JSONL，写出数据库形状的 staging JSONL；不连数据库 | T08 强校验+封存暂存流水线 | 适配重建：保留"staging 中间层+manifest"概念；不直接复用实现（旧实现无逐行强校验与原子封存） | baseline code_entries 哈希 961c1c46…；docstring | 旧脚本与旧 validator/import 的版本配套关系 | T08 |
| `tools/research_db_validate_staging.py` | 校验 staging JSONL | T08 校验器 | 替换重写；已知缺陷（空输入通过、缺供应商父表跳过）已按新 Spec 复现登记为 FAIL_BASELINE，不得复用其判定逻辑 | baseline 哈希 6cfe8857…；`evidence/legacy_baseline.json` | 无 | T08 |
| `tools/research_db_import_staging.py` | `psql` + `schema.sql` 导入；另含 SQLite smoke 模式 | T09 幂等导入与事务回执 | 适配重建：真实 PostgreSQL 重放/断连/回执语义按 T09 新实现；SQLite smoke 模式**不继承**（原 Spec 禁止 SQLite 冒充目标库） | baseline 哈希 c3a35124…；docstring | 旧导入在部分失败后的实际落库状态（旧库不可连，无法核对） | T09 |
| `tools/research_db_admin_server.py` | 本地 admin/public 服务器（含 `/public`、`/api/public/projects` 路由） | 拆分：内部投影/查询 → T10/T11；公开路由 → D01 | 排除出首期：public 路由与静态页不进入候选实现；内部投影与检索按 T10/T11 重建 | baseline 哈希 a6d44d67…；路由清单实测（public.html/public.js/api/public/projects） | public 输出字段完整清单（D01 启动时再核定） | T10、T11、D01 |
| `db/research_db/schema.sql`（44 张表） | 旧 DDL（users/roles/sources/providers/ingest_batches/source_project_records*/canonical_projects/project_*/instructors/taxonomy_*/…） | T03 关系模型与版本化迁移 | 保留为代表性旧 schema：T03 逐表决策保留/转换/弃用，并作为"旧 schema 代表性副本升级"测试的输入；不原位替换 | baseline 哈希 987eb20d…；44 个 CREATE TABLE 实测 | 各表在旧库中的真实数据量与空表情况（旧库禁止连接） | T03 |
| 五家抓取器（集思未来 `sou_crawler`、中科爬虫、HIREP 爬虫、盐趣 `ocr_posters_ppocrv6.py`、引知归档） | 产出五源 processed JSONL / OCR CSV / 公开归档 markdown | 上游生产者 | 不修改（本轮不改共享抓取器）；T04 适配器只读其输出；T05 登记素材；T06 消费盐趣 OCR；T07 消费引知归档 | 各源登记输入哈希见 `source_registry.json` | 抓取器内部字段语义（如 HIREP `business_id` 构成）由适配样本验证，不假设 | T04、T05、T06、T07 |
| 中科 `tests/`（test_cli/test_config/test_pipeline） | 抓取器自身测试入口 | 不属于新库任务 | 保留原样，仅作为"既有实现"证据登记；T01 不修改不运行其网络路径 | git status（工作区既有脏文件，归属原工作流） | 无 | 无 |
| 旧交付副本目录（`*/Poster`、`*.zip`、日期命名交付夹、`盐趣海报-2026年9月4日/Poster` 标题改名副本） | 人工交付/展示副本 | T05 素材登记 | 排除出主事实源输入；T05 以 blob 哈希统一登记，改名副本与原图的同一性由哈希判定，不按文件名 | `source_registry.json` excluded 节；`pilot_manifest.json` second_delivery_naming | 标题改名副本与原图的完整对应表（T05 建立） | T05 |
| `引知/data/archive/api`、`html`、`external_pages`、`logs` | 归档的非公开抓取面 | 无 | 永不读取：不在 public 允许清单 | `source_registry.json` excluded 节 | 无 | 无 |

## 2. 旧逻辑语义 → 新契约要点（供 T02/T03 引用）

| 旧逻辑 | 新契约处理 | 任务 |
| --- | --- | --- |
| 旧 validate/import 以"文件存在即可导入"为前提 | T08 封存 manifest + 逐项验证后才可导入；任何验证后输入变更使资格失效 | T08 |
| 旧导入无幂等回执证据 | T09 同输入重放零新增、批次标识重用拒绝、计数取自已提交回执 | T09 |
| 旧 schema 当前值直接覆盖（无观察史） | T02 观察序+字段状态；T10 投影可由历史+人工账本重建 | T02、T10 |
| 旧 admin server 公开路由与内部查询同进程 | 内部（T10/T11）与公开（D01）物理分离；候选数据不得进入公开接口 | T10、T11、D01 |

## 3. 边界声明

- 本映射不改变任何旧文件；旧工具、旧 schema、旧库均保持只读不动。
- "复用/适配/替换"均为 T02–T11 的实现约束，不构成本轮已完成实现。
- 若独立复核发现旧实体职责判定有误，以复核结论为准并回改本清单。
