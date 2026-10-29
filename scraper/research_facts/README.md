# 科研素材事实输入包 (research_facts)

把课题海报、项目手册、网页资料整理成**同一套带证据的 JSON**。

每个字段都带：原文、来源位置、抽取方式、抽取可信度、宣传标记、核验状态。
六个规范字段，缺一个就留空；来源之间矛盾就双方都留；供应商宣传一律标记为
未核验，不会自动变成"已证实的事实"。

> 目的：写稿、做图、答疑时不必再反复拼接和核对同一批资料。
> 依据：父仓库 `2026-06-02-research-project-database-design.md`
> （第 6 章字段、8.2 字段风险分级、8.5 发布门禁、14.4 产出声明类型、4.4–4.7 导入映射与去重候选）。

---

## 1. 六个规范字段

| 字段 | 中文 | 风险 | 对应设计文档落点 |
| --- | --- | --- | --- |
| `project_title` | 课题名 | low | `canonical_projects.title` |
| `instructor` | 导师 | **high** | `instructors.name` |
| `start_date` | 日期 | low | `project_offerings.start_date_text` |
| `duration` | 周期 | low | `project_offerings.duration` |
| `suitable_audience` | 适合人群 | medium | `project_match_profiles.suitable_student_directions` |
| `output_description` | 产出描述 | **high** | `project_deliverable_claims.claim_text` |

风险分级来自设计文档 8.2：high 风险字段未经人工审核不得进入对外展示。

### 字段状态（五种，互斥）

| 状态 | 含义 | 是否带取值 |
| --- | --- | --- |
| `missing` | 任何来源都没提到 | 否 |
| `resolved` | 多源一致且都是平实陈述 | 是 |
| `resolved_with_promotional` | 内容一致，但夹带宣传表述 | 是（对外需过滤） |
| `conflict` | 来源之间不一致 | **否**，双方证据全留 |
| `promotional_only` | 只有宣传承诺 | **否** |

---

## 2. 一条记录长什么样

```jsonc
{
  "record_key": "demo-partner:external_id:RS-2027-0142",
  "identity": {
    "provider": "demo-partner",
    "external_id": "RS-2027-0142",
    "basis": "external_id",        // external_id | title | title_similarity | unresolved
    "review_required": false
  },
  "document_ids": ["demo-partner#RS-2027-0142", "poster-RS-2027-0142", "handbook-RS-2027-0142"],
  "fields": {
    "duration": {
      "status": "conflict",
      "risk_level": "low",
      "value": null,                        // 冲突时不选边
      "raw_text": null,
      "conflict_values": ["4周+2周", "8周"],
      "note": "来源之间不一致，未选择任何一方；双方证据均已保留。",
      "claims": [
        {
          "raw_text": "4周在线小组科研+2周论文指导",
          "normalized_value": "4周+2周",
          "normalization": { "rule": "duration_composite", "arithmetic": "none" },
          "locator": {
            "kind": "json_path",
            "document_id": "demo-partner#RS-2027-0142",
            "pointer": "$.raw.cycle",
            "detail": "profile=demo"
          },
          "extraction_confidence": "high",
          "evidence_kind": "factual",
          "verification_status": "unverified"
        }
      ]
    }
  }
}
```

`record_key` 形如 `{provider}:{依据}:{标识}`，可读、可 grep、可作下游主键。

---

## 3. 四类输入源

| 来源类型 | 适配器 | 输入 | 读取方式 |
| --- | --- | --- | --- |
| 网页资料 | `web_json` | 合作方爬虫产出的 `records.jsonl` | 按 **source profile（字段表）** 映射 |
| 课题海报 | `poster_ocr` | OCR 文本块 JSONL（含 bbox / conf） | 按几何位置合并左右栏，再按行匹配标签 |
| 项目手册 | `handbook_pdf` | PDF 文本层 JSONL（含 page / block） | 一行一块，要求 `标签：值` 显式分隔 |
| 开课时间表 | `table_csv` | CSV（含"依据"列） | 每行一个课题/批次，作为**独立来源**参与冲突判定 |

四类输入最终都变成同一种东西：**带定位的字段主张（FieldClaim）**。

### 输入契约（真实接线用）

海报 / 手册，每行一个 JSON 对象：

```jsonc
{
  "document_id": "poster-RS-2027-0142",      // 必填，一次运行内唯一
  "provider": "demo-partner",                 // 必填
  "external_id": "RS-2027-0142",              // 强烈建议：跨源归组的唯一依据
  "title_hint": "遥感无人机",                  // 可选：没有 external_id 时的身份依据
  "source_authority": "supplier_marketing",   // supplier_marketing | supplier_official | internal_note | unknown
  "image": "posters/RS-2027-0142.jpg",        // 海报：原图
  "pages": [{"page": 1, "blocks": [ … ]}],    // 手册：分页文本层
  "blocks": [{"text": "开课日期", "bbox": [40,120,130,30], "conf": 0.97}],
  "meta": {}
}
```

`bbox` 为 `[x, y, w, h]`（像素）；`conf` 为 OCR 引擎自评分，**是真实测量值**，
只用于给抽取可信度设上限，不参与任何推断。

**本包不跑 OCR，也不解析 PDF。** 上游产出这两个 JSONL 的方式见第 8 节，
把重活留在外面，抽取规则才能在没有几 GB 模型依赖的情况下被测试。

网页资料：沿用现有 `sou_crawler` 的 `records.jsonl`，无需改格式。

---

## 4. 怎么跑

```bash
cd scraper/research_facts

# 1) 预演：只读，不写任何文件。打印输入清单、规范字段、记录预览
python3 -m research_facts ingest --dry-run \
  --profile-file data/synthetic/web_profile.demo.json \
  --input data/synthetic/web_domestic.jsonl:web_json \
  --input data/synthetic/poster_ocr.jsonl:poster_ocr \
  --input data/synthetic/handbook_pdf.jsonl:handbook_pdf

# 2) 正式运行
python3 -m research_facts ingest --output-dir data/facts-demo \
  --profile-file data/synthetic/web_profile.demo.json \
  --input data/synthetic/web_domestic.jsonl:web_json \
  --input data/synthetic/poster_ocr.jsonl:poster_ocr \
  --input data/synthetic/handbook_pdf.jsonl:handbook_pdf

# 3) 看缺失 / 冲突 / 宣传三份报告
python3 -m research_facts report --output-dir data/facts-demo

# 4) 校验产物符合字段结构
python3 -m research_facts validate --output-dir data/facts-demo

# 5) 查某一个字段的全部证据（写稿时最常用）
python3 -m research_facts field --output-dir data/facts-demo \
  --record demo-partner:external_id:RS_2027_0142 --field duration

# 6) 记录人工审核 / 裁决冲突（详见第 6 节）
python3 -m research_facts review --output-dir data/facts-demo --record <record_key> \
  --field output_description --approve --reviewer "你的名字"

# 7) 导出写稿/做图用事实卡（详见第 7 节）
python3 -m research_facts export --output-dir data/facts-demo --record <record_key>

# 8) 打印 web 来源字段表（真实接线时看这里）
python3 -m research_facts profiles

# 9) 接线自检：拿到合作方任何导出，先看可映射性与覆盖率（不落盘）
python3 -m research_facts inspect \
  --profile-file data/profiles/zhongke_schedule.csv.json \
  --input "../中科/中科课题开课时间汇总-2026-09-23.csv:table_csv"

# 9) 开课时间表 CSV（真实来源，第 9 节有实跑结果）
python3 -m research_facts ingest --output-dir /tmp/rf-zk \
  --profile-file data/profiles/zhongke_schedule.csv.json \
  --input "../中科/中科课题开课时间汇总-2026-09-23.csv:table_csv"

# 7) 直接吃现有合作方产出（无需改格式）
python3 -m research_facts ingest --output-dir /tmp/rf-sou \
  --profile sou_domestic \
  --input "../集思未来/output/incremental/20260928/domestic/processed/records.jsonl:web_json"
```

`--input` 的 `路径:来源类型` 后缀是**必填**的。三个适配器都读 `.jsonl`，
靠猜会把手册当海报读而且不报错——所以这里强制声明。

其他参数：`--max-records`（每个输入文件文档数上限）、`--identity-threshold`、
`--strict-identity`（禁用标题相似度归组）、`--review-file`（审核文件位置）、
`--verbose`。
网络参数（`rate-limit` / `timeout` / `retries`）已在 `Settings` 中但当前无消费方，
因为本包不联网，见第 7 节。

### 测试

```bash
python3 -m unittest discover -s tests -t .   # 零依赖，212 例
# 或（装了 pytest 的话）
python3 -m pytest -q
```

212 个用例，全部离线，只吃 `data/synthetic/` 里的合成资料。

---

## 5. 输出文件

| 文件 | 回答什么问题 |
| --- | --- |
| `facts.jsonl` | 每个课题的六个字段 + 全部证据 |
| `evidence_index.jsonl` | **证据索引**：一行一条主张，带文档、来源类型、定位、原文哈希、抽取可信度 |
| `documents.jsonl` | 读进来了哪些源文档、来源权威等级、原文 sha256 |
| `missing_report.json` | 缺什么（按字段）＋ 存在但不可用的（冲突 / 仅宣传） |
| `conflict_report.json` | 哪里矛盾，**双方原文与定位**，`resolution: manual_review_required` |
| `promotional_claims_report.json` | 哪些是宣传承诺，各需要什么免责声明 |
| `quality_summary.json` | 覆盖率、来源分布、未映射源字段、错误分类、内容摘要 |
| `facts.public.jsonl` | 对外投影：高风险字段进待审队列，宣传表述已过滤 |
| `rejected_candidates.jsonl` | **被拒收的标签匹配**：看到了什么、为什么没采用 |
| `duplicate_candidates.json` | **重复候选**（只生成、绝不自动合并），标注可否合并与不可得信号 |
| `cohort_groups.json` | **同名不同批次**：同一课题的各次开课，写稿时据此指明批次 |
| `run_manifest.json` | 运行元信息：输入哈希、计数、`content_digest`、审核与裁决应用情况 |
| `reviews.json` | 人工审核决定（`review` 子命令写入，本包不自动生成） |

`facts.public.jsonl` 里每条记录带两个标记：

- `ready_for_review`：写稿所需资料齐全且无冲突；
- `publishable`：门禁全过（含高风险字段已过审）。

若某字段整体都是宣传，对外投影会直接移除它并记入
`fields_dropped_as_purely_promotional`，而不是输出一个空串。

---

## 6. 人工审核与冲突裁决

### 6.1 审核：解锁字段能否对外

机器不能把供应商陈述变成已证实事实，这一步必须由人来做，并留下痕迹。

机器不能把供应商陈述变成已证实事实，这一步必须由人来做，并留下痕迹。

```bash
# 1) 先看这个字段现在是什么状态、有什么可审的
python3 -m research_facts field --output-dir data/facts-demo \
  --record demo-partner:external_id:RS_2027_0311 --field output_description

# 2) 记录通过（或 --reject 否决、--reset 撤销）
python3 -m research_facts review --output-dir data/facts-demo \
  --record demo-partner:external_id:RS_2027_0311 --field output_description \
  --approve --reviewer "军亮" --note "已与官网邮件核对产出清单"

# 3) 看全部决定
python3 -m research_facts review --output-dir data/facts-demo --list

# 4) 重跑 ingest 生效（审核文件是输入，会记进 manifest 的 sha256）
python3 -m research_facts ingest --output-dir data/facts-demo \
  --profile-file data/synthetic/web_profile.demo.json \
  --input ... （同第 4 节）
```

### 6.2 裁决：冲突时选哪一方

冲突字段不能靠审核解锁（没有"待审的值"，只有几个互斥的说法）。需要单独裁决：

```bash
# 1) 先看各方说法
python3 -m research_facts review --output-dir data/facts-demo \
  --record demo-partner:external_id:RS_2027_0142 --field duration --show-sides

# 2) 裁决：必须逐字指定采用哪一方的原话
python3 -m research_facts review --output-dir data/facts-demo \
  --record demo-partner:external_id:RS_2027_0142 --field duration \
  --adjudicate --choose "8周" --reviewer "军亮" --note "手册与海报一致，网页为旧口径"

# 3) 重跑 ingest 生效
```

裁决后字段状态变为 `resolved`，并带 `resolution: "human_adjudication"`。
**故意不新增状态值** —— 加一个状态会改动每份报告的统计口径，而那些口径下游已经在用。
被判舍弃的一方**一条证据都不删**，`conflict_values` 也照旧保留。

裁决的三条硬约束（防止它变成越权通道）：

1. **只能选来源真说过的原话。** `--choose` 必须是某一方展示值逐字一致的值，
   自创值（如"10周（综合推断）"）会被 CLI 直接拒绝。
2. **纯宣传的一方不可选。** 只含宣传表述的那一侧无法被裁决采用。
3. **证据一变即失效。** 裁决与审核共用同一套证据指纹机制。

### 6.3 合并：人工决定把两个身份并成一个

```bash
# 1) 提案：只提交"可比字段全部一致"的候选，未署名则不会生效
python3 tools/propose_merges.py \
  --inputs "<file1>:web_json" "<file2>:table_csv" \
  --profile-file data/profiles/zhongke_schedule.csv.json \
  --out data/profiles/dup_merges.json --reviewer "军亮"

# 2) 应用：ingest 读合并决定文件
python3 -m research_facts ingest --output-dir /tmp/rf-x --merge-file data/profiles/dup_merges.json …
```

合并实现为**身份并集**而非记录改写：两个记录块在归组阶段合成一块，之后
字段逻辑照常走。所以"同一实体、事实有分歧"仍会报冲突 —— 判定两个记录是同一个
东西，并不意味着它们的事实一致。

四道闸：

1. **只有可比字段全一致才可提案**（`is_mergeable`）。真实数据里 564 对候选里
   **560 对只差一个开课日期** —— 那是同一课题的不同批次，合并会抹掉真实差异。
2. **未署名不生效**。提案工具不填 `--reviewer` 就写出的决定会以
   `awaiting_reviewer` 跳过。
3. **证据指纹绑定**。指纹集合化（重复陈述不改变指纹），重新抓取后证据一变，
   合并自动 `evidence_changed_since_decision` 失效。
4. **一方不存在即跳过**（`one_side_absent`），不会静默忽略。

### 6.4 三条设计要点

1. **审核绑定的是"这一份证据"。** 每条决定都记一个证据指纹（选中值 +
   每条主张原文 + 来源文档的哈希）。重新抓取后内容一变，指纹不匹配，
   该决定自动变成 `stale`，字段退回待审队列。
   没有这一层，审核过"示例导师甲"就会在页面换成别人之后继续生效。
2. **审核不解除政策边界。** 审核只解锁"字段可否对外"；
   `prohibited_claim`（保录/100%/保证发表）的句子在任何情况下都不会进入对外文案。
3. **无可审之物不可审。** `missing` / `promotional_only` 的字段直接拒绝记录审核；
   `conflict` 要走上面的裁决通道。

---

## 7. 导出事实卡（写稿 / 做图 / 答疑直接用）

JSON 是给机器看的；写稿的人需要另一种形态。`export` 渲染成带证据的事实卡：

```bash
# 内部事实卡：字段、取值、状态、每条原文与来源位置、宣传标记 ⚠️、证据清单
python3 -m research_facts export --output-dir data/facts-demo \
  --record demo-partner:external_id:RS_2027_0142

# 对外版：已过滤宣传、含审核结论与未过门禁清单
python3 -m research_facts export --output-dir data/facts-demo \
  --record demo-partner:external_id:RS_2027_0311 --public

# 全部记录导出成文件 / 结构化 JSON
python3 -m research_facts export --output-dir data/facts-demo --out cards.md
python3 -m research_facts export --output-dir data/facts-demo --format json
```

卡片里每个字段都写清四件事：**用了哪个值、为什么用、还有谁说了什么、
每句话来自哪里**。冲突字段会单列"各方说法（均未采用）"并提示写稿前需人工确认；
缺失字段写成"来源未给出（未做任何推断补写）"，而不是留空让人误以为查过了。

---

## 8. 验收对照

| 验收项 | 实现方式 | 测试 |
| --- | --- | --- |
| 未知字段不补写 | 无证据 → `missing` + `value: null`；未映射的源字段只进 `unmapped_source_keys` 报告 | `TestCriterion1*` |
| 矛盾资料保留双方证据 | `conflict` 不选边，`claims` 全留；简称/全称、条目包含关系各有明确容差规则 | `TestCriterion2*` |
| 重复导入结果稳定 | 行序、取值选择、身份标题全部按显式规则确定；`content_digest` 只覆盖事实内容 | `TestCriterion3*`（含 6 种输入顺序排列） |
| 供应商宣传不自动当已证实事实 | 逐句分类 `factual` / `conditional_claim` / `prohibited_claim`；`verification_status` 恒为 `unverified`；仅宣传字段不出值；对外投影过滤宣传句 | `TestCriterion4*` |

### 明确的"不推断"边界

- `4周在线小组科研+2周论文指导` → 归一为 `4周+2周`，**不加成 6 周**（`arithmetic: "none"`）。
- `2027-01-08T16:00:00.000Z` → 取字面日期 `2027-01-08`，**不做时区换算**（UTC+8 已是 9 号）。
- `2027年9月` → `2027-09`，`day: not_stated`，**不补成 9 月 1 日**。
- `报名截止：2026-12-01` → **不是** `start_date`，故意不映射（截止与开课是两个事实）。
- `副教授：张三` → 标签匹配到 `副教授`；`教授` 不会命中词中间的 `副教授`。
- 来源里没有导师名字 → 导师就缺失，**不会**从简介里猜。
- 课题名/导师是**名称类字段**：即使名字里带营销词也不丢取值
  （项目名可能真的叫"冲击QS前30"），但宣传标记照样记录、对外照样过滤。
  不能被自动当成事实的是**承诺**，不是**名称**。

### 宣传识别必须用真实数据校准

话术表（`claims.py`）是按真实导出校准过的。第一版有三条把学术常用词
误判成营销：**"检索"**（检索增强生成 RAG）、**"福利"**（社会福利）、
**"冲击"**（作为研究对象的冲击）；"爆款"也是合法的传播学选题。
误判的后果是真正的承诺被噪声淹没，所以这些样本已固化为
`TestAcademicVocabularyIsNotMarketing` 回归集。
**加任何新话术，都要重跑一遍合作方导出并人工读一遍
`promotional_claims_report.json`。**

---

## 9. 真实数据校准记录（重要）

合成 fixture 只能证明规则自洽。真实导出推翻了两条假设，这部分改动是**必须**的：

### 9.1 海报不是"标签：值"版式 —— 曾有 46% 的主张是编造的

在 195 张真实海报（盐趣，PP-OCRv6 已识别）上实跑，第一版抽出 98 条主张，
其中 **49 条是编造的**：

| 误判 | 机制 |
| --- | --- |
| `教授` → `招生中` | 海报是**表格版式**，表头"教授"与右邻单元格"招生中"被行合并拼成了"标签：值" |
| `项目周期` → `开班人数` | 同上，表头行 |
| `项目名称` → `教授背景 招生状态` | 4 格表头行被拆成 3 格后，标签恰好成了首格 |

几何上无法区分真假：`开课时间 | 2026-09-19`（真）与 `教授 | 招生中`（假）
形状完全相同。真正能分开的是三条规则，已全部落地：

1. **行模式下标签必须是该行最左格**（`label_must_lead_row`）。真标签值对的首格是标签；
   表头行永远不是。
2. **值必须能通过该字段的类型校验**（`TYPED_FIELDS`）。`开班人数` 归一不出周期 → 拒收，
   记入 `rejected_candidates.jsonl`，不静默丢弃。
3. **行模式收窄标签词表**：裸 `教授/讲师/教师` 在真实海报里作为**取值**（"终身正教授"）
   远比作为标签常见，改由复合标签 `授课教授/指导老师/导师` 承担；手册的行内匹配不受影响。

复测结果：**195 张 → 43 条主张，全部是归一化成功的真实日期，零编造**。

代价是刻意的欠抽取：这张模板族的课题名/导师/周期/适合人群/产出描述基本抽不到。
理由写在下面的"已知限制"里 —— 海报模板族需要单独的字段表，那是需要你拍板的事。

### 9.2 海报模板普查：4 个模板族，只有 2 个值得接

对全部 195 张盐趣海报（该供应商的 100%）跑普查，按"位于行首且未被规则排除的标签集合"分簇：

| 模板族签名 | 海报数 | 占比 | 抽出字段 | 有大数字 | 机构+职称行 |
| --- | ---: | ---: | --- | ---: | ---: |
| `<无行首标签>` | 150 | **76.9%** | 无 | 99% | 56% |
| `开课时间` | 43 | 22.1% | start_date 43 | — | — |
| `项目名称` | 1 | 0.5% | 无 | — | — |
| `项目名称+项目周期` | 1 | 0.5% | 无 | — | — |

对占 77% 的"统计条"族逐项量化后，只有一项能诚实地映射：

| 海报上的内容 | 占比 | 能否映射 | 判断 |
| --- | ---: | --- | --- |
| `10 封教授网申推荐信+1 篇英文会议论文辅导` | **100%** | ✅ 产出描述 | 已接（形状规则） |
| `3周 线上直播｜6周 论文辅导｜6次 产学研导师课` | 99% | ❌ 周期 | 是交付阶段计数，不是周期 |
| `法学院正教授` | 56% | ❌ 导师 | 是机构不是姓名 |
| 裸日期块 | 98% | ❌ 日期 | 不知是开课/首课/结课 |

因此只加了一条**只喂产出描述**的形状规则
（`\d+ 封/篇/份` + 紧邻成果物词），标 `extractor: deliverable_shape`、
可信度 `low`、并经宣传识别标为 `conditional_claim`：

```
195 张 → 191 条证据：43 条真实日期 + 148 条"已标记的宣传承诺"（不作事实用），零编造
```

**故意不做**：把 `3周/6周` 读成周期、把 `法学院正教授` 读成导师姓名、把裸日期读成开课日期。
这三者都是猜测，正是本包拒绝的事。模板签名写进每份文档的 meta，
所以"海报读到了但这个模板族不可映射"这件事本身是可见的，不会被静默吞掉。

### 9.3 HIREP 开课时间表的粒度是 (课题ID, 产品包ID)

同一课题有 3 个产品包、3 个不同开课日。只按 `课题ID` 归组会产出 **322 处假冲突**。
因此表档支持 `id_columns` 复合主键，一行 = 一个批次。修正后 1604 行 → 1604 条记录，零假冲突。

### 9.4 已在真实数据上验证的来源

| 来源 | 数据 | 结果 |
| --- | --- | --- |
| 集思未来 domestic | `processed/records.jsonl` 255 条 | 255 记录 / 1520 证据 / 0 错误 |
| 中科 课题开课时间汇总 | CSV 2830 行 | 2830 记录，课题名·导师·日期 100% |
| HIREP 当前公开课题 | CSV 1604 行 | 1604 记录，复合主键后零假冲突 |
| 中科 网页档案 | 400 个 `details.json` | 400 记录，课题名 100%、导师 398/400 |
| 盐趣 海报 | 195 张已 OCR 海报 | 191 条证据，零编造（见 9.1/9.2） |
| 三来源重复候选 | 1,855 条记录 | 564 对同源内重复，0 对跨供应商（见 9.5） |

### 9.5 跨来源重复候选：只生成，不合并

按设计文档 4.7 的权重与阈值（0.75 高置信、0.55 起报）实现，但**只采集六个字段**，
机构/分类/共用链接等信号拿不到，如实列进 `unavailable_signals`：

```
三来源 1,855 条记录 → 2.4s
同源内候选 564 对 | 跨供应商候选 0 对 | 最高可得 0.95（跨供应商上限 0.60）
```

两个结论：

> 更正一版：上一轮我把它说成"564 对同源重复"是**错的**。逐对比对字段后，
> 564 对中 **560 对开课日期不同**（2026-11-06 vs 2027-02-12），那是同一课题的
> 不同批次，不是重复；**真正全部一致的只有 4 对**（全在中科：同标题、同导师、
> 同开课日，不同课题ID —— 源侧数据重复）。已按第 6.3 节只合并了这 4 对
> （1855 → 1851 条），其余 560 对明确拒绝合并，并已加 `is_mergeable` 判定作为
> 长期闸门。

1. **中科源侧有 4 对真实重复**已合并。其余同名课题是不同批次，按设计文档 4.7
   不自动合并，留在候选里等运营判断。
2. **三家课题目录在课题层面本就不重叠**（跨供应商 0 候选）。跨供应商归并在当前
   数据上不是瓶颈；若将来目录重叠，因为缺机构/分类信号，候选分数达不到 0.75
   高置信线，只能落 0.55–0.75 常规候选带人工复核。

### 9.6 同名不同批次：不合并，但必须看得见

402 组课题组、涉及 981 条记录，最多的一组有 **11 个批次**（量化金融…）。这在写稿
时是个真实的坑：同一课题排期不同，顾问很容易写错批次。

按第 9.5 的建议取方案 (a)：**不引入"批次"实体**，批次差异已由 `start_date`
表达；只增加一份分组报告 `cohort_groups.json`，按课题名分组列出各次开课与
`record_key`，每组标 `resolution: keep_separate`。写稿与答疑时据此指明期次即可。

分组已接进两处产物，写稿时不必再翻报告：

- **内部事实卡**：`# 标题` 下加一行
  `⚠ 同一课题共 **5 期**，开课日期：2026-09-07、2026-10-17　写稿时务必指明期次`
  （"5 期"与"2 个不同开课日"是两件事，所以分开写，不写成"5 个批次：2 个日期"）
- **对外投影**：`批次：共 5 期，最近一期 2026-10-17` —— 只给数量与最近一期，
  不展开全部历史，避免对外页面暗示只有一次开课。

报告另有两段，都**只作提示、不改任何语义**：

- `related_groups`：**疑似同一课题的不同写法**。分组键是去标点空格后的精确匹配，
  所以**过度分组不可能发生**，真实风险是欠分组。限定到"≥2 期的课题组"后实测
  只有 **1 对**（`--` 与 `——` 的写法差异，相似度 0.963）；此前报的 36 对是在
  全部记录里测的，其中绝大多数已由 `duplicate_candidates` 覆盖。链接条目一律
  带 `merged: false`，不改 `record_key`、不重新分组。
- `same_date_sibling_groups`：**组内存在同日记录**，那不是期次而是疑似重复，
  实测 55 组。这份清单是合并闸门的输入，不自动处理。
- 另有 `subject_signature`，标题集变了它就变，便于察觉关联关系随源数据漂移。

### 9.7 接线自检：不用先要到样本

`inspect` 子命令给一份候选导出就能回答两个问题，**只读不落盘**：

```bash
$ python3 -m research_facts inspect \
    --profile-file data/profiles/zhongke_schedule.csv.json \
    --input "../中科/中科课题开课时间汇总-2026-09-23.csv:table_csv"
接线自检：mappable_with_gaps：3/6 个字段有数据，3 个待补来源
  字段覆盖率：
    - 课题名(project_title) 100%  可用 300 / 冲突 0 / 仅宣传 0
    - 导师(instructor)     100%  可用 300 / 冲突 0 / 仅宣传 0
    - 日期(start_date)     100%  可用 300 / 冲突 0 / 仅宣传 0
    - 周期(duration)         0%  可用   0 / 冲突 0 / 仅宣传 0
    …
```

判定分四档：`unusable`（输入读不了）→ `unmappable`（六字段全空）→
`partially_mappable`（≥4 个空）→ `mappable_with_gaps` / `mappable`。
并输出 `unmapped_source_keys` —— 那就是**字段表的待补清单**，不用再凭印象猜。
另有 `subject_signature`，用来判断两个导出是否同一批课题目录。

这解掉了"真实接线需要少量脱敏样本"里的大部分阻塞：先拿手上任何一份导出跑
`inspect`，不可映射就尽早放弃，可映射就直接照着 `unmapped_source_keys` 写字段表。

**CSV 源的待补清单**（原先只有 web_json 会算，CSV 完全没有）：HIREP 那张 15 列表
映射 3 列后，报告会点名 12 个未消费列，并把其中 7 个**形似某字段**的列单独提出：

```
⚠ 未映射但形似某字段的列（请确认是有意排除还是待补）：
  · 首课时间           → 形似 start_date/duration × 400
  · 讲授课开始时间      → 形似 start_date × 400
  · 研究课开始时间      → 形似 start_date × 400
  · 第二阶段开始时间    → 形似 start_date × 400
  · 公开列表核对时间(UTC) → 形似 start_date × 400
```

这张表里同时有 `开课时间（日期）`、`首课时间`、`讲授课开始时间`、`研究课开始时间`
—— 四个都是日期，只有一个是"开课日期"。静默留下三个不映射，正是需要被看见的
那个决定。**形似提示只是提问，不是映射**：命中也只是提示，不阻断。

**口径声明**（`semantics`）：表档可给每个字段附一句源方口径说明，例如 HIREP 写明
"取自 开课时间（日期），依据列注明为 firstCourseBeginTime；同表的讲授课/研究课
分段起止是排期而非开课日期，故不映射"。口径进证据 detail 与 `inspect` 输出，
使它成为可核对的显式声明，而不是靠人记得。

### 9.8 中科"海报"是封面配图，不值得 OCR

中科归档里的 `haibaoPic.jpg` 看着像海报，抽样 6 张实跑发现 **4 张是纯照片**
（0–1 个文字块），1 张是真设计海报，1 张部分。也就是约 5/6 是 AI 生成的封面图，
不含任何字段数据。

全量 1,594 张按 mobile 模型 4s/张约需 1.8 小时，而可用信息接近于零 ——
中科的字段数据在 `details.json` 里（已实测：400 条，课题名 100%、导师 398/400）。
**结论：不做全量 OCR。** 若日后需要，用 `tools/survey_poster_templates.py`
抽样 100 张即可，不必全量。

---

## 10. 合规与边界

- **本包不发起任何网络请求。** 只读本地文件。真实抓取仍由各合作方
  `sou_crawler` 负责（它们已有诚实 UA、限速、robots 门禁、安全重试）。
- **数据最小化**：只提取上表六个字段，不采集学生个人信息、不抓取账号页。
- **宣传与事实分离**：`prohibited_claim` 不得进入销售话术与对外展示；
  `conditional_claim` 必须附条件与免责声明。
- **资产权利**：本包不下载图片/PDF，只记录来源 URL 与 sha256，
  展示授权由发布门禁另行处理。
- **去重只做候选**：标题相似度归组会标 `review_required: true`，
  遵循设计文档 4.7「只生成候选，不自动合并」。

---

## 11. 真实接线

### 10.1 需要你提供的两样东西

1. **少量脱敏样本**：每个来源 2–3 份（海报图 / 手册 PDF / 网页详情 JSON），
   覆盖"字段齐全 / 字段缺失 / 来源互相矛盾"三种情况。
2. **现用字段表**：合作方返回的字段名与含义。不用写代码——写成 JSON 传给
   `--profile-file` 即可：

```json
{
  "name": "partner_a",
  "provider": "partner_a",
  "source_authority": "supplier_official",
  "external_id_paths": ["$.data.topicId", "$.data.id"],
  "title_paths": ["$.data.title"],
  "fields": {
    "project_title":      ["$.data.title"],
    "instructor":         ["$.data.teacherName", "$.data.professor"],
    "start_date":         ["$.data.startTime"],
    "duration":           ["$.data.durationText"],
    "suitable_audience":  ["$.data.fitStudents"],
    "output_description": ["$.data.deliverables"]
  }
}
```

字段留空即"该来源不提供此字段"，运行时会如实记为缺失。
自动检测顺序里，**你提供的字段表优先于内置推断**。

内置已有 4 份档：`sou_domestic` / `sou_overseas` / `zhongke` / `generic`。
其中 `zhongke` 故意只映射课题名与导师：它的开课日期在另一份 CSV 里，
不确认口径就不映射，宁可缺失也不猜。

`sou_domestic` 已在真实导出上验证过：

```
集思未来 domestic processed/records.jsonl  255 条
  → 255 条记录 / 1520 条证据 / 0 错误
  课题名 100%  导师 100%  周期 100%  产出描述 100%  适合人群 100%  日期 245/255
  宣传识别：255 条产出描述含推荐信/检索/发表承诺 → conditional_claim（可用但标记）
  课题名误判：0
```

### 10.2 海报 OCR 结果怎么来

复用 `scraper/盐趣/ocr_posters_ppocrv6.py`（PaddleOCR）或任意引擎，
把结果转成本包的块格式即可：

```python
{"document_id": "poster-<hash>", "provider": "...", "external_id": "...",
 "image": "relative/path.jpg", "source_authority": "supplier_marketing",
 "blocks": [{"text": b.text, "bbox": list(map(int, b.box)), "conf": b.conf}
            for b in ocr_result]}
```

### 10.3 手册 PDF 文本层怎么来

```python
import fitz  # pymupdf
doc = fitz.open("handbook.pdf")
pages = [{"page": i + 1,
          "blocks": [{"text": page.get_text("text")}]}   # 或按 block 切分保留 bbox
         for i, page in enumerate(doc)]
```

### 10.4 布局变了怎么办

抽取规则全部写在数据里，不埋在选择器深处：

| 变化 | 改哪里 |
| --- | --- |
| 海报/手册换了标签措辞（如"开课时间"→"启动日期"） | `research_facts/labels.py` 的 `LABELS`，加一个词 |
| 出现了全新的字段 | 先在 `config.py` 的 `CANONICAL_FIELDS` 立项（含风险等级与设计文档落点），再在 `LABELS` 加标签、在字段表加路径 |
| 合作方改了 JSON 字段名 | 只改字段表 JSON；`quality_summary.json` 的 `unmapped_source_keys` 就是待补清单 |
| 新的宣传话术 | `claims.py` 的 `CONDITIONAL_PATTERNS` / `PROHIBITED_PATTERNS`，然后按第 6 节校准 |

改完跑一遍 `python3 -m unittest discover -s tests -t .`，
标签类断言会立刻告诉你有没有误伤别的标签。

---

## 12. 已知限制

1. **只有六个字段。** 来源里其余字段一律不映射、不猜测。
2. **周期不做算术。** `4周+2周` 不会被加成 `6周`；若业务需要总周期，
   要在下游显式计算并说明口径。
3. **冲突不自动裁决。** 报告只负责把双方证据摆齐，判定权在人。
4. **审核是本地的、单人的。** `reviews.json` 只记录决定与指纹，
   没有多人协作、权限分级、工作流状态机；`verification_status` 在
   事实记录里恒为 `unverified`，只有对外投影会标 `reviewed`。
5. **身份归组有猜测成分。** 标题相似度只是候选，会标 `review_required`；
   补齐 `external_id` 后 `record_key` 会变，需要一次迁移。
6. **多行取值靠几何。** 海报上标签行之后的续行按位置接续，
   若版面中间夹了未识别的段落，可能被并进来——`raw_text` 与 `locator`
   保留了完整范围，便于人工核对。
7. **时间字段不建模口径。** 开课 / 报名截止 / 项目周期是三件事，
   本包只处理开课日期与周期，其余留待后续按 `project_offerings` 建模。
8. **单来源无冲突可查。** 只吃一个来源时 `conflict` 恒为 0，
   跨源矛盾要等第二份资料进来才暴露。
9. **不联网。** 见第 10 节。
10. **海报模板族尚未接线。** 营销型海报是"大数字 + 说明"的版式（`3周 线上直播`｜
    `6周 论文辅导`｜`6次 产学研导师课`），不是"标签：值"。当前只可靠抽出海报上
    明确带标签的字段（如 `开课时间`）。要把这类模板接上，需要为每个模板族各写一份
    字段表（与 web profile 同样的数据化做法）——**这是下一步需要你确认的事**。
11. **CSV 是一行一个批次。** 表档的行粒度取决于合作方的表，不自动推断；
    `id_columns` 写错会产生成片假冲突，接线时要先确认表的粒度。

---

## 13. 目录

```
research_facts/
  research_facts/
    config.py         规范字段注册表、来源类型、运行参数
    schema.py         Locator / FieldClaim / FieldState / ProjectFactRecord
    labels.py         标签表与行/行组扫描（含边界保护）
    extract.py        命中 → 主张；抽取可信度策略
    normalize.py      值归一化（只重排，不推断）
    claims.py         宣传话术识别与对外过滤
    merge.py          跨源归组 + 字段状态判定
    reports.py        证据索引、缺失、冲突、宣传、质量汇总
    projections.py    对外投影与发布门禁
    review.py         人工审核与冲突裁决决定 + 证据指纹
    dedup.py          跨来源重复候选（只生成候选，绝不自动合并）
    merging.py        人工合并决定 + 证据指纹 + 身份并集
    wiring.py         接线自检：可映射性、覆盖率、字段表待补清单与口径
    exporter.py       事实卡渲染（markdown / json）
    pipeline.py       读入 → 合并 → 报告 → 落盘
    cli.py            命令行
    storage.py        确定性 JSONL/JSON 读写与内容摘要
    utils.py          文本、哈希、JSONPath、脱敏
    adapters/
      base.py         适配器契约
      textblock.py    海报 OCR / 手册 PDF
      web_json.py     网页资料 + source profile（字段表）
      csv_table.py    开课时间表 CSV + 表档（支持复合主键）
  data/synthetic/     合成资料集（4 类源，含冲突/宣传/缺失样本）
  data/profiles/      真实来源字段表（中科/HIREP 开课时间表）与合并决定文件
  data/real/          真实数据实跑产物（海报 OCR、网页档案、模板普查报告）
  tools/              五个只读脚本（OCR→契约、CSV→契约、档案→JSONL、模板普查、合并提案）
  data/facts-demo/    一次完整运行的产物
  tests/              212 个用例
```
