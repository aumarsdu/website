# 中科课题增量采集工作流程

本流程只覆盖以下两个已确认允许公开访问的中科 SPA。它将每次结果写为独立快照，保留原始响应、分类字典和新增详情，以便复核、重跑和生成目录镜像。

## 范围与边界

- 入口范围：`https://jf.cas-harbour.cn/avocado/#/` 与 `https://jf.cas-harbour.cn/mini/#/`。
- 公开接口范围：这两个页面使用的课题列表、课题详情和课题分类接口，均位于 `jf.cas-harbour.cn/zhongkehaobo/v2/topic/`。
- 不采集 `gecacademy.cn`、其他网站、其他项目页或筛选/国家/城市/时间等非课题列表返回值；它们不能出现在规范化课题记录或课题目录中。
- 分类字典：海报平台课题分类树。
- 新增详情：仅对相对于本地 `output/processed/projects.jsonl` 新出现的海报平台课题获取公开详情页响应。
- 历史详情补全：`backfill-details` 以指定列表快照为基准，找出没有公开详情响应的课题 ID 后分批续采；已有详情自动跳过。
- 附件：详情或列表中公开暴露的海报、PDF 等链接交给 `download-assets` 下载，保留在对应课题目录。每个唯一 URL 仅下载一次，文件按 SHA-256 存入 `output/cache/assets/`，再以硬链接或复制方式放入所有引用它的课题目录。
- 不使用登录态、Cookie、Authorization、token 或任何绕过机制。遇到 401、403、验证码或登录要求立即停止该源。

## 每 30 天巡检

每 30 天至少执行一次以下公开接口刷新与审计，且始终只覆盖 `https://jf.cas-harbour.cn/avocado/#/` 与 `https://jf.cas-harbour.cn/mini/#/`：

```bash
python -m sou_crawler --rate-limit 1.5 --max-pages 100 --max-details 200 refresh-public-topics --snapshot-id audit-<YYYYMMDD>
python -m sou_crawler normalize
python -m sou_crawler reconcile-site-layout
python -m sou_crawler audit-archive --snapshot-id audit-<YYYYMMDD>
```

审计应确认当前公开列表没有课题或详情缺口，且所有 `details.json` 位于 `output/site/<一级分类>/<方向>/<课题>/`。范围外记录、目录或原始文件只能先由 `scope_audit_<批次>_out_of_scope.json` 清单确认，再在当次对话获得明确删除确认后执行 `cleanup-out-of-scope --confirm`；周期巡检不自动删除文件。

## 增量运行

开始前确认目标站点仍允许公开访问，并从本目录执行。不要覆盖旧快照；每次使用新的日期或批次标识。

```bash
# 仅显示将使用的公开接口和限额，不发起网络请求
python -m sou_crawler --max-pages 100 --max-details 200 refresh-public-topics --snapshot-id 20260730 --dry-run

# 采集公开列表、分类字典和新增海报平台课题详情
python -m sou_crawler --rate-limit 1.5 --max-pages 100 --max-details 200 refresh-public-topics --snapshot-id 20260730
```

`--max-pages` 是每个列表源的硬上限，`--max-details` 是新增详情的硬上限。报告中的 `truncated: true` 表示限额不足，不能把该快照当作完整更新；提高限额后必须使用新的 `--snapshot-id` 重跑，不能覆盖旧快照。

## 历史详情补全

当 `audit-archive` 的 `details.missing_from_current_list` 不为空时，对同一个完整列表快照执行以下命令。它只请求缺失的公开详情页，原始响应写入独立的 `backfill_<批次>` 目录；每次最多处理 `--max-details` 条，可重复执行至报告中的 `remaining_after` 为 `0`。

```bash
# 先确认待补采数量与样例 ID，不发起网络请求
python -m sou_crawler --max-details 200 backfill-details --snapshot-id 20260730 --dry-run

# 每批补采最多 200 条，失败项保留到下一次重试
python -m sou_crawler --rate-limit 1.5 --max-details 200 backfill-details --snapshot-id 20260730
```

补采报告与原始响应位置：

```text
output/reports/backfill_details_<批次>.json
output/raw/details/backfill_<批次>/harbour_topics/
```

详情补齐后，再运行 `normalize`、`download-assets` 和 `audit-archive`，以便把完整详情、PDF 和海报写入课题目录并复核附件缺口。`--max-assets` 按唯一 URL 计数；同一附件被多个课题引用时只联网下载一次，但每个课题目录都会获得对应的硬链接或副本。

快照写入：

```text
output/raw/lists/refresh_<批次>/
output/raw/details/refresh_<批次>/
output/raw/taxonomy/refresh_<批次>/
output/reports/refresh_<批次>.json
```

## 处理与目录镜像

先运行范围、完整性和位置审计。只有当刷新报告无失败/截断、审计报告中当前列表没有缺失、目录没有错位、范围外清单为空时，才进入处理阶段。

```bash
# 对照本次公开列表，检查记录、详情、附件和目录位置
python -m sou_crawler audit-archive --snapshot-id 20260730

# 合并历史与新快照，输出 JSONL、CSV、SQLite 和课题详情目录
python -m sou_crawler normalize

# 下载新发现且本地尚不存在的公开海报、封面和 PDF
python -m sou_crawler download-assets

# 需要按当前分类结果重新放置本地素材时执行；旧目录由脚本可恢复地迁移
python3 scripts/rebuild_site_mirror.py --output-dir output

# 生成完整性报告
python -m sou_crawler report
```

如审计报告出现 `misplaced_detail_paths`，先运行以下命令，再重新审计。该命令只移动同一记录的旧目录；目标目录已有同名但内容不同的素材时会保留旧目录并报告冲突。

```bash
python -m sou_crawler reconcile-site-layout
```

目标目录固定为：

```text
output/site/<一级分类>/<方向>/<课题>/details.json
output/site/<一级分类>/<方向>/<课题>/<海报或附件>
```

`details.json` 保存规范化字段和详情页完整公开响应；PDF 与海报和课题同目录。没有可靠分类时，记录会进入 `未分类/未分方向`，应先检查分类字典或可审计关键词映射，再决定是否人工补充规则。

## 范围审计与清理

`audit-archive` 读取 `refresh_<批次>` 的当前公开列表，检查：当前课题是否进入本地记录、每条记录是否存在于正确目录、详情/附件是否齐全，以及是否混入范围外的记录、目录或原始文件。结果写入：

```text
output/reports/scope_audit_<批次>.json
output/reports/scope_audit_<批次>_out_of_scope.json
```

审计命令不会删除任何内容。范围外清单必须先人工确认，再按清单批量清理；清理命令要求显式 `--confirm`，且会重新校验每条记录和文件路径仍与清单匹配。

```bash
python -m sou_crawler cleanup-out-of-scope --snapshot-id 20260730 --confirm
```

清理后重新运行 `normalize`、`download-assets` 和 `audit-archive`；保留审计和清理报告作为可追溯证据。

## 海报批次归档

仅在目录镜像和资产下载成功后，按刷新报告中新增的海报来源复制到目标批次目录。使用以下命令时，会保留相对于 `output/site` 的分类、方向、课题三级结构，已有同内容文件跳过，已有不同内容文件保留并在报告中列为冲突：

```bash
python -m sou_crawler archive-snapshot-topics --snapshot-id audit-<YYYYMMDD> --target-dir /absolute/path/to/batch
```

需要先核对范围时增加 `--dry-run`。若附件尚未下载完成，归档只包含当前已落盘的 `details.json` 和附件，不应称为全量附件归档。

对某一新增快照补齐公开海报和 PDF 时，不要运行全库 `download-assets`。改用以下命令，仅处理该快照新增课题的附件；它始终使用全库课题的目录映射，避免同名课题丢失 `__ID` 目录后缀。`--max-assets` 按唯一 URL 限制，每次运行都会复用已有 SHA-256 缓存并跳过已完成目录：

```bash
python -m sou_crawler --rate-limit 1.5 --max-assets 200 download-snapshot-assets --snapshot-id audit-<YYYYMMDD>
python -m sou_crawler archive-snapshot-topics --snapshot-id audit-<YYYYMMDD> --target-dir /absolute/path/to/batch
```

遇到 401 或 403 时，下载器会停止对应素材主机的后续请求并记录失败，不会尝试绕过访问控制。

验收时至少检查：复制数量、重复跳过数量、失败文件和目标路径是否仍保持 `分类/方向/课题/文件`。

## 飞书表格写入

飞书是真实外部服务。准备阶段只允许读取表格已有课题并生成去重后的待写入清单，以课题名称和稳定来源 ID/URL 为主键复核。写入前必须在当前对话获得明确确认；确认后按小批次写入，并保存每批成功、跳过、失败数量。

写入完成后重新读取目标视图，验证待写入列表中的每个课题均已存在。若表格字段、权限、去重键或写入结果不明确，停止写入并先解决差异，不重复提交整批数据。

## 异常处理与升级条件

| 现象 | 处理 |
| --- | --- |
| `truncated: true` | 增加上限并使用新批次重新采集；不要直接清洗为完整数据。 |
| 401、403、登录、验证码 | 停止该源，不尝试重放认证信息或规避限制。 |
| `duplicate_page_payload` | 停止继续翻页，检查接口分页参数和响应内容。 |
| 分类字典失败 | 不运行 `normalize`，避免新记录落入错误目录。 |
| 新增数量异常 | 先比较原始快照与上次报告，确认页面数和接口字段，再继续。 |
| 出现范围外清单 | 停止处理；先确认清单，再删除对应记录、目录和原始文件。 |
| 飞书去重不确定 | 只生成待写入清单，等待人工确认后再写入。 |

## 完成标准

- 刷新报告没有失败和截断。
- 范围审计中当前列表没有缺失，范围外记录为零，且没有目录错位。
- `normalize_stats.json` 的记录数与预期变化一致。
- 每个新增课题目录均有 `details.json`；有公开 PDF 或海报链接时，对应文件已下载或在资产报告中有明确失败原因。
- `crawl_report.json` 已更新。
- 如需飞书同步，写入后已完成去重和回读验证。
