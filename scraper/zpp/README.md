# xntj.tv 授权归档器

用于将 `https://xntj.tv/` 的**公开内容**保存为可恢复的本地归档。站点所有者已授权，且
`robots.txt` 允许抓取；工具仍保持保守限速，不会绕过登录、验证码或其他访问控制。

## 输出

默认输出到 `archive/`：

- `pages/`：原始 HTML；
- `markdown/`：可阅读页面及 EP 的逐字稿；
- `metadata/`：每页的 JSON 元数据和提取结果；
- `assets/`：同源图片、样式、脚本、音视频和下载文件；
- `archive.sqlite3`：URL、资源、响应状态和 hash；
- `summary.json`：本次运行汇总。

## 运行

```bash
python3 -m xntj_archive discover
python3 -m xntj_archive crawl --rate-limit 1
python3 -m xntj_archive report
```

`crawl` 可安全重复运行。`--max-pages` 能限制本次页面数量；`--dry-run` 只完成发现和计划检查，不写入页面或资源。

## 限制

只采集 `xntj.tv` 同源公开 URL；外部链接仅记录在页面元数据中。HTTP 401、403 和需要交互式授权的内容会保留状态，不会尝试规避。对源站结构发生改变的页面，仍会保存 HTML 并标记解析结果。

