# R3/R5 独立复核记录 — not_seen_run_report 与 quality_queue(identity_candidate)

- 复核者身份声明：本复核由独立 AI 复核代理执行，未参与 R3/R5 的实现工作。按复核要求阅读了 `projection.py`（目标函数 `not_seen_run_report` L306–433、`_staged_native_ids` L436–446、`quality_queue` L449–505）、`contract.py`（identity_key 语义）、`source_registry.json`、`test_projection_completion.py` 及两份证据 JSON；**未用 `not_seen_run_report`/`quality_queue` 本身对真实库复算证据数字**（复核数字全部来自自写脚本 + 只读 SQL）。唯一例外：运行了 `test_projection_completion.py` 的 13 个单元用例（合成 fixture + 临时库 r3_*/r5_*，属实现健全性检查，与证据数字无关）。
- 复核日期：2026-09-28
- 复核对象：R3 `not_seen_run_report`（evidence/r3_not_seen_run.json）、R5 `quality_queue` 第三类 identity_candidate（evidence/r5_quality_queue.json）
- 数据库访问方式（只读）：`/opt/homebrew/opt/postgresql@16/bin/psql -h 127.0.0.1 -p 55441 -U candidate_t03 -d candidate_full_1 -tA -c "SQL"`。全程仅 SELECT，未写入任何数据库对象；除本复核记录外未写任何文件。

## 一、实现审查（对照规格逐项）

| 规格条目 | 实现位置 | 结论 |
|---|---|---|
| 源/输入来自 source_registry.json；unknown source 报错 | L327–334 `unknown_source` | 符合 |
| 运行分类：路径含 full_refresh→full_refresh；含 incremental→incremental；单输入→complete_single_file；否则 unknown | L338–348 | 符合 |
| 默认基准=登记顺序中最后一个合格运行 | L350–357 `eligible_positions[-1]`，合格集仅含 full_refresh/complete_single_file | 符合 |
| 增量运行显式不可作基准（显式传入时报错） | L369–370 `incremental_run_not_a_baseline`；默认选择中也排除 | 符合 |
| unknown 类型显式传入时报错 | L371–372 `not_a_complete_run` | 符合 |
| staging→运行映射：按批序拼接 `<source>-NNN/staging/records.jsonl`，按 registry unit_count 累计边界切分 | L377–389 + `_staged_native_ids`（sorted glob，零填充批号字典序正确） | 符合；多输入源行数 ≠ sum(unit_count) 时报 `staging_registry_misaligned`（fail-loud）；单输入豁免对齐检查（规格：唯一文件即全集） |
| identity_key = contract.identity_key(source_code, 行内 id) | L391–401 | 符合（canonical JSON `{"native_id","source"}`） |
| 输出 db_identities / not_seen_in_baseline / added_by_incremental / no_incremental_sighting / incremental_inputs / readonly | L412–433，分桶定义与规格一致（added ∩ 增量；no_sighting = not_seen − added） | 符合 |
| 只读性 | 函数内仅 SELECT（pg_candidate.psql）与文件读取，无 INSERT/UPDATE/DELETE；测试含 quality_issues 前后计数断言 | 符合 |

R5：第三类 `identity_candidate` 查询为 `source_records WHERE identity_status='candidate'`，附 `source_code` 与 `COALESCE(source_record_current.status,'absent')`，按 (source_code, source_record_id) 排序——与规格一致。解析用 `split("|", 3)`：identity_key 是 canonical JSON（不含 `|`）且为 maxsplit 尾段，安全；`source_record_current` 有 source_record_id 唯一索引（7972 行 = 7972 distinct），LEFT JOIN 不会产生重复队列项。

## 二、R3 独立复算（自写脚本，未调用被复核函数）

方法（三条相互独立的证据链）：
1. **staging 切分链**：按 sorted `<source>-NNN` 拼接各源 staging/records.jsonl（24 个文件逐一验证 splitlines 与 `'\n'` 切分计数一致，行数=500×n+余量），按 registry unit_count 累计边界切分为各运行的 id 集；
2. **原始文件交叉验证链**：从 `scraper/` 下原始运行文件（集思未来 records.jsonl 6+4 个、HIREP projects.jsonl 5 个、中科 projects.jsonl）直接抽取原生 id（jisi=id/record_key、hirep=business_id、zhongke=id），与切分出的各段**逐段集合比对**——3 个多输入源共 14 段全部完全一致（含 2 行、10 行的微小增量段），证明累计边界映射真实还原了"段→运行"归属；
3. **数据库链**：直接 SQL 取各源 `source_records.identity_key` 集合，做集合差与分桶。

与证据 JSON 的比较是**全集合逐元素相等**（不止对计数）：

| 源 | db_identities | not_seen | added_by_incremental | no_incremental_sighting | 与证据比较 |
|---|---|---|---|---|---|
| jisi_future_sou_tools | 800 | **187** | **98** | **89** | 三列表逐元素一致 PASS |
| jisi_future_domestic | 1342 | 298 | 46 | 252 | 逐元素一致 PASS |
| zhongke | 2806 | **0** | 0 | 0 | 一致 PASS |
| hirep | 2768 | **747** | **473** | **274** | 三列表逐元素一致 PASS |
| yanqu_ocr | 192 | 0 | 0 | 0 | 一致 PASS |
| yinzhi_public | 64 | 0 | 0 | 0 | 一致 PASS |

辅助核对：各报告 baseline_input/baseline_run_type/baseline_unit_count 与 registry 及我的切分一致；incremental_inputs 内容与 registry 逐路径一致；证据列表无跨源身份污染；库内 identity_status 分布（confirmed 7716 + candidate 256 = 7972）与 R2 复核记录的总记录数吻合。

补充数据事实（非缺陷）：
- hirep full_refresh_20260602 原始文件 2825 行仅 2021 个唯一 business_id（文件内含重复）；staging 段集合与原始文件集合仍逐段一致。
- yanqu staging 195 行含 3 个重复 id → 192 唯一，与库内 192 一致。
- zhongke 原始 projects.jsonl 现有 2831 个唯一 id，封存 staging 为 2806；多出的 25 条 crawled_at=2026-09-28T13:11（封存之后重新采集）。封存基准落后于原始文件属设计内（staging 为权威）。

## 三、R5 独立复算

- `SELECT count(*) FROM source_records WHERE identity_status='candidate'` = **256**；按源分布 `yanqu_ocr=192、yinzhi_public=64`；其余 4 源全部 confirmed。与证据 `identity_candidate_total=256`、`identity_candidate_by_source={yanqu_ocr:192, yinzhi_public:64}` 一致。
- 256 条 candidate 的 current 指针状态全部为 `unresolved`（均挂有 source_record_current 行，状态 unresolved）；证据 sample 的 source_record_id 9198/9199 逐字段与库一致。
- 队列构成核对：conflicts=0、quality_issues open=6548（全部为 T10 期 P2 `not_seen_in_complete_batch:full-*`：hirep 2526、zhongke 2500、jisi 1522）、candidate 256 → 合计 **6804** = 证据 `queue_total` 一致。

## 四、证据 JSON 与库事实矛盾检查

- r3_not_seen_run.json：metadata（database=candidate_full_1、executed_at=2026-09-28、semantics 描述）与实现/实际一致；六份报告的所有标量字段与集合字段经上述复算全部一致，**未发现矛盾**。
- r5_quality_queue.json：queue_total、identity_candidate_total、by_source、sample、matches_audit=true 均与库事实一致，**未发现矛盾**。

## 五、发现的问题与建议（NOTE 级，均不影响本轮任何输出数字）

1. **`_staged_native_ids` 用 `str.splitlines()`（projection.py L443）存在潜在脆弱性**。splitlines 还会在 U+2028/U+2029 等处断行；原始集思未来文件中实测含 U+2028（sou_tools 0703 文件 2 处），而当前 24 个 staging 文件均无此类字符（逐一验证），故本轮结果正确。但若未来 staging 序列化（ensure_ascii=False 下 json.dumps 不转义 U+2028/U+2029）引入裸行分隔符，行计数与 unit_count 边界映射会**静默错位**（仅多输入源有对齐检查兜底，且错位量恰为 0 时无法察觉）。建议改用 `split('\n')`。
2. **hirep 的 `HIREP/output_pbl_new_20260703`（444 行/274 唯一 id）被归为 unknown**：不作基准（正确），也不计入增量 sighting。后果：hirep `no_incremental_sighting=274` 经诊断**全部**恰好是来自该 0703-new 运行的库内身份——它们在 2026-07-03 的登记运行中被观测过，"强下架嫌疑"标签对这 274 条言过其实。该行为符合规格字面分桶定义（sighting 仅限增量运行），但建议在报告消费方文档中说明，或在后续规格中明确此类"非全集、非增量"运行的 sighting 资格。
3. **yinzhi_public 的 registry `unit_count=739` 是 content.md 原始行数**（实测 738 个换行符），而封存迁移 seal.json 为 rows_read=64/accepted=64；报告并列输出 `baseline_unit_count=739` 与 `db_identities=64、not_seen=0`，读者可能误以为核对了 739 条记录。属 registry 元数据口径不一致（其余源 unit_count=记录数），不影响身份集合与结论；注意单输入源豁免对齐检查在此是必要前提（否则将触发 staging_registry_misaligned）。
4. **轻微边界**：inputs 缺 `unit_count` 时会以 KeyError 而非 ProjectionError 失败（当前 registry 均有该字段）；假想"单输入源路径含 incremental"时路径标记优先于 complete_single_file（→ no_baseline_run），与规格"增量显式不可作基准"的优先级相容，当前 registry 无此情形。

## 六、单元测试

`python3 -m unittest test_projection_completion` → **Ran 13 tests, OK**（合成 registry/staging fixture + 每用例独立临时库，含增量基准拒绝、对齐报错、只读断言、candidate 入队/confirmed 不入队等）。

## 七、总体判定

**PASS_WITH_NOTES** — R3 六个源（含要求的 jisi_future_sou_tools 187/98/89、zhongke 0、hirep 747/473/274）与 R5 的 256=192+64（队列合计 6804）全部用独立方法复算命中，且证据集合逐元素一致；实现语义与规格相符、只读性成立；无影响输出的逻辑缺陷。上述 4 项 NOTE（1 项鲁棒性建议、1 项分桶语义口径提示、1 项 registry 元数据口径、1 项轻微边界）建议在后续迭代中处理，但不构成本轮证据的置信度问题。

---

# 修复后复核（第二会话）

- 复核日期：2026-09-29
- 复核范围：上一轮 4 项 NOTE 修正后的 `not_seen_run_report`（运行粒度 not_seen 报告）及再生成的 evidence/r3_not_seen_run.json（2026-09-28T23:00 版，含 `review_notes_applied` 字段逐条声明 NOTE1–NOTE4 已应用）。R5 quality_queue 未改动（evidence/r5_quality_queue.json 时间戳早于修正、该函数不依赖被修正的 `_staged_native_ids`/`not_seen_run_report`），仅做库事实一致性抽查。
- 复核者身份声明：本节由第二个独立复核会话执行，未参与实现。**全程未调用、未运行任何被复核函数**（未执行 `projection.not_seen_run_report`/`quality_queue`，未跑单元测试）；全部数字来自自写脚本（heredoc，未落盘）对封存 staging 文件、source_registry.json 与只读 SQL 的独立计算。为逐项核验修正 1/4 的代码落点，对 `projection.py` 相关行做了**最小静态阅读**（grep 定位 + L306–452 函数体目视），未执行其中任何代码；除本文件增补外未写任何文件。
- 数据库访问方式（只读）：`/opt/homebrew/opt/postgresql@16/bin/psql -h 127.0.0.1 -p 55441 -U candidate_t03 -d candidate_full_1 -tA -c "SQL"`，全程仅 SELECT。

## 一、方法（与实现相互独立的三条证据链）

1. **staging 切分链**：24 个 `candidate_data/full_migration_1/<source>-NNN/staging/records.jsonl` 按批序（目录名字典序）拼接，统一用 `split("\n")` 切分（与修正 1 的语义一致）；按 registry 各输入 `unit_count` 累计边界切分出"段→运行"，多输入源断言 `sum(unit_count) == 总行数`（hirep 3742、jisi_sou 1344、jisi_dom 2276 全部吻合），单输入源按规格"唯一文件即全集"豁免对齐检查（yinzhi 64 行 vs unit_count 739、yanqu 195）。对每行取 `id` 字段，自算 identity_key = `json.dumps({"native_id":..., "source":...}, ensure_ascii=False, sort_keys=True, separators=(",",":"))`（contract.canonical_json 语义）。
2. **原始文件交叉链**：对修正 2 的关键段（hirep 段2 = `HIREP/output_pbl_new_20260703`）及 hirep 段1、jisi_sou 全部 6 段，从 scraper 根下原始运行文件抽取原生 id（hirep=business_id、jisi=id）做逐段集合比对——全部完全相等（hirep 0703-new：444 行/274 唯一 = staging 段 444 行/274 唯一）。
3. **数据库链**：`source_records ⨝ sources` 直接取各源 `identity_key` 全集，做集合差与分桶。

## 二、修正逐项核验

| 修正项 | 核验方式 | 结论 |
|---|---|---|
| 1. `_staged_native_ids` 用 `split("\n")` | 数据前提：24 个 staging 文件逐一检查，均**无 U+2028/U+2029、无 CR、无空行、全部以 \n 结尾**（故本次修正对当前数据是行为中性的，不改变任何数字，符合预期）；代码落点：projection.py L449 `records.read_text(encoding="utf-8").split("\n")`，L450 跳过空行（正确处理结尾换行的空尾元素），docstring 明确 U+2028/U+2029 理由 | PASS |
| 2. 嫌疑分桶="仅基准之后运行的 sighting 证明存活" | 代码落点 L400–404：sighted_after = 基准位置之后**所有**运行（不分类型，含 unknown 型 HIREP 0703-new）identity 集合并集；L424–429 按 ∈/∉ 切分出 `sighted_after_baseline`/`not_sighted_after_baseline`；L430–432 `later_runs` = 基准之后有序路径列表。数字核验见第三节；hirep 关键案例：0703-new 段 274 个唯一 id 全部在库、**全部**属于 not_seen（即旧口径的 274 强嫌疑确实全部来自该基准后运行的 sighting），not_seen 747 全部被 later_runs 覆盖 → strong=0 | PASS |
| 3. 报告含 `baseline_staged_rows` 与 `baseline_unit_count` 并存 | 证据 JSON 六源均含两字段：baseline_staged_rows = 613/1044/2806/2021/192/64（yinzhi=64 ✓），与我的独立计算（基准段内**去重后** native id 数）逐一相等；baseline_unit_count = 613/1044/2806/2825/195/739 并列输出，口径差异（hirep 2021 vs 2825、yanqu 192 vs 195、yinzhi 64 vs 739）与上一轮 NOTE3 描述的事实一致 | PASS |
| 4. inputs 缺 unit_count → ProjectionError("registry_input_missing_unit_count") | 代码落点 L377–379：`entry.get("unit_count")` 为缺失（None）或非 int 时 `raise ProjectionError("registry_input_missing_unit_count")`（比规格略强：非整数值如字符串数字也会报错）。当前 registry 六源 inputs 均有 int 型 unit_count，守卫不触发。静态确认，未执行 | PASS |

## 三、六源独立复算 vs 证据 JSON（逐元素，不止对计数）

| 源 | db_identities | not_seen | sighted_after_baseline | not_sighted_after_baseline(strong) | 与证据比较 |
|---|---|---|---|---|---|
| jisi_future_sou_tools | 800 | **187** | **98** | **89** | 三列表逐元素一致 PASS |
| jisi_future_domestic | 1342 | 298 | 46 | 252 | 三列表逐元素一致 PASS |
| zhongke | 2806 | 0 | 0 | 0 | 一致 PASS |
| hirep | 2768 | **747** | **747** | **0** | 三列表逐元素一致 PASS |
| yanqu_ocr | 192 | 0 | 0 | 0 | 一致 PASS |
| yinzhi_public | 64 | 0 | 0 | 0 | 一致 PASS |

同时逐元素核验：`not_seen_in_baseline = sighted_after ⊔ not_sighted_after`（不相交并）在六源全部成立；`later_runs` 有序列表与 registry 顺序逐一相等（jisi_sou 4 个增量、jisi_dom 2 个、hirep 4 个含 0703-new、三个单输入源为空）；`baseline_input`/`baseline_run_type`/`baseline_unit_count` 与独立计算一致——**基准=登记顺序最后一个合格运行**（jisi 两源=20260703 full_refresh；zhongke/yanqu/yinzhi=唯一输入 complete_single_file；hirep=20260602 full_refresh，0703-new 为 unknown 不作基准）；`readonly=True` 六源全部声明。跨源身份污染检查：六源 DB identity_key 中 `"source"` 字段全部等于本源 source_code，污染为 0。

## 四、只读性与库状态一致性

- 静态：`not_seen_run_report`（L306–435）函数体唯一的 DB 调用是 SELECT（L406–413，经 pg_candidate.psql），函数内无 INSERT/UPDATE/DELETE（grep 命中的写入语句 L61/87/95 属 apply_override/withdraw_override、L291 属批粒度 `not_seen_report`，均非本函数）。
- 经验：库状态与上一轮复核快照完全一致——source_records 7972（confirmed 7716 + candidate 256）、quality_issues open 6548（hirep 2526 + zhongke 2500 + jisi 1522，全部 P2 not_seen_in_complete_batch）、conflicts 0；R5 证据（queue_total 6804 = 6548 + 256，candidate 256 = yanqu 192 + yinzhi 64）与库事实仍然吻合。本次复核全程仅 SELECT，未写任何数据库对象。

## 五、残留注记（均不影响本轮任何数字与结论）

1. **口径说明**：`baseline_staged_rows` 实为"基准运行段内去重后的 native id 数"（实现按集合聚合），与 `baseline_unit_count`（registry 登记单元数）在 hirep（2021 vs 2825，原始文件含重复行）、yanqu（192 vs 195，3 个重复 id）、yinzhi（64 vs 739，unit_count 为 content.md 物理行数而封存 accepted=64）三源不同。数字本身正确且两口径并存正是 NOTE3 的要求，建议在 README/消费方文档中注明两字段定义，避免误读。
2. **轻微边界（预先存在，非本次修正引入）**：`_staged_native_ids` 对"目录存在但 staging/records.jsonl 缺失"的批目录静默跳过（L447–448）。多输入源有 `staging_registry_misaligned` 兜底；单输入源在该极端情形（封存文件丢失）会以空集为全集、产出 not_seen=全库的显眼数字而非报错。当前 24 个封存文件齐全，无影响。

## 六、总体判定（修复后）

**PASS** — 上一轮 4 项 NOTE 全部核验闭环：NOTE1（split("\n")）、NOTE2（嫌疑分桶改为基准后 sighting，hirep 强嫌疑 274→0、sighted_after 747）、NOTE3（baseline_staged_rows 并存，yinzhi=64）、NOTE4（unit_count 缺失结构化报错）。六源 not_seen/sighted_after/strong 三元组用完全独立的方法复算并逐元素命中再生成的证据 JSON；基准选择、只读性、库状态一致性全部成立。无影响输出的新缺陷；第五节两条残留注记属文档口径与极端边界，建议后续迭代处理。
