# AGENTS.md - Poster OCR 项目规则

本项目是 macOS 本地海报 OCR 工程，用于教育行业营销海报文案批量识别和飞书导入。

## 必守规则

- 不要引入云 OCR、云 LLM OCR 或第三方图片识别 API。
- 不要上传 `data/input/` 里的任何图片。
- 不要删除用户原始图片，不要清空 `data/input/`。
- 不要读取、输出或记录 token、secret、password、API key、cookie、session、private key。
- 优先保持 Apple Vision 路径轻量、稳定、无需额外依赖。
- PaddleOCR 只能作为可选增强引擎，不要让默认流程依赖它。
- 修改输出字段时，必须同步更新 `README.md` 和 `scripts/jsonl_to_feishu_csv.py`。
- 保持中文注释、中文 README 和面向运营同事可读的说明。

## 默认验收

修改 Swift 主流程后运行：

```bash
make check
make build
```

修改飞书 CSV 转换脚本后，至少确认：

```bash
python3 scripts/jsonl_to_feishu_csv.py --help
```

不要自动安装 PaddleOCR，除非用户明确批准。
