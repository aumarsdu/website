# 草料二维码授权归档项目

本项目用于在授权范围内归档单个草料二维码 H5 活码页面及其关联数据。默认目标是：

```text
https://h.qr61.cn/odBU6p/qYtCDec
```

入口 URL 可以是 `h5.clewm.net` 包装地址；程序会读取 `url=` 参数并标准化为上面的真实活码 URL。项目不会枚举其他二维码，不会爬取整站，不会绕过登录、验证码、后台鉴权或风控。

## 归档内容

- 活码展示内容：优先调用草料 OpenAPI V2 `qrcodes/getContent`
- 公开 H5 展示内容：在没有 API Key 时可用 `--public-only` 调用页面公开前端接口归档 Markdown 和元数据
- 活码关联操作项：调用 `qrcodes/getOperation`
- 表单结构：从操作项中识别 `element_type=2` 的 `tpl_id`，再调用 `forms/getTemplate`
- 表单记录：在 API Key 授权范围内调用 `record/getRecords`，按 `tpl_id` 和 `qrcode.id` 过滤
- H5 页面快照：抓取入口包装 URL 和标准化后的真实活码 URL
- 页面/API 内容中引用的图片、文件、音频、视频、`navLink:` 链接和外链资源
- 外链页面：只抓取 `external_page_whitelist` 中精确配置的 URL，并保存到独立目录

## 合规边界

- API Key 只从环境变量读取，默认变量名为 `CAOLIAO_API_KEY`。
- 配置文件和日志不会保存 API Key。
- 默认 User-Agent 为透明归档工具标识，请在 `config.example.json` 中替换 contact。
- 默认限速为每次请求间隔 `1.0` 秒。
- 默认单表单最多读取 `200` 页记录，每页最多 `50` 条。草料 V2 记录列表文档说明 `page_size` 最大为 50。
- 默认最多下载 `500` 个资源、`20` 个显式白名单外链页面，可在配置或命令行调整。
- 外链页面默认不抓取，只有配置到 `external_page_whitelist` 的精确 URL 才允许。

## 安装

项目仅使用 Python 标准库运行，要求 Python 3.11+。

```bash
python3 --version
python3 -m pip install -e .
```

如果不想安装，也可以直接用模块方式运行：

```bash
python3 -m caoliao_archiver.cli --help
```

## 配置

复制示例配置后修改 contact、输出目录和外链白名单：

```bash
cp config.example.json config.local.json
```

设置 API Key：

```bash
export CAOLIAO_API_KEY="你的草料 OpenAPI Key"
```

不要把真实 API Key 写入配置文件、命令行参数或提交记录。

## Dry Run

Dry run 只验证目标 URL、范围和归档计划，不调用官方 API，不下载资源。

```bash
python3 -m caoliao_archiver.cli --config config.example.json --dry-run
```

输出计划会写入：

```text
data/archive/reports/dry_run_plan.json
```

## 正式运行

```bash
python3 -m caoliao_archiver.cli --config config.local.json
```

如需临时跳过附件下载：

```bash
python3 -m caoliao_archiver.cli --config config.local.json --no-assets
```

如需限制本次资源下载数量：

```bash
python3 -m caoliao_archiver.cli --config config.local.json --max-assets 100 --max-external-pages 5
```

## 无 API Key 的公开 H5 归档

当暂时没有 OpenAPI Key，但需要先归档公开展示内容时，可使用 public-only 模式：

```bash
python3 -m caoliao_archiver.cli --config config.example.json --public-only --dry-run
python3 -m caoliao_archiver.cli --config config.example.json --public-only --max-assets 100 --max-external-pages 0
```

public-only 模式会调用页面公开前端接口：

```text
POST https://data.caoliao.net/x-llm/api/aicraft/getContentByRoute
{"route": "h.qr61.cn/odBU6p/qYtCDec"}
```

它会保存公开 Markdown、公开 headers、H5 快照和允许范围内的公开引用资源。它不会读取表单结构、表单记录或任何需要 OpenAPI Key 的数据。

## 输出结构

```text
data/archive/
  public/
    content.json
    content.md
    headers.html
  api/
    qrcode_content.json
    qrcode_operations.json
    form_templates/{tpl_id}.json
    records/{tpl_id}.jsonl
  html/
    entry_page.html
    qrcode_page.html
  external_pages/
    index.jsonl
    {hash}-{host}-{name}.html
  assets/
    index.jsonl
    files/
  reports/
    dry_run_plan.json
    summary.json
    public_dry_run_plan.json
    public_summary.json
```

每条记录 JSONL 都包含：

- `source_qrcode_url`
- `tpl_id`
- `crawled_at`
- `record`

## 完成判断

正式运行结束后查看：

```bash
python3 -m json.tool data/archive/reports/summary.json
```

public-only 模式查看：

```bash
python3 -m json.tool data/archive/reports/public_summary.json
```

`completion.complete` 为 `true` 才代表本次运行模式的授权范围内没有发现失败、错误或因数量上限跳过的项目。若为 `false`，检查 `completion.blockers`：

- `pages_failed`：H5 快照、外链页或资源下载存在失败。
- `errors_present`：OpenAPI、解析、网络或存储阶段存在错误。
- `assets_skipped_over_limit`：发现的资源超过 `max_assets`。
- `external_pages_skipped_over_limit`：白名单外链页超过 `max_external_pages`。

## 测试

使用标准库 unittest：

```bash
python3 -m unittest discover -s tests
```

测试只覆盖本地 URL 标准化、解析、去重、配置加载和存储序列化，不访问线上站点。

## 选择器和页面变化

项目主要依赖官方 OpenAPI，不依赖脆弱 DOM 选择器。H5 页面只用于快照和补充提取资源 URL。解析器会处理常见的 `src`、`href`、`srcset`、内联 CSS `url(...)` 和草料页面中的 `navLink:`。若页面结构变化，优先确认官方 API 返回字段是否已经包含所需数据；只有 API 缺失时才扩展 `caoliao_archiver/parser.py` 的资源提取逻辑。

## 已参考的官方文档

- OpenAPI V2 说明：`https://cli.im/open-api/openapi/v2/overview.html`
- 鉴权：`https://cli.im/open-api/openapi/v2/auth.html`
- 活码内容：`https://cli.im/open-api/openapi/v2/api/qrcodes-get-content.html`
- 活码关联操作项：`https://cli.im/open-api/openapi/v2/api/qrcodes-get-operation.html`
- 获取表单结构：`https://cli.im/open-api/openapi/v2/api/record/forms-get-template.html`
- 获取记录列表：`https://cli.im/open-api/openapi/v2/api/record/record-get-records.html`
