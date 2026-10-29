# crawler_common — 爬虫共享库

scraper 工作区的 8 个爬虫项目源自同一模板，fetcher / 白名单 / 脱敏 / 哈希 /
storage 等横切逻辑被复制了 8 份。本包把它们收敛为唯一实现，供各项目逐步接入。

## 模块

| 模块 | 职责 |
|---|---|
| `fetcher.Fetcher` | 同步限速抓取：域名白名单（重定向后复核）、诚实 UA（必填）、超时/429/5xx 安全重试、robots.txt 门禁 |
| `robots.RobotsCache` | 按域缓存 robots.txt；404 放行，401/403/5xx/网络错误保守禁止 |
| `errors` | 工作区标准错误分类 + 可重试状态码集合 |
| `url_rules` | 精确主机白名单 / 含子域名白名单 |
| `redact` | 请求头与扁平 JSON 的敏感字段落盘脱敏（`[REDACTED]`） |
| `digest` | SHA-256（bytes/text/流式文件） |
| `fsutil` | `link_or_copy`（硬链接优先、失败回退复制） |
| `storage` | JSON / JSONL 读写（含 append 与惰性迭代） |

## 合规边界

本库只提供合规原语，不提供任何绕过能力：不做 UA 轮换、不做代理池、
不处理验证码、不绕过鉴权。`Fetcher` 强制要求非空 User-Agent，
401/403/404 永不重试。

## 接入方式

新项目直接安装：

```bash
pip install -e ../shared
```

存量项目建议先在 scripts / 新模块中使用，待验证后再替换自有实现。

## 运行测试

```bash
PYTHONPATH=src <python-with-httpx-and-pytest> -m pytest tests -q
```
