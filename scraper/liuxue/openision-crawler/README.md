# Openision Crawler

针对 `https://www.openision.com/` 的合规抓取工程。当前第一阶段重点是接口侦察、公开页面快照、嵌入数据提取、资产 URL 清单、SQLite 原始响应存储和 endpoint 汇总。

## 合规边界

- 使用透明 User-Agent：`AuthorizedOpenisionCrawler/1.0 contact=YOUR_EMAIL_HERE`。
- 默认单线程、0.5-2 秒随机延迟。
- 不绕过验证码、登录、付费墙、鉴权或访问控制。
- 不使用代理池规避限流。
- 遇到 401/403/429 只记录风险，不做绕过。
- 页面里的 OSS 签名图片 URL 会对 `security-token`、`OSSAccessKeyId`、`Signature` 等查询参数做脱敏或去除后再落盘。

## 安装

标准库静态侦察无需第三方依赖：

```bash
cd /Users/liujunliang/Workspace/Projects/archive/knowledge-legacy/scraper/liuxue/openision-crawler
python3 -m openision_crawler.cli --help
```

浏览器 XHR/fetch 侦察需要安装可选依赖：

```bash
python3 -m pip install -e '.[probe,test,yaml]'
playwright install chromium
```

## 配置

默认读取 `config/settings.yaml`；如果不存在，使用 `config/settings.example.yaml`。

如需修改联系邮箱，复制配置文件：

```bash
cp config/settings.example.yaml config/settings.yaml
```

然后把 `user_agent` 中的 `YOUR_EMAIL_HERE` 替换为授权联系人邮箱。

## 运行第一阶段侦察

当前环境如果没有 Playwright，先运行标准库静态侦察：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli static-probe
```

安装 Playwright 后运行浏览器接口侦察：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli probe
PYTHONPATH=src python3 -m openision_crawler.cli summarize-endpoints
```

## 运行第二阶段 API 分页抓取

先做 dry-run，确认目标和参数：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli crawl-api --target all --dry-run
```

抓取筛选字典：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli crawl-api --target filters --rate-limit 0.5
```

抓取专业库公开列表：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli crawl-api --target majors --page-size 100 --rate-limit 0.5
```

抓取案例库公开列表：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli crawl-api --target cases --page-size 100 --rate-limit 0.5
```

全量抓取公开列表和字典：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli crawl-api --target all --page-size 100 --rate-limit 0.5
```

默认 API 查询使用公开页面可调用的 minimal query：

- 专业库：`/api/v1/major/smart_search?search_type=school_and_major&data=&sort=qs`
- 案例库：`/api/v1/cases?search_type=keyword&data=&sort=qs`

这比页面默认的 QS 1-200 / GPA / 费用筛选覆盖更广。命令运行时会调用公开 `fc_auth` 获取短期 FC token，并只在内存中使用 `FCAuthorization` 请求头；token 不写入文件。

如果授权范围包含登录后数据，手动登录：

```bash
PYTHONPATH=src python3 -m openision_crawler.cli login
```

不要把账号、密码、cookie 或 `storage_state.json` 提交或分享。

## 输出

- `data/probe/html/`: 公开页面 HTML 快照，敏感 URL 查询参数已脱敏。
- `data/probe/network.jsonl`: Playwright XHR/fetch 网络日志，安装 Playwright 后由 `probe` 生成。
- `data/probe/endpoints_summary.md`: endpoint 汇总报告。
- `data/openision.sqlite`: crawl runs、raw responses、endpoints、errors、source records、assets。
- `data/normalized/home_initial_schools.jsonl`: 首页服务端嵌入的推荐学校数据。
- `data/raw/filters/`: 筛选字典原始 JSON。
- `data/raw/majors_list.jsonl`: 专业库分页 raw 响应与记录。
- `data/raw/cases_list.jsonl`: 案例库分页 raw 响应与记录。
- `data/normalized/majors_list.jsonl`: 专业库结构化记录。
- `data/normalized/cases_list.jsonl`: 案例库结构化记录。
- `data/reports/crawl_report.md`: 第二阶段 API 抓取报告。
- `data/reports/asset_manifest.json`: 资产 URL 清单，签名参数已去除或脱敏。
- `data/reports/static_probe_report.md`: 标准库静态侦察报告。

## 生成河狸陪三库

三库生成使用已落盘的 `data/normalized/majors_list.jsonl` 和 `data/normalized/cases_list.jsonl`，不访问线上网络。

```bash
PYTHONPATH=src python3 -m openision_crawler.cli build-libraries
```

输出：

- `data/libraries/program_library.jsonl`
- `data/libraries/school_library.jsonl`
- `data/libraries/admission_case_library.jsonl`
- `data/reports/library_quality_report.json`
- `data/openision.sqlite` 中的 `program_library`、`school_library`、`admission_case_library` 表

合规说明：

- 院校库是由专业和案例聚合生成的派生库。
- GPA 只作为申请参考或案例背景，不代表录取线。
- 学费未知值不会被展示成免费。
- 来源 URL 和第三方资源 URL 只作为内部溯源字段。

## 测试

不安装 pytest 时可使用标准库测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

安装测试依赖后：

```bash
PYTHONPATH=src pytest
```

## 下一阶段

浏览器 `probe` 跑出 `data/probe/network.jsonl` 后，先查看：

```bash
sed -n '1,200p' data/probe/endpoints_summary.md
```

再基于真实 endpoint 实现正式 API 分页抓取。不要猜测不存在的接口。
