# macOS 本地海报 OCR 工具

这个工具用于把小红书、朋友圈、竞品广告海报里的中文/中英混排文案批量识别出来，整理成可查看、可复盘、可导入飞书多维表的文本结果。它面向教育行业营销获客场景，不是通用 OCR 产品。

## 为什么默认用 Apple Vision

Apple Vision 是 macOS 自带的本地 OCR 能力，不需要上传图片，也不需要额外购买云服务。对常见海报、截图、朋友圈图片，它的安装成本低、速度稳定，适合作为第一版默认引擎。

PaddleOCR 只作为可选增强，用在 Apple Vision 漏识别、复杂背景、小字、密集版式等困难海报上。

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

## 什么时候用 PaddleOCR

以下情况可以用 PaddleOCR 复核：

- Apple Vision 漏识别
- 海报背景复杂
- 字体很小
- 文字特别密集
- 中英文混排很多

安装 PaddleOCR：

```bash
make paddle-install
```

运行 PaddleOCR：

```bash
make paddle INPUT=data/input
```

注意：macOS 本地 PaddleOCR 默认走 CPU，速度可能明显慢于 Apple Vision。

## 隐私说明

默认 OCR 全部在本机执行，不上传图片到云 OCR、云 LLM 或第三方 API。请不要把 `data/input/` 里的用户图片上传到外部服务。

## 常见问题

### 没装 Xcode Command Line Tools

如果 `make build` 失败，并提示找不到 Swift 或 Xcode 工具，请先安装 Xcode Command Line Tools：

```bash
xcode-select --install
```

### 图片格式不支持

请优先使用 png、jpg、jpeg、heic。webp 依赖系统 ImageIO 支持，如果跳过或报错，可以先把图片转成 png。

### PaddleOCR 很慢

这是正常情况。macOS 本地安装默认走 CPU，适合少量困难海报二次识别，不建议第一批全量都用 PaddleOCR。

### 中文文件名

工具支持中文文件名和带空格路径。结果文件会保存在 `data/output/` 下。

### 没识别出文字

先查看 `needs_review` 是否为 `true`。如果图片文字太小、对比度低或背景复杂，可以尝试：

```bash
make ocr-fast INPUT=data/input
make paddle INPUT=data/input
```

也可以先把图片裁剪、放大或提高对比度后再识别。
