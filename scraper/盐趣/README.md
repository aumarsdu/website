# 盐趣海报 OCR 与改名管线

对**手工收集**的竞品"盐趣"科研课题海报图片做离线文字识别（OCR）与按标题改名。
**不包含任何网络抓取**：图片来源为人工保存的截图/导出图（文件名多含微信图片日期），
不读取 cookie、不访问网站、不收集个人信息。

## 组成

| 脚本 | 职责 |
|---|---|
| `ocr_posters_ppocrv6.py` | 用本地 PaddleOCR PP-OCRv6 模型批量识别海报文字，输出 CSV + 可断点续跑的 JSONL checkpoint |
| `rename_posters_by_title.py` | 依据 OCR 结果中的标题簇给海报文件改名（两阶段 rename 防半途损坏，默认 preview、`--apply` 才实际改名） |

数据目录（不入 git）：`Poster/`、`盐趣7-9月项目合集/<学科>/`、日期命名 zip。
本目录产物是 research_db 五源库中"盐趣"来源的数据源头（见
`db/research_db/goal_20260908_side/source_registry.json` 的 yanqu 条目）。

## 环境

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # pillow + paddleocr
# PP-OCRv6 模型文件由 paddleocr 按需下载到本地缓存，之后可离线运行
```

## 常用命令

```bash
# OCR（断点续跑；失败记录用 --retry-errors 重试）
.venv/bin/python ocr_posters_ppocrv6.py \
  --input "盐趣7-9月项目合集" \
  --output "盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv" \
  --checkpoint ocr_checkpoint.jsonl

# 改名（先预览再 --apply）
.venv/bin/python rename_posters_by_title.py \
  --poster-dir "盐趣7-9月项目合集" \
  --ocr-csv "盐趣7-9月项目合集/海报文字识别_PP-OCRv6.csv" \
  --mapping-csv Poster/海报改名映射_PP-OCRv6.csv
```

## 已知限制

- `rename_posters_by_title.py` 顶部的像素阈值（`SUBJECT_TAG_MIN_Y` 等）是针对当前
  两代海报模板（约 1440/1520px 高）调出的启发式；新模板出现时需整组复核，
  否则标题拼接可能混入学科标签簇或漏拼第二行。
- `TITLE_CLEANUP_PATTERNS` 中的正则是针对个别海报 OCR 噪声的过拟合补丁，新增时
  请在注释里写明来源海报。
- `ocr_posters_ppocrv6.py` 按 `record_for_file` 精确匹配 CSV 行，缺失记录会抛
  KeyError 终止全量——属有意设计（防止静默漏改名），重跑前先补齐 OCR checkpoint。
