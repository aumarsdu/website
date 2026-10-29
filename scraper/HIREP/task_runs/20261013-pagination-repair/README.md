# 2026-10-13 HIREP 增量分页修复

本目录是独立的本地代码副本，用于本次已授权采集。原 `HIREP/sou_crawler/` 保留，未提交 Git。

## 修复依据与行为

- 官方公开组件 `https://pbl.hirepglobal.com/js/886.85ce392a.js` 使用 `pageIndex` 和 `pageSize`。
- 2026-10-13 用 `pageIndex=1,2`、`pageSize=200` 验证：响应 `current=1,2`，两页 ID 无重叠。
- 原实现传 `current`，服务器重复返回第一页，并触发大页回退。修复版改用 `pageIndex`，取消大页回退。
- 始终每页 200 条；重复页立即报错；超过 `--max-pages` 拒绝将部分列表作为完整基线。
- 本次正式列表 8 页全部成功，记录数 1564，与服务端 `total=1564` 一致。

## 运行与恢复

必须从本目录运行，以使用修复副本。使用原环境的 Python，明确指定原配置及输出位置：

```bash
cd /Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP/task_runs/20261013-pagination-repair
PYTHONPATH=. /Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP/.venv/bin/python -m sou_crawler \
  --config-dir /Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP/config \
  --output-dir /Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP/output_pbl_incremental_20261013_repaired \
  --rate-limit 2 --timeout 30 --retries 1 --concurrency 1 --max-pages 100 \
  crawl-pbl-incremental
```

相同输出批次可断点续跑；新日常批次须换日期目录。保留历史 `raw/`、资源清单和下载缓存。

## 验证

```bash
PYTHONPATH=. /Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP/.venv/bin/python -m pytest \
  -c /dev/null -q tests/test_pagination_repair.py tests/test_pbl_list_pagination.py \
  tests/test_pbl_crawler.py tests/test_verify_pbl_output.py

/Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP/.venv/bin/python \
  scripts/verify_pbl_output.py \
  --output-dir /Users/liujunliang/Workspace/knowledge-legacy/scraper/HIREP/output_pbl_incremental_20261013_repaired \
  --strict
```

`-c /dev/null` 用于防止父项目 pytest 配置把原目录加入 Python 搜索路径；本目录设有完整的针对性断言，没有降低断言。23 项测试通过，缓存路径权限产生 1 条警告；严格数据验收应在采集结束后执行。

仅采集 PBL 公开课题及其明确引用的附件；透明 User-Agent，串行、2 秒间隔，401/403 停止对应访问，不使用 Cookie、凭据或绕过机制。没有外部表格写入、发布或 Git 同步。
