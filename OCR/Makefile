SHELL := /bin/bash

INPUT ?= data/input
APPLE_OUT ?= data/output/apple_vision
PLAIN_TEXT_DIR ?= data/output/plain_text
FEISHU_OUT ?= data/output/feishu/poster_ocr_feishu.csv
PADDLE_OUT ?= data/output/paddleocr

# 批量产线默认输出到仓库之外：识别文本含学生 PII，不进版本库
BATCH_OUT ?= /tmp/ocr-batch
REVIEW_OUT ?= /tmp/ocr-review
GOLDEN_DIR ?= data/golden

# 主库根路径（博主图工作簿与归档所在处）；迁移后可用 --root 覆盖
HELIPEI_ROOT ?= /Users/liujunliang/Documents/02-Area/06-事业/数字牧民/河狸陪

# 档位：批量 small / 复核 medium；并发上限 6（10 核机器留余量）
BATCH_TIER ?= small
REVIEW_TIER ?= medium
WORKERS ?= 6

# 冒烟用：LIMIT=100 只处理前 100 张；0 = 全量
LIMIT ?= 0
LIMIT_FLAG = $(if $(filter 0,$(LIMIT)),,--limit $(LIMIT))

PY := .venv_paddleocr/bin/python

.PHONY: build ocr ocr-fast feishu paddle-install paddle paddle-batch paddle-review golden-manifest golden-check clean check

build:
	swift build -c release

ocr:
	swift run -c release poster-ocr --input "$(INPUT)" --out "$(APPLE_OUT)" --plain-text-dir "$(PLAIN_TEXT_DIR)"

ocr-fast:
	swift run -c release poster-ocr --input "$(INPUT)" --out "$(APPLE_OUT)" --plain-text-dir "$(PLAIN_TEXT_DIR)" --level fast

feishu:
	python3 scripts/jsonl_to_feishu_csv.py --input "$(APPLE_OUT)/results.jsonl" --out "$(FEISHU_OUT)"

paddle-install:
	bash scripts/install_paddle.sh

# 单图 / 少图补识别入口
paddle:
	@if [[ ! -f .venv_paddleocr/bin/activate ]]; then \
		echo "未找到 .venv_paddleocr，请先运行：make paddle-install"; \
		exit 2; \
	fi
	source .venv_paddleocr/bin/activate && python scripts/paddle_ocr.py --input "$(INPUT)" --out "$(PADDLE_OUT)" --plain-text-dir "$(PLAIN_TEXT_DIR)"

# 批量识别（PP-OCRv6 small 档，6 并发，可断点续跑）
paddle-batch:
	@if [[ ! -x "$(PY)" ]]; then echo "未找到 $(PY)，请先运行：make paddle-install"; exit 2; fi
	"$(PY)" -u scripts/ocr_batch_runner.py --root "$(HELIPEI_ROOT)" --tier "$(BATCH_TIER)" --workers "$(WORKERS)" --out "$(BATCH_OUT)" $(LIMIT_FLAG) --resume

# 难图复核（PP-OCRv6 medium 档）
paddle-review:
	@if [[ ! -x "$(PY)" ]]; then echo "未找到 $(PY)，请先运行：make paddle-install"; exit 2; fi
	"$(PY)" -u scripts/ocr_batch_runner.py --root "$(HELIPEI_ROOT)" --tier "$(REVIEW_TIER)" --workers 4 --out "$(REVIEW_OUT)" --resume

# 生成回归金标准清单（分层抽样，待人工标注）
golden-manifest:
	@if [[ ! -x "$(PY)" ]]; then echo "未找到 $(PY)，请先运行：make paddle-install"; exit 2; fi
	"$(PY)" scripts/make_golden_manifest.py --root "$(HELIPEI_ROOT)" --out "$(GOLDEN_DIR)/manifest.csv"

# 与金标准比对，产出差异表
golden-check:
	@if [[ ! -x "$(PY)" ]]; then echo "未找到 $(PY)，请先运行：make paddle-install"; exit 2; fi
	"$(PY)" scripts/make_golden_manifest.py --check --manifest "$(GOLDEN_DIR)/manifest.csv" --results "$(BATCH_OUT)/results.jsonl" --out "$(GOLDEN_DIR)/diff.csv"

clean:
	bash scripts/clean_outputs.sh

check:
	@echo "== Poster OCR 环境检查 =="
	@echo "pwd: $$(pwd)"
	@echo "uname -m: $$(uname -m)"
	@echo "swift: $$(command -v swift || echo '未找到')"
	@swift --version || true
	@echo "python3: $$(command -v python3 || echo '未找到')"
	@python3 --version || true
	@echo "xcode-select: $$(command -v xcode-select || echo '未找到')"
	@xcode-select -p || true
	@echo ""
	@echo "== PaddleOCR 通道 =="
	@if [[ -x "$(PY)" ]]; then \
		echo "venv: $(PY)（存在）"; \
		"$(PY)" -c "import paddleocr, paddle; print('  paddleocr:', paddleocr.__version__); print('  paddlepaddle:', paddle.__version__)" || true; \
		"$(PY)" -c "import sys; print('  python:', sys.version.split()[0])" || true; \
	else \
		echo "venv: $(PY)（缺失）→ 运行 make paddle-install"; \
	fi
	@echo "  批量档位: $(BATCH_TIER)   复核档位: $(REVIEW_TIER)   并发: $(WORKERS)"
	@echo "  批量输出: $(BATCH_OUT)（仓外，避免 PII 进版本库）"
	@echo "  复核输出: $(REVIEW_OUT)"
	@echo "  模型缓存: $$HOME/.paddlex/official_models"
	@ls -1 "$$HOME/.paddlex/official_models" 2>/dev/null | head -8 | sed 's/^/    /' || echo "    （未下载模型，首次运行会自动拉取）"
	@echo ""
	@echo "== 金标准基线 =="
	@if [[ -f "$(GOLDEN_DIR)/manifest.csv" ]]; then \
		echo "  清单: $(GOLDEN_DIR)/manifest.csv"; \
		echo "  已标注行数: $$(grep -c '待确认' "$(GOLDEN_DIR)/manifest.csv" || true) 条待确认"; \
	else \
		echo "  清单缺失 → 运行 make golden-manifest"; \
	fi
