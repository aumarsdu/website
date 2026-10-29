# R2 独立复核记录 — t11_golden_full.json 期望值验证

- 复核者身份声明：本复核由独立 AI 复核代理执行，未参与 R2（golden 冻结）的实现工作；复核全程未读取 `search.py`、`generate_t11_golden_full.py`、`test_search*.py` 等实现/测试/生成代码，检索语义完全由 golden 文件的任务描述与数据库实际数据独立推导。
- 复核日期：2026-09-28
- 复核对象：`fixtures/t11_golden_full.json`（frozen_at=2026-09-28，corpus: candidate_full_1，records=7972，observations=9453，sources=6）
- 数据库访问方式（只读）：`/opt/homebrew/opt/postgresql@16/bin/psql -h 127.0.0.1 -p 55441 -U candidate_t03 -d candidate_full_1 -tA -c "SQL"`。全程仅执行 SELECT 类查询，未写入、未创建、未删除任何数据库对象。

## 一、独立推导的检索语义

基于任务说明与对数据库的直接探查（不依赖任何实现代码）：

1. 期望集合 = 满足条件的 `DISTINCT source_records.identity_key`（跨该记录所有 observation 的 payload business）。
2. 探查确认的关键事实：
   - `identity_key` 全局唯一：`count(*) = count(distinct identity_key) = 7972`，因此"去重后的 identity 集合"等价于"合格的 source_record 集合"。
   - 每条 source_record 至少有 1 条 observation（无孤儿记录）；observations 共 9453 条，其中 256 条 `order_key` 为 NULL（日期窗口过滤自然排除 NULL），全部挂在有效记录上。
   - `observations.payload_id` 全部非空；`content_payloads` 与 `content_payload_bodies` 一一对应（各 5181 条），无缺 body 的 payload。
   - `business` jsonb 键分布：title=4989、category=2989、institution=2859、instructor=2851、duration=2080、start_date=1747 等；**不存在 `price` 键**（这解释了 price_min 查询期望为 0）。
   - `order_key` 为 ISO 时间戳文本（32 字符，如 `2026-06-02T07:39:40.154226+00:00`），可按字典序做日期窗口比较。
3. 由语义推导的过滤规则：
   - `q`：`business ? 'title' AND business->>'title' ILIKE '%<q>%'`（包含匹配，ILIKE 英文大小写不敏感；`%`/`_` 视作字面量需转义）。
   - `category`：`business->>'category' = '<cat>'` 精确等值。
   - `source`：经 `source_records.source_id → sources.source_code` 等值匹配。
   - `instructor`：`business ? 'instructor' AND business->>'instructor' ILIKE '%<instructor>%'`。
   - `has_instructor=true`：`business ? 'instructor'`。
   - `date_from/date_to`：observation 级窗口 `order_key >= '<date_from>' AND order_key < '<date_to>+1天'`（date_to 当日闭区间）。
   - `price_min`：`business ? 'price' AND (business->>'price')::numeric >= <阈值>`。
   - 多条件为 AND；单条过滤查询中"任一 observation/payload 满足即合格"（记录级 EXISTS 语义）。
   - 分页/排序参数只影响返回切片，不改变合格集合（golden 中 q18/q19 的 expected_identities 即全集，与 q01/q03 同集合）。

## 二、复核方法

对每条查询，用自写 SQL 计算合格 identity 集合（统一模板）：

```sql
SELECT DISTINCT sr.identity_key
FROM source_records sr
JOIN sources s  ON s.source_id = sr.source_id
JOIN observations o ON o.source_record_id = sr.source_record_id
JOIN content_payload_bodies b ON b.payload_id = o.payload_id
WHERE <各查询条件>
ORDER BY 1;
```

随后与 golden 的 `expected_identities` 做逐元素集合 diff（排序后 `diff`），同时核对 `expected_total` 与集合元素个数一致。q13–q16 为零结果查询，双方集合均为空集。

## 三、逐条复核结论（20/20 全量覆盖）

| 查询 id | 过滤类型 | 我的 SQL 条件（摘要） | golden total | 我推 total | 集合对比 | 结论 |
|---|---|---|---|---|---|---|
| q01_ai | q 中文包含 | title ILIKE '%人工智能%' | 577 | 577 | 完全一致 | PASS |
| q02_ml | q 中文包含 | title ILIKE '%机器学习%' | 380 | 380 | 完全一致 | PASS |
| q03_market | q 中文包含 | title ILIKE '%市场%' | 503 | 503 | 完全一致 | PASS |
| q04_quantum | q 中文包含 | title ILIKE '%量子%' | 82 | 82 | 完全一致 | PASS |
| q05_ai_english | q 英文大小写不敏感 | title ILIKE '%AI%' | 424 | 424 | 完全一致 | PASS |
| q06_business_cat | category 等值 | category = '商科' | 1101 | 1101 | 完全一致 | PASS |
| q07_business_cat_exact | category 精确等值 | category = '计算机' | 389 | 389 | 完全一致 | PASS |
| q08_source_hirep | source 等值 | source_code = 'hirep' | 2768 | 2768 | 完全一致 | PASS |
| q09_source_domestic | source 等值 | source_code = 'jisi_future_domestic' | 1342 | 1342 | 完全一致 | PASS |
| q10_instructor_prof | instructor 包含 | instructor ILIKE '%Prof%' | 111 | 111 | 完全一致 | PASS |
| q11_has_instructor | 字段存在性 | business ? 'instructor' | 5576 | 5576 | 完全一致 | PASS |
| q12_date_window | order_key 窗口 | order_key >= '2026-06-02' AND < '2026-06-03' | 3840 | 3840 | 完全一致 | PASS |
| q13_price_floor | price 数值阈值 | price 存在且 ::numeric >= 100 | 0 | 0 | 双方空集（business 无 price 键） | PASS |
| q14_ai_and_cat | q+category 组合 | category='计算机科研' AND title ILIKE '%人工智能%' | 0 | 0 | 双方空集 | PASS |
| q15_nonexistent_word | q 无命中 | title ILIKE '%不存在的词xyz%' | 0 | 0 | 双方空集 | PASS |
| q16_nonexistent_category | category 无命中 | category = '不存在的分类' | 0 | 0 | 双方空集 | PASS |
| q17_percent_literal | LIKE 通配符转义 | title ILIKE '%100\%%'（% 作字面量） | 1 | 1 | 完全一致 | PASS |
| q18_ai_page2 | 分页（合格集合不变） | 同 q01 条件 | 577 | 577 | 完全一致 | PASS |
| q19_sorted_market | 排序（合格集合不变） | 同 q03 条件 | 503 | 503 | 完全一致 | PASS |
| q20_all | 无过滤全集 | 无 WHERE 约束 | 7972 | 7972 | 完全一致 | PASS |

说明：
- 每条均同时核对了 `expected_total` 与 `expected_identities` 元素个数相等、集合逐元素一致（排序后 diff 为空）。
- q18/q19 的 golden `expected_identities` 存的是全集（577/503），与分页/排序语义（只影响切片顺序与窗口）自洽，复核按全集对比。
- 复核过程中复核脚本自身出现过两次比对工具误报（jq select 用了短 id 未命中 golden 长 id），已定位为复核脚本问题并修正后重跑，与 golden 数据无关。

## 四、总体结论

**PASS** — 对 `fixtures/t11_golden_full.json` 全部 20 条查询（覆盖 q 中文/英文包含、大小写不敏感、category 精确等值、source 等值、instructor 包含、字段存在性、日期窗口、price 阈值、组合条件、负例、LIKE 转义、分页/排序、全集共 12 类过滤语义）用独立编写的直接 SQL 逐条重推 DISTINCT identity_key 集合：20/20 的期望计数与期望集合均与 golden 完全一致，未发现任何数量差异或集合差异。

冻结文件可信，可作为 T11 检索实现的 golden 基准使用。
