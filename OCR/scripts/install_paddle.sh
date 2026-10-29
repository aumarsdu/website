#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv_paddleocr
source .venv_paddleocr/bin/activate

python -m pip install --upgrade pip setuptools wheel

# 版本以 requirements-paddle.txt 为准（已锁定，保证回归基线可复现）
# paddlepaddle 走官方 CPU 源；macOS 本地默认走 CPU
grep -E '^paddlepaddle==' requirements-paddle.txt | while read -r _pkg ver; do
  python -m pip install "${ver}" -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
done
python -m pip install -r requirements-paddle.txt

python - <<'PY'
import paddle
paddle.utils.run_check()
print("PaddlePaddle OK")
PY

cat <<'MSG'

PaddleOCR 安装完成。
提示：macOS 本地环境默认走 CPU，复杂海报和大批量图片会比较慢。
批量识别请用 `make paddle-batch`（默认 small 档、6 并发），复核用 `make paddle-review`（medium 档）。
MSG
