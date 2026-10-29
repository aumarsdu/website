# T01 独立再复核（G-R，2026-09-26）

## 身份、范围与方法

- 复核者：本次由 Owner 指派、未参与候选实现的独立 AI；任务指定标识为 `gpt-6-sol via codex-cli`。本机 `codex --version` 返回 `codex-cli 0.155.1`；模型路由元数据无法由本机 shell 独立证明，此处模型名按本次会话授权标识记录。
- 日期：2026-09-26。工作目录：`/Users/liujunliang/Workspace/knowledge-legacy/scraper/db/research_db/goal_20260908_side`。
- 先只读查看 `GOAL.md`、`task_state.json`、2026-09-08 Spec 的 T01 章节、2026-09-25 remaining Spec 的 R1–R4、`evidence/independent_review_t01.md`。旧报告只作为待验证声明；以下结论来自本轮命令、文件和抽样。没有网络请求、数据库连接、Git 写操作或冻结物修改。测试在临时 fixture 目录中按其设计运行，设置 `PYTHONDONTWRITEBYTECODE=1` 和 `-B`；没有生成 `__pycache__`。
- `pwd; git status --short --branch; git rev-parse --show-toplevel`：当前目录如上，Git 根为 `/Users/liujunliang/Workspace/knowledge-legacy`，隔离区在根仓库显示为 `?? scraper/db/research_db/goal_20260908_side/`；根仓库原有其他脏项未触碰。

## 1. 冻结完整性：PASS（登记文件字节哈希）；源文件位置漂移见第 2 项

命令：

```bash
python3 -B - <<'PY'
import hashlib, json
from pathlib import Path
ledger = json.loads(Path('candidate_hashes.json').read_text())
bad = [(p, h, hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else 'MISSING') for p, h in ledger.items()]
bad = [x for x in bad if x[1] != x[2]]
print(len(ledger), len(bad), bad)
print(hashlib.sha256(Path('pilot_manifest.json').read_bytes()).hexdigest())
PY
```

实测：`76 0 []`；`pilot_manifest.json` 为 `1bbf64e94b3ff02c5ef0cf798603237e63ffeb2d02e300b0fc75e43d7e3949c5`。账本现有 76 项，已逐项重算，包含原 T01 的 25 项，全部一致。关键当前值：`evidence/validation.json` 账本与磁盘均为 `bfa926b445fb127ac5bcdd835a3121348517323a6806414ca3c878d73bb08f6c`；`source_registry.json` 均为 `26a65f86…`；`baseline.json` 均为 `9f928af5…`；`target_policy.json` 均为 `a963e3c4…`。上一轮 validation 哈希不一致现已消除；本轮未见账本与磁盘偏差。哈希相同仅证明这些登记文件与**当前账本**一致，不能单凭账本证明历史上从未改写；`source_registry.json` 自身有 T06 的显式位置重绑定 amendment。

## 2. T01-R1 样本代表性与物理引用：FAIL

命令：用 `python3 -B` 读取 `pilot_manifest.json` 的六个 `sources[].references`，将每个 `relative_path` 接到 `/Users/liujunliang/Workspace/knowledge-legacy/scraper`，逐文件计算 SHA-256，并按 `position` 流式查找非空 JSONL 行；CSV 用 `csv.DictReader` 核对 `poster_path`，引知按 `start_line/end_line` 回读。独立摘要命令的核心为：

```python
for source in manifest['sources']:
    for ref in source['references']:
        path = scraper_root / ref['relative_path']
        if not path.is_file(): missing.append((source['source_code'], ref['relative_path']))
        elif sha256(path.read_bytes()).hexdigest() == ref['file_sha256']: matched += 1
```

实测 `175` 个冻结引用中 `155` 个路径存在且文件哈希一致，`20` 个引用缺失，均指向 `盐趣/盐趣海报-2026年9月4日/海报文字识别_PP-OCRv6.csv`。`baseline.json` 的 18 个 `source_entries` 也为 `17/18` 匹配，唯一缺失同此路径。`source_registry.json` 已把盐趣输入改登记为 `盐趣/盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv`，此副本存在且 SHA-256 与冻结引用所记 `0ff1a345…` 相同；但**冻结 manifest 本身没有可用物理路径**。其 20 个盐趣样本无法从冻结路径直接复现。

独立抽样：盐趣 CSV 第 `1/52/195` 行的 `poster_path` 与 `evidence/yanqu_position_check.json` 对应值相同，合集目录下三张原图均存在、SHA-256 均与登记值相同；合集 CSV 实际数据行 `195/195`。引知 10 个锚点所在 `content.md` 文件存在、SHA-256 匹配、`739` 物理行中 10 个行段均存在且非空；观察到的是 front matter、标题、分节和引导行，不能当项目条目。集思 sou_tools 首末两个抽样位置 `1/12`、中科 `1/2806`、HIREP `1/112` 均在各自所指文件中存在，文件 SHA-256 与引用一致。另将中科首个 JSONL 流式计为 `2806/2806`，HIREP full 首个流式计为 `2825/2825`，与 `source_registry.json` 的 `unit_count` 相同。

分级：**blocking**。本次验收明确要求冻结样本的物理文件和位置一致；同哈希重绑定有保全价值，但不能把缺失的冻结路径算作通过。需由 Writer 提供受控、可追溯的新冻结引用或版本化重绑定证据，再由独立者复核；本报告不修改冻结物。

## 3. T01-R2 旧到新映射：FAIL（“当前 candidate_data 为 0 文件”这一复核命题）；映射本身通过

命令：读取 `baseline.json` 的 `code_entries` 与 `evidence/legacy_to_candidate_mapping.md`，逐项核对四个 `tools/research_db_*.py` 及 `db/research_db/schema.sql` 的映射行和哈希前缀；对七个 code entries 重新计算当前磁盘哈希；用 `Path('candidate_data').rglob('*')` 统计文件。结果：映射覆盖四个旧工具及 DDL，所引基线哈希前缀与 `baseline.json` 一致，并列有五源抓取器、交付副本边界、引知非公开面和中科测试。七个基线代码条目中 `6/7` 当前哈希相同；唯一不同的是 `tools/research_db_admin_server.py`，见第 7 项。

`candidate_data/` 当前有 **17 个文件**，含 `.target_ownership.json` 及四入口 pilot 的 staging/sealed 文件；归属标记的 `task=T04`。`task_state.json` 的 T04 条目也把这批试点列为 T04 交付。因此旧报告的“0 文件”是 T01 当时快照，当前命题为假；后续 T04 有归属，不把这 17 个文件定性为 T01 提前迁移。**non-blocking**，但不得在当前状态沿用“0 文件”作为隔离证据。

## 4. T01-R3 目标身份防护：FAIL（与旧 target_check 快照逐项一致这一命题）；当前预检与反例通过

命令及输出：

```bash
python3 -B target_guard.py --policy target_policy.json --target candidate_data --dry-run
```

```json
{"status": "target_ok", "resolved": "/Users/liujunliang/Workspace/knowledge-legacy/scraper/db/research_db/goal_20260908_side/candidate_data", "empty": false, "owned": true, "files": 17, "bytes": 214146}
```

`evidence/target_check.json` 保存的旧快照为 `target_ok, empty=true, owned=false, files=0, bytes=0`；故不一致。当前结果与 T04 已建试点及归属标记相符，guard 没有错误放行无主非空目录。浏览 `test_target_guard.py` 的 17 个用例，可见父路径穿越、绝对路径、越界 symlink、受保护路径重叠、缺目录、非空无主、无效归属标记等反例；交付副本误入和读取前后变化由 `test_inventory.py` 覆盖。`target_policy.json` 的 16 个受保护根包括五源、共享 `tools`、旧 schema/预览/admin 路径及隔离区 `evidence`。**non-blocking**：旧回执是有日期的空目录快照，不应作为当前预检回执使用。

## 5. T01-R4 采集时间依据：PASS

命令：以 `python3 -B` 流式 `json.loads` 扫描 `HIREP/output_pbl_full_refresh_20260602/processed/projects.jsonl` 每个非空行，累计 `crawled_at` 的行数、缺失数、`min/max`，与 `source_registry.json` 及 `evidence/capture_time_evidence.json` 同一窗口比较；另用 `stat().st_mtime` 转 UTC。

实测：`rows=2825`、`with_time=2825`、`missing=0`、`min=2026-06-02T07:39:40.154226+00:00`、`max=2026-06-02T07:39:40.187285+00:00`，两处登记完全一致；文件 mtime 为 `2026-07-07T04:40:56.363307+00:00`，比记录的观察时间晚约一月。HIREP 登记明确将 mtime 视为后续复制/处理时间，不充作观察时间。盐趣 CSV 现场检查的列名不含采集时间，登记的 `observation_time=unknown`、CSV mtime 为处理时间、交付目录日期为命名时间；`observed_order=unknown`，未伪造时序。

## 6. T01 相关测试与质量：PASS

命令与本轮退出结果：

```bash
PYTHONDONTWRITEBYTECODE=1 python3.14 -B -m unittest test_inventory test_target_guard -q
# Ran 34 tests in 0.393s; OK; exit 0
PYTHONDONTWRITEBYTECODE=1 ruff check inventory.py test_inventory.py target_guard.py test_target_guard.py
# All checks passed!; exit 0
PYTHONDONTWRITEBYTECODE=1 ruff format --check inventory.py test_inventory.py target_guard.py test_target_guard.py
# 4 files already formatted; exit 0
PYTHONDONTWRITEBYTECODE=1 pyright --project pyrightconfig.json
# 0 errors, 0 warnings, 0 informations; exit 0
```

同一 34 项还用当前默认 `python3 -B` 跑过一次，亦 `34/34`，但默认 Python 是 `3.12.12`；按 `environment.json` 的锁定值改用 `python3.14`，实测 `3.14.7` 并重跑成功。`ruff 0.16.8`、`pyright 1.1.411`、`psql/postgres 16.15` 与环境登记一致。本轮没有运行后续任务完整 114 项测试，也没有启动或连接 PostgreSQL；这些不属于本次 T01 复核断言。

## 7. 隔离性与 T03 备注：FAIL（T03 入口备注未见于指定账本记录）；未发现可归属 T01 的外部代码写入

命令：核对 `target_policy.json` 的 16 个 `protected_roots`，在 `task_state.json` 中定位 `Task=T03` 并搜索 `PHD`、`data_staging`、`docs/`、`protected_roots`；四词在 T03 条目中均未出现。旧 `evidence/independent_review_t01.md` 曾称三路径遗漏已记入 T03 入口检查，但指定的 `task_state.json` T03 记录并不支持此断言；该任务现标 `DONE`。guard 规定目标必须处于 side_root 内，故这些根未列入当前 policy 不直接形成可达越界；**non-blocking**，但应补证据或更正历史说法。

对照 `baseline.json` 的 7 个旧代码/文档哈希，现有 `6/7` 一致；`tools/research_db_admin_server.py` 的当前哈希为 `953f349f…`，与基线 `a6d44d67…` 不同。只读 `git log -3 -- scraper/tools/research_db_admin_server.py` 显示 `1316694d 2026-09-26 08:23:02 +0800 fix(tools): harden admin server SQL construction`，且 `git show HEAD:... | shasum -a 256` 与当前文件均为 `953f349f…`。因此能确认隔离区外旧工具发生了版本漂移，不能从这些证据断言它由 T01 实现写入。没有发现可直接归属本轮 T01 候选的隔离区外代码改动；Git 根的大量其他脏项不纳入归因。

## 问题分级与结论

- **blocking**：冻结 `pilot_manifest.json` 的 20 个盐趣样本引用指向已不存在的原 CSV 位置。新位置同哈希且三张抽样原图匹配，但冻结引用现状未满足物理位置可复现要求。需受控地登记新版本位置/重绑定并独立再核对，不能仅依赖 T06 amendment 自我声明放行 T01-R1。
- **non-blocking**：`candidate_data/` 当前 17 文件为 T04 归属，旧“0 文件”快照不能复用；当前 target_guard 预检为 `owned=true`，与旧空目录回执不同；T03 账本记录没有三路径入口备注；旧 admin 工具在独立 Git 提交中变更，导致基线代码哈希 6/7 当前吻合。上述现象需要在后续账本/回执中准确标注，不足以单独证明 T01 候选越界写入。
- 本次综合判定 `NEEDS_CHANGES`。这不否认哈希账本、R4、T01 测试和目标 guard 当前行为已通过；它表示 G-R 对**当前冻结样本位置**不能签署 PASS。本报告只写本文件，未更改 `task_state.json` 或任何冻结物。

{"verdict": "NEEDS_CHANGES", "blocking_issues": ["pilot_manifest.json 中 20 个 yanqu_ocr 冻结引用的原 CSV 物理路径已不存在；虽有同 SHA-256 的 collection 副本，冻结位置本身不能直接复现，T01-R1 需受控重绑定并独立复核"], "non_blocking_notes": ["candidate_data 当前 17 个 T04 归属文件，旧 0 文件快照不再适用", "target_guard 当前预检 owned=true、empty=false，与旧 target_check.json 空目录快照不同", "task_state.json 的 T03 记录未含 PHD/data_staging/docs 入口检查备注", "旧 admin server 由独立 Git 提交改变，baseline 代码条目当前 6/7 哈希吻合；未发现可归属 T01 的外部代码写入"], "reviewer": "gpt-6-sol via codex-cli", "date": "2026-09-26"}
