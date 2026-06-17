SHELL := /bin/bash

INPUT ?= data/input
APPLE_OUT ?= data/output/apple_vision
PLAIN_TEXT_DIR ?= data/output/plain_text
FEISHU_OUT ?= data/output/feishu/poster_ocr_feishu.csv
PADDLE_OUT ?= data/output/paddleocr

.PHONY: build ocr ocr-fast feishu paddle-install paddle clean check

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

paddle:
	@if [[ ! -f .venv_paddleocr/bin/activate ]]; then \
		echo "未找到 .venv_paddleocr，请先运行：make paddle-install"; \
		exit 2; \
	fi
	source .venv_paddleocr/bin/activate && python scripts/paddle_ocr.py --input "$(INPUT)" --out "$(PADDLE_OUT)" --plain-text-dir "$(PLAIN_TEXT_DIR)"

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
