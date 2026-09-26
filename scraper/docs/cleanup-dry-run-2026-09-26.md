# scraper 冗余数据清理清单（2026-09-26）

> **执行状态（2026-09-26 更新）**：Tier A 六项已全部删除并逐项验证（A3/A4 因并行
> 命令工作目录问题首次未删，已用绝对路径重删并复核）。工作区 115GB → 101GB
> （约 14GB，部分空间待 APFS 回收）。Tier B / Tier C 仍未执行，等待安排。
> asidan A6：前批次 20 个独有文件已迁入 `20260816T025031Z_102dea88/`（3091→3111 文件），
> `20260816T024956Z_ab9521da/` 整目录删除；seed_intel.sqlite 与 silver/gold 无引用。

> **文件夹归一（同日追加，经授权）**：参照集思未来模式（顶层 = 网站顶层分类）：
> - `HIREP/Poster/`：根级 人文/商科/工科/理科 四目录经 `diff -rq` 验证为交付目录
>   `HIREP海报-2026年7月10日/` 内同名目录的子集（人文/商科/理科逐字节一致；
>   工科交付侧多 2 个 `Finish_海报-*.jpg` 新文件），已删除（≈3.1G）；
>   6 代 `output_pbl_merged_unique_*` 与 `_reports` 移入 `Poster/_intermediate/`（未删除）。
>   顶层现为：交付目录 + 同名 zip（3219=3219 文件吻合）+ `_intermediate/`。
> - `中科/Poster/`（中方课题/双教授课题 + _classification）、`盐趣`（学科四分类）、
>   `集思未来/poster`（by_project_type 与 by_subject 双轴，见 _organization_summary.json）
>   已符合网站顶层分类模式，未改动。

原始校验记录如下。

硬链接警告：`集思未来/output/organized_by_site/`（341 个硬链接共享同一 74MB PDF）与
`中科/output/`（cache↔site 硬链接）存在硬链接共享。移动/复制这些目录必须用
`rsync -H` / `cp -c`，`du -sh` 的名义值会重复计数。

---

## Tier A：已验证纯重复，删除其中一份零信息损失

| # | 删除目标 | 体积 | 冗余原因与校验证据 | 保留的另一份 |
|---|---|---|---|---|
| A1 | `盐趣/盐趣海报-2026年9月4日/` | 2.5G | 与顶层 `盐趣/Poster/` 逐字节一致（`diff -rq` 通过，388 文件） | `盐趣/Poster/` + 同名 zip |
| A2 | `集思未来/poster/` 下 9 个顶层分类目录（2026暑期线下营地项目、Astra 1v1、PBL小组科研标准版、专业选修课程、全球华人导师-香港、全球在研、实验室RA项目、研助起航计划、职业通途计划） | 3.1G | 与 `poster/集思未来-海报-2026年7月10日/` 内同名目录逐字节一致（`diff -rq` 通过，差异仅 `.DS_Store`） | 交付目录 + 交付 zip（文件数 1641=1641） |
| A3 | `HIREP/HIREP-2026年9月2日/` | 2.7G | 与同名 zip 内容一致（文件数 1956=1956）；目录内还混有 215M `_download_cache` | `HIREP-2026年9月2日.zip`（2.6G） |
| A4 | `中科/中科-2026年9月2日/` | 0.77G | 与同名 zip 内容一致（文件数 1401=1401） | `中科-2026年9月2日.zip`（741M） |
| A5 | `盐趣/盐趣-海报-2026年7月10日.csv` | 1.6M | 与 `盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv` 三份同尺寸拷贝之一 | 保留 `盐趣7-9月项目合集/` 内一份 |
| A6 | `asidan/data/bronze/raw_assets/20260816T024956Z_ab9521da/` 中与 `20260816T025031Z_102dea88/` 重名的 1962 个文件 | ≈3.5G | 文件名为 URL 哈希，同名即同源；抽样 8 对 `cmp` 全部逐字节一致；silver/gold 无任何批次路径引用 | 后一批次（3091 文件）完整保留；前一批次独有的 ~20 文件建议先移入后一批次 |

**Tier A 小计：约 12.5 GB**

```bash
# A1
rm -rf "盐趣/盐趣海报-2026年9月4日"
# A2
cd 集思未来/poster && rm -ri "2026暑期线下营地项目" "Astra 1v1" "PBL小组科研标准版" \
  "专业选修课程" "全球华人导师-香港" "全球在研" "实验室RA项目" "研助起航计划" "职业通途计划"
# A3 / A4
rm -rf "HIREP/HIREP-2026年9月2日" "中科/中科-2026年9月2日"
# A5
rm "盐趣/盐趣-海报-2026年7月10日.csv"
# A6（先移出前批次独有文件再清重叠）
```

## Tier B：历史快照 / 旧基线（建议外移冷存储，是否删除需业务确认）

| 目标 | 体积 | 说明 |
|---|---|---|
| `中科/output/site_before_taxonomy_20260707` + `site_before_keyword_20260707` | 8.6G | 站点镜像旧快照，当前镜像已重建 |
| `中科/output_check_20260703/` | 4.9G | 7月核对副本 |
| `中科/Poster/` | 5.3G | 业务素材，建议移出代码工作区（与 集思/HIREP 素材统一归档） |
| `集思未来/output/full_refresh/` 两个旧基线 | 13G（名义） | 注意与 `output/assets/` 硬链接共享，独立增量需 `du -sh --apparent-size` 或逐目录核实 |
| `集思未来/output/assets/` | 6.5G | 全局附件池，若基线外移需一并规划 |
| `集思未来/集思-2026年9月2日/`、`开课时间-2026年10月以后/`+`-已处理/`、`output_domestic/` | ≈2.6G | HANDOFF.md 确认前者为 organized 输出的复制副本；开课时间两目录内容大量重叠 |
| `HIREP/output_pbl_full_refresh_20260602/` | 1.7G | 与 `output_pbl_full_20260602` 高度重复的重建基线 |
| `HIREP/Poster/` 下 5 个 merged_unique 变体 | 5.1G | 同一脚本的五代迭代产物，建议只留最终代 |
| `dianlu/data/processed/projects.json` + `projects.normalized.json` + `projects.normalized.csv` | ≈0.22G | 同一数据四种格式，保留 `.normalized.jsonl` 与 sqlite 即可 |
| `集思未来/yt_audio_ZIaOBAjvc38.webm` + `转录结果.md` | 32M | 与爬虫无关，建议移至 `docs/` 或素材库而非删除 |
| `中科/tmp/`、`中科-开课时间-2026年10月1日以后/` | 0.75G | 飞书导入中间物 / 业务交付，确认后归档 |

**Tier B 潜在：约 25–30 GB**

## Tier C：缓存与垃圾（随时可删，无需确认）

- `__pycache__/` × 543、`.pytest_cache/` × 5、`.ruff_cache/` × 2
- `.DS_Store` × 111
- `.playwright-mcp/`（scraper 根 696K + `集思未来/` 3.7M，browser-use 调试日志）
- `PHD/`（空目录）

```bash
find scraper -name '__pycache__' -type d -prune -exec rm -rf {} +
find scraper -name '.DS_Store' -delete
find scraper \( -name '.pytest_cache' -o -name '.ruff_cache' \) -type d -prune -exec rm -rf {} +
rm -rf scraper/.playwright-mcp "scraper/集思未来/.playwright-mcp"
```

## 已排除、不要动

- `data_staging/postgres_cluster/`（560M 旧 PG）：spec 明确禁止擅自处置，待 research_db 流程决策
- `盐趣7-9月项目合集/`、各 `output_pbl_incremental_*`：业务在用数据
- 各项目 `.venv/`（约 850M）：在用环境，可重建但无清理收益
