#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv_paddleocr
source .venv_paddleocr/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install paddlepaddle==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install -U "paddleocr[doc-parser]"

python - <<'PY'
import paddle
paddle.utils.run_check()
print("PaddlePaddle OK")
PY

cat <<'MSG'

PaddleOCR 安装完成。
提示：macOS 本地环境默认走 CPU，复杂海报和大批量图片会比较慢。
MSG
