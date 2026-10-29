# AGENTS.md - Poster OCR 项目规则

本项目是 macOS 本地海报 OCR 工程，用于教育行业营销海报文案批量识别和飞书导入。

本文件分为 **红线**（不可突破）、**产线与引擎**、**档位与参数**、**质检口径**、**长任务与调度**、**产物与数据契约**、**跨仓一致性** 七块。每条规则都对应一个动作或一条检查命令。

---

## 一、红线（不可突破）

- 不要引入云 OCR、云 LLM OCR 或第三方图片识别 API。
- 不要上传 `data/input/` 里的任何图片。
- 不要删除用户原始图片，不要清空 `data/input/`，也不要重命名或移动归档原图。
- 不要读取、输出或记录 token、secret、password、API key、cookie、session、private key。
- **OCR 识别文本本身是 PII 载体**（含学生姓名、院校、录取年份、成绩），不得外发、不得入云、不得提交进 git、不得放进可对外发送的目录。原始图片同理。
- 识别产物默认落在仓库之外（例如 `/tmp/ocr-*`）；确需放仓内时必须命中 `.gitignore`。

## 二、产线与引擎

- **产线一 · 单图/少图海报识别**：默认 Apple Vision（`make ocr` / `make ocr-fast`）。保持轻量、稳定、无需额外依赖。
- **产线二 · 批量识别**：主引擎是 PaddleOCR PP-OCRv6。`make paddle-batch` 跑 small 档全量，`make paddle-review` 跑 medium 档复核难图。
- 两条产线互不依赖：poster-ocr 的默认流程**不依赖** PaddleOCR，但"批量产线的主引擎是 PP-OCRv6"——不要把本节读成"PaddleOCR 不得作主引擎"。
- `scripts/paddle_ocr.py` 是**单图/少图补识别**入口；批量请用 `scripts/ocr_batch_runner.py`。
- PaddleOCR 已装于 `.venv_paddleocr`（paddleocr 3.7.0 / paddlepaddle 3.3.0 / Python 3.12.12），模型缓存在 `~/.paddlex/official_models/`。**不要重复安装**；版本以 `requirements-paddle.txt` 锁定值为准。
- 不要自动安装或升级 PaddleOCR，除非用户明确批准。

## 三、档位与参数

- 批量层默认 `PP-OCRv6_small`，复核层 `PP-OCRv6_medium`，端侧 `PP-OCRv6_tiny`。
- 实测 small 与 medium 输出仅差 1 个字符、耗时约一半。**不要不指定档位就整批跑 medium。**
- 并发上限 6（10 核机器留余量），每个进程 `OMP_NUM_THREADS=1`。
- 图高 > 2200 px 必须切片（重叠 200 px）后再识别；切片产出的文本**不得直接作为事实引用**，只能进复核队列。
- 每条结果必须记录 `paddleocr_version` / `model_det` / `model_rec` / `params`，否则无法复现。

## 四、质检口径

- **禁止用「中文字数阈值」判断识别成功或失败。** 字符多不等于准：同一批样本上 Tesseract 多出 24 个中文字但全是错字（"耶和鲁""常春芯""HLA A7"）。
- 统一按三条分流，命中任一条即写入 `review_queue.csv`：
  1. 零中文输出；
  2. 平均置信度 < 0.70；
  3. 命中关键实体——院校 / 金额 / 分数 / 日期 / 承诺话术（保录、保offer、必录、保过、100%、全额奖学金）。
- 复核由**人工读图**完成；未经人工确认的文本不得作为事实引用。
- OCR 文本只是线索。对外可发的事实仍以主库母版 F 编号为准（见主库 `06_数据分析与复盘/` 的对账报告）。

## 五、长任务与调度

- 不要用 `launchctl submit` 托管长任务：keepalive 会在任务结束后**无限重启**，重启实例以覆盖模式重开输出文件，会把已跑完的结果清空。
- 长跑用「前台分片 + 追加写 + `--resume`」：中断后重跑同一条命令即可续，不要删了重跑。
- 确实需要后台托管时，记录 job 名，并在任务结束后 `launchctl bootout gui/$(id -u)/<job>` 注销（`launchctl remove` 为旧式别名）。
- 单张失败不得中断整批；失败样本必须留在结果里并带错误原因。

## 六、产物与数据契约

- 批量产物三件套：`results.jsonl`（逐张明细）、`review_queue.csv`（复核队列）、`summary.json`（汇总）。字段定义见 README「产线清单」。
- 修改或新增产物字段时，必须同步更新 `README.md`、`scripts/jsonl_to_feishu_csv.py` 与本节的字段契约。
- 关键字段（引擎、档位、版本、参数、置信度、复核原因）不得删除或改名——下游脚本与历史比对都依赖它们。

## 七、跨仓一致性

- 工具仓只定义"怎么做"（能力、参数、分流机制）；**"什么算合格事实"由主库定义**，以 `03_内部管理/制度流程/` 的 SOP 与 `06_数据分析与复盘/` 的对账报告为准。
- 同一口径不在两处各写一份；本仓引用主库结论，不复制改写。

---

## 默认验收

修改 Swift 主流程后运行：

```bash
make check
make build
```

修改批量脚本、产线或参数后运行：

```bash
make check            # 含 PaddleOCR 通道、版本、档位、模型缓存检查
make golden-manifest  # 生成分层金标准清单
make golden-check     # 与金标准比对，产出差异表
```

修改飞书 CSV 转换脚本后，至少确认：

```bash
python3 scripts/jsonl_to_feishu_csv.py --help
```

不要自动安装 PaddleOCR，除非用户明确批准。
