# macOS 本地海报 OCR 工具

这个工具用于把小红书、朋友圈、竞品广告海报里的中文/中英混排文案批量识别出来，整理成可查看、可复盘、可导入飞书多维表的文本结果。它面向教育行业营销获客场景，不是通用 OCR 产品。

## 为什么默认用 Apple Vision

Apple Vision 是 macOS 自带的本地 OCR 能力，不需要上传图片，也不需要额外购买云服务。对常见海报、截图、朋友圈图片，它的安装成本低、速度稳定，适合作为第一版默认引擎。

PaddleOCR 只作为可选增强，用在 Apple Vision 漏识别、复杂背景、小字、密集版式等困难海报上。

## 产线清单

两条产线互不依赖，按场景选：

| 产线 | 命令 | 引擎 / 档位 | 适用 | 输出 |
|---|---|---|---|---|
| **一 · 单图 / 少图** | `make ocr` / `make ocr-fast` | Apple Vision | 海报预览、零星识别 | `data/output/apple_vision/`、`data/output/plain_text/` |
| **二 · 批量** | `make paddle-batch` | PaddleOCR **PP-OCRv6 small**，6 并发 | 博主图批量抽文本（默认 1622 张） | `/tmp/ocr-batch/`（仓外） |
| **二 · 复核** | `make paddle-review` | PP-OCRv6 **medium**，4 并发 | 难图、关键图二次识别 | `/tmp/ocr-review/`（仓外） |
| **回归基线** | `make golden-manifest` / `make golden-check` | PP-OCRv6 | 改模型/改参数后验证没变差 | `data/golden/manifest.csv`、`diff.csv` |

常用变量（可覆盖）：

```bash
make paddle-batch BATCH_TIER=small WORKERS=6 BATCH_OUT=/tmp/ocr-batch
make paddle-review REVIEW_TIER=medium REVIEW_OUT=/tmp/ocr-review
make golden-check BATCH_OUT=/tmp/ocr-batch
```

> 批量产线的输出默认落在**仓库之外**：识别文本含学生姓名、院校、录取年份等 PII，不进版本库。

### 档位怎么选

| 档位 | 参数量 | 实测单张耗时 | 用在哪 |
|---|---|---|---|
| `tiny` | 1.5M | 1.6–3.1 s | 端侧 / 极低成本场景 |
| `small` | 7.7M | 3.2–7.0 s | **批量默认**（与 medium 实测仅差 1 个字符） |
| `medium` | 34.5M | 5.7–12.5 s | **复核默认**、难图兜底 |

## 放入图片

把需要识别的图片放到：

```bash
data/input/
```

支持常见图片格式：png、jpg、jpeg、tif、tiff、bmp、heic。webp 是否可识别取决于当前 macOS 的 ImageIO 支持。

## 运行第一批 OCR

先构建工具：

```bash
make build
```

运行 Apple Vision OCR：

```bash
make ocr INPUT=data/input
```

生成飞书导入 CSV：

```bash
make feishu
```

如果只想用更快但可能略低准确率的模式：

```bash
make ocr-fast INPUT=data/input
```

## 查看结果

Apple Vision 批量结果：

```text
data/output/apple_vision/results.csv
data/output/apple_vision/results.jsonl
```

每张图的纯文本 Markdown：

```text
data/output/plain_text/
```

飞书多维表导入文件：

```text
data/output/feishu/poster_ocr_feishu.csv
```

飞书 CSV 中的主标题、副标题、核心卖点、信任背书、CTA、目标人群、用户痛点等字段第一版先留空，方便后续人工或 AI 清洗填写。

批量产线（`make paddle-batch`）的结果：

```text
/tmp/ocr-batch/results.jsonl      # 逐张明细
/tmp/ocr-batch/review_queue.csv   # 需人工读图的复核队列
/tmp/ocr-batch/summary.json       # 汇总统计
```

## 字段契约

`results.jsonl` 每行一张图：

| 字段 | 含义 | 可信度 |
|---|---|---|
| `blogger` / `note_id` / `fname` / `title` | 定位键，与业务工作簿唯一键一致 | 可靠 |
| `path` | 原图绝对路径（只读引用） | 可靠 |
| `engine` / `tier` | 如 `PP-OCRv6_small` | 可靠 |
| `paddleocr_version` / `model_det` / `model_rec` | 引擎版本与模型名，**可复现必需** | 可靠 |
| `params` | 切片高度 / 重叠 / 复核阈值 | 可靠 |
| `mode` | `full`（整图） / `sliced`（长图切片） | 可靠 |
| `zh_chars` / `en_words` | 中文字数 / 英文词数，**仅用于分流，不得当准确率** | 弱 |
| `conf_avg` | 识别置信度均值 | 参考 |
| `text` | 识别文本 | 线索级 |
| `fact_fields` | 命中的关键实体类别（院校 / 金额 / 分数 / 日期 / 承诺） | 提示级 |
| `needs_review` / `review_reasons` | 是否需人工读图及原因 | 判定级 |
| `elapsed` / `error` | 耗时与异常 | 可靠 |

`review_queue.csv` 列：博主 / 笔记ID / 笔记标题 / 图片文件名 / 档位 / 模式 / 中文字数 / 置信度 / 复核原因 / 命中关键实体 / 图片路径。

修改或新增字段时，必须同步更新本节、`scripts/jsonl_to_feishu_csv.py` 与 `AGENTS.md`。

## 复核口径

**不要用「中文字数阈值」判断识别成功或失败。** 字符多不等于准——同一批样本上，旧引擎多出 24 个中文字但全是错字（"耶和鲁""常春芯""HLA A7"）。

统一按三条分流，命中任一条即进 `review_queue.csv`：

1. 零中文输出；
2. 平均置信度 < 0.70；
3. 命中关键实体：院校 / 金额 / 分数 / 日期 / 承诺话术（保录、保 offer、必录、保过、100%、全额奖学金）。

复核由**人工读图**完成；未经人工确认的文本不得作为事实引用。对外可发的事实以业务主库的母版条目为准。

## 长任务与重跑

- 批量识别中断后，**直接重跑同一条命令**即可（`--resume` 会跳过已完成条目），不要删了重跑。
- 长图（高 > 2200 px）会自动切片识别，切片产出的文本**不得直接作为事实引用**，只进复核队列。
- 不要用 `launchctl submit` 托管长任务：keepalive 会在任务结束后无限重启，重启实例会覆盖既有输出。确需托管时，任务结束务必 `launchctl bootout gui/$(id -u)/<job>` 注销。

## 什么时候用 PaddleOCR

以下情况用 PaddleOCR 复核：

- Apple Vision 漏识别
- 海报背景复杂
- 字体很小
- 文字特别密集
- 中英文混排很多

安装 PaddleOCR：

```bash
make paddle-install
```

单图补识别：

```bash
make paddle INPUT=data/input
```

批量识别（推荐）：

```bash
make paddle-batch
```

注意：macOS 本地 PaddleOCR 默认走 CPU，速度可能明显慢于 Apple Vision；批量请用 `make paddle-batch`（small 档 + 6 并发），不要整批跑 medium。

## 隐私说明

默认 OCR 全部在本机执行，不上传图片到云 OCR、云 LLM 或第三方 API。请不要把 `data/input/` 里的用户图片上传到外部服务。

**识别文本本身也是 PII 载体**（含学生姓名、院校、录取年份、成绩）。因此：

- 批量产物默认输出到仓库之外（`/tmp/ocr-batch`），不要提交进 git；
- 不要把产物放进可对外发送的目录；
- 含 PII 的原图同样不得外发。

## 常见问题

### 没装 Xcode Command Line Tools

如果 `make build` 失败，并提示找不到 Swift 或 Xcode 工具，请先安装 Xcode Command Line Tools：

```bash
xcode-select --install
```

### 图片格式不支持

请优先使用 png、jpg、jpeg、heic。webp 依赖系统 ImageIO 支持，如果跳过或报错，可以先把图片转成 png。

### PaddleOCR 很慢

这是正常情况。macOS 本地安装默认走 CPU。批量请用 `make paddle-batch`（small 档、6 并发），复核用 `make paddle-review`（medium 档），不要第一批全量都用 PaddleOCR。

### 中文文件名

工具支持中文文件名和带空格路径。结果文件会保存在 `data/output/` 下。

### 没识别出文字

先查看 `needs_review` 是否为 `true`。如果图片文字太小、对比度低或背景复杂，可以尝试：

```bash
make ocr-fast INPUT=data/input
make paddle INPUT=data/input
```

也可以先把图片裁剪、放大或提高对比度后再识别。若仍不可靠，说明该图需要人工读图，不要靠调参硬凑。

### 改完模型/参数后怎么确认没变差

```bash
make golden-check
```

先 `make golden-manifest` 生成清单并完成人工标注，之后每次改动都跑一次 `golden-check` 看差异表与关键实体命中率。
